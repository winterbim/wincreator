"""Governed execution (G02): decision -> gate -> signed receipt -> verification.

The order is the guarantee:

1. VEOR decides on the *proposed effect* before anything executes. ``DENY``,
   ``REVIEW`` without a consumed one-shot approval, a sidecar error, a timeout
   or a malformed response never reach the gate.
2. The decision artifact is written to disk and bound into the capture as a
   hashed input file, so the attestation commits to the authorization that
   preceded it.
3. The gate runs through the WinCreator proof kernel exactly as an ungoverned
   task would, and the capture is recorded by the runtime as usual.
4. VEOR signs an execution receipt that binds the decision (tool, args digest,
   policy digest, decision) to a digest of the capture (attestation digest,
   exit code, stdout/stderr hashes).
5. The receipt is accepted only after VEOR's own offline verifier exits zero
   with ``ok=true`` and both digest and signature checks, and only if every
   bound field matches the artifact and the capture.

Authority stays split (ADR 0002): governance never writes a proof verdict, a
ledger status or a task state. A verified receipt is journaled, not promoted.
"""

from dataclasses import dataclass, field
import hashlib
import json
import os
from typing import Any, Dict, List, Mapping, Optional
import uuid

from harness import governance, kernel
from harness.contracts import TaskContract
from harness.store import InvalidTransition, StoreError
from harness.util import (
    atomic_write_json,
    file_digest,
    iso_time,
    portable_path,
    sha256_text,
)

DECISION_SCHEMA = "wincreator.governance-decision/v1"
DECISION_FILE = "governance-decision.json"
RECEIPT_FILE = "governance-receipt.json"
GATE_TOOL = "wincreator.gate.execute"
# Executing a gate is a side effect (it writes the proof ledger). Annotating it
# as destructive is the honest description, and VEOR then requires a one-shot
# approval before it answers ALLOW. The annotations are not caller-supplied: a
# caller that could relax them could talk its way past the review path.
GATE_ANNOTATIONS = {"readOnlyHint": False, "destructiveHint": True}
PIN_ENV = "WINCREATOR_VEOR_PIN"
PUBLIC_KEY_ENV = "VEOR_RECEIPT_PUBLIC_KEY"
_RECEIPT_KIND = "veor.execution-receipt/v1"


class GovernanceDenied(RuntimeError):
    """VEOR refused the effect, or no valid authorization covers it."""


@dataclass(frozen=True)
class GovernanceConfig:
    """Where the pinned sidecar, its keys and its public counterpart live."""

    pin_path: str
    home: Optional[str] = None
    node: str = "node"
    receipt_public_key: Optional[str] = None
    timeout: float = 60.0
    sidecar_env: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def for_root(
        cls,
        root,
        pin=None,
        home=None,
        node=None,
        receipt_public_key=None,
        timeout=None,
        sidecar_env=None,
    ):
        return cls(
            pin_path=os.path.abspath(
                pin
                or os.environ.get(PIN_ENV)
                or os.path.join(str(root), "tools", "veor-pin.json")
            ),
            home=home or os.environ.get("VEOR_HOME"),
            node=node or os.environ.get("VEOR_NODE") or "node",
            receipt_public_key=receipt_public_key
            or os.environ.get(PUBLIC_KEY_ENV),
            timeout=float(timeout or 60.0),
            sidecar_env=dict(sidecar_env or {}),
        )


# --------------------------------------------------------------- small helpers
def _file_sha256(path):
    return file_digest(path)


