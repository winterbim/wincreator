"""Done Gate: the stop hook, the CLI gate and the plugin/Action wiring."""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skill" / "wincreator" / "scripts" / "done_gate.py"
HEADER = (
    "| ID | Level | Claim | Gate (what proves it) | Status | Evidence |\n"
    "|----|-------|-------|------------------------|--------|----------|\n"
)
CLAIMED = "| P1 | Micro | parser rejects malformed input | `pytest -q` | CLAIMED | |\n"
EVIDENCED = (
    "| P1 | Micro | parser rejects malformed input | `pytest -q` | EVIDENCED | "
    "run 2026-01-01: `pytest -q` -> exit=0, 12 passed |\n"
)


def run_gate(args, cwd, stdin="", env=None):
    environment = {
        k: v for k, v in os.environ.items()
        if not k.startswith("WINCREATOR_") and k != "CLAUDE_PROJECT_DIR"
    }
    environment.update(env or {})
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd, input=stdin, capture_output=True, text=True, env=environment,
    )


def test_embedded_self_test_passes(tmp_path):
    result = run_gate(["--self-test"], tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_cli_blocks_on_claimed_and_opens_on_evidenced(tmp_path):
    ledger = tmp_path / "PROOF_LEDGER.md"
    ledger.write_text(HEADER + CLAIMED, encoding="utf-8")
    blocked = run_gate([], tmp_path)
    assert blocked.returncode == 1
    assert "DONE GATE: BLOCKED" in blocked.stdout and "[P1]" in blocked.stdout

    ledger.write_text(HEADER + EVIDENCED, encoding="utf-8")
    opened = run_gate([], tmp_path)
    assert opened.returncode == 0
    assert "DONE GATE: OPEN" in opened.stdout


def test_cli_without_ledger_passes_unless_required(tmp_path):
    assert run_gate([], tmp_path).returncode == 0
    assert run_gate(["--require-ledger"], tmp_path).returncode == 1


def test_summary_file_is_appended_as_markdown(tmp_path):
    (tmp_path / "PROOF_LEDGER.md").write_text(HEADER + CLAIMED, encoding="utf-8")
    summary = tmp_path / "summary.md"
    summary.write_text("existing\n", encoding="utf-8")
    run_gate(["--summary", str(summary)], tmp_path)
    text = summary.read_text(encoding="utf-8")
    assert text.startswith("existing\n")
    assert "## WinCreator Done Gate" in text and "**BLOCKED**" in text


def test_hook_blocks_once_then_never_loops(tmp_path):
    (tmp_path / "PROOF_LEDGER.md").write_text(HEADER + CLAIMED, encoding="utf-8")
    first = run_gate(["--hook"], tmp_path, json.dumps({"cwd": str(tmp_path), "stop_hook_active": False}))
    assert first.returncode == 0
    decision = json.loads(first.stdout)
    assert decision["decision"] == "block"
    assert "P1" in decision["reason"] and "WAIVED" in decision["reason"]

    second = run_gate(["--hook"], tmp_path, json.dumps({"cwd": str(tmp_path), "stop_hook_active": True}))
    assert second.returncode == 0 and second.stdout.strip() == ""


def test_hook_is_silent_without_ledger_and_when_switched_off(tmp_path):
    payload = json.dumps({"cwd": str(tmp_path)})
    assert run_gate(["--hook"], tmp_path, payload).stdout.strip() == ""
    (tmp_path / "PROOF_LEDGER.md").write_text(HEADER + CLAIMED, encoding="utf-8")
    off = run_gate(["--hook"], tmp_path, payload, env={"WINCREATOR_DONE_GATE": "off"})
    assert off.returncode == 0 and off.stdout.strip() == ""


def test_hook_uses_payload_cwd_not_process_cwd(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "PROOF_LEDGER.md").write_text(HEADER + CLAIMED, encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    result = run_gate(["--hook"], elsewhere, json.dumps({"cwd": str(project)}))
    assert json.loads(result.stdout)["decision"] == "block"


def test_plugin_and_action_point_at_the_shipped_script():
    hooks = json.loads((REPO / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    command = hooks["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert "skill/wincreator/scripts/done_gate.py --hook" in command
    assert "${CLAUDE_PLUGIN_ROOT}" in command

    plugin = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert plugin["name"] == "wincreator"
    for skills_dir in plugin["skills"]:
        assert (REPO / skills_dir / "wincreator" / "SKILL.md").is_file()

    marketplace = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert [entry["name"] for entry in marketplace["plugins"]] == ["wincreator"]

    action = (REPO / "action.yml").read_text(encoding="utf-8")
    assert "skill/wincreator/scripts/done_gate.py" in action
    assert "${{ inputs." not in action.split("run: |", 1)[1], "inputs must reach bash through env, not interpolation"


def test_hook_gates_the_project_root_when_the_agent_stops_in_a_subdirectory(tmp_path):
    (tmp_path / "PROOF_LEDGER.md").write_text(HEADER + CLAIMED, encoding="utf-8")
    subdir = tmp_path / "src"
    subdir.mkdir()
    payload = json.dumps({"cwd": str(subdir)})
    assert run_gate(["--hook"], subdir, payload).stdout.strip() == ""
    rooted = run_gate(["--hook"], subdir, payload, env={"CLAUDE_PROJECT_DIR": str(tmp_path)})
    assert json.loads(rooted.stdout)["decision"] == "block"
