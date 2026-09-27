#!/usr/bin/env python3
"""Measure structural code cost without pretending to measure correctness.

The output is deliberately a vector, not a weighted score. A distillation
report can only PASS or request REVIEW; it never proves semantic correctness.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

SCHEMA_SNAPSHOT = "wincreator.distillation-snapshot/v1"
SCHEMA_REPORT = "wincreator.distillation-report/v1"
SOURCE_EXTENSIONS = {
    ".c", ".cc", ".cpp", ".cs", ".css", ".go", ".h", ".hpp", ".html",
    ".java", ".js", ".jsx", ".kt", ".kts", ".lua", ".mjs", ".php",
    ".py", ".rb", ".rs", ".scss", ".sh", ".sql", ".svelte", ".swift",
    ".ts", ".tsx", ".vue",
}
DEFAULT_EXCLUDES = (
    ".git/**", ".hg/**", ".svn/**", ".venv/**", "venv/**", "node_modules/**",
    "dist/**", "build/**", "coverage/**", ".next/**", ".cache/**", "vendor/**",
)
LARGE_FILE_LINES = 400


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _is_excluded(rel, patterns):
    rel = rel.replace(os.sep, "/")
    return any(fnmatch.fnmatch(rel, pattern) for pattern in patterns)


def _read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def _manifest_info(path, rel, text):
    name = path.name
    if name == "package.json":
        try:
            data = json.loads(text)
            deps = sorted((data.get("dependencies") or {}).keys())
            return {"path": rel, "kind": "package.json", "declared_runtime_dependencies": deps}
        except (json.JSONDecodeError, AttributeError):
            return {"path": rel, "kind": "package.json", "declared_runtime_dependencies": None}
    if re.fullmatch(r"requirements(?:[-_.][^/]*)?\.txt", name, flags=re.I):
        deps = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith(("-r ", "--")):
                continue
            deps.append(re.split(r"[<>=!~\[\s]", line, maxsplit=1)[0].lower())
        return {"path": rel, "kind": "requirements", "declared_runtime_dependencies": sorted(set(filter(None, deps)))}
    if name in {"pyproject.toml", "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts"}:
        return {"path": rel, "kind": name, "declared_runtime_dependencies": None}
    return None


def snapshot(root, excludes=()):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    patterns = tuple(DEFAULT_EXCLUDES) + tuple(excludes)
    files = []
    manifests = []
    duplicate_candidates = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root).as_posix()
        if _is_excluded(rel, patterns):
            continue
        text = _read_text(path)
        if text is None:
            continue
        manifest = _manifest_info(path, rel, text)
        if manifest:
            manifests.append(manifest)
        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        raw = path.read_bytes()
        lines = text.splitlines()
        nonblank = [line.strip() for line in lines if line.strip()]
        files.append({
            "path": rel,
            "bytes": len(raw),
            "lines": len(lines),
            "nonblank_lines": len(nonblank),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
        duplicate_candidates.extend(line for line in nonblank if len(line) >= 24)

    total_candidates = len(duplicate_candidates)
    unique_candidates = len(set(duplicate_candidates))
    duplicate_instances = total_candidates - unique_candidates
    known_dependencies = sorted({
        dep
        for item in manifests
        if item["declared_runtime_dependencies"] is not None
        for dep in item["declared_runtime_dependencies"]
    })
    unknown_manifests = sorted(item["path"] for item in manifests if item["declared_runtime_dependencies"] is None)
    metrics = {
        "source_files": len(files),
        "source_bytes": sum(item["bytes"] for item in files),
        "nonblank_lines": sum(item["nonblank_lines"] for item in files),
        "max_file_nonblank_lines": max((item["nonblank_lines"] for item in files), default=0),
        "large_files": sum(item["nonblank_lines"] >= LARGE_FILE_LINES for item in files),
        "duplicate_line_instances": duplicate_instances,
        "duplicate_line_candidates": total_candidates,
        "known_runtime_dependencies": len(known_dependencies),
        "dependency_manifests": len(manifests),
        "unknown_dependency_manifests": len(unknown_manifests),
    }
    body = {
        "schema": SCHEMA_SNAPSHOT,
        "root": root.name,
        "metrics": metrics,
        "dependencies": known_dependencies,
        "unknown_dependency_manifests": unknown_manifests,
        "files": files,
    }
    return {**body, "digest": {"algorithm": "sha256", "value": _digest(body)}}


def verify_snapshot(data):
    if data.get("schema") != SCHEMA_SNAPSHOT:
        return False
    digest = data.get("digest", {})
    if digest.get("algorithm") != "sha256" or not isinstance(digest.get("value"), str):
        return False
    body = {key: value for key, value in data.items() if key != "digest"}
    return _digest(body) == digest["value"]


def compare(before, after, mode="audit"):
    if not verify_snapshot(before) or not verify_snapshot(after):
        raise ValueError("snapshot digest verification failed")
    bm, am = before["metrics"], after["metrics"]
    keys = (
        "source_files", "source_bytes", "nonblank_lines", "max_file_nonblank_lines",
        "large_files", "duplicate_line_instances", "known_runtime_dependencies",
        "dependency_manifests", "unknown_dependency_manifests",
    )
    delta = {key: am[key] - bm[key] for key in keys}
    reasons = []
    if after["dependencies"] != before["dependencies"]:
        added = sorted(set(after["dependencies"]) - set(before["dependencies"]))
        removed = sorted(set(before["dependencies"]) - set(after["dependencies"]))
        if added:
            reasons.append("runtime dependencies added: " + ", ".join(added))
    else:
        added, removed = [], []
    new_unknown = sorted(set(after["unknown_dependency_manifests"]) - set(before["unknown_dependency_manifests"]))
    if new_unknown:
        reasons.append("new dependency manifest requires human inspection: " + ", ".join(new_unknown))

    if mode == "refactor":
        guarded = (
            "source_files", "source_bytes", "nonblank_lines", "max_file_nonblank_lines",
            "large_files", "duplicate_line_instances", "known_runtime_dependencies",
        )
        for key in guarded:
            if delta[key] > 0:
                reasons.append(f"refactor structural cost increased: {key} +{delta[key]}")
    elif mode == "feature" and added:
        reasons.append("feature dependency growth must be justified explicitly")

    verdict = "REVIEW" if reasons else "PASS"
    body = {
        "schema": SCHEMA_REPORT,
        "mode": mode,
        "verdict": verdict,
        "before_digest": before["digest"]["value"],
        "after_digest": after["digest"]["value"],
        "delta": delta,
        "dependencies_added": added,
        "dependencies_removed": removed,
        "reasons": reasons,
    }
    return {**body, "digest": {"algorithm": "sha256", "value": _digest(body)}}


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(data, path=None):
    rendered = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if path:
        Path(path).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


def self_test():
    checks = []
    def check(name, condition):
        checks.append((name, bool(condition)))

    with tempfile.TemporaryDirectory(prefix="wincreator-distill-") as directory:
        root = Path(directory)
        (root / "app.py").write_text("def add(a, b):\n    return a + b\n\nprint(add(1, 2))\n", encoding="utf-8")
        (root / "package.json").write_text(json.dumps({"dependencies": {"left-pad": "1.3.0"}}), encoding="utf-8")
        first = snapshot(root)
        check("snapshot_digest", verify_snapshot(first))
        (root / "app.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
        (root / "package.json").write_text(json.dumps({"dependencies": {}}), encoding="utf-8")
        second = snapshot(root)
        report = compare(first, second, "refactor")
        check("simpler_refactor_passes", report["verdict"] == "PASS")
        check("dependency_removal_seen", report["dependencies_removed"] == ["left-pad"])
        (root / "extra.py").write_text("x = 1\n" * 20, encoding="utf-8")
        third = snapshot(root)
        check("growth_refactor_reviews", compare(second, third, "refactor")["verdict"] == "REVIEW")
        tampered = json.loads(json.dumps(third))
        tampered["metrics"]["nonblank_lines"] += 1
        check("tamper_detected", not verify_snapshot(tampered))
        check("audit_never_upgrades_correctness", compare(second, third, "audit")["verdict"] == "PASS")

    for name, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    print(f"self-test: {sum(ok for _, ok in checks)}/{len(checks)} passed")
    return 0 if all(ok for _, ok in checks) else 2


def build_parser():
    parser = argparse.ArgumentParser(prog="distill")
    parser.add_argument("--self-test", action="store_true")
    sub = parser.add_subparsers(dest="command")
    snap = sub.add_parser("snapshot", help="capture a structural-cost vector")
    snap.add_argument("root")
    snap.add_argument("--out")
    snap.add_argument("--exclude", action="append", default=[])
    comp = sub.add_parser("compare", help="compare two verified snapshots")
    comp.add_argument("before")
    comp.add_argument("after")
    comp.add_argument("--mode", choices=("audit", "feature", "refactor"), default="audit")
    comp.add_argument("--out")
    verify = sub.add_parser("verify", help="verify a snapshot digest")
    verify.add_argument("snapshot")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.self_test:
        return self_test()
    if args.command == "snapshot":
        _write(snapshot(args.root, args.exclude), args.out)
        return 0
    if args.command == "compare":
        report = compare(_load(args.before), _load(args.after), args.mode)
        _write(report, args.out)
        return 1 if report["verdict"] == "REVIEW" else 0
    if args.command == "verify":
        ok = verify_snapshot(_load(args.snapshot))
        print("DISTILLATION SNAPSHOT OK" if ok else "DISTILLATION SNAPSHOT INVALID")
        return 0 if ok else 1
    build_parser().print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