def _veor_canonical(value):
    """Mirror VEOR's canonicalJson: sorted keys, compact separators, no HTML escape."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        # VEOR serializes 1.0 as "1"; mirroring that faithfully is not worth a
        # silent mismatch, so floats are refused instead of approximated.
        raise governance.GovernanceUnavailable(
            "governance args must not contain floats; VEOR hashes them differently"
        )
    if isinstance(value, (list, tuple)):
        return [_veor_canonical(item) for item in value]
    if isinstance(value, Mapping):
        out = {}
        for key in value:
            if not isinstance(key, str):
                raise governance.GovernanceUnavailable(
                    "governance args keys must be strings"
                )
            out[key] = _veor_canonical(value[key])
        return {key: out[key] for key in sorted(out)}
    raise governance.GovernanceUnavailable(
        f"governance args contain a non-JSON value: {type(value).__name__}"
    )


def veor_args_digest(args):
    """Recompute VEOR's ``hashObject(args)`` so a lying sidecar is caught."""
    encoded = json.dumps(
        _veor_canonical(args), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def effect_for(contract: TaskContract, workspace=None) -> Dict[str, Any]:
    """The effect VEOR is asked about: this contract's gate, nothing wider."""
    return {
        "tool": GATE_TOOL,
        "args": {
            "task_id": contract.task_id,
            "contract_digest": contract.digest(),
            "level": contract.level,
            "tier": contract.tier,
            "gate": contract.gate.command_string(),
            "workspace": portable_path(workspace) if workspace else None,
        },
    }


def _record_problems(record, decision, effect):
    problems: List[str] = []
    if not isinstance(record, Mapping):
        return ["VEOR returned no decision record"]
    if record.get("tool") != effect["tool"]:
        problems.append("RECORD_TOOL_MISMATCH")
    if record.get("decision") != decision.decision:
        problems.append("RECORD_DECISION_MISMATCH")
    if record.get("policyDigest") != decision.policy_digest:
        problems.append("RECORD_POLICY_MISMATCH")
    expected = veor_args_digest(effect["args"])
    if record.get("argsDigest") != expected:
        problems.append("RECORD_ARGS_DIGEST_MISMATCH")
    return problems


def _receipt_problems(body, decision_document, binding_digest):
    problems: List[str] = []
    if not isinstance(body, Mapping):
        return ["MISSING_RECEIPT_BODY"]
    if body.get("kind") != _RECEIPT_KIND:
        problems.append("UNEXPECTED_KIND")
    if body.get("tool") != decision_document.get("tool"):
        problems.append("TOOL_MISMATCH")
    if body.get("argsDigest") != decision_document.get("args_digest"):
        problems.append("ARGS_DIGEST_MISMATCH")
    if body.get("decision") != "ALLOW":
        problems.append("DECISION_NOT_ALLOW")
    if body.get("executed") is not True:
        problems.append("EFFECT_NOT_EXECUTED")
    if body.get("resultDigest") != binding_digest:
        problems.append("RESULT_DIGEST_MISMATCH")
    if body.get("policyDigest") != decision_document.get("policy_digest"):
        problems.append("POLICY_DIGEST_MISMATCH")
    if not body.get("receiptId"):
        problems.append("MISSING_RECEIPT_ID")
    return problems


def _decision_path(store, task_id):
    directory = os.path.join(
        store.attest_dir, "governance", f"{task_id}-{uuid.uuid4().hex[:12]}"
    )
    return os.path.join(directory, DECISION_FILE)


def _block(store, task_id, code, reasons, **extra):
    payload = {"code": code, "reasons": list(reasons), "at": iso_time()}
    payload.update(extra)
    try:
        store.record_governance_event(
            task_id, None, payload, actor="governance", event_type="governance_blocked"
        )
    except StoreError:
        # The journal is best effort here: refusing to execute is the point.
        pass


# ---------------------------------------------------------------- verification
def verify_capture(
    attestation_path,
    receipt_path,
    decision_path,
    public_key_path,
    home,
    pin,
    node="node",
    timeout=60,
):
    """Re-derive the whole chain from disk. Raises unless every link holds."""
    ok, issues = kernel.verify_attestation(attestation_path)
    if not ok:
        raise governance.GovernanceUnavailable(
            "the capture does not verify: " + "; ".join(issues)
        )
    try:
        with open(attestation_path, encoding="utf-8") as handle:
            attestation = json.load(handle)
    except (OSError, ValueError) as error:
        raise governance.GovernanceUnavailable(f"cannot read the capture: {error}")
    payload = attestation["payload"]
    try:
        decision_sha256 = _file_sha256(decision_path)
    except OSError as error:
        raise governance.GovernanceUnavailable(
            f"cannot read the decision artifact: {error}"
        )
    bound = [
        entry
        for entry in payload.get("files", [])
        if entry.get("sha256") == decision_sha256
        and os.path.basename(str(entry.get("path", ""))) == DECISION_FILE
    ]
    if not bound:
        raise governance.GovernanceUnavailable(
            "the decision artifact is not bound by this capture; the authorization "
            "cannot be tied to what ran"
        )
    try:
        with open(decision_path, encoding="utf-8") as handle:
            decision_document = json.load(handle)
    except (OSError, ValueError) as error:
        raise governance.GovernanceUnavailable(
            f"cannot read the decision artifact: {error}"
        )
    if decision_document.get("schema") != DECISION_SCHEMA:
        raise governance.GovernanceUnavailable(
            f"unexpected decision artifact schema: {decision_document.get('schema')!r}"
        )
    if decision_document.get("decision") != "ALLOW":
        raise governance.GovernanceUnavailable(
            "the bound decision artifact is not an ALLOW"
        )
    binding = governance.bind_result(
        attestation["digest"]["value"],
        payload.get("capture", {}).get("exit_code"),
        payload.get("stdout", {}).get("sha256"),
        payload.get("stderr", {}).get("sha256"),
    )
    # VEOR's own verifier: exit 0, ok=true, digest and signature confirmed.
    document = governance.verify_receipt(
        home, pin, receipt_path, public_key_path, node=node, timeout=timeout
    )
    try:
        with open(receipt_path, encoding="utf-8") as handle:
            receipt = json.load(handle)
    except (OSError, ValueError) as error:
        raise governance.GovernanceUnavailable(f"cannot read the receipt: {error}")
    body = receipt.get("body")
    problems = _receipt_problems(body, decision_document, binding["digest"])
    if problems:
        raise governance.GovernanceUnavailable(
            "the receipt does not bind this decision and capture: " + ", ".join(problems)
        )
    return {
        "ok": True,
        "kind": document.get("kind"),
        "checks": document.get("checks"),
        "receipt_id": body.get("receiptId"),
        "receipt_digest": body.get("digest") or receipt.get("digest"),
        "binding_digest": binding["digest"],
        "attestation_digest": attestation["digest"]["value"],
        "decision_sha256": decision_sha256,
        "verification_argv": governance.receipt_verifier_argv(
            home, pin, receipt_path, public_key_path, node
        ),
        "verified_at": iso_time(),
    }


def verify_task(executor, task_id, config):
    """Problems (if any) with the governance side of one task's proof."""
    events = [
        event
        for event in executor.store.events(task_id)
        if str(event.get("type", "")).startswith("governance_")
    ]
    if not events:
        return []
    bound = [event for event in events if event["type"] == "governance_bound"]
    if not bound:
        latest = events[-1]
        return [
            f"{task_id}: governed task has no verified VEOR receipt "
            f"(last governance event: {latest['type']})"
        ]
    record = bound[-1]["payload"]
    if not config.receipt_public_key or not os.path.isfile(config.receipt_public_key):
        return [
            f"{task_id}: cannot re-verify the VEOR receipt: no readable public key "
            f"(set {PUBLIC_KEY_ENV} or pass the receipt public key)"
        ]
    try:
        with open(config.pin_path, encoding="utf-8") as handle:
            pin = governance.load_pin(config.pin_path)
    except governance.GovernanceUnavailable as error:
        return [f"{task_id}: cannot load the VEOR pin: {error}"]
    for key in ("attestation_path", "receipt_path", "decision_path"):
        if not record.get(key):
            return [f"{task_id}: governance journal event is missing {key}"]
    home = config.home
    if home is None:
        home = governance.resolve_home(config.pin_path, home=None)
    try:
        summary = verify_capture(
            record["attestation_path"],
            record["receipt_path"],
            record["decision_path"],
            config.receipt_public_key,
            home,
            pin,
            node=config.node,
            timeout=config.timeout,
        )
    except governance.GovernanceUnavailable as error:
        return [f"{task_id}: governance: {error}"]
    problems: List[str] = []
    for journal_key, summary_key in (
        ("receipt_id", "receipt_id"),
        ("receipt_digest", "receipt_digest"),
        ("binding_digest", "binding_digest"),
        ("attestation_digest", "attestation_digest"),
    ):
        if record.get(journal_key) != summary[summary_key]:
            problems.append(
                f"{task_id}: governance journal {journal_key} does not match the "
                "re-verified artifact"
            )
    proof = executor.store.latest_proof(task_id)
    if proof is None or proof["attestation_path"] != record["attestation_path"]:
        problems.append(
            f"{task_id}: the verified receipt is not bound to the stored proof"
        )
    return problems


# ----------------------------------------------------------------------- run
def run(executor, task_id, config, advisory="ALLOW", retry_reason=None):
    """Decide, execute under the decision, sign, verify, journal."""
    store = executor.store
    task = store.get_task(task_id)
    try:
        pin = governance.load_pin(config.pin_path)
    except governance.GovernanceUnavailable as error:
        _block(store, task_id, "GOVERNANCE_UNAVAILABLE", [str(error)])
        raise
    status = governance.check(config.pin_path, home=config.home)
    if not status.ready:
        _block(store, task_id, "GOVERNANCE_BLOCKED", status.reasons)
        raise governance.GovernanceUnavailable(
            "governance is not READY: " + "; ".join(status.reasons)
        )
    if not config.receipt_public_key or not os.path.isfile(config.receipt_public_key):
        _block(
            store,
            task_id,
            "RECEIPT_KEY_MISSING",
            [
                "no readable receipt verification key; a receipt could not be "
                f"verified, so nothing is executed (set {PUBLIC_KEY_ENV})"
            ],
        )
        raise governance.GovernanceUnavailable(
            "a receipt public key is required before a governed run"
        )

    effect = effect_for(task.contract, workspace=task.workspace)
    sidecar = governance.Sidecar(
        status.veor_home,
        pin,
        node=config.node,
        timeout=config.timeout,
        env=config.sidecar_env,
    )
    decision = sidecar.decide(
        effect["tool"],
        dict(effect["args"]),
        annotations=dict(GATE_ANNOTATIONS),
        advisory=advisory,
    )
    record = decision.raw.get("record")
    if decision.decision != "ALLOW":
        _block(
            store,
            task_id,
            f"DECISION_{decision.decision}",
            decision.reasons,
            policy_digest=decision.policy_digest,
            challenge_id=(record or {}).get("challengeId"),
            tool=effect["tool"],
        )
        raise GovernanceDenied(
            f"VEOR answered {decision.decision} "
            f"({', '.join(decision.reasons) or 'no reason given'}); nothing was executed"
        )
    problems = _record_problems(record, decision, effect)
    if problems:
        _block(store, task_id, "DECISION_RECORD_INVALID", problems)
        raise governance.GovernanceUnavailable(
            "VEOR's decision record does not describe the effect that was requested: "
            + ", ".join(problems)
        )

    document = {
        "schema": DECISION_SCHEMA,
        "task_id": task_id,
        "contract_digest": task.contract.digest(),
        "pin_digest": status.pin_digest,
        "veor_commit": pin["commit"],
        "policy_digest": decision.policy_digest,
        "tool": effect["tool"],
        "args_digest": record["argsDigest"],
        "decision": decision.decision,
        "reasons": list(decision.reasons),
        "challenge_id": record.get("challengeId"),
        "approval": record.get("approval"),
        "sandbox": {
            "backend": "none",
            "os_enforced": False,
            "note": "the gate runs as a plain child process of the proof kernel; "
            "VEOR does not sandbox it",
        },
        "at": iso_time(),
    }
    decision_path = atomic_write_json(_decision_path(store, task_id), document)
    store.record_governance_event(
        task_id,
        None,
        {
            "decision": decision.decision,
            "policy_digest": decision.policy_digest,
            "tool": effect["tool"],
            "args_digest": record["argsDigest"],
            "decision_path": portable_path(decision_path),
            "decision_sha256": _file_sha256(decision_path),
            "contract_digest": task.contract.digest(),
            "challenge_id": record.get("challengeId"),
        },
        event_type="governance_decision",
    )

    current = store.get_task(task_id).state
    if current not in {"PENDING", "READY"}:
        if not retry_reason:
            _block(
                store,
                task_id,
                "NOT_READY",
                [f"task is {current}; a governed retry needs a stated reason"],
            )
            raise InvalidTransition(
                f"task {task_id} is {current}; re-run it with a retry reason so the "
                "new attempt is journaled, never silently repeated"
            )
        store.retry(task_id, reason=retry_reason, actor="governance")
        store.record_governance_event(
            task_id,
            None,
            {
                "previous_state": current,
                "retry_reason": retry_reason,
                "decision_sha256": _file_sha256(decision_path),
            },
            event_type="governance_retry",
        )

    summary: Dict[str, Any] = {}

    def on_capture(capture):
        summary.update(
            _finalize(
                executor,
                config,
                pin,
                status,
                sidecar,
                task_id,
                document,
                decision,
                decision_path,
                capture,
            )
        )

    result = executor.run(
        task_id,
        extra_files=[decision_path],
        on_capture=on_capture,
        governed=True,
    )
    result["governance"] = summary or None
    return result


def _finalize(
    executor,
    config,
    pin,
    status,
    sidecar,
    task_id,
    document,
    decision,
    decision_path,
    capture,
):
    store = executor.store
    payload = capture["payload"]
    attempt_no = capture["attempt_no"]
    attestation_digest = capture["attestation"]["digest"]["value"]
    binding = governance.bind_result(
        attestation_digest,
        payload["capture"]["exit_code"],
        payload["stdout"]["sha256"],
        payload["stderr"]["sha256"],
    )
    receipt = sidecar.receipt(
        decision.raw["record"],
        binding["digest"],
        executed=True,
        verified=None,
        sandbox=document["sandbox"],
    )
    body = receipt.get("body") or {}
    problems = _receipt_problems(body, document, binding["digest"])
    if problems:
        store.record_governance_event(
            task_id,
            attempt_no,
            {
                "problem": "receipt does not bind this decision and capture",
                "reasons": problems,
                "binding_digest": binding["digest"],
            },
            event_type="governance_receipt_rejected",
        )
        raise governance.GovernanceUnavailable(
            "VEOR's receipt does not bind this decision and capture: "
            + ", ".join(problems)
        )
    receipt_path = atomic_write_json(
        os.path.join(os.path.dirname(capture["attestation_path"]), RECEIPT_FILE),
        receipt,
    )
    try:
        summary = verify_capture(
            capture["attestation_path"],
            receipt_path,
            decision_path,
            config.receipt_public_key,
            status.veor_home,
            pin,
            node=config.node,
            timeout=config.timeout,
        )
    except governance.GovernanceUnavailable as error:
        store.record_governance_event(
            task_id,
            attempt_no,
            {
                "problem": str(error),
                "receipt_path": portable_path(receipt_path),
                "binding_digest": binding["digest"],
            },
            event_type="governance_receipt_rejected",
        )
        raise
    store.record_governance_event(
        task_id,
        attempt_no,
        {
            "attempt_no": attempt_no,
            "decision": "ALLOW",
            "tool": document["tool"],
            "args_digest": document["args_digest"],
            "policy_digest": document["policy_digest"],
            "veor_commit": document["veor_commit"],
            "pin_digest": document["pin_digest"],
            "decision_path": portable_path(decision_path),
            "decision_sha256": summary["decision_sha256"],
            "attestation_path": portable_path(capture["attestation_path"]),
            "attestation_digest": attestation_digest,
            "receipt_path": portable_path(receipt_path),
            "receipt_id": summary["receipt_id"],
            "receipt_digest": summary["receipt_digest"],
            "binding_digest": binding["digest"],
            "capture_status": payload["capture"]["status"],
            "verification": {
                "kind": summary["kind"],
                "checks": summary["checks"],
                "argv": summary["verification_argv"],
            },
            "sandbox": document["sandbox"],
            "verified_at": summary["verified_at"],
        },
        event_type="governance_bound",
    )
    return summary


def run_ready(executor, config, retry_reason=None):
    """Govern every READY task; nothing runs ungoverned here."""
    results = []
    for task in executor.store.list_tasks(state="READY"):
        results.append(run(executor, task.task_id, config, retry_reason=retry_reason))
    return results


__all__ = [
    "DECISION_SCHEMA",
    "GATE_TOOL",
    "GovernanceConfig",
    "GovernanceDenied",
    "effect_for",
    "run",
    "run_ready",
    "verify_capture",
    "verify_task",
    "veor_args_digest",
]
