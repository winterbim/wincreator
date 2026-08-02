import json
import sys

import pytest

from conftest import prove


def test_review_evidenced_links_capture_and_updates_ledger(wincreator, ledger, tmp_path):
    attestation, path, _code = prove(wincreator, ledger, tmp_path, builder="builder-01")

    review, review_path = wincreator.review_attestation(
        str(path),
        verdict="EVIDENCED",
        reviewer="skeptic-01",
        ledger=str(ledger),
    )

    assert review["payload"]["capture_digest"] == attestation["digest"]["value"]
    assert review["payload"]["reviewer"] == "skeptic-01"
    assert review_path.endswith("review.json")
    assert wincreator.read_claim(str(ledger), "P1")["status"] == "EVIDENCED"


def test_captured_fail_cannot_be_reviewed_as_evidenced(wincreator, ledger, tmp_path):
    _attestation, path, _code = prove(
        wincreator,
        ledger,
        tmp_path,
        command=[sys.executable, "-c", "import sys; sys.exit(1)"],
    )

    with pytest.raises(ValueError, match="CAPTURED_FAIL"):
        wincreator.review_attestation(
            str(path), verdict="EVIDENCED", reviewer="skeptic-01", ledger=str(ledger)
        )


def test_regulated_builder_cannot_review_own_capture(wincreator, ledger, tmp_path, clean_git_repo):
    ledger_path = clean_git_repo / "PROOF_LEDGER.md"
    ledger_path.write_text(ledger.read_text(encoding="utf-8"), encoding="utf-8")
    import subprocess
    subprocess.run(["git", "add", "PROOF_LEDGER.md"], cwd=clean_git_repo, check=True)
    subprocess.run(["git", "commit", "-qm", "ledger"], cwd=clean_git_repo, check=True)
    attestation, path, _code = wincreator.run_and_attest(
        "P1",
        [sys.executable, "-c", "print('ok')"],
        ledger=str(ledger_path),
        attest_dir=str(tmp_path / "attestations"),
        cwd=str(clean_git_repo),
        quiet=True,
        tier="regulated",
        builder="same-person",
    )

    with pytest.raises(ValueError, match="must differ"):
        wincreator.review_attestation(
            str(path), verdict="EVIDENCED", reviewer="same-person", ledger=str(ledger_path)
        )


def test_insufficient_review_blocks_completion(wincreator, ledger_check, ledger, tmp_path):
    _attestation, path, _code = prove(wincreator, ledger, tmp_path)
    wincreator.review_attestation(
        str(path), verdict="INSUFFICIENT", reviewer="skeptic-01", ledger=str(ledger)
    )
    assert wincreator.read_claim(str(ledger), "P1")["status"] == "INSUFFICIENT"
    _checked, problems = wincreator.verify_ledger_references(str(ledger))
    assert any("not evidenced" in problem for problem in problems)
    assert ledger_check.check(str(ledger)) == 1
