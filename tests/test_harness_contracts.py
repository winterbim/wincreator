import json

import pytest

from conftest import harness_contract


def test_contract_round_trip_preserves_digest():
    from harness.contracts import TaskContract

    contract = harness_contract(tier="standard", max_attempts=2)
    restored = TaskContract.from_dict(json.loads(json.dumps(contract.to_dict())))

    assert restored == contract
    assert restored.digest() == contract.digest()


def test_standard_tier_defaults_to_required_review():
    contract = harness_contract(tier="standard")

    assert contract.require_review is True


def test_lite_tier_may_skip_review():
    contract = harness_contract(tier="lite", require_review=False)

    assert contract.require_review is False


def test_standard_tier_cannot_disable_review():
    with pytest.raises(ValueError, match="cannot disable independent review"):
        harness_contract(tier="standard", require_review=False)


def test_multiline_claim_is_rejected():
    with pytest.raises(ValueError, match="single line"):
        harness_contract(claim="line one\nline two")


def test_unknown_contract_field_is_rejected():
    from harness.contracts import ContractError, TaskContract

    document = harness_contract().to_dict()
    document["extra"] = True

    with pytest.raises(ContractError, match="unsupported field"):
        TaskContract.from_dict(document)


def test_unknown_gate_field_is_rejected():
    from harness.contracts import ContractError, TaskContract

    document = harness_contract().to_dict()
    document["gate"]["shell"] = True

    with pytest.raises(ContractError, match="gate has unsupported field"):
        TaskContract.from_dict(document)


def test_missing_required_field_is_rejected():
    from harness.contracts import ContractError, TaskContract

    document = harness_contract().to_dict()
    del document["claim"]

    with pytest.raises(ContractError, match="missing required field"):
        TaskContract.from_dict(document)


def test_empty_gate_command_is_rejected():
    from harness.contracts import ContractError, GateSpec, TaskContract

    with pytest.raises(ContractError, match="gate.command"):
        TaskContract(
            task_id="H1",
            name="n",
            claim="c",
            level="Micro",
            tier="lite",
            gate=GateSpec(command=()),
        )


@pytest.mark.parametrize("attempts", [0, 21, True, "3"])
def test_max_attempts_is_bounded_and_typed(attempts):
    with pytest.raises(ValueError):
        harness_contract(max_attempts=attempts)


def test_invalid_level_and_id_are_rejected():
    with pytest.raises(ValueError, match="level must be one of"):
        harness_contract(level="Epic")
    with pytest.raises(ValueError, match="task_id"):
        harness_contract(task_id="../escape")


def test_changing_the_gate_changes_the_digest():
    first = harness_contract()
    second = harness_contract(command=["python3", "-c", "print('other')"])

    assert first.digest() != second.digest()


def test_case_sensitive_claim_change_changes_digest():
    first = harness_contract(claim="export preserves rows")
    second = harness_contract(claim="Export preserves rows")

    assert first.digest() != second.digest()
