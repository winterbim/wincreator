import sqlite3

import pytest

from conftest import harness_contract

from harness.store import InvalidTransition, StoreError


def _ready(store, contract):
    store.register_task(contract, actor="builder-01")
    store.transition(contract.task_id, "READY", actor="builder-01", reason="admitted")
    return store.get_task(contract.task_id)


def test_registration_is_pending_and_idempotent(harness_store):
    contract = harness_contract()

    first = harness_store.register_task(contract, actor="builder-01")
    second = harness_store.register_task(contract, actor="builder-01")

    assert first.state == "PENDING"
    assert second.state == "PENDING"
    assert first.contract.digest() == contract.digest()


def test_reregistering_a_changed_contract_is_refused(harness_store):
    harness_store.register_task(harness_contract(claim="first claim"))

    with pytest.raises(ValueError, match="already registered with a different contract"):
        harness_store.register_task(harness_contract(claim="second claim"))


@pytest.mark.parametrize(
    "start, target",
    [
        ("PENDING", "RUNNING"),
        ("PENDING", "SUCCEEDED"),
        ("READY", "SUCCEEDED"),
        ("READY", "AWAITING_REVIEW"),
        ("SUCCEEDED", "READY"),
        ("FAILED", "SUCCEEDED"),
    ],
)
def test_invalid_transitions_are_rejected(harness_store, start, target):
    contract = harness_contract()
    harness_store.register_task(contract)
    if start != "PENDING":
        # The starting state is a fixture: the guard under test is the edge,
        # not the path used to reach the source state.
        with sqlite3.connect(harness_store.db_path) as connection:
            connection.execute(
                "UPDATE tasks SET state=? WHERE task_id=?", (start, contract.task_id)
            )

    with pytest.raises(InvalidTransition):
        harness_store.transition(contract.task_id, target)


def test_running_requires_an_open_attempt(harness_store):
    contract = harness_contract()
    _ready(harness_store, contract)

    with pytest.raises(InvalidTransition, match="without exactly one open attempt"):
        harness_store.transition(contract.task_id, "RUNNING")


def test_leaving_running_requires_closing_the_attempt(harness_store):
    contract = harness_contract()
    _ready(harness_store, contract)
    harness_store.begin_attempt(contract.task_id, owner_pid=1)

    with pytest.raises(InvalidTransition, match="cannot leave RUNNING"):
        harness_store.transition(contract.task_id, "FAILED")


def test_succeeded_without_an_evidence_review_is_refused(harness_store):
    contract = harness_contract()
    _ready(harness_store, contract)
    harness_store.begin_attempt(contract.task_id, owner_pid=1)

    with pytest.raises(InvalidTransition, match="without a captured proof"):
        harness_store.finish_attempt(contract.task_id, 1, "PASS", "SUCCEEDED")

    attempt = harness_store.current_attempt(contract.task_id)
    assert attempt["state"] == "RUNNING", "the refused transition must roll back"


def test_attempt_numbering_abandonment_and_retry_budget(harness_store):
    contract = harness_contract(max_attempts=2)
    _ready(harness_store, contract)

    first = harness_store.begin_attempt(contract.task_id, owner_pid=1)
    with pytest.raises(InvalidTransition, match="only READY"):
        harness_store.begin_attempt(contract.task_id, owner_pid=1)
    harness_store.abandon_attempt(contract.task_id, first, reason="test")
    harness_store.retry(contract.task_id, reason="changed plan")

    second = harness_store.begin_attempt(contract.task_id, owner_pid=1)
    harness_store.abandon_attempt(contract.task_id, second, reason="test")

    assert (first, second) == (1, 2)
    with pytest.raises(InvalidTransition, match="exhausted"):
        harness_store.retry(contract.task_id, reason="third try")


def test_retry_requires_a_failed_blocked_or_interrupted_task(harness_store):
    contract = harness_contract()
    _ready(harness_store, contract)

    with pytest.raises(InvalidTransition, match="retry needs"):
        harness_store.retry(contract.task_id, reason="nothing to retry")


def test_journal_chain_is_clean_after_normal_use(harness_store):
    contract = harness_contract()
    _ready(harness_store, contract)
    harness_store.begin_attempt(contract.task_id, owner_pid=1)
    harness_store.abandon_attempt(contract.task_id, 1, reason="crash simulation")
    harness_store.retry(contract.task_id, reason="resume")

    events = harness_store.events(contract.task_id)

    assert [event["type"] for event in events] == [
        "task_registered",
        "state_changed",
        "attempt_started",
        "state_changed",
        "attempt_abandoned",
        "state_changed",
        "state_changed",
        "retry_scheduled",
    ]
    assert events[0]["payload"]["contract_sha256"] == contract.digest()
    assert harness_store.verify_integrity() == []


def test_journal_detects_an_edited_event(harness_store):
    contract = harness_contract()
    _ready(harness_store, contract)

    with sqlite3.connect(harness_store.db_path) as connection:
        connection.execute(
            "UPDATE events SET payload_json=? WHERE type='task_registered'",
            ('{"contract_sha256":"tampered"}',),
        )

    problems = harness_store.verify_integrity()

    assert any("digest mismatch" in problem for problem in problems)


def test_journal_detects_a_deleted_middle_event(harness_store):
    contract = harness_contract()
    _ready(harness_store, contract)
    harness_store.begin_attempt(contract.task_id, owner_pid=1)
    events = harness_store.events(contract.task_id)
    assert len(events) >= 3

    with sqlite3.connect(harness_store.db_path) as connection:
        connection.execute("DELETE FROM events WHERE seq=?", (events[1]["seq"],))

    problems = harness_store.verify_integrity()

    assert any("prev_digest does not link" in problem for problem in problems)


def test_contract_edit_in_the_database_is_detected(harness_store):
    contract = harness_contract()
    harness_store.register_task(contract)

    with sqlite3.connect(harness_store.db_path) as connection:
        connection.execute(
            "UPDATE tasks SET contract_json=? WHERE task_id=?",
            ('{"task_id":"H1"}', contract.task_id),
        )

    problems = harness_store.verify_integrity()

    assert any("unreadable contract" in problem for problem in problems)


def test_succeeded_state_forged_at_sql_level_is_detected(harness_store):
    contract = harness_contract()
    harness_store.register_task(contract)

    with sqlite3.connect(harness_store.db_path) as connection:
        connection.execute(
            "UPDATE tasks SET state='SUCCEEDED' WHERE task_id=?", (contract.task_id,)
        )

    problems = harness_store.verify_integrity()

    assert any("SUCCEEDED without any stored proof" in problem for problem in problems)


def test_missing_store_is_reported_not_raised(harness_store):
    from harness.store import Store

    store = Store("/nonexistent/harness-root")

    assert store.verify_integrity()
    with pytest.raises(StoreError, match="no harness store"):
        store.ensure_initialized()
