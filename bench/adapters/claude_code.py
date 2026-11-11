#!/usr/bin/env python3
"""Claude Code adapter for WinCreator paired coding benchmarks.

Runs `claude -p` non-interactively in the benchmark workspace with an explicit
model, closed stdin, no session persistence and a fixed tool allow-list. It
never uses `bypassPermissions`: edits are accepted, the listed tools are
allowed, and anything else that would prompt is denied.

Besides provider usage it records what the benchmark needs to interpret a
result honestly:

- which model(s) the provider reports having served;
- whether the ON arm actually opened or executed the WinCreator skill
  (treatment uptake), so "installed but ignored" is not counted as treatment;
- every tool input that names a path outside the workspace, so a run that
  could have read the held-out grader is visible instead of assumed away.

The raw stream-json trace is written next to the metrics file, not to stdout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

METRICS_SCHEMA = "wincreator.bench-agent-metrics/claude-code-v1"
ALLOWED_TOOLS = ("Bash", "Edit", "Write", "Read", "Glob", "Grep")
INSTRUCTION = "Complete the task described in TASK.md in the current directory."
SKILL_MARKER = ".agents/skills/wincreator"
SKILL_SCRIPTS = (
    "quick_prove.py", "wincreator.py", "ledger_check.py", "adequacy_check.py",
    "challenge_packet.py", "distill_check.py", "done_gate.py",
)
ABSOLUTE_PATH = re.compile(r"(?<![\w.~:/-])(/(?:[\w.@+-]+/)*[\w.@+-]+)")
SYSTEM_PREFIXES = ("/usr/", "/bin/", "/dev/", "/proc/", "/tmp/", "/etc/", "/opt/", "/lib", "/sbin/", "/var/")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def build_command(claude_bin, model):
    return [
        claude_bin,
        "-p", INSTRUCTION,
        "--model", model,
        "--output-format", "stream-json",
        "--verbose",
        "--permission-mode", "acceptEdits",
        "--permission-prompts", "none",
        "--allowedTools", *ALLOWED_TOOLS,
        "--no-session-persistence",
        "--strict-mcp-config",
    ]


def _tool_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _tool_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _tool_strings(item)


def outside_paths(tool_input, workspace):
    """Absolute paths named in a tool input that are outside the workspace.

    Interpreter and system locations are ignored; what remains is what could
    reach the benchmark checkout (graders, other runs).
    """
    workspace = str(workspace).rstrip("/")
    found = set()
    for text in _tool_strings(tool_input):
        if "../" in text:
            found.add("<relative parent reference>")
        for match in ABSOLUTE_PATH.findall(text):
            if match == workspace or match.startswith(workspace + "/"):
                continue
            if match.startswith(SYSTEM_PREFIXES) or match.count("/") < 2:
                continue
            found.add(match)
    return sorted(found)


def parse_trace(text, workspace):
    events, parse_errors = [], 0
    for raw in text.splitlines():
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            parse_errors += 1
            continue
        if isinstance(value, dict):
            events.append(value)
        else:
            parse_errors += 1

    tool_calls, tool_names = 0, {}
    skill_reads, skill_executions, outside = set(), set(), set()
    final_text = ""
    for event in events:
        if event.get("type") != "assistant":
            continue
        for block in (event.get("message") or {}).get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                final_text = block.get("text") or final_text
            if block.get("type") != "tool_use":
                continue
            tool_calls += 1
            name = block.get("name") or "?"
            tool_names[name] = tool_names.get(name, 0) + 1
            tool_input = block.get("input") or {}
            strings = list(_tool_strings(tool_input))
            for text_value in strings:
                if SKILL_MARKER not in text_value:
                    continue
                for part in re.findall(rf"{re.escape(SKILL_MARKER)}/[\w./-]+", text_value):
                    relative = part[len(SKILL_MARKER) + 1:]
                    script = os.path.basename(relative)
                    if name == "Bash" and script in SKILL_SCRIPTS and re.search(
                            rf"python[\d.]*\s+(?:-\S+\s+)*\S*{re.escape(script)}", text_value):
                        skill_executions.add(script)
                    else:
                        skill_reads.add(relative)
            outside.update(outside_paths(tool_input, workspace))

    result = next((event for event in reversed(events) if event.get("type") == "result"), {})
    model_usage = result.get("modelUsage") if isinstance(result.get("modelUsage"), dict) else {}
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else None
    return {
        "event_count": len(events),
        "parse_errors": parse_errors,
        "result_subtype": result.get("subtype"),
        "is_error": result.get("is_error"),
        "num_turns": result.get("num_turns"),
        "duration_api_ms": result.get("duration_api_ms"),
        "total_cost_usd": result.get("total_cost_usd"),
        "usage": {
            key: usage.get(key) for key in (
                "input_tokens", "output_tokens",
                "cache_creation_input_tokens", "cache_read_input_tokens",
            )
        } if usage else None,
        "served_models": sorted(model_usage),
        "provider_model_identity": "observed" if model_usage else "unavailable",
        "tool_calls": tool_calls,
        "tool_names": dict(sorted(tool_names.items())),
        "skill_files_read": sorted(skill_reads),
        "skill_scripts_executed": sorted(skill_executions),
        "treatment_uptake": bool(skill_reads or skill_executions),
        "outside_workspace_paths": sorted(outside),
        "final_text_tail": final_text[-1200:],
    }


def claude_version(claude_bin):
    completed = subprocess.run(
        [claude_bin, "--version"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, timeout=30, check=False,
    )
    return (completed.stdout or completed.stderr).strip() or None


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def run(args):
    workspace = Path(os.environ.get("WINCREATOR_BENCH_WORKSPACE", os.getcwd())).resolve()
    metrics_out = os.environ.get("WINCREATOR_BENCH_METRICS_OUT")
    if not metrics_out:
        raise ValueError("WINCREATOR_BENCH_METRICS_OUT is required")
    if not args.model:
        raise ValueError("set --model or WINCREATOR_BENCH_MODEL to one exact model for both arms")
    binary = shutil.which(args.claude_bin)
    if not binary:
        raise ValueError(f"Claude Code executable not found: {args.claude_bin}")

    command = build_command(binary, args.model)
    completed = subprocess.run(
        command, cwd=workspace, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    trace_path = Path(metrics_out).with_name("agent-trace.jsonl")
    trace_path.write_text(completed.stdout, encoding="utf-8")

    parsed = parse_trace(completed.stdout, workspace)
    metrics = {
        "schema": METRICS_SCHEMA,
        "adapter": "claude-code",
        "claude_code_version": claude_version(binary),
        "requested_model": args.model,
        "condition": os.environ.get("WINCREATOR_BENCH_CONDITION"),
        "case": os.environ.get("WINCREATOR_BENCH_CASE"),
        "permission_mode": "acceptEdits",
        "permission_prompts": "none",
        "allowed_tools": list(ALLOWED_TOOLS),
        "session_persistence": False,
        "stdin": "devnull",
        "exit_code": completed.returncode,
        "trace_sha256": sha256_bytes(completed.stdout.encode("utf-8")),
        "stderr_tail": completed.stderr[-1000:],
        **parsed,
    }
    write_json(metrics_out, metrics)
    sys.stdout.write(parsed["final_text_tail"] + "\n")
    return completed.returncode


def self_test():
    command = build_command("claude", "model-x")
    assert command[command.index("--model") + 1] == "model-x"
    assert command[command.index("--permission-mode") + 1] == "acceptEdits"
    assert "bypassPermissions" not in command
    assert "--dangerously-skip-permissions" not in command
    assert "--no-session-persistence" in command

    workspace = "/runs/case/rep-01/on/workspace"
    trace = "\n".join(json.dumps(event) for event in [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Read",
             "input": {"file_path": f"{workspace}/.agents/skills/wincreator/SKILL.md"}},
            {"type": "tool_use", "name": "Bash",
             "input": {"command": "python3 .agents/skills/wincreator/scripts/quick_prove.py 'c' -- python3 t.py"}},
            {"type": "tool_use", "name": "Read", "input": {"file_path": "/repo/bench/cases/x/grader.py"}},
            {"type": "tool_use", "name": "Bash", "input": {"command": "/usr/bin/python3 test_x.py"}},
            {"type": "tool_use", "name": "Bash",
             "input": {"command": "echo https://rates.internal.example/v2/rates/USD"}},
            {"type": "tool_use", "name": "Bash",
             "input": {"command": "cat .agents/skills/wincreator/references/agents.md"}},
            {"type": "text", "text": "done"},
        ]}},
        {"type": "result", "subtype": "success", "num_turns": 4, "total_cost_usd": 0.01,
         "usage": {"input_tokens": 10, "output_tokens": 5},
         "modelUsage": {"served-model": {}}},
    ]) + "\nnot json\n"
    parsed = parse_trace(trace, workspace)
    assert parsed["parse_errors"] == 1
    assert parsed["tool_calls"] == 6
    assert parsed["skill_files_read"] == ["SKILL.md", "references/agents.md"]
    assert parsed["skill_scripts_executed"] == ["quick_prove.py"]
    assert parsed["treatment_uptake"] is True
    assert parsed["outside_workspace_paths"] == ["/repo/bench/cases/x/grader.py"]
    assert parsed["served_models"] == ["served-model"]
    assert parsed["usage"]["output_tokens"] == 5
    assert parsed["final_text_tail"] == "done"

    control = parse_trace(json.dumps({"type": "result", "subtype": "success"}), workspace)
    assert control["treatment_uptake"] is False
    assert control["provider_model_identity"] == "unavailable"
    print("self-test: PASS")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--claude-bin", default=os.environ.get("WINCREATOR_BENCH_CLAUDE_BIN", "claude"))
    parser.add_argument("--model", default=os.environ.get("WINCREATOR_BENCH_MODEL"))
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    try:
        return run(args)
    except (OSError, ValueError) as error:
        print(f"CLAUDE CODE ADAPTER ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
