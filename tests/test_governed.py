"""Hermetic tests for the governed execution path (G02).

These use a fake decision kernel: they prove what the *harness* does with an
answer, including every refusal. The real pinned VEOR sidecar, its Ed25519
receipts and its offline verifier are exercised in ``test_g02_integration.py``.
"""

import json
import os
import uuid

import pytest

from conftest import REPO, harness_contract

from harness import governance, governed
from harness.store import InvalidTransition

from harness.governance import GovernanceUnavailable


# --------------------------------------------------------------------- fixtures
def _checkout(tmp_path, version="0.4.0-dev.6"):
    import subprocess

    home = tmp_path / "veor"
    (home / "src" / "kernel").mkdir(parents=True)
    (home / "package.json").write_text(
        json.dumps({"name": "veor-runtime", "version": version}), encoding="utf-8"
    )
    (home / "src" / "kernel" / "stdio.js").write_text("// fake\n", encoding="utf-8")
    identity = ["-c", "user.email=t@example.invalid", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=home, check=True)
    subprocess.run(["git", *identity, "add", "."], cwd=home, check=True)
    subprocess.run(["git", *identity, "commit", "-qm", "seed"], cwd=home, check=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=home, capture_output=True, text=True, check=True
    ).stdout.strip()
    return home, commit


def _pin(tmp_path, home, commit):
    pin_path = tmp_path / "pin.json"
    pin_path.write_text(
        json.dumps(
            {
                "schema": governance.PIN_SCHEMA,
                "repository": "https://example.invalid/veor",
                "commit": commit,
                "package_version": "0.4.0-dev.6",
                "node_major": 22,
                "audited_at": "2026-10-24",
                "audit_document": "docs/VEOR_GUARDIAN_AUDIT.md",
                "sidecar": {
                    "entrypoint": "src/kernel/stdio.js",
                    "protocol": "json-lines",
                    "receipt_verify": ["src/cli.js", "verify", "receipt"],
                },
                "vendored": False,
            }
        ),
        encoding="utf-8",
    )
    return pin_path


class FakeVeor:
    """Stands in for the pinned sidecar; records what the harness asked."""

    def __init__(self, decision="ALLOW"):
        self.decision = decision
        self.reasons = ["POLICY_ALLOW"]
        self.policy_digest = "a" * 64
        self.calls = []
        self.decision_record = None
        self.mutate_record = None
        self.mutate_receipt = None

    def request(self, sidecar, method, params):
        self.calls.append((method, params))
        if method == "decide":
            record = {
                "at": "2026-10-24T00:00:00.000000Z",
                "tool": params["tool"]["name"],
                "argsDigest": governed.veor_args_digest(params["args"]),
                "decision": self.decision,
                "reasons": list(self.reasons),
                "policyDigest": self.policy_digest,
                "capability": "gate.execute",
                "challengeId": "challenge-1" if self.decision == "REVIEW" else None,
                "approval": "VERIFIED_APPROVAL" if self.decision == "ALLOW" else None,
            }
            if self.mutate_record:
                self.mutate_record(record)
            self.decision_record = record
            return {
                "decision": self.decision,
                "reasons": list(self.reasons),
                "policyDigest": self.policy_digest,
                "record": record,
                "challenge": None,
            }
        if method == "receipt":
            record = params["decisionRecord"]
            body = {
                "kind": "veor.execution-receipt/v1",
                "keyId": "fake",
                "receiptId": str(uuid.uuid4()),
                "decidedAt": record["at"],
                "completedAt": "2026-10-24T00:00:01.000000Z",
                "tool": record["tool"],
                "argsDigest": record["argsDigest"],
                "decision": record["decision"],
                "executed": params["executed"],
                "verified": params.get("verified"),
                "resultDigest": params["resultDigest"],
                "sandbox": params.get("sandbox"),
                "policyDigest": record["policyDigest"],
            }
            if self.mutate_receipt:
                self.mutate_receipt(body)
            return {"body": body, "signature": "fake-signature", "digest": "d" * 64}
        raise AssertionError(f"unexpected sidecar method {method}")


