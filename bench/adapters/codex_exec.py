#!/usr/bin/env python3
"""Codex CLI adapter for WinCreator paired coding benchmarks.

Runs Codex non-interactively with an explicit model, closed stdin, ephemeral
session state, JSONL observability, and workspace-write sandboxing. It never
uses the dangerous sandbox/approval bypass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

METRICS_SCHEMA = "wincreator.bench-agent-metrics/codex-v1"


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def build_command(codex_bin, model, reasoning_effort, prompt, keep_user_config=False):
    command = [
        codex_bin,
        "--ask-for-approval",
        "never",
        "exec",
        "--ephemeral",
        "--json",
        "--skip-git-repo-check",
        "--model",
        model,
        "--sandbox",
        "workspace-write",
        "--color",
        "never",
    ]
    if not keep_user_config:
        command.extend(["--ignore-user-config", "--ignore-rules"])
    if reasoning_effort:
        command.extend(["-c", f'model_reasoning_effort="{reasoning_effort}"'])
    command.append(prompt)
    return command


def parse_jsonl(text):
    events = []
    parse_errors = 0
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

    thread_ids = [
        event.get("thread_id")
        for event in events
        if event.get("type") == "thread.started" and event.get("thread_id")
    ]
    completed = [event for event in events if event.get("type") == "turn.completed"]
    failed = [event for event in events if event.get("type") in {"turn.failed", "error"}]
    usage = completed[-1].get("usage") if completed else None
    server_model = None
    for event in reversed(completed):
        candidate = event.get("server_model")
        if isinstance(candidate, str) and candidate.strip():
            server_model = candidate.strip()
            break
    return {
        "event_count": len(events),
        "parse_errors": parse_errors,
        "thread_id": thread_ids[-1] if thread_ids else None,
        "turn_completed_count": len(completed),
        "failure_event_count": len(failed),
        "usage": usage if isinstance(usage, dict) else None,
        "server_model": server_model,
        "provider_model_identity": "observed" if server_model else "unavailable",
    }


def codex_version(codex_bin):
    completed = subprocess.run(
        [codex_bin, "--version"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=15,
        check=False,
    )
    text = (completed.stdout or completed.stderr).strip()
    return text or None


def write_metrics(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(encoded)
    os.replace(temporary, path)


def run(args):
    workspace = Path(os.environ.get("WINCREATOR_BENCH_WORKSPACE", os.getcwd())).resolve()
    prompt_path = os.environ.get("WINCREATOR_BENCH_PROMPT")
    metrics_out = os.environ.get("WINCREATOR_BENCH_METRICS_OUT")
    condition = os.environ.get("WINCREATOR_BENCH_CONDITION")
    case_id = os.environ.get("WINCREATOR_BENCH_CASE")

    if not prompt_path:
        raise ValueError("WINCREATOR_BENCH_PROMPT is required")
    if not metrics_out:
        raise ValueError("WINCREATOR_BENCH_METRICS_OUT is required")
    prompt = Path(prompt_path).read_text(encoding="utf-8")

    binary = shutil.which(args.codex_bin)
    if not binary:
        raise ValueError(f"Codex executable not found: {args.codex_bin}")

    command = build_command(
        binary,
        args.model,
        args.reasoning_effort,
        prompt,
        keep_user_config=args.keep_user_config,
    )
    version = codex_version(binary)
    completed = subprocess.run(
        command,
        cwd=workspace,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    # Preserve the native Codex trace for the outer benchmark harness.
    if completed.stdout:
        sys.stdout.write(completed.stdout)
        sys.stdout.flush()
    if completed.stderr:
        sys.stderr.write(completed.stderr)
        sys.stderr.flush()

    parsed = parse_jsonl(completed.stdout)
    metrics = {
        "schema": METRICS_SCHEMA,
        "adapter": "codex-exec",
        "codex_version": version,
        "requested_model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "condition": condition,
        "case": case_id,
        "sandbox": "workspace-write",
        "approval_policy": "never",
        "ephemeral": True,
        "ignore_user_config": not args.keep_user_config,
        "stdin": "devnull",
        "exit_code": completed.returncode,
        "jsonl_sha256": sha256_bytes(completed.stdout.encode("utf-8")),
        **parsed,
    }
    write_metrics(metrics_out, metrics)
    return completed.returncode


def self_test():
    command = build_command(
        "codex", "gpt-test", "high", "Do work", keep_user_config=False
    )
    assert command[:4] == ["codex", "--ask-for-approval", "never", "exec"]
    assert "--ephemeral" in command
    assert "--json" in command
    assert "--sandbox" in command
    assert command[command.index("--sandbox") + 1] == "workspace-write"
    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command
    assert "dangerously-bypass-approvals-and-sandbox" not in " ".join(command)

    sample = "\n".join([
        json.dumps({"type": "thread.started", "thread_id": "abc"}),
        json.dumps({
            "type": "turn.completed",
            "usage": {
                "input_tokens": 100,
                "cached_input_tokens": 20,
                "output_tokens": 30,
                "reasoning_output_tokens": 10,
            },
        }),
    ])
    parsed = parse_jsonl(sample)
    assert parsed["thread_id"] == "abc"
    assert parsed["usage"]["input_tokens"] == 100
    assert parsed["usage"]["reasoning_output_tokens"] == 10
    assert parsed["provider_model_identity"] == "unavailable"

    observed = parse_jsonl(json.dumps({
        "type": "turn.completed",
        "server_model": "provider-model",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }))
    assert observed["provider_model_identity"] == "observed"
    assert observed["server_model"] == "provider-model"

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "metrics.json"
        write_metrics(path, {"schema": METRICS_SCHEMA, "ok": True})
        assert json.loads(path.read_text(encoding="utf-8"))["ok"] is True

    print("self-test: PASS")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--codex-bin", default=os.environ.get("CODEX_BIN", "codex"))
    parser.add_argument(
        "--model",
        default=os.environ.get("WINCREATOR_BENCH_MODEL"),
        help="explicit Codex model; required for benchmark runs",
    )
    parser.add_argument(
        "--reasoning-effort",
        default=os.environ.get("WINCREATOR_BENCH_REASONING_EFFORT", "high"),
    )
    parser.add_argument(
        "--keep-user-config",
        action="store_true",
        help="allow CODEX_HOME config/rules; weakens treatment isolation",
    )
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if not args.model:
        parser.error("--model or WINCREATOR_BENCH_MODEL is required")
    try:
        return run(args)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"CODEX ADAPTER ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
