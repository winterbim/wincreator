#!/usr/bin/env python3
"""Run paired WinCreator ON/OFF coding-agent ablations."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "wincreator.ablation-run/v1"
SOURCE_EXTENSIONS = {
    ".c", ".cc", ".cpp", ".cs", ".dart", ".go", ".java", ".js", ".jsx",
    ".kt", ".php", ".py", ".rb", ".rs", ".sh", ".sql", ".swift", ".ts", ".tsx",
}
EXCLUDE = {".git", ".agents", ".wincreator", "__pycache__", "node_modules", "dist", "build", "target", "venv", ".venv"}


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    return sha256_bytes(Path(path).read_bytes())


def tree_digest(root):
    entries = []
    root = Path(root)
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDE for part in relative.parts):
            continue
        entries.append([relative.as_posix(), file_sha(path)])
    return sha256_bytes(json.dumps(entries, separators=(",", ":")).encode())


def structure(root):
    files = nonblank = total_bytes = largest = 0
    for path in Path(root).rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDE for part in relative.parts):
            continue
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        count = sum(bool(line.strip()) for line in text.splitlines())
        files += 1
        nonblank += count
        total_bytes += len(raw)
        largest = max(largest, count)
    return {
        "source_files": files,
        "nonblank_lines": nonblank,
        "source_bytes": total_bytes,
        "largest_file_nonblank_lines": largest,
    }


def run_process(command, cwd, timeout, env=None):
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command, cwd=cwd, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, timeout=timeout, check=False,
        )
        status, code = "completed", completed.returncode
        stdout, stderr = completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        status, code = "timeout", None
        stdout, stderr = exc.stdout or "", exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
    return {
        "status": status,
        "exit_code": code,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "stdout_sha256": sha256_bytes(stdout.encode()),
        "stderr_sha256": sha256_bytes(stderr.encode()),
        "stdout_tail": stdout[-4000:],
        "stderr_tail": stderr[-4000:],
    }


def load_manifest(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != "wincreator.ablation-manifest/v1":
        raise ValueError("invalid benchmark manifest schema")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("benchmark manifest requires at least one case")
    seen = set()
    for case in cases:
        required = {"id", "task", "seed", "grader", "timeout_seconds"}
        missing = required - set(case)
        if missing:
            raise ValueError(f"{case.get('id', '<unknown>')}: missing {sorted(missing)}")
        if case["id"] in seen:
            raise ValueError(f"duplicate case id: {case['id']}")
        seen.add(case["id"])
    return data


def render_command(parts, workspace, prompt, condition):
    values = {
        "workspace": str(workspace),
        "prompt": str(prompt),
        "condition": condition,
    }
    return [part.format(**values) for part in parts]


def prepare_workspace(case, manifest_dir, condition, run_root):
    seed = (manifest_dir / case["seed"]).resolve()
    task = (manifest_dir / case["task"]).resolve()
    if not seed.is_dir() or not task.is_file():
        raise ValueError(f"{case['id']}: missing seed or task")
    workspace = run_root / "workspace"
    shutil.copytree(seed, workspace)
    prompt = workspace / "TASK.md"
    task_text = task.read_text(encoding="utf-8")
    if condition == "on":
        skill_target = workspace / ".agents" / "skills" / "wincreator"
        skill_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT / "skill" / "wincreator", skill_target)
        task_text += (
            "\n\n---\nBenchmark treatment: WinCreator is installed at "
            ".agents/skills/wincreator. Use it for this task. "
            "Do not inspect files outside this workspace.\n"
        )
    else:
        task_text += (
            "\n\n---\nBenchmark control: complete the coding task normally. "
            "Do not inspect files outside this workspace.\n"
        )
    prompt.write_text(task_text, encoding="utf-8")
    return workspace, prompt


def run_case(case, manifest_dir, condition, repetition, agent_template, output_root):
    run_root = output_root / case["id"] / f"rep-{repetition:02d}" / condition
    run_root.mkdir(parents=True, exist_ok=False)
    workspace, prompt = prepare_workspace(case, manifest_dir, condition, run_root)
    before_digest = tree_digest(workspace)
    command = render_command(agent_template, workspace, prompt, condition)
    env = os.environ.copy()
    env.update({
        "WINCREATOR_BENCH_WORKSPACE": str(workspace),
        "WINCREATOR_BENCH_PROMPT": str(prompt),
        "WINCREATOR_BENCH_CONDITION": condition,
        "WINCREATOR_BENCH_CASE": case["id"],
    })
    agent = run_process(command, workspace, int(case["timeout_seconds"]), env)
    grader_path = (manifest_dir / case["grader"]).resolve()
    grader = run_process(
        [sys.executable, str(grader_path), str(workspace)],
        manifest_dir,
        int(case.get("grader_timeout_seconds", 60)),
        os.environ.copy(),
    )
    result = {
        "schema": SCHEMA,
        "case": case["id"],
        "condition": condition,
        "repetition": repetition,
        "task_sha256": file_sha(manifest_dir / case["task"]),
        "seed_tree_sha256": tree_digest(manifest_dir / case["seed"]),
        "grader_sha256": file_sha(grader_path),
        "workspace_before_sha256": before_digest,
        "workspace_after_sha256": tree_digest(workspace),
        "agent_command": command,
        "agent": agent,
        "grader": grader,
        "passed": grader["status"] == "completed" and grader["exit_code"] == 0,
        "structure": structure(workspace),
        "isolation": {
            "grader_copied_into_workspace": False,
            "workspace_process_isolation": "cwd-only",
            "warning": "Use a container/bwrap adapter for a security-hidden oracle.",
        },
    }
    result["digest"] = sha256_bytes(
        json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    )
    (run_root / "result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def summarize(results):
    summary = {}
    for condition in ("off", "on"):
        rows = [item for item in results if item["condition"] == condition]
        if not rows:
            continue
        passed = sum(item["passed"] for item in rows)
        summary[condition] = {
            "runs": len(rows),
            "passed": passed,
            "pass_rate": passed / len(rows),
            "mean_agent_duration_ms": round(
                sum(item["agent"]["duration_ms"] for item in rows) / len(rows)
            ),
            "mean_nonblank_lines": round(
                sum(item["structure"]["nonblank_lines"] for item in rows) / len(rows), 2
            ),
        }
    return summary


def run_benchmark(manifest_path, agent_template, output, repetitions=3, condition="both"):
    manifest_path = Path(manifest_path).resolve()
    manifest = load_manifest(manifest_path)
    manifest_dir = manifest_path.parent
    output_root = Path(output).resolve()
    if output_root.exists():
        raise ValueError(f"output already exists: {output_root}")
    output_root.mkdir(parents=True)
    conditions = ["off", "on"] if condition == "both" else [condition]
    results = []
    for repetition in range(1, repetitions + 1):
        for case in manifest["cases"]:
            for current in conditions:
                results.append(
                    run_case(case, manifest_dir, current, repetition, agent_template, output_root)
                )
    bundle = {
        "schema": "wincreator.ablation-bundle/v1",
        "manifest_sha256": file_sha(manifest_path),
        "repetitions": repetitions,
        "conditions": conditions,
        "results": results,
        "summary": summarize(results),
    }
    bundle["digest"] = sha256_bytes(
        json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()
    )
    (output_root / "bundle.json").write_text(
        json.dumps(bundle, indent=2) + "\n", encoding="utf-8"
    )
    return bundle


def self_test():
    with tempfile.TemporaryDirectory(prefix="wincreator-bench-") as directory:
        root = Path(directory)
        seed = root / "case" / "seed"
        seed.mkdir(parents=True)
        (seed / "answer.py").write_text("VALUE = 0\n", encoding="utf-8")
        (root / "case" / "task.md").write_text("Set VALUE to 1.\n", encoding="utf-8")
        (root / "case" / "grader.py").write_text(
            "import runpy,sys,pathlib\n"
            "p=pathlib.Path(sys.argv[1])/'answer.py'\n"
            "raise SystemExit(0 if runpy.run_path(str(p))['VALUE']==1 else 1)\n",
            encoding="utf-8",
        )
        manifest = {
            "schema": "wincreator.ablation-manifest/v1",
            "cases": [{
                "id": "smoke",
                "task": "case/task.md",
                "seed": "case/seed",
                "grader": "case/grader.py",
                "timeout_seconds": 20,
            }],
        }
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        agent = root / "agent.py"
        agent.write_text(
            "import os,pathlib\n"
            "w=pathlib.Path(os.environ['WINCREATOR_BENCH_WORKSPACE'])\n"
            "assert (w/'.agents/skills/wincreator/SKILL.md').exists() == "
            "(os.environ['WINCREATOR_BENCH_CONDITION']=='on')\n"
            "(w/'answer.py').write_text('VALUE = 1\\n')\n",
            encoding="utf-8",
        )
        bundle = run_benchmark(
            root / "manifest.json", [sys.executable, str(agent)],
            root / "out", repetitions=1, condition="both",
        )
        assert bundle["summary"]["off"]["passed"] == 1
        assert bundle["summary"]["on"]["passed"] == 1
        assert len(bundle["results"]) == 2
        assert all(not row["isolation"]["grader_copied_into_workspace"] for row in bundle["results"])
    print("self-test: PASS")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--manifest", default=str(ROOT / "bench" / "benchmark.json"))
    parser.add_argument("--output")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--condition", choices=("off", "on", "both"), default="both")
    parser.add_argument("agent_command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if not args.output:
        parser.error("--output is required")
    command = list(args.agent_command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("agent command is required after --")
    if args.repetitions < 1:
        parser.error("--repetitions must be >= 1")
    try:
        bundle = run_benchmark(
            args.manifest, command, args.output, args.repetitions, args.condition
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"BENCHMARK ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(bundle["summary"], indent=2))
    print(f"bundle: {Path(args.output).resolve() / 'bundle.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