@pytest.fixture
def veor_env(tmp_path, monkeypatch):
    home, commit = _checkout(tmp_path)
    pin_path = _pin(tmp_path, home, commit)
    public_key = tmp_path / "receipt.pub.pem"
    public_key.write_text("-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----\n")

    monkeypatch.setattr(governance, "node_version", lambda: "v22.3.0")

    def fake_verify(home_, pin_, receipt_path, public_key_path, node="node", timeout=60):
        try:
            with open(receipt_path, encoding="utf-8") as handle:
                receipt = json.load(handle)
        except (OSError, ValueError) as error:
            raise GovernanceUnavailable(
                f"VEOR receipt verification failed with exit 1: {error}"
            )
        body = receipt.get("body") or {}
        if body.get("kind") != "veor.execution-receipt/v1" or body.get("executed") is not True:
            raise GovernanceUnavailable("VEOR receipt verification failed: BAD_SIGNATURE")
        return {
            "ok": True,
            "kind": "veor.receipt-verify/v1",
            "checks": {"structure": True, "digest": True, "signature": True, "ledger": None},
        }

    monkeypatch.setattr(governance, "verify_receipt", fake_verify)
    veor = FakeVeor()
    monkeypatch.setattr(
        governance.Sidecar,
        "_request",
        lambda sidecar_self, method, params: veor.request(sidecar_self, method, params),
    )

    config = governed.GovernanceConfig.for_root(
        tmp_path, pin=str(pin_path), home=str(home), receipt_public_key=str(public_key)
    )
    return {"config": config, "veor": veor, "home": home, "pin": pin_path}


def _run(executor, veor_env, task_id="H1", **kwargs):
    return governed.run(executor, task_id, veor_env["config"], **kwargs)


# ----------------------------------------------------------------------- tests
def test_deny_executes_nothing(harness_executor, veor_env):
    veor_env["veor"].decision = "DENY"
    veor_env["veor"].reasons = ["UNKNOWN_TOOL"]
    harness_executor.register(harness_contract(tier="lite"))

    with pytest.raises(governed.GovernanceDenied) as error:
        _run(harness_executor, veor_env)

    assert "DENY" in str(error.value)
    task = harness_executor.store.get_task("H1")
    assert task.state == "PENDING"
    assert harness_executor.store.latest_proof("H1") is None
    assert [call[0] for call in veor_env["veor"].calls] == ["decide"]
    events = harness_executor.store.events("H1")
    assert events[-1]["type"] == "governance_blocked"
    assert events[-1]["payload"]["code"] == "DECISION_DENY"
    assert not any(event["type"].startswith("attempt") for event in events)


def test_review_without_a_consumed_approval_executes_nothing(harness_executor, veor_env):
    veor_env["veor"].decision = "REVIEW"
    veor_env["veor"].reasons = ["MCP_SIDE_EFFECT_HINT"]
    harness_executor.register(harness_contract(tier="lite"))

    with pytest.raises(governed.GovernanceDenied):
        _run(harness_executor, veor_env)

    assert harness_executor.store.latest_proof("H1") is None
    blocked = harness_executor.store.events("H1")[-1]["payload"]
    assert blocked["code"] == "DECISION_REVIEW"
    assert blocked["challenge_id"] == "challenge-1"


def test_unavailable_governance_executes_nothing(harness_executor, tmp_path, monkeypatch):
    home, commit = _checkout(tmp_path)
    pin_path = _pin(tmp_path, home, commit)
    public_key = tmp_path / "receipt.pub.pem"
    public_key.write_text("x", encoding="utf-8")
    monkeypatch.setattr(governance, "node_version", lambda: None)
    config = governed.GovernanceConfig.for_root(
        tmp_path, pin=str(pin_path), home=str(home), receipt_public_key=str(public_key)
    )
    harness_executor.register(harness_contract(tier="lite"))

    with pytest.raises(GovernanceUnavailable):
        governed.run(harness_executor, "H1", config)

    assert harness_executor.store.latest_proof("H1") is None
    assert harness_executor.store.events("H1")[-1]["payload"]["code"] == "GOVERNANCE_BLOCKED"


def test_missing_receipt_key_executes_nothing(harness_executor, veor_env, tmp_path):
    config = governed.GovernanceConfig(
        pin_path=veor_env["config"].pin_path,
        home=veor_env["config"].home,
        receipt_public_key=str(tmp_path / "absent.pem"),
    )
    harness_executor.register(harness_contract(tier="lite"))

    with pytest.raises(GovernanceUnavailable):
        governed.run(harness_executor, "H1", config)

    assert harness_executor.store.latest_proof("H1") is None
    assert harness_executor.store.events("H1")[-1]["payload"]["code"] == "RECEIPT_KEY_MISSING"
    assert veor_env["veor"].calls == []


