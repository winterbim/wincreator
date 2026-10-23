"""Minimal execution engine: run a typed task, persist proof, resume safely.

Execution discipline:

- the gate is always executed by the WinCreator proof kernel, never re-run by
  this module;
- a task becomes ``SUCCEEDED`` only with a stored ``CAPTURED_PASS`` proof whose
  review verdict is ``EVIDENCED`` — enforced in the store, not here;
- an attempt row is committed before the gate starts, so a killed process
  leaves auditable evidence of what was in flight;
- ``resume`` reaps attempts whose owner is dead or whose lease expired and
  treats the gate as at-least-once: a retried gate runs again.
"""

import os
from typing import Dict, Iterable, List, Optional

from harness import kernel
from harness.contracts import ContractError, TaskContract, TaskView
from harness.store import (
    InvalidTransition,
    Store,
    StoreError,
    UnknownTask,
)
from harness.util import iso_time, parse_iso, pid_alive, utc_now

REVIEW_STATE = {
    "EVIDENCED": "SUCCEEDED",
    "INSUFFICIENT": "BLOCKED",
    "DISPROVEN": "FAILED",
}


class RuntimeError_(RuntimeError):
    """A runtime-level operation could not be completed."""


class Executor:
    def __init__(
        self,
        root,
        builder=None,
        lease_seconds=900,
        quiet=False,
    ):
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        self.store = Store(root)
        self.builder = builder or os.environ.get("WINCREATOR_BUILDER") or "harness-builder"
        self.lease_seconds = lease_seconds
        self.quiet = quiet

    # ---------------------------------------------------------------- helpers
    def _say(self, message):
        if not self.quiet:
            print(message)

    def initialize(self):
        self.store.initialize()
        return self.store

    def register(self, contract: TaskContract):
        return self.store.register_task(contract, actor=self.builder)

    def status(self):
        return [
            {
                "task_id": task.task_id,
                "state": task.state,
                "name": task.contract.name,
                "tier": task.contract.tier,
                "attempts": len(task.attempts),
                "max_attempts": task.contract.max_attempts,
                "capture_status": (task.proof or {}).get("capture_status"),
                "review_verdict": (task.proof or {}).get("review_verdict"),
            }
            for task in self.store.list_tasks()
        ]

    # -------------------------------------------------------------------- run
    def _is_governed(self, task_id):
        return any(
            event["type"].startswith("governance_")
            for event in self.store.events(task_id)
        )

    def run(self, task_id, extra_files=(), on_capture=None, governed=False):
        task = self.store.get_task(task_id)
        if governed and on_capture is None:
            # The flag alone is an caller assertion. Without a verifier nothing
            # checks the VEOR receipt, so this is an ungoverned execution
            # wearing a governed label. Refuse it.
            raise InvalidTransition(
                f"task {task_id}: governed execution requires a capture verifier; "
                "use the governance path"
            )
        if not governed and self._is_governed(task_id):
            raise InvalidTransition(
                f"task {task_id} is governed and must run through the governance path; "
                "a plain run or retry would bypass the VEOR decision"
            )
        if task.state == "PENDING":
            self.store.transition(task_id, "READY", actor=self.builder, reason="admitted")
        elif task.state != "READY":
            raise InvalidTransition(
                f"task {task_id} is {task.state}; run needs READY "
                "(use `resume` for interrupted work, `retry --reason` for failed work)"
            )
        attempt_no = self.store.begin_attempt(
            task_id,
            owner_pid=os.getpid(),
            lease_seconds=self.lease_seconds,
            actor=self.builder,
        )
        self._say(f"[RUNNING] {task_id} attempt {attempt_no} tier={task.contract.tier}")
        try:
            kernel.ensure_claim(task.ledger_path, task.contract)
            attestation, attestation_path, return_code = kernel.capture(
                task.contract,
                task.ledger_path,
                task.attest_dir,
                task.workspace,
                builder=self.builder,
                extra_files=extra_files,
            )
        except (OSError, ValueError, KeyError, RuntimeError) as error:
            self.store.finish_attempt(
                task_id,
                attempt_no,
                outcome="ERROR",
                state="FAILED",
                reason="gate could not run",
                detail=str(error),
                actor=self.builder,
            )
            self._say(f"[FAILED] {task_id} gate could not run: {error}")
            return {
                "task_id": task_id,
                "state": "FAILED",
                "attempt_no": attempt_no,
                "capture_status": None,
                "attestation_path": None,
                "attestation_digest": None,
                "return_code": None,
                "review_required": False,
                "error": str(error),
            }
        payload = attestation["payload"]
        capture_status = payload["capture"]["status"]
        attestation_digest = attestation["digest"]["value"]
        review_document, _review_path = kernel.capture_review(attestation_path)
        review_verdict = None
        reviewer = None
        review_digest = None
        if review_document:
            review_verdict = review_document["payload"]["verdict"]
            reviewer = review_document["payload"]["reviewer"]
            review_digest = review_document["digest"]["value"]
        self.store.record_proof(
            task_id,
            attempt_no,
            attestation_path=os.path.abspath(attestation_path),
            attestation_digest=attestation_digest,
            capture_status=capture_status,
            return_code=payload["capture"]["exit_code"],
            review_verdict=review_verdict,
            reviewer=reviewer,
            review_digest=review_digest,
            actor=self.builder,
        )
        if on_capture is not None:
            try:
                on_capture(
                    {
                        "task_id": task_id,
                        "attempt_no": attempt_no,
                        "attestation": attestation,
                        "attestation_path": attestation_path,
                        "payload": payload,
                    }
                )
            except (OSError, ValueError, RuntimeError) as error:
                self.store.finish_attempt(
                    task_id,
                    attempt_no,
                    outcome="ERROR",
                    state="BLOCKED",
                    reason="governance could not establish a verified receipt",
                    detail=str(error),
                    actor=self.builder,
                )
                self._say(f"[BLOCKED] {task_id} governance: {error}")
                return {
                    "task_id": task_id,
                    "state": "BLOCKED",
                    "attempt_no": attempt_no,
                    "capture_status": capture_status,
                    "attestation_path": os.path.abspath(attestation_path),
                    "attestation_digest": attestation_digest,
                    "return_code": payload["capture"]["exit_code"],
                    "review_required": False,
                    "error": str(error),
                }
        if capture_status == "CAPTURED_FAIL":
            state, reason = "FAILED", "gate failed"
        elif capture_status == "CAPTURE_ERROR":
            state, reason = "BLOCKED", "capture error"
        elif review_verdict in REVIEW_STATE:
            state, reason = REVIEW_STATE[review_verdict], f"review verdict={review_verdict}"
        elif task.contract.require_review:
            state, reason = "AWAITING_REVIEW", "independent review required"
        else:
            state = "FAILED"
            reason = "capture passed without an EVIDENCED review"
        try:
            self.store.finish_attempt(
                task_id,
                attempt_no,
                outcome="PASS" if capture_status == "CAPTURED_PASS" else "FAIL",
                state=state,
                reason=reason,
                detail=None,
                actor=self.builder,
            )
        except InvalidTransition:
            # The proof exists but the ledger refuses the transition. Record the
            # attempt as finished in a state the machine accepts, never silently.
            self.store.finish_attempt(
                task_id,
                attempt_no,
                outcome="ERROR",
                state="BLOCKED",
                reason=reason,
                detail="state machine rejected the transition; see proof row",
                actor=self.builder,
            )
            state = "BLOCKED"
        self._say(
            f"[{state}] {task_id} capture={capture_status} "
            f"exit={payload['capture']['exit_code']} proof={attestation_digest[:12]}"
        )
        return {
            "task_id": task_id,
            "state": state,
            "attempt_no": attempt_no,
            "capture_status": capture_status,
            "attestation_path": os.path.abspath(attestation_path),
            "attestation_digest": attestation_digest,
            "return_code": payload["capture"]["exit_code"],
            "review_required": state == "AWAITING_REVIEW",
            "error": payload["capture"]["error"],
        }

    # ----------------------------------------------------------------- resume
    def reap(self, task_ids: Optional[Iterable[str]] = None, alive=None):
        """Close attempts whose owner is dead or whose lease expired."""
        alive = alive or pid_alive
        targets = (
            [self.store.get_task(task_id) for task_id in task_ids]
            if task_ids
            else self.store.list_tasks()
        )
        reaped = []
        for task in targets:
            if task.state != "RUNNING":
                continue
            attempt = self.store.open_attempt(task.task_id)
            if attempt is None:
                reason = "RUNNING task had no open attempt"
                self.store.transition(
                    task.task_id, "INTERRUPTED", actor="resume", reason=reason
                )
                reaped.append(
                    {"task_id": task.task_id, "attempt_no": None, "reason": reason}
                )
                continue
            if not self._reapable(attempt, alive):
                continue
            reason = (
                f"attempt owner pid {attempt['owner_pid']} is gone"
                if not alive(attempt["owner_pid"])
                else f"attempt lease expired at {attempt['lease_expires_at']}"
            )
            self.store.abandon_attempt(task.task_id, attempt["attempt_no"], reason)
            reaped.append(
                {
                    "task_id": task.task_id,
                    "attempt_no": attempt["attempt_no"],
                    "reason": reason,
                }
            )
            self._say(f"[INTERRUPTED] {task.task_id} attempt {attempt['attempt_no']}: {reason}")
        return reaped

    @staticmethod
    def _reapable(attempt, alive):
        if attempt.get("state") != "RUNNING":
            return False
        if not alive(attempt.get("owner_pid")):
            return True
        lease = parse_iso(attempt.get("lease_expires_at"))
        return lease is None or lease <= utc_now()

    def resume(self, task_ids=None, retry=True):
        reaped = self.reap(task_ids)
        results: List[Dict[str, object]] = []
        targets = (
            [self.store.get_task(task_id) for task_id in task_ids]
            if task_ids
            else self.store.list_tasks()
        )
        for task in targets:
            current = self.store.get_task(task.task_id)
            if current.state == "INTERRUPTED" and retry:
                if self._is_governed(task.task_id):
                    self._say(
                        f"[BLOCKED] {task.task_id} is governed; resume will not retry it "
                        "ungoverned (re-run through `run-governed`)"
                    )
                    continue
                try:
                    self.store.retry(
                        task.task_id, reason="resume after interruption", actor="resume"
                    )
                except InvalidTransition as error:
                    self._say(f"[INTERRUPTED] {task.task_id}: {error}")
                    continue
            current = self.store.get_task(task.task_id)
            if current.state == "READY":
                if self._is_governed(task.task_id):
                    self._say(
                        f"[SKIPPED] {task.task_id} is governed; resume will not run it "
                        "without a fresh VEOR decision (re-run through `run-governed`)"
                    )
                    continue
                results.append(self.run(task.task_id))
        return {"reaped": reaped, "results": results}

    def run_ready(self):
        results = []
        for task in self.store.list_tasks(state="READY"):
            if self._is_governed(task.task_id):
                self._say(
                    f"[SKIPPED] {task.task_id} is governed; use `run-governed` so a "
                    "VEOR decision precedes the gate"
                )
                continue
            results.append(self.run(task.task_id))
        return results

    # ----------------------------------------------------------------- review
    def review(
        self,
        task_id,
        verdict,
        reviewer,
        challenge,
        automatic=False,
    ):
        verdict = verdict.upper()
        if verdict not in REVIEW_STATE:
            raise ValueError(f"invalid review verdict: {verdict}")
        task = self.store.get_task(task_id)
        if task.state != "AWAITING_REVIEW":
            raise InvalidTransition(
                f"task {task_id} is {task.state}; review needs AWAITING_REVIEW"
            )
        proof = self.store.latest_proof(task_id)
        if proof is None or proof["capture_status"] != "CAPTURED_PASS":
            raise StoreError(f"task {task_id} has no passing capture to review")
        if proof["review_verdict"] is not None:
            raise StoreError(f"task {task_id} proof is already reviewed (immutable)")
        packet_path = os.path.join(
            self.store.packet_dir, f"{task_id}-attempt{proof['attempt_no']}.json"
        )
        kernel.write_challenge_packet(proof["attestation_path"], packet_path)
        review_document, review_path = kernel.review(
            proof["attestation_path"],
            verdict,
            reviewer,
            task.ledger_path,
            challenge,
            packet_path=packet_path,
            automatic=automatic,
            expected_claim_id=task_id,
        )
        review_digest = review_document["digest"]["value"]
        self.store.record_review(
            task_id,
            proof["attempt_no"],
            verdict=verdict,
            reviewer=reviewer,
            review_digest=review_digest,
            actor=reviewer,
        )
        state = REVIEW_STATE[verdict]
        self.store.transition(
            task_id, state, actor=reviewer, reason=f"review verdict={verdict}"
        )
        self._say(f"[{state}] {task_id} reviewed {verdict} by {reviewer}")
        return {
            "task_id": task_id,
            "state": state,
            "verdict": verdict,
            "reviewer": reviewer,
            "review_path": review_path,
            "review_digest": review_digest,
        }

    def retry(self, task_id, reason, governed=False):
        if not reason or not reason.strip():
            raise ValueError("retry requires a stated reason")
        if not governed and self._is_governed(task_id):
            raise InvalidTransition(
                f"task {task_id} is governed; a retry would execute the gate without a "
                "fresh VEOR decision (use `run-governed --retry-reason`)"
            )
        previous = self.store.retry(task_id, reason=reason, actor=self.builder)
        self._say(f"[READY] {task_id} retry scheduled from {previous}: {reason}")
        return previous

    # ----------------------------------------------------------------- verify
    def _governance_problems(self, task, governance_config=None):
        """Re-verify any VEOR receipt bound to this task's proof.

        A governed task whose receipt cannot be verified offline is a problem,
        never a silent pass. Tasks that never entered the governance path are
        unaffected, which keeps VEOR optional.
        """
        if not self._is_governed(task.task_id):
            return []
        from harness import governed

        config = governance_config or governed.GovernanceConfig.for_root(
            self.store.root
        )
        try:
            return governed.verify_task(self, task.task_id, config)
        except governed.governance.GovernanceUnavailable as error:
            return [f"{task.task_id}: governance: {error}"]

    def verify(self, require_complete=False, governance_config=None):
        problems = list(self.store.verify_integrity())
        summary = {"tasks": 0, "succeeded": 0, "proofs": 0, "pending": []}
        tasks = self.store.list_tasks()
        summary["tasks"] = len(tasks)
        for task in tasks:
            if task.state == "SUCCEEDED":
                summary["succeeded"] += 1
            else:
                summary["pending"].append(f"{task.task_id}={task.state}")
            proof = task.proof
            if proof is None:
                continue
            summary["proofs"] += 1
            problems.extend(self._governance_problems(task, governance_config))
            ok, issues = kernel.verify_attestation(proof["attestation_path"])
            if not ok:
                problems.extend(
                    f"{task.task_id}: capture {proof['attestation_path']}: {issue}"
                    for issue in issues
                )
                continue
            if proof["review_verdict"] is None:
                continue
            review_path = os.path.join(
                os.path.dirname(proof["attestation_path"]), "review.json"
            )
            review_ok, review_issues = kernel.verify_review(
                review_path, proof["attestation_path"]
            )
            if not review_ok:
                problems.extend(
                    f"{task.task_id}: review {review_path}: {issue}"
                    for issue in review_issues
                )
                continue
            with open(review_path, encoding="utf-8") as handle:
                import json as _json

                review_document = _json.load(handle)
            if review_document["digest"]["value"] != proof["review_digest"]:
                problems.append(
                    f"{task.task_id}: stored review digest does not match the retained review"
                )
            if review_document["payload"]["verdict"] != proof["review_verdict"]:
                problems.append(
                    f"{task.task_id}: stored review verdict does not match the retained review"
                )
            try:
                claim = kernel.claim_status(task.ledger_path, task.task_id)
            except (KeyError, ValueError) as error:
                problems.append(f"{task.task_id}: ledger row unreadable: {error}")
                continue
            if task.state == "SUCCEEDED":
                if claim["status"] != "EVIDENCED":
                    problems.append(
                        f"{task.task_id}: task is SUCCEEDED but ledger row is {claim['status']}"
                    )
                if proof["attestation_digest"] not in claim["evidence"]:
                    problems.append(
                        f"{task.task_id}: ledger evidence does not reference the stored proof"
                    )
            elif claim["status"] == "EVIDENCED" and task.state != "SUCCEEDED":
                problems.append(
                    f"{task.task_id}: ledger row is EVIDENCED but task is {task.state}"
                )
        if require_complete:
            for entry in summary["pending"]:
                problems.append(f"task not complete: {entry}")
            if os.path.isfile(self.store.ledger_path):
                problems.extend(
                    f"ledger: {violation}"
                    for violation in kernel.ledger_violations(self.store.ledger_path)
                )
                checked, ledger_problems = kernel.verify_ledger(self.store.ledger_path)
                summary["ledger_captures"] = checked
                problems.extend(ledger_problems)
        return problems, summary
