import importlib.util
from pathlib import Path
import sys


def load_quick(repo_root):
    script_dir = repo_root / "skill" / "wincreator" / "scripts"
    sys.path.insert(0, str(script_dir))
    try:
        spec = importlib.util.spec_from_file_location("quick_prove", script_dir / "quick_prove.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(script_dir))


def test_quick_lite_creates_evidenced_claim(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    quick = load_quick(repo_root)
    ledger = tmp_path / ".wincreator" / "PROOF_LEDGER.md"
    attest = tmp_path / ".wincreator" / "attestations"

    code = quick.main([
        "python executes successfully",
        "--ledger", str(ledger),
        "--attest-dir", str(attest),
        "--",
        sys.executable, "-c", "print('ok')",
    ])

    assert code == 0
    text = ledger.read_text(encoding="utf-8")
    assert "python executes successfully" in text
    assert "EVIDENCED" in text
    assert "CLAIMED" not in text.splitlines()[-1]
    assert list(attest.rglob("attestation.json"))
    assert list(attest.rglob("review.json"))


def test_quick_standard_stops_at_pending(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    quick = load_quick(repo_root)
    ledger = tmp_path / ".wincreator" / "PROOF_LEDGER.md"
    attest = tmp_path / ".wincreator" / "attestations"

    code = quick.main([
        "python executes successfully",
        "--tier", "standard",
        "--ledger", str(ledger),
        "--attest-dir", str(attest),
        "--",
        sys.executable, "-c", "print('ok')",
    ])

    assert code == 0
    assert "PENDING" in ledger.read_text(encoding="utf-8")
    assert not list(attest.rglob("review.json"))


def test_quick_initializes_precreated_empty_ledger(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    quick = load_quick(repo_root)
    ledger = tmp_path / ".wincreator" / "PROOF_LEDGER.md"
    ledger.parent.mkdir(parents=True)
    ledger.touch()
    attest = tmp_path / ".wincreator" / "attestations"

    code = quick.main([
        "empty ledger is initialized",
        "--ledger", str(ledger),
        "--attest-dir", str(attest),
        "--",
        sys.executable, "-c", "print('ok')",
    ])

    assert code == 0
    text = ledger.read_text(encoding="utf-8")
    assert "| ID | Level | Claim | Gate (what proves it) | Status | Evidence |" in text
    assert "empty ledger is initialized" in text
    assert "EVIDENCED" in text


def test_quick_standard_capture_verifies_from_the_project_directory(tmp_path, monkeypatch, capsys):
    """Regression: the default quick ledger lives in .wincreator/, not in the cwd.

    Capture evidence used to be written relative to the cwd while `verify`
    re-derived it relative to the ledger, so every un-reviewed quick capture was
    reported as an unidentifiable proof chain instead of an honest PENDING.
    """
    repo_root = Path(__file__).resolve().parents[1]
    quick = load_quick(repo_root)
    monkeypatch.chdir(tmp_path)

    code = quick.main([
        "python executes successfully",
        "--tier", "standard",
        "--",
        sys.executable, "-c", "print('ok')",
    ])
    assert code == 0
    printed = capsys.readouterr().out
    assert "challenge_packet.py" in printed and "--challenge-packet" in printed

    import wincreator
    checked, problems = wincreator.verify_ledger_references(
        str(Path.cwd() / ".wincreator" / "PROOF_LEDGER.md")
    )
    assert checked == 1
    assert len(problems) == 1 and "is PENDING" in problems[0], problems


def test_quick_failing_gate_verifies_as_disproven(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    quick = load_quick(repo_root)
    monkeypatch.chdir(tmp_path)

    code = quick.main([
        "python exits zero",
        "--",
        sys.executable, "-c", "raise SystemExit(3)",
    ])
    assert code == 3

    import wincreator
    _checked, problems = wincreator.verify_ledger_references(
        str(Path.cwd() / ".wincreator" / "PROOF_LEDGER.md")
    )
    assert len(problems) == 1 and "is DISPROVEN" in problems[0], problems