def test_allow_runs_the_gate_and_binds_decision_and_receipt(harness_executor, veor_env):
    harness_executor.register(harness_contract(tier="lite"))

    result = _run(harness_executor, veor_env)

    assert result["state"] == "SUCCEEDED"
    summary = result["governance"]
    assert summary["checks"]["signature"] is True
    assert summary["binding_digest"] == summary["binding_digest"].lower()
    proof = harness_executor.store.latest_proof("H1")
    assert proof["attestation_digest"] == summary["attestation_digest"]
    with open(proof["attestation_path"], encoding="utf-8") as handle:
        attestation = json.load(handle)
    bound = [
        entry["path"]
        for entry in attestation["payload"]["files"]
        if entry["path"].endswith("governance-decision.json")
    ]
    assert bound, "the decision artifact must be a hashed input of the capture"
    events = [event["type"] for event in harness_executor.store.events("H1")]
    assert events.count("governance_decision") == 1
    assert events.count("governance_bound") == 1
    bound_event = [
        event
        for event in harness_executor.store.events("H1")
        if event["type"] == "governance_bound"
    ][0]
    assert bound_event["payload"]["sandbox"]["os_enforced"] is False
    assert bound_event["payload"]["receipt_id"] == summary["receipt_id"]


def test_receipt_that_does_not_bind_the_capture_blocks(harness_executor, veor_env):
    veor_env["veor"].mutate_receipt = lambda body: body.update(resultDigest="0" * 64)
    harness_executor.register(harness_contract(tier="lite"))

    result = _run(harness_executor, veor_env)

    assert result["state"] == "BLOCKED"
    assert "does not bind" in result["error"]
    assert harness_executor.store.get_task("H1").state == "BLOCKED"
    events = [event["type"] for event in harness_executor.store.events("H1")]
    assert "governance_receipt_rejected" in events
    assert "governance_bound" not in events
    assert harness_executor.store.latest_proof("H1") is not None


def test_receipt_for_another_tool_blocks(harness_executor, veor_env):
    veor_env["veor"].mutate_receipt = lambda body: body.update(tool="filesystem.write_file")
    harness_executor.register(harness_contract(tier="lite"))

    result = _run(harness_executor, veor_env)

    assert result["state"] == "BLOCKED"
    assert "TOOL_MISMATCH" in result["error"]


def test_sidecar_lying_about_the_args_digest_blocks_before_execution(
    harness_executor, veor_env
):
    veor_env["veor"].mutate_record = lambda record: record.update(argsDigest="f" * 64)
    harness_executor.register(harness_contract(tier="lite"))

    with pytest.raises(GovernanceUnavailable, match="does not describe the effect"):
        _run(harness_executor, veor_env)

    assert harness_executor.store.latest_proof("H1") is None
    assert harness_executor.store.get_task("H1").state == "PENDING"
    assert harness_executor.store.events("H1")[-1]["payload"]["code"] == (
        "DECISION_RECORD_INVALID"
    )


def test_governed_task_cannot_be_run_or_retried_ungoverned(harness_executor, veor_env):
    harness_executor.register(harness_contract(tier="lite"))
    _run(harness_executor, veor_env)

    with pytest.raises(InvalidTransition, match="governed"):
        harness_executor.run("H1")
    with pytest.raises(InvalidTransition, match="governed"):
        harness_executor.retry("H1", reason="try again")
    assert harness_executor.run_ready() == []
    outcome = harness_executor.resume()
    assert outcome["results"] == []


def test_a_governed_retry_needs_a_reason_and_a_new_decision(harness_executor, veor_env):
    harness_executor.register(
        harness_contract(tier="lite", command=["python3", "-c", "raise SystemExit(3)"])
    )
    first = _run(harness_executor, veor_env)
    assert first["state"] == "FAILED"

    with pytest.raises(InvalidTransition, match="retry reason"):
        _run(harness_executor, veor_env)
    assert harness_executor.store.get_task("H1").state == "FAILED"
    assert len(harness_executor.store.get_task("H1").attempts) == 1

    second = _run(harness_executor, veor_env, retry_reason="gate fixed after review")
    assert second["attempt_no"] == 2
    events = [event["type"] for event in harness_executor.store.events("H1")]
    assert "governance_retry" in events
    assert events.count("governance_decision") == 3


