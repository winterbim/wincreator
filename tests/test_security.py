import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import prove


def test_gate_cannot_read_signing_key(wincreator, ledger, tmp_path, monkeypatch):
    monkeypatch.setenv("WINCREATOR_SIGNING_KEY", "top-secret-signing-key")
    attestation, _path, code = prove(
        wincreator,
        ledger,
        tmp_path,
        command=[
            sys.executable,
            "-c",
            "import os,sys; sys.exit(9 if os.getenv('WINCREATOR_SIGNING_KEY') else 0)",
        ],
    )
    assert code == 0
    assert attestation["payload"]["capture"]["status"] == "CAPTURED_PASS"
    assert "signature" in attestation


def test_regulated_capture_rejects_dirty_tree_before_gate(wincreator, ledger, clean_git_repo, tmp_path):
    ledger_path = clean_git_repo / "PROOF_LEDGER.md"
    ledger_path.write_text(ledger.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run(["git", "add", "PROOF_LEDGER.md"], cwd=clean_git_repo, check=True)
    subprocess.run(["git", "commit", "-qm", "ledger"], cwd=clean_git_repo, check=True)
    (clean_git_repo / "dirty.txt").write_text("dirty", encoding="utf-8")
    marker = clean_git_repo / "gate-ran"

    with pytest.raises(ValueError, match="clean Git tree"):
        wincreator.run_and_attest(
            "P1",
            [sys.executable, "-c", f"open({str(marker)!r}, 'w').write('ran')"],
            ledger=str(ledger_path),
            attest_dir=str(tmp_path / "attestations"),
            cwd=str(clean_git_repo),
            quiet=True,
            tier="regulated",
            builder="builder-01",
        )
    assert not marker.exists()


def test_allow_dirty_is_recorded_for_standard(wincreator, ledger, tmp_path):
    attestation, _path, _code = prove(
        wincreator, ledger, tmp_path, allow_dirty=True, tier="standard"
    )
    assert attestation["payload"]["policy"]["dirty_override"] is True


def test_private_capture_is_marked_and_uses_private_directory(wincreator, ledger, tmp_path):
    attestation, path, _code = prove(wincreator, ledger, tmp_path, private=True)
    assert attestation["payload"]["policy"]["private"] is True
    assert "private" in str(path)
