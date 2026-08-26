import json
from pathlib import Path
import sys


def _ledger(path):
    path.write_text(
        "| ID | Level | Claim | Gate (what proves it) | Status | Evidence |\n"
        "|----|-------|-------|------------------------|--------|----------|\n"
        "| P1 | Micro | all emails are normalized | `python test.py` | CLAIMED | |\n",
        encoding="utf-8",
    )


def test_verify_accepts_historical_failed_attempts_before_latest_evidence(wincreator, tmp_path):
    ledger = tmp_path / "PROOF_LEDGER.md"
    gate = tmp_path / "test.py"
    attest_dir = tmp_path / ".wincreator" / "attestations"
    _ledger(ledger)

    gate.write_text("print('green but incomplete')\n", encoding="utf-8")
    _a1, first, code = wincreator.run_and_attest(
        "P1", [sys.executable, str(gate)], ledger=str(ledger),
        attest_dir=str(attest_dir), cwd=str(tmp_path), quiet=True, tier="standard"
    )
    assert code == 0
    wincreator.review_attestation(first, "INSUFFICIENT", "skeptic", str(ledger))

    gate.write_text("raise SystemExit(1)\n", encoding="utf-8")
    _a2, _second, code = wincreator.run_and_attest(
        "P1", [sys.executable, str(gate)], ledger=str(ledger),
        attest_dir=str(attest_dir), cwd=str(tmp_path), quiet=True, tier="standard"
    )
    assert code != 0

    gate.write_text("print('fixed')\n", encoding="utf-8")
    _a3, latest, code = wincreator.run_and_attest(
        "P1", [sys.executable, str(gate)], ledger=str(ledger),
        attest_dir=str(attest_dir), cwd=str(tmp_path), quiet=True, tier="standard"
    )
    assert code == 0
    wincreator.review_attestation(latest, "EVIDENCED", "skeptic", str(ledger))

    checked, problems = wincreator.verify_ledger_references(str(ledger))
    assert checked == 3
    assert problems == []


def test_verify_still_rejects_tampered_historical_capture(wincreator, tmp_path):
    ledger = tmp_path / "PROOF_LEDGER.md"
    gate = tmp_path / "test.py"
    attest_dir = tmp_path / ".wincreator" / "attestations"
    _ledger(ledger)

    gate.write_text("print('first')\n", encoding="utf-8")
    _a1, first, _code = wincreator.run_and_attest(
        "P1", [sys.executable, str(gate)], ledger=str(ledger),
        attest_dir=str(attest_dir), cwd=str(tmp_path), quiet=True, tier="standard"
    )
    wincreator.review_attestation(first, "INSUFFICIENT", "skeptic", str(ledger))

    gate.write_text("print('latest')\n", encoding="utf-8")
    _a2, latest, _code = wincreator.run_and_attest(
        "P1", [sys.executable, str(gate)], ledger=str(ledger),
        attest_dir=str(attest_dir), cwd=str(tmp_path), quiet=True, tier="standard"
    )
    wincreator.review_attestation(latest, "EVIDENCED", "skeptic", str(ledger))

    historical = Path(first)
    document = json.loads(historical.read_text(encoding="utf-8"))
    document["payload"]["tool_version"] = "tampered-version"
    historical.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    checked, problems = wincreator.verify_ledger_references(str(ledger))
    assert checked == 2
    assert any("digest mismatch" in problem for problem in problems)


def test_verify_uses_latest_unreviewed_state_not_older_evidence(wincreator, tmp_path):
    ledger = tmp_path / "PROOF_LEDGER.md"
    gate = tmp_path / "test.py"
    attest_dir = tmp_path / ".wincreator" / "attestations"
    _ledger(ledger)

    gate.write_text("print('first')\n", encoding="utf-8")
    _a1, first, _code = wincreator.run_and_attest(
        "P1", [sys.executable, str(gate)], ledger=str(ledger),
        attest_dir=str(attest_dir), cwd=str(tmp_path), quiet=True, tier="standard"
    )
    wincreator.review_attestation(first, "EVIDENCED", "skeptic", str(ledger))

    gate.write_text("print('new run')\n", encoding="utf-8")
    wincreator.run_and_attest(
        "P1", [sys.executable, str(gate)], ledger=str(ledger),
        attest_dir=str(attest_dir), cwd=str(tmp_path), quiet=True, tier="standard"
    )

    checked, problems = wincreator.verify_ledger_references(str(ledger))
    assert checked == 2
    assert any("latest capture integrity is valid but the claim is not evidenced" in p for p in problems)