def test_an_interrupted_governed_attempt_is_never_retried_ungoverned(
    harness_executor, veor_env
):
    harness_executor.register(harness_contract(tier="lite"))
    store = harness_executor.store
    store.transition("H1", "READY", actor="test", reason="admitted")
    store.record_governance_event(
        "H1", None, {"decision": "ALLOW"}, event_type="governance_decision"
    )
    attempt = store.begin_attempt("H1", owner_pid=999999, lease_seconds=1)
    store.abandon_attempt("H1", attempt, "owner vanished mid-capture")

    outcome = harness_executor.resume()

    assert outcome["results"] == []
    assert store.get_task("H1").state == "INTERRUPTED"
    assert store.latest_proof("H1") is None

    result = _run(harness_executor, veor_env, retry_reason="recovered after crash")
    assert result["attempt_no"] == 2
    assert result["state"] == "SUCCEEDED"


def test_the_decision_artifact_holds_no_raw_arguments(harness_executor, veor_env):
    harness_executor.register(
        harness_contract(
            tier="lite",
            command=["python3", "-c", "print('ok')", "--token=SECRET-VALUE-42"],
        )
    )

    _run(harness_executor, veor_env)

    bound = [
        event
        for event in harness_executor.store.events("H1")
        if event["type"] == "governance_bound"
    ][0]["payload"]
    with open(bound["decision_path"], encoding="utf-8") as handle:
        text = handle.read()
    assert "SECRET-VALUE-42" not in text
    assert "args_digest" in text


def test_verify_reports_a_missing_receipt_and_accepts_a_verified_one(
    harness_executor, veor_env
):
    harness_executor.register(harness_contract(tier="lite"))
    _run(harness_executor, veor_env)

    problems, _summary = harness_executor.verify(governance_config=veor_env["config"])
    assert problems == []

    # A governed proof with no verifiable receipt must never pass silently.
    receipt_path = [
        event
        for event in harness_executor.store.events("H1")
        if event["type"] == "governance_bound"
    ][0]["payload"]["receipt_path"]
    os.replace(receipt_path, receipt_path + ".moved")

    problems, _summary = harness_executor.verify(governance_config=veor_env["config"])
    assert problems and "governance:" in problems[0]


def test_verify_rejects_a_tampered_receipt(harness_executor, veor_env):
    harness_executor.register(harness_contract(tier="lite"))
    result = _run(harness_executor, veor_env)
    receipt_path = [
        event
        for event in harness_executor.store.events("H1")
        if event["type"] == "governance_bound"
    ][0]["payload"]["receipt_path"]
    with open(receipt_path, encoding="utf-8") as handle:
        receipt = json.load(handle)
    receipt["body"]["executed"] = False
    with open(receipt_path, "w", encoding="utf-8") as handle:
        json.dump(receipt, handle)
    assert result["state"] == "SUCCEEDED"

    problems, _summary = harness_executor.verify(
        governance_config=veor_env["config"]
    )

    assert any("governance:" in problem for problem in problems)


def test_ungoverned_mode_never_needs_node(harness_executor, monkeypatch):
    def explode():
        raise AssertionError("the ungoverned path must not look for Node.js")

    monkeypatch.setattr(governance, "node_version", explode)
    harness_executor.register(harness_contract(tier="lite"))

    result = harness_executor.run("H1")

    assert result["state"] == "SUCCEEDED"
    problems, _summary = harness_executor.verify(require_complete=True)
    assert problems == []


def test_effect_is_the_contract_gate_and_nothing_wider():
    contract = harness_contract(tier="lite")
    effect = governed.effect_for(contract, workspace="/tmp/ws")

    assert effect["tool"] == governed.GATE_TOOL
    assert effect["args"]["gate"] == contract.gate.command_string()
    assert effect["args"]["contract_digest"] == contract.digest()
    assert set(effect["args"]) == {
        "task_id",
        "contract_digest",
        "level",
        "tier",
        "gate",
        "workspace",
    }


def test_args_digest_matches_veor_canonicalization_and_refuses_floats():
    assert governed.veor_args_digest({"b": 1, "a": "x"}) == governed.veor_args_digest(
        {"a": "x", "b": 1}
    )
    assert governed.veor_args_digest({}) != governed.veor_args_digest({"a": ""})
    with pytest.raises(GovernanceUnavailable, match="float"):
        governed.veor_args_digest({"a": 1.5})


def test_governed_module_never_writes_a_verdict():
    source = (REPO / "harness" / "governed.py").read_text(encoding="utf-8")

    for forbidden in (
        "update_ledger",
        "review_attestation",
        "record_review",
        "transition(",
        "finish_attempt(",
    ):
        assert forbidden not in source, forbidden
