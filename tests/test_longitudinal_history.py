import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys

from conftest import make_challenge_packet


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
    first_packet = make_challenge_packet(wincreator, _a1, first)
    wincreator.review_attestation(first, "INSUFFICIENT", "skeptic", str(ledger), challenge="test falsification challenge", challenge_packet=str(first_packet))

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
    latest_packet = make_challenge_packet(wincreator, _a3, latest)
    wincreator.review_attestation(latest, "EVIDENCED", "skeptic", str(ledger), challenge="test falsification challenge", challenge_packet=str(latest_packet))

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
    first_packet = make_challenge_packet(wincreator, _a1, first)
    wincreator.review_attestation(first, "INSUFFICIENT", "skeptic", str(ledger), challenge="test falsification challenge", challenge_packet=str(first_packet))

    gate.write_text("print('latest')\n", encoding="utf-8")
    _a2, latest, _code = wincreator.run_and_attest(
        "P1", [sys.executable, str(gate)], ledger=str(ledger),
        attest_dir=str(attest_dir), cwd=str(tmp_path), quiet=True, tier="standard"
    )
    latest_packet = make_challenge_packet(wincreator, _a2, latest)
    wincreator.review_attestation(latest, "EVIDENCED", "skeptic", str(ledger), challenge="test falsification challenge", challenge_packet=str(latest_packet))

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
    first_packet = make_challenge_packet(wincreator, _a1, first)
    wincreator.review_attestation(first, "EVIDENCED", "skeptic", str(ledger), challenge="test falsification challenge", challenge_packet=str(first_packet))

    gate.write_text("print('new run')\n", encoding="utf-8")
    wincreator.run_and_attest(
        "P1", [sys.executable, str(gate)], ledger=str(ledger),
        attest_dir=str(attest_dir), cwd=str(tmp_path), quiet=True, tier="standard"
    )

    checked, problems = wincreator.verify_ledger_references(str(ledger))
    assert checked == 2
    assert any("current proof integrity is valid but the claim is not evidenced" in p for p in problems)


def test_verify_tracks_ledger_evidence_when_overlapping_captures_finish_out_of_start_order(wincreator, tmp_path):
    ledger = tmp_path / "PROOF_LEDGER.md"
    attest_dir = tmp_path / ".wincreator" / "attestations"
    _ledger(ledger)

    started = tmp_path / "slow-started"
    release = tmp_path / "release-slow"
    slow = [
        sys.executable, "-c",
        (
            "from pathlib import Path; import time; "
            "Path('slow-started').write_text('started'); "
            "deadline=time.monotonic()+5; "
            "release=Path('release-slow'); "
            "exec(\"while not release.exists():\\n"
            "    assert time.monotonic() < deadline, 'release timeout'\\n"
            "    time.sleep(0.01)\"); "
            "time.sleep(0.2); print('slow')"
        ),
    ]
    fast = [
        sys.executable, "-c",
        "from pathlib import Path; Path('release-slow').write_text('go'); print('fast')",
    ]

    def capture(command):
        return wincreator.run_and_attest(
            "P1", command, ledger=str(ledger), attest_dir=str(attest_dir),
            cwd=str(tmp_path), quiet=True, tier="lite", auto_approve_lite=True,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        slow_future = pool.submit(capture, slow)
        # Synchronize on the slow child actually starting. run_and_attest takes
        # its claim-state snapshot before spawning the child, so this proves the
        # slow capture owns the older snapshot without relying on scheduler timing.
        import time
        deadline = time.monotonic() + 5
        while not started.exists():
            assert time.monotonic() < deadline, "slow gate did not start"
            time.sleep(0.01)
        fast_future = pool.submit(capture, fast)
        fast_future.result()
        try:
            slow_future.result()
        except RuntimeError as error:
            assert "stale result not applied" in str(error)
        else:
            raise AssertionError("older overlapping capture was allowed to overwrite newer proof state")

    current = wincreator.read_claim(str(ledger), "P1")
    assert current["status"] == "EVIDENCED"
    checked, problems = wincreator.verify_ledger_references(str(ledger))
    assert checked == 1
    assert problems == []


def test_verify_rejects_manual_rollback_to_older_evidenced_chain(wincreator, tmp_path):
    ledger = tmp_path / "PROOF_LEDGER.md"
    gate = tmp_path / "test.py"
    attest_dir = tmp_path / ".wincreator" / "attestations"
    _ledger(ledger)

    gate.write_text("print('first pass')\n", encoding="utf-8")
    _a1, first, code = wincreator.run_and_attest(
        "P1", [sys.executable, str(gate)], ledger=str(ledger),
        attest_dir=str(attest_dir), cwd=str(tmp_path), quiet=True, tier="standard"
    )
    assert code == 0
    first_packet = make_challenge_packet(wincreator, _a1, first)
    wincreator.review_attestation(first, "EVIDENCED", "skeptic", str(ledger), challenge="test falsification challenge", challenge_packet=str(first_packet))
    older = wincreator.read_claim(str(ledger), "P1")

    gate.write_text("raise SystemExit(1)\n", encoding="utf-8")
    _a2, _second, code = wincreator.run_and_attest(
        "P1", [sys.executable, str(gate)], ledger=str(ledger),
        attest_dir=str(attest_dir), cwd=str(tmp_path), quiet=True, tier="standard"
    )
    assert code != 0
    assert wincreator.read_claim(str(ledger), "P1")["status"] == "DISPROVEN"

    # Simulate an agent trying to resurrect a previously valid proof after a
    # newer failed attempt by copying the old status/evidence back into ledger.
    wincreator.update_ledger(str(ledger), "P1", "EVIDENCED", older["evidence"])

    checked, problems = wincreator.verify_ledger_references(str(ledger))
    assert checked == 2
    assert any("older proof chain" in problem for problem in problems)
