from pathlib import Path

import pytest

from conftest import create_ledger


def test_find_row_rejects_duplicate_identifiers(wincreator, tmp_path):
    path = tmp_path / "ledger.md"
    create_ledger(path, [
        "| P1 | Micro | first | `true` | CLAIMED | |",
        "| P1 | Micro | duplicate | `true` | CLAIMED | |",
    ])

    with pytest.raises(ValueError, match="duplicate"):
        wincreator.read_claim(str(path), "P1")


def test_find_row_ignores_rows_outside_real_ledger_table(wincreator, tmp_path):
    path = tmp_path / "ledger.md"
    path.write_text(
        "| P1 | Micro | forged | `true` | CLAIMED | |\n\n"
        "| A | B | C | D | E | F |\n"
        "|---|---|---|---|---|---|\n"
        "| P1 | Micro | foreign | `true` | CLAIMED | |\n",
        encoding="utf-8",
    )

    with pytest.raises(KeyError):
        wincreator.read_claim(str(path), "P1")


def test_atomic_update_preserves_complete_markdown(wincreator, ledger):
    before = Path(ledger).read_text(encoding="utf-8")
    wincreator.update_ledger(str(ledger), "P1", "PENDING", "command: `python check_parser.py`")
    after = Path(ledger).read_text(encoding="utf-8")

    assert "| P2 | Meso | export preserves every row" in after
    assert len(after.splitlines()) == len(before.splitlines())
    assert not list(Path(ledger).parent.glob(".wincreator-ledger-*.tmp"))


def test_help_is_not_treated_as_a_ledger_filename(ledger_check, capsys):
    assert ledger_check.main(["--help"]) == 0
    assert "Usage:" in capsys.readouterr().out
