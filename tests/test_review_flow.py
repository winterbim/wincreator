import json
from pathlib import Path
import sys

import pytest

from conftest import make_challenge_packet, prove


def test_review_evidenced_links_capture_and_updates_ledger(wincreator, ledger, tmp_path):
    attestation, path, _code = prove(wincreator, ledger, tmp_path, builder="builder-01")

    packet = make_challenge_packet(wincreator, attestation, path)
    review, review_path = wincreator.review_attestation(
        str(path),
        verdict="EVIDENCED",
        reviewer="skeptic-01", challenge="test falsification challenge",
        challenge_packet=str(packet),
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
            str(path), verdict="EVIDENCED", reviewer="skeptic-01", challenge="test falsification challenge", ledger=str(ledger)
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
            str(path), verdict="EVIDENCED", reviewer="same-person", challenge="test falsification challenge", ledger=str(ledger_path)
        )


def test_insufficient_review_blocks_completion(wincreator, ledger_check, ledger, tmp_path):
    attestation, path, _code = prove(wincreator, ledger, tmp_path)
    packet = make_challenge_packet(wincreator, attestation, path)
    wincreator.review_attestation(
        str(path), verdict="INSUFFICIENT", reviewer="skeptic-01", challenge="test falsification challenge", challenge_packet=str(packet), ledger=str(ledger)
    )
    assert wincreator.read_claim(str(ledger), "P1")["status"] == "INSUFFICIENT"
    _checked, problems = wincreator.verify_ledger_references(str(ledger))
    assert any("not evidenced" in problem for problem in problems)
    assert ledger_check.check(str(ledger)) == 1


def test_cli_marks_automated_review_explicitly(wincreator, ledger, tmp_path):
    attestation, path, _code = prove(wincreator, ledger, tmp_path)
    packet = make_challenge_packet(wincreator, attestation, path)
    code = wincreator.main([
        "review",
        "P1",
        "--attestation",
        str(path),
        "--ledger",
        str(ledger),
        "--verdict",
        "evidenced",
        "--reviewer",
        "ci-skeptic",
        "--challenge",
        "attack whether the release gate covers the claimed behavior",
        "--challenge-packet",
        str(packet),
        "--automatic",
    ])
    review = json.loads((Path(path).parent / "review.json").read_text(encoding="utf-8"))
    assert code == 0
    assert review["payload"]["automatic"] is True


def test_cli_rejects_capture_from_different_claim(wincreator, ledger, tmp_path):
    _attestation, path, _code = prove(wincreator, ledger, tmp_path)
    code = wincreator.main([
        "review",
        "P2",
        "--attestation",
        str(path),
        "--ledger",
        str(ledger),
        "--verdict",
        "evidenced",
        "--reviewer",
        "skeptic-02",
    ])
    assert code == 2
    assert not (Path(path).parent / "review.json").exists()
    assert wincreator.read_claim(str(ledger), "P1")["status"] == "PENDING"


def test_standard_builder_cannot_review_own_capture(wincreator, ledger, tmp_path):
    _attestation, path, _code = prove(
        wincreator,
        ledger,
        tmp_path,
        builder="same-person",
    )
    with pytest.raises(ValueError, match="must differ"):
        wincreator.review_attestation(
            str(path),
            verdict="EVIDENCED",
            reviewer="same-person", challenge="test falsification challenge",
            ledger=str(ledger),
        )


def test_review_is_immutable_once_written(wincreator, ledger, tmp_path):
    attestation, path, _code = prove(wincreator, ledger, tmp_path)
    packet = make_challenge_packet(wincreator, attestation, path)
    wincreator.review_attestation(
        str(path), verdict="EVIDENCED", reviewer="skeptic-01", challenge="test falsification challenge", challenge_packet=str(packet), ledger=str(ledger)
    )
    with pytest.raises(FileExistsError, match="immutable review"):
        wincreator.review_attestation(
            str(path), verdict="DISPROVEN", reviewer="skeptic-02", challenge="test falsification challenge", challenge_packet=str(packet), ledger=str(ledger)
        )


