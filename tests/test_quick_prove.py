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
