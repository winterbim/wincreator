import json
from pathlib import Path
import shutil

import pytest

from conftest import prove


def reviewed_capture(wincreator, ledger, tmp_path):
    attestation, path, _code = prove(wincreator, ledger, tmp_path)
    wincreator.review_attestation(
        str(path), verdict="EVIDENCED", reviewer="skeptic-01", ledger=str(ledger)
    )
    return attestation, Path(path)


@pytest.mark.parametrize("column,replacement", [
    (0, "P9"),
    (1, "Macro"),
    (2, "parser accepts malformed input"),
    (3, "`true`"),
    (4, "WAIVED"),
    (5, "rewritten evidence"),
])
def test_verify_rejects_ledger_row_tampering(wincreator, ledger, tmp_path, column, replacement):
    _attestation, _path = reviewed_capture(wincreator, ledger, tmp_path)
    lines = ledger.read_text(encoding="utf-8").splitlines()
    row_index = next(i for i, line in enumerate(lines) if line.startswith("| P1 "))
    cells = lines[row_index][1:-1].split("|")
    cells[column] = f" {replacement} "
    lines[row_index] = "|" + "|".join(cells) + "|"
    ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")

    _checked, problems = wincreator.verify_ledger_references(str(ledger))
    assert problems


@pytest.mark.parametrize("target", ["attestation", "stdout", "stderr"])
def test_verify_rejects_tampered_capture_artifact(wincreator, ledger, tmp_path, target):
    _attestation, path = reviewed_capture(wincreator, ledger, tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if target == "attestation":
        data["payload"]["capture"]["exit_code"] = 42
        path.write_text(json.dumps(data), encoding="utf-8")
    else:
        artifact = wincreator._resolve_recorded_path(
            data["payload"][target]["path"], str(path)
        )
        Path(artifact).write_text("tampered", encoding="utf-8")

    ok, problems = wincreator.verify_attestation(str(path))
    assert not ok
    assert problems


def test_verify_rejects_tampered_evidence_file(wincreator, ledger, tmp_path):
    artifact = tmp_path / "report.ifc"
    artifact.write_bytes(b"original")
    _attestation, path, _code = prove(wincreator, ledger, tmp_path, files=[str(artifact)])
    artifact.write_bytes(b"changed")
    ok, problems = wincreator.verify_attestation(str(path))
    assert not ok
    assert any("changed" in problem for problem in problems)


def test_verify_rejects_manual_status_change_after_capture(wincreator, ledger, tmp_path):
    _attestation, _path, _code = prove(wincreator, ledger, tmp_path)
    wincreator.update_ledger(str(ledger), "P1", "EVIDENCED", "manual pass")
    _checked, problems = wincreator.verify_ledger_references(str(ledger))
    assert any("review" in problem.lower() or "status" in problem.lower() for problem in problems)


def test_verify_enforces_schema_even_with_recomputed_digest(wincreator, ledger, tmp_path):
    _attestation, path, _code = prove(wincreator, ledger, tmp_path)
    path = Path(path)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["payload"]["unauthorized_field"] = "must fail schema"
    document["digest"]["value"] = wincreator.canonical_digest(document["payload"])
    path.write_text(json.dumps(document), encoding="utf-8")

    ok, problems = wincreator.verify_attestation(str(path))
    assert not ok
    assert any("schema-invalid" in problem for problem in problems)


def test_verify_cli_rejects_ledger_with_zero_capture_targets(wincreator, ledger, tmp_path, capsys):
    code = wincreator.main([
        "verify",
        "--ledger",
        str(ledger),
        "--attest-dir",
        str(tmp_path / "empty-attestations"),
    ])
    output = capsys.readouterr().out
    assert code == 1
    assert "no capture attestation references" in output
    assert "VERIFY OK" not in output


def test_capture_bundle_remains_verifiable_after_relocation(
    wincreator, ledger, tmp_path
):
    source = tmp_path / "source"
    source.mkdir()
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    bundled_ledger = bundle / "PROOF_LEDGER.md"
    bundled_ledger.write_text(ledger.read_text(encoding="utf-8"), encoding="utf-8")

    _attestation, path, code = wincreator.run_and_attest(
        "P1",
        ["python3", "-c", "print('portable capture')"],
        ledger=str(bundled_ledger),
        attest_dir=str(bundle / "attestations"),
        cwd=str(source),
        quiet=True,
        tier="standard",
    )
    assert code == 0
    wincreator.review_attestation(
        path,
        verdict="EVIDENCED",
        reviewer="portable-skeptic",
        ledger=str(bundled_ledger),
    )
    relative_attestation = Path(path).relative_to(bundle)

    relocated = tmp_path / "downloaded-bundle"
    shutil.move(str(bundle), relocated)
    relocated_attestation = relocated / relative_attestation
    document = json.loads(relocated_attestation.read_text(encoding="utf-8"))
    assert not Path(document["payload"]["stdout"]["path"]).is_absolute()
    assert not Path(document["payload"]["stderr"]["path"]).is_absolute()
    assert not Path(document["payload"]["ledger"]).is_absolute()
    review = json.loads(
        (relocated_attestation.parent / "review.json").read_text(encoding="utf-8")
    )
    assert not Path(review["payload"]["capture_path"]).is_absolute()

    ok, problems = wincreator.verify_attestation(str(relocated_attestation))
    assert ok, problems
    checked, problems = wincreator.verify_ledger_references(
        str(relocated / "PROOF_LEDGER.md")
    )
    assert checked == 1
    assert problems == []
