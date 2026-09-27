#!/usr/bin/env python3
"""Validate that WinCreator benchmark cases are well-formed and RED at baseline."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(manifest_path):
    manifest_path = Path(manifest_path).resolve()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("schema") != "wincreator.ablation-manifest/v1":
        raise ValueError("invalid benchmark manifest schema")
    root = manifest_path.parent
    problems = []
    seen = set()
    receipts = []
    for case in data.get("cases", []):
        case_id = case.get("id")
        if not case_id or case_id in seen:
            problems.append(f"invalid or duplicate case id: {case_id!r}")
            continue
        seen.add(case_id)
        task = (root / case["task"]).resolve()
        seed = (root / case["seed"]).resolve()
        grader = (root / case["grader"]).resolve()
        if not task.is_file() or not seed.is_dir() or not grader.is_file():
            problems.append(f"{case_id}: missing task, seed, or grader")
            continue
        if grader.is_relative_to(seed):
            problems.append(f"{case_id}: grader must live outside agent seed workspace")
            continue
        completed = subprocess.run(
            [sys.executable, str(grader), str(seed)],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=int(case.get("grader_timeout_seconds", 60)),
            check=False,
        )
        if completed.returncode == 0:
            problems.append(f"{case_id}: baseline seed is already green")
        receipts.append({
            "id": case_id,
            "task_sha256": sha(task),
            "grader_sha256": sha(grader),
            "baseline_exit_code": completed.returncode,
        })
    return receipts, problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", default=str(ROOT / "bench" / "benchmark.json")
    )
    args = parser.parse_args(argv)
    try:
        receipts, problems = validate(args.manifest)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(f"BENCH CASE VALIDATION: ERROR — {exc}", file=sys.stderr)
        return 2
    for receipt in receipts:
        print(
            f"  [RED] {receipt['id']} baseline_exit={receipt['baseline_exit_code']} "
            f"task={receipt['task_sha256'][:12]} grader={receipt['grader_sha256'][:12]}"
        )
    if problems:
        for problem in problems:
            print(f"  [FAIL] {problem}")
        print(f"BENCH CASE VALIDATION: FAIL — {len(problems)} problem(s)")
        return 1
    print(f"BENCH CASE VALIDATION: PASS — {len(receipts)} RED case(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
