import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import launch_digest


def test_packet_contains_checklist_and_rules():
    text = launch_digest.build_packet("v9.9.9-test", ROOT)
    assert "v9.9.9-test" in text
    assert "npx skills add winterbim/wincreator" in text
    for name, _, _ in launch_digest.CHECKLIST:
        assert name in text
    assert "ON/OFF" in text
    assert "human approval" in text


def test_packet_reports_missing_draft(tmp_path):
    text = launch_digest.build_packet("v9.9.9-test", tmp_path)
    assert "DRAFT MISSING" in text


def test_cli_writes_output(tmp_path, capsys):
    out = tmp_path / "packet" / "digest.md"
    rc = launch_digest.main(["--tag", "v0.0.0", "--out", str(out), "--root", str(ROOT)])
    assert rc == 0
    assert out.is_file()
    assert "launch packet written" in capsys.readouterr().out
