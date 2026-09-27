#!/usr/bin/env python3
"""Deterministic proof-adequacy gate for WinCreator (stdlib only).

A green test command is not enough if the tests cannot detect a deliberately
seeded fault. This tool runs the baseline gate, then re-runs it against isolated
literal mutations and reports whether every required mutation was killed.
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

MANIFEST_SCHEMA = "wincreator.adequacy-manifest/v1"
REPORT_SCHEMA = "wincreator.adequacy-report/v1"
DEFAULT_EXCLUDES = {
    ".git", ".hg", ".svn", ".venv", ".wincreator", "__pycache__",
    "build", "coverage", "dist", "node_modules", "target", "venv",
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_manifest(manifest):
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("invalid adequacy manifest schema")
    mutations = manifest.get("mutations")
    if not isinstance(mutations, list) or not mutations:
        raise ValueError("manifest requires a non-empty mutations list")
    seen = set()
    for item in mutations:
        if not isinstance(item, dict):
            raise ValueError("each mutation must be an object")
        allowed = {"id", "path", "find", "replace", "count", "required"}
        unknown = set(item) - allowed
        if unknown:
            raise ValueError("unknown mutation field(s): " + ", ".join(sorted(unknown)))
        mutation_id = item.get("id")
        if not isinstance(mutation_id, str) or not mutation_id.strip():
            raise ValueError("mutation id must be a non-empty string")
        if mutation_id in seen:
            raise ValueError(f"duplicate mutation id: {mutation_id}")
        seen.add(mutation_id)
        if not isinstance(item.get("path"), str) or not item["path"]:
            raise ValueError(f"{mutation_id}: path must be a non-empty string")
        if not isinstance(item.get("find"), str) or not item["find"]:
            raise ValueError(f"{mutation_id}: find must be a non-empty string")
        if not isinstance(item.get("replace", ""), str):
            raise ValueError(f"{mutation_id}: replace must be a string")
        count = item.get("count", 1)
        if not isinstance(count, int) or count < 1:
            raise ValueError(f"{mutation_id}: count must be an integer >= 1")
        if "required" in item and not isinstance(item["required"], bool):
            raise ValueError(f"{mutation_id}: required must be boolean")


def _confined(root, relative):
    root = root.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"mutation path escapes root: {relative}") from exc
    if path == root:
        raise ValueError("mutation path must name a file")
    return path


def _ignore(_directory, names):
    return [name for name in names if name in DEFAULT_EXCLUDES]


def copy_workspace(root, destination):
    shutil.copytree(root, destination, ignore=_ignore, symlinks=False)


def run_gate(command, cwd, timeout):
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {
            "status": "completed",
            "exit_code": completed.returncode,
            "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(completed.stderr.encode()).hexdigest(),
            "stdout_tail": completed.stdout[-2000:],
            "stderr_tail": completed.stderr[-2000:],
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return {
            "status": "timeout",
            "exit_code": None,
            "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
            "stdout_tail": stdout[-2000:],
            "stderr_tail": stderr[-2000:],
        }


def apply_mutation(workspace, mutation):
    target = _confined(workspace, mutation["path"])
    if not target.is_file():
        raise ValueError(f"{mutation['id']}: target is not a file: {mutation['path']}")
    if target.is_symlink():
        raise ValueError(f"{mutation['id']}: symlink targets are not allowed")
    text = target.read_text(encoding="utf-8")
    expected = mutation.get("count", 1)
    actual = text.count(mutation["find"])
    if actual != expected:
        raise ValueError(
            f"{mutation['id']}: expected {expected} literal match(es), found {actual}"
        )
    changed = text.replace(mutation["find"], mutation.get("replace", ""), expected)
    if changed == text:
        raise ValueError(f"{mutation['id']}: mutation made no change")
    target.write_text(changed, encoding="utf-8")
    return {
        "path": mutation["path"],
        "before_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "after_sha256": hashlib.sha256(changed.encode()).hexdigest(),
        "match_count": expected,
    }


def run_adequacy(root, manifest, command, timeout=120):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("root must be a directory")
    if not command:
        raise ValueError("gate command is required")
    validate_manifest(manifest)

    manifest_payload = dict(manifest)
    manifest_digest = digest(manifest_payload)
    report = {
        "schema": REPORT_SCHEMA,
        "root": str(root),
        "manifest_digest": manifest_digest,
        "command": list(command),
        "timeout_seconds": timeout,
        "baseline": None,
        "mutations": [],
        "verdict": "ERROR",
    }

    with tempfile.TemporaryDirectory(prefix="wincreator-adequacy-") as temporary:
        temporary = Path(temporary)
        frozen = temporary / "frozen"
        copy_workspace(root, frozen)

        baseline = run_gate(command, frozen, timeout)
        report["baseline"] = baseline
        if baseline["status"] != "completed" or baseline["exit_code"] != 0:
            report["reason"] = "baseline gate must pass before mutation adequacy can be measured"
            payload = dict(report)
            report["digest"] = digest(payload)
            return report

        any_required_survivor = False
        any_invalid = False

        for index, mutation in enumerate(manifest["mutations"]):
            case_root = temporary / f"case-{index:03d}"
            shutil.copytree(frozen, case_root, ignore=_ignore, symlinks=False)
            required = mutation.get("required", True)
            record = {
                "id": mutation["id"],
                "required": required,
                "path": mutation["path"],
            }
            try:
                record["change"] = apply_mutation(case_root, mutation)
                gate = run_gate(command, case_root, timeout)
                record["gate"] = gate
                if gate["status"] == "completed" and gate["exit_code"] == 0:
                    record["result"] = "SURVIVED"
                    any_required_survivor |= required
                elif gate["status"] == "timeout":
                    record["result"] = "KILLED_TIMEOUT"
                else:
                    record["result"] = "KILLED"
            except (OSError, UnicodeError, ValueError) as exc:
                record["result"] = "INVALID"
                record["error"] = str(exc)
                any_invalid = True
            report["mutations"].append(record)

    if any_invalid:
        report["verdict"] = "ERROR"
        report["reason"] = "one or more declared mutations were invalid"
    elif any_required_survivor:
        report["verdict"] = "INSUFFICIENT"
        report["reason"] = "at least one required seeded fault survived the declared gate"
    else:
        report["verdict"] = "ADEQUATE"
        report["reason"] = "every required seeded fault was detected by the declared gate"

    payload = dict(report)
    report["digest"] = digest(payload)
    return report


def verify_report(report):
    if report.get("schema") != REPORT_SCHEMA:
        raise ValueError("invalid adequacy report schema")
    supplied = report.get("digest")
    payload = dict(report)
    payload.pop("digest", None)
    if supplied != digest(payload):
        raise ValueError("adequacy report digest mismatch")
    return True


def write_report(report, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def self_test():
    results = []
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "project"
        root.mkdir()
        (root / "demo.py").write_text(
            "def classify(x):\n    return 'positive' if x > 0 else 'other'\n",
            encoding="utf-8",
        )
        (root / "check.py").write_text(
            "from demo import classify\n"
            "assert classify(1) == 'positive'\n"
            "assert classify(0) == 'other'\n",
            encoding="utf-8",
        )
        gate = [sys.executable, "check.py"]

        adequate = {
            "schema": MANIFEST_SCHEMA,
            "mutations": [
                {
                    "id": "flip-positive",
                    "path": "demo.py",
                    "find": "x > 0",
                    "replace": "x < 0",
                }
            ],
        }
        report = run_adequacy(root, adequate, gate)
        results.append(("killed_fault_is_adequate", report["verdict"] == "ADEQUATE"))

        survivor = {
            "schema": MANIFEST_SCHEMA,
            "mutations": [
                {
                    "id": "untested-negative-detail",
                    "path": "demo.py",
                    "find": "else 'other'",
                    "replace": "else ('negative' if x < 0 else 'other')",
                }
            ],
        }
        report = run_adequacy(root, survivor, gate)
        results.append(("surviving_fault_is_insufficient", report["verdict"] == "INSUFFICIENT"))

        escaping = {
            "schema": MANIFEST_SCHEMA,
            "mutations": [
                {
                    "id": "escape",
                    "path": "../outside.py",
                    "find": "x",
                    "replace": "y",
                }
            ],
        }
        report = run_adequacy(root, escaping, gate)
        results.append(("scope_escape_fails_closed", report["verdict"] == "ERROR"))

        payload = dict(report)
        payload["verdict"] = "ADEQUATE"
        try:
            verify_report(payload)
        except ValueError:
            results.append(("tamper_is_detected", True))
        else:
            results.append(("tamper_is_detected", False))

    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    count = sum(value for _name, value in results)
    print(f"self-test: {count}/{len(results)} passed")
    return 0 if count == len(results) else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command_name", required=True)

    run_parser = sub.add_parser("run", help="run baseline and controlled mutations")
    run_parser.add_argument("--root", default=".")
    run_parser.add_argument("--manifest", required=True)
    run_parser.add_argument("--out", required=True)
    run_parser.add_argument("--timeout", type=int, default=120)
    run_parser.add_argument("gate", nargs=argparse.REMAINDER)

    verify_parser = sub.add_parser("verify", help="verify report integrity")
    verify_parser.add_argument("--report", required=True)

    sub.add_parser("self-test", help="run deterministic embedded checks")

    args = parser.parse_args(argv)
    if args.command_name == "self-test":
        return self_test()
    if args.command_name == "verify":
        verify_report(load_json(args.report))
        print("ADEQUACY REPORT: VERIFIED")
        return 0

    gate = list(args.gate)
    if gate and gate[0] == "--":
        gate = gate[1:]
    manifest = load_json(args.manifest)
    try:
        report = run_adequacy(args.root, manifest, gate, args.timeout)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ADEQUACY: ERROR — {exc}", file=sys.stderr)
        return 2
    write_report(report, args.out)
    print(f"ADEQUACY: {report['verdict']} — {report['reason']}")
    print(f"report: {args.out}")
    print(f"digest: {report['digest']}")
    return 0 if report["verdict"] == "ADEQUATE" else 1


if __name__ == "__main__":
    sys.exit(main())
