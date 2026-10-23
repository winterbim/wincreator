import json
import os
import sys

import pytest

from conftest import harness_contract

from harness import kernel
from harness.store import InvalidTransition


def test_lite_task_runs_reaches_succeeded_and_verifies(harness_executor):
    contract = harness_contract(tier="lite")
    harness_executor.register(contract)

    result = harness_executor.run(contract.task_id)

    assert result["state"] == "SUCCEEDED"
    assert result["capture_status"] == "CAPTURED_PASS"
    proof = harness_executor.store.latest_proof(contract.task_id)
    assert proof["review_verdict"] == "EVIDENCED"
    assert os.path.isfile(proof["attestation_path"])
    claim = kernel.claim_status(harness_executor.store.ledger_path, contract.task_id)
    assert claim["status"] == "EVIDENCED"
    problems, summary = harness_executor.verify(require_complete=True)
    assert problems == []
    assert summary["succeeded"] == 1
    event_types = [event["type"] for event in harness_executor.store.events(contract.task_id)]
    assert event_types.count("proof_recorded") == 1
    assert "state_changed" in event_types


def test_standard_task_stops_at_awaiting_review(harness_executor):
    contract = harness_contract(tier="standard")
    harness_executor.register(contract)

    result = harness_executor.run(contract.task_id)

    assert result["state"] == "AWAITING_REVIEW"
    assert result["review_required"] is True
    assert harness_executor.store.latest_proof(contract.task_id)["review_verdict"] is None
    assert kernel.claim_status(harness_executor.store.ledger_path, contract.task_id)["status"] == "PENDING"
    problems, summary = harness_executor.verify()
    assert problems == []
    assert summary["pending"] == [f"{contract.task_id}=AWAITING_REVIEW"]


def test_standard_task_is_evidenced_only_by_review(harness_executor):
    contract = harness_contract(tier="standard")
    harness_executor.register(contract)
    harness_executor.run(contract.task_id)

    reviewed = harness_executor.review(
        contract.task_id,
        "evidenced",
        "skeptic-01",
        "attack whether the captured gate exercises the exact claim",
    )

    assert reviewed["state"] == "SUCCEEDED"
    assert harness_executor.store.get_task(contract.task_id).state == "SUCCEEDED"
    assert kernel.claim_status(harness_executor.store.ledger_path, contract.task_id)["status"] == "EVIDENCED"
    assert harness_executor.verify(require_complete=True)[0] == []

    with pytest.raises((InvalidTransition, ValueError)):
        harness_executor.review(
            contract.task_id,
            "evidenced",
            "skeptic-02",
            "second review of an already reviewed capture",
        )


def test_insufficient_review_blocks_the_task(harness_executor):
    contract = harness_contract(tier="standard")
    harness_executor.register(contract)
    harness_executor.run(contract.task_id)

    result = harness_executor.review(
        contract.task_id,
        "insufficient",
        "skeptic-01",
        "the gate never exercised the error path named by the claim",
    )

    assert result["state"] == "BLOCKED"
    assert kernel.claim_status(harness_executor.store.ledger_path, contract.task_id)["status"] == "INSUFFICIENT"
    problems, summary = harness_executor.verify()
    assert problems == []
    assert f"{contract.task_id}=BLOCKED" in summary["pending"]


def test_failing_gate_is_disproven_never_evidenced(harness_executor):
    contract = harness_contract(
        tier="lite", command=[sys.executable, "-c", "import sys; sys.exit(3)"]
    )
    harness_executor.register(contract)

    result = harness_executor.run(contract.task_id)

    assert result["state"] == "FAILED"
    assert result["capture_status"] == "CAPTURED_FAIL"
    assert kernel.claim_status(harness_executor.store.ledger_path, contract.task_id)["status"] == "DISPROVEN"


def test_unlaunchable_gate_is_blocked_with_a_capture_error(harness_executor):
    contract = harness_contract(tier="lite", command=["/nonexistent/wincreator-gate"])
    harness_executor.register(contract)

    result = harness_executor.run(contract.task_id)

    assert result["state"] == "BLOCKED"
    assert result["capture_status"] == "CAPTURE_ERROR"
    assert result["error"]


