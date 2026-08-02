import json
import sys

import pytest

from conftest import prove


def test_prove_binds_exact_claim_and_gate(wincreator, ledger, tmp_path):
    attestation, _path, code = prove(wincreator, ledger, tmp_path)

    claim = attestation["payload"]["claim"]
    assert code == 0
    assert claim["id"] == "P1"
    assert claim["level"] == "Micro"
    assert claim["text"] == "parser rejects malformed input"
    assert claim["gate"] == "`python check_parser.py`"
    assert len(claim["row_sha256"]) == 64
    assert len(claim["ledger_sha256_before"]) == 64


def test_passing_gate_is_captured_not_auto_approved(wincreator, ledger, tmp_path):
    attestation, _path, code = prove(wincreator, ledger, tmp_path)

    assert code == 0
    assert attestation["payload"]["capture"]["status"] == "CAPTURED_PASS"
    assert wincreator.read_claim(str(ledger), "P1")["status"] == "PENDING"


def test_nonzero_gate_is_captured_fail_and_never_evidenced(wincreator, ledger, tmp_path):
    attestation, _path, code = prove(
        wincreator,
        ledger,
        tmp_path,
        command=[sys.executable, "-c", "import sys; sys.exit(7)"],
    )

    assert code == 7
    assert attestation["payload"]["capture"]["status"] == "CAPTURED_FAIL"
    assert wincreator.read_claim(str(ledger), "P1")["status"] == "DISPROVEN"


def test_missing_required_file_stops_before_gate(wincreator, ledger, tmp_path):
    marker = tmp_path / "gate-ran"
    with pytest.raises(FileNotFoundError, match="required evidence file"):
        prove(
            wincreator,
            ledger,
            tmp_path,
            command=[sys.executable, "-c", f"open({str(marker)!r}, 'w').write('ran')"],
            files=[str(tmp_path / "missing.ifc")],
        )
    assert not marker.exists()


def test_optional_missing_file_is_explicit(wincreator, ledger, tmp_path):
    attestation, _path, _code = prove(
        wincreator,
        ledger,
        tmp_path,
        optional_files=[str(tmp_path / "optional.ifc")],
    )
    assert attestation["payload"]["files"] == [
        {"path": "optional.ifc", "optional": True, "missing": True}
    ]


def test_command_start_failure_is_recorded_as_capture_error(wincreator, ledger, tmp_path):
    attestation, _path, code = prove(
        wincreator,
        ledger,
        tmp_path,
        command=[str(tmp_path / "does-not-exist")],
    )
    assert code == 2
    assert attestation["payload"]["capture"]["status"] == "CAPTURE_ERROR"
    assert wincreator.read_claim(str(ledger), "P1")["status"] == "BLOCKED"


def test_auto_approve_lite_rejected_before_execution_in_standard_mode(
    wincreator, ledger, tmp_path
):
    marker = tmp_path / "gate-ran"
    with pytest.raises(ValueError, match="only valid in Lite"):
        prove(
            wincreator,
            ledger,
            tmp_path,
            command=[sys.executable, "-c", f"open({str(marker)!r}, 'w').write('ran')"],
            auto_approve_lite=True,
            tier="standard",
        )
    assert not marker.exists()