def test_review_schema_rejects_recomputed_unknown_fields(wincreator, ledger, tmp_path):
    attestation, path, _code = prove(wincreator, ledger, tmp_path)
    packet = make_challenge_packet(wincreator, attestation, path)
    _review, review_path = wincreator.review_attestation(
        str(path), verdict="EVIDENCED", reviewer="skeptic-01", challenge="test falsification challenge", challenge_packet=str(packet), ledger=str(ledger)
    )
    review_path = Path(review_path)
    document = json.loads(review_path.read_text(encoding="utf-8"))
    document["payload"]["unauthorized_field"] = "forged"
    document["digest"]["value"] = wincreator.canonical_digest(document["payload"])
    review_path.write_text(json.dumps(document), encoding="utf-8")

    ok, problems = wincreator.verify_review(str(review_path), str(path))
    assert not ok
    assert any("schema-invalid" in problem for problem in problems)


def test_standard_review_requires_explicit_challenge(wincreator, ledger, tmp_path):
    _attestation, path, _code = prove(wincreator, ledger, tmp_path)
    with pytest.raises(ValueError, match="review challenge must be non-empty"):
        wincreator.review_attestation(
            str(path),
            verdict="EVIDENCED",
            reviewer="skeptic-01",
            ledger=str(ledger),
        )


def test_review_v3_binds_blind_packet_and_older_reviews_remain_verifiable(wincreator, ledger, tmp_path):
    attestation, path, _code = prove(wincreator, ledger, tmp_path)
    packet = make_challenge_packet(wincreator, attestation, path)
    challenge = "attempted to falsify the claim by checking the unexercised error path"
    review, review_path = wincreator.review_attestation(
        str(path),
        verdict="EVIDENCED",
        reviewer="skeptic-01",
        challenge=challenge,
        challenge_packet=str(packet),
        ledger=str(ledger),
    )
    assert review["schema"] == "wincreator.review/v3"
    assert review["payload"]["challenge"] == challenge
    assert review["payload"]["challenge_packet"]["digest"]
    ok, problems = wincreator.verify_review(review_path, str(path))
    assert ok, problems

    v2 = json.loads(Path(review_path).read_text(encoding="utf-8"))
    v2["schema"] = "wincreator.review/v2"
    v2["payload"].pop("challenge_packet")
    v2["digest"]["value"] = wincreator.canonical_digest(v2["payload"])
    v2_path = tmp_path / "review-v2.json"
    v2_path.write_text(json.dumps(v2), encoding="utf-8")
    ok, problems = wincreator.verify_review(str(v2_path), str(path))
    assert ok, problems

    v1 = json.loads(v2_path.read_text(encoding="utf-8"))
    v1["schema"] = "wincreator.review/v1"
    v1["payload"].pop("challenge")
    v1["digest"]["value"] = wincreator.canonical_digest(v1["payload"])
    v1_path = tmp_path / "review-v1.json"
    v1_path.write_text(json.dumps(v1), encoding="utf-8")
    ok, problems = wincreator.verify_review(str(v1_path), str(path))
    assert ok, problems


def test_standard_review_rejects_missing_or_tampered_blind_packet(wincreator, ledger, tmp_path):
    attestation, path, _code = prove(wincreator, ledger, tmp_path)
    with pytest.raises(ValueError, match="requires --challenge-packet"):
        wincreator.review_attestation(
            str(path),
            verdict="EVIDENCED",
            reviewer="skeptic-01",
            challenge="attack the evidence",
            ledger=str(ledger),
        )

    packet = make_challenge_packet(wincreator, attestation, path)
    document = json.loads(packet.read_text(encoding="utf-8"))
    document["payload"]["capture"]["status"] = "CAPTURED_FAIL"
    packet.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="digest mismatch"):
        wincreator.review_attestation(
            str(path),
            verdict="EVIDENCED",
            reviewer="skeptic-01",
            challenge="attack the evidence",
            challenge_packet=str(packet),
            ledger=str(ledger),
        )