def test_missing_required_file_stops_before_the_gate(harness_executor, tmp_path):
    marker = tmp_path / "gate-ran"
    contract = harness_contract(
        tier="lite",
        command=[sys.executable, "-c", f"open({str(marker)!r}, 'w').write('ran')"],
        files=["missing.txt"],
    )
    harness_executor.register(contract)

    result = harness_executor.run(contract.task_id)

    assert result["state"] == "FAILED"
    assert "required evidence file" in result["error"]
    assert not marker.exists()


def test_verify_detects_a_tampered_attestation(harness_executor):
    contract = harness_contract(tier="lite")
    harness_executor.register(contract)
    harness_executor.run(contract.task_id)
    path = harness_executor.store.latest_proof(contract.task_id)["attestation_path"]

    with open(path, encoding="utf-8") as handle:
        document = json.load(handle)
    document["payload"]["capture"]["exit_code"] = 99
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle)

    problems = harness_executor.verify()[0]

    assert any("digest mismatch" in problem for problem in problems)


def test_verify_require_complete_flags_pending_work(harness_executor):
    contract = harness_contract(tier="standard")
    harness_executor.register(contract)
    harness_executor.run(contract.task_id)

    problems = harness_executor.verify(require_complete=True)[0]

    assert any("task not complete" in problem for problem in problems)
    assert any("not evidenced" in problem for problem in problems)


def test_builder_cannot_review_own_capture(harness_executor):
    contract = harness_contract(tier="standard")
    harness_executor.register(contract)
    harness_executor.run(contract.task_id)

    with pytest.raises(ValueError, match="builder and reviewer must differ"):
        harness_executor.review(
            contract.task_id,
            "evidenced",
            "builder-01",
            "review my own work",
        )


def test_run_refuses_a_task_that_already_succeeded(harness_executor):
    contract = harness_contract(tier="lite")
    harness_executor.register(contract)
    harness_executor.run(contract.task_id)

    with pytest.raises(InvalidTransition, match="use `resume`"):
        harness_executor.run(contract.task_id)


def test_pid_liveness_reports_a_dead_owner_as_dead():
    from harness.util import pid_alive

    assert pid_alive(None) is False
    assert pid_alive(0) is False
    assert pid_alive(-5) is False
    assert pid_alive(999_999_999) is False
    assert pid_alive(os.getpid()) is True


def test_resume_recovers_an_attempt_whose_owner_is_gone(harness_executor):
    contract = harness_contract(tier="lite", max_attempts=2)
    harness_executor.register(contract)
    harness_executor.store.transition(contract.task_id, "READY", actor="builder-01")
    harness_executor.store.begin_attempt(contract.task_id, owner_pid=999_999_999)

    outcome = harness_executor.resume()

    assert outcome["reaped"], "the dead-owner attempt must be reaped"
    assert outcome["results"][0]["state"] == "SUCCEEDED"
    task = harness_executor.store.get_task(contract.task_id)
    assert [attempt["state"] for attempt in task.attempts] == ["ABANDONED", "COMPLETED"]
    event_types = [event["type"] for event in harness_executor.store.events(contract.task_id)]
    assert "attempt_abandoned" in event_types
    assert "retry_scheduled" in event_types
    assert harness_executor.store.verify_integrity() == []


def test_resume_without_retry_leaves_work_interrupted(harness_executor):
    contract = harness_contract(tier="lite", max_attempts=2)
    harness_executor.register(contract)
    harness_executor.store.transition(contract.task_id, "READY", actor="builder-01")
    harness_executor.store.begin_attempt(contract.task_id, owner_pid=999_999_999)

    outcome = harness_executor.resume(retry=False)

    assert outcome["reaped"]
    assert outcome["results"] == []
    assert harness_executor.store.get_task(contract.task_id).state == "INTERRUPTED"


def test_reap_honours_the_lease_for_a_live_owner(harness_executor):
    contract = harness_contract(tier="lite")
    harness_executor.register(contract)
    harness_executor.store.transition(contract.task_id, "READY", actor="builder-01")
    harness_executor.store.begin_attempt(
        contract.task_id, owner_pid=os.getpid(), lease_seconds=60
    )

    assert harness_executor.reap(alive=lambda pid: True) == []
    assert harness_executor.store.get_task(contract.task_id).state == "RUNNING"
