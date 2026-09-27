#!/usr/bin/env python3
"""WinCreator structural distillation evidence (stdlib only).

Captures measurable structural cost before/after a behavior-preserving cleanup.
It deliberately does not produce a universal quality score or claim optimality.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

POLICY_SCHEMA = "wincreator.distill-policy/v1"
SNAPSHOT_SCHEMA = "wincreator.distill-snapshot/v1"
REPORT_SCHEMA = "wincreator.distill-report/v1"
DEFAULT_POLICY = {
    "schema": POLICY_SCHEMA,
    "source_extensions": [
        ".c", ".cc", ".cpp", ".cs", ".css", ".dart", ".go", ".h", ".hpp",
        ".html", ".java", ".js", ".jsx", ".kt", ".php", ".py", ".rb", ".rs",
        ".sh", ".sql", ".svelte", ".swift", ".ts", ".tsx", ".vue",
    ],
    "exclude_dirs": [
        ".git", ".hg", ".svn", ".venv", ".wincreator", "__pycache__", "build",
        "coverage", "dist", "node_modules", "target", "vendor", "venv",
    ],
    "exclude_globs": ["*.min.js", "*.min.css", "*.map"],
    "duplicate_window_lines": 6,
    "duplicate_min_chars": 120,
}
LOWER_IS_BETTER = (
    "source_files", "nonblank_lines", "declared_dependencies",
    "duplicate_fingerprints", "largest_file_lines",
)
MANIFEST_NAMES = {"package.json", "pyproject.toml", "Cargo.toml", "go.mod"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def normalize_policy(raw=None):
    policy = dict(DEFAULT_POLICY)
    if raw:
        unknown = set(raw) - set(DEFAULT_POLICY)
        if unknown:
            raise ValueError("unknown policy key(s): " + ", ".join(sorted(unknown)))
        policy.update(raw)
    if policy.get("schema") != POLICY_SCHEMA:
        raise ValueError(f"policy schema must be {POLICY_SCHEMA}")
    for key in ("source_extensions", "exclude_dirs", "exclude_globs"):
        values = policy.get(key)
        if not isinstance(values, list) or not all(isinstance(x, str) and x for x in values):
            raise ValueError(f"policy {key} must be a string list")
        policy[key] = sorted(set(values))
    policy["source_extensions"] = sorted(
        x if x.startswith(".") else f".{x}" for x in policy["source_extensions"]
    )
    for key in ("duplicate_window_lines", "duplicate_min_chars"):
        if not isinstance(policy.get(key), int) or policy[key] < 1:
            raise ValueError(f"policy {key} must be a positive integer")
    return policy


def load_policy(path=None):
    if not path:
        return normalize_policy()
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("policy must be a JSON object")
    return normalize_policy(raw)


def resolve_scopes(root, scopes):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"root is not a directory: {root}")
    out = []
    for value in scopes or ["."]:
        item = (root / value).resolve()
        try:
            item.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"scope escapes root: {value}") from exc
        if not item.exists():
            raise ValueError(f"scope does not exist: {value}")
        out.append(item)
    return root, out


def excluded(rel, policy):
    if any(part in policy["exclude_dirs"] for part in rel.parts):
        return True
    name, path = rel.name, rel.as_posix()
    return any(fnmatch.fnmatch(name, p) or fnmatch.fnmatch(path, p) for p in policy["exclude_globs"])


def is_manifest_name(name):
    return name in MANIFEST_NAMES or fnmatch.fnmatch(name, "requirements*.txt")


def ancestor_manifests(root, scopes):
    seen_dirs = set()
    for scope in scopes:
        directory = scope if scope.is_dir() else scope.parent
        while True:
            if directory not in seen_dirs:
                seen_dirs.add(directory)
                for child in sorted(directory.iterdir()):
                    if child.is_file() and is_manifest_name(child.name):
                        yield child
            if directory == root:
                break
            directory = directory.parent


def relevant_files(root, scopes, policy, warnings):
    seen = set()
    for scope in scopes:
        if scope.is_file():
            candidates = [scope]
        else:
            candidates = []
            for current, dirs, files in os.walk(scope, topdown=True, followlinks=False):
                base = Path(current)
                dirs[:] = [
                    name for name in dirs
                    if name not in policy["exclude_dirs"] and not excluded((base / name).relative_to(root), policy)
                ]
                candidates.extend(base / name for name in files)
        for path in candidates:
            rel = path.relative_to(root)
            if excluded(rel, policy) or rel.as_posix() in seen:
                continue
            seen.add(rel.as_posix())
            if path.is_symlink():
                warnings.append(f"symlink ignored: {rel.as_posix()}")
                continue
            is_source = path.suffix.lower() in policy["source_extensions"]
            is_manifest = is_manifest_name(rel.name)
            if is_source or is_manifest:
                yield path, rel, is_source, is_manifest

    for path in ancestor_manifests(root, scopes):
        rel = path.relative_to(root)
        if excluded(rel, policy) or rel.as_posix() in seen:
            continue
        seen.add(rel.as_posix())
        if path.is_symlink():
            warnings.append(f"symlink ignored: {rel.as_posix()}")
            continue
        yield path, rel, False, True


def read_utf8(path, rel, warnings):
    data = path.read_bytes()
    if b"\0" in data:
        warnings.append(f"binary-looking file ignored: {rel.as_posix()}")
        return None, data
    try:
        return data.decode("utf-8"), data
    except UnicodeDecodeError:
        warnings.append(f"non-UTF-8 file ignored: {rel.as_posix()}")
        return None, data


def dependency_names(rel, text):
    deps, warnings = set(), []
    if rel.name == "package.json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return deps, [f"invalid package.json: {rel.as_posix()}"]
        for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            if isinstance(data.get(section), dict):
                deps.update(f"npm:{name}" for name in data[section])
    elif fnmatch.fnmatch(rel.name, "requirements*.txt"):
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if line and not line.startswith(("-r", "--requirement", "-c", "--constraint")):
                name = re.split(r"[<>=!~;\s\[]", line, 1)[0]
                if name:
                    deps.add(f"python:{name.lower()}")
    elif rel.name == "pyproject.toml":
        match = re.search(r"(?ms)^dependencies\s*=\s*(\[.*?\])", text)
        if match:
            try:
                items = ast.literal_eval(match.group(1))
                for item in items if isinstance(items, list) else []:
                    name = re.split(r"[<>=!~;\s\[]", str(item), 1)[0]
                    if name:
                        deps.add(f"python:{name.lower()}")
            except (SyntaxError, ValueError):
                warnings.append(f"could not parse project dependencies: {rel.as_posix()}")
    elif rel.name == "Cargo.toml":
        section = ""
        families = ("dependencies", "dev-dependencies", "build-dependencies")
        subtable_dependency = None
        for raw in text.splitlines():
            line = raw.strip()
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
                subtable_dependency = None
                for family in families:
                    prefix = family + "."
                    marker = "." + family + "."
                    if section.startswith(prefix):
                        subtable_dependency = section[len(prefix):].split(".", 1)[0].strip("\"'")
                    elif marker in section:
                        subtable_dependency = section.rsplit(marker, 1)[1].split(".", 1)[0].strip("\"'")
                if subtable_dependency:
                    deps.add("cargo:" + subtable_dependency)
            elif (
                any(section == family or section.endswith("." + family) for family in families)
                and "=" in line
                and not line.startswith("#")
            ):
                deps.add("cargo:" + line.split("=", 1)[0].strip().strip("\"'"))
    elif rel.name == "go.mod":
        block = False
        for raw in text.splitlines():
            line = raw.strip()
            if line == "require (":
                block = True
                continue
            if block and line == ")":
                block = False
                continue
            if line.startswith("require "):
                line = line[8:].strip()
            elif not block:
                continue
            if line and not line.startswith("//"):
                deps.add("go:" + line.split()[0])
    return deps, warnings


def logical_lines(text):
    out = []
    for raw in text.splitlines():
        line = " ".join(raw.strip().split())
        if not line or line.startswith(("#", "//", "/*", "*", "*/")):
            continue
        if re.fullmatch(r"[{}()\[\];,]+", line):
            continue
        out.append(line)
    return out


def build_snapshot(root=".", scopes=None, policy=None):
    policy = normalize_policy(policy)
    root, scopes = resolve_scopes(root, scopes)
    warnings, files, deps, manifests = [], [], set(), []
    duplicate_hits = defaultdict(list)
    for path, rel, is_source, is_manifest in relevant_files(root, scopes, policy, warnings):
        text, raw = read_utf8(path, rel, warnings)
        if text is None:
            continue
        if is_manifest:
            found, issues = dependency_names(rel, text)
            deps.update(found)
            warnings.extend(issues)
            manifests.append(rel.as_posix())
        if not is_source:
            continue
        lines = text.splitlines()
        files.append({
            "path": rel.as_posix(), "bytes": len(raw), "lines": len(lines),
            "nonblank_lines": sum(bool(x.strip()) for x in lines),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
        logical = logical_lines(text)
        width = policy["duplicate_window_lines"]
        for i in range(len(logical) - width + 1):
            block = "\n".join(logical[i:i + width])
            if len(block) >= policy["duplicate_min_chars"]:
                duplicate_hits[digest(block)].append(f"{rel.as_posix()}:{i + 1}")
    files.sort(key=lambda x: x["path"])
    duplicates = [
        {"fingerprint": fp, "occurrences": locs}
        for fp, locs in sorted(duplicate_hits.items()) if len(locs) > 1
    ]
    metrics = {
        "source_files": len(files),
        "source_lines": sum(x["lines"] for x in files),
        "nonblank_lines": sum(x["nonblank_lines"] for x in files),
        "source_bytes": sum(x["bytes"] for x in files),
        "largest_file_lines": max((x["lines"] for x in files), default=0),
        "declared_dependencies": len(deps),
        "duplicate_fingerprints": len(duplicates),
    }
    payload = {
        "schema": SNAPSHOT_SCHEMA,
        "scopes": [p.relative_to(root).as_posix() or "." for p in scopes],
        "policy": policy,
        "policy_digest": digest(policy),
        "metrics": metrics,
        "files": files,
        "dependencies": sorted(deps),
        "manifests": sorted(set(manifests)),
        "duplicates": duplicates,
        "warnings": sorted(set(warnings)),
    }
    return {**payload, "digest": digest(payload)}


def verify_snapshot(snapshot):
    if snapshot.get("schema") != SNAPSHOT_SCHEMA:
        raise ValueError("invalid distill snapshot schema")
    supplied = snapshot.get("digest")
    payload = dict(snapshot)
    payload.pop("digest", None)
    if supplied != digest(payload):
        raise ValueError("snapshot digest mismatch")
    if snapshot.get("policy_digest") != digest(snapshot.get("policy")):
        raise ValueError("snapshot policy digest mismatch")


def compare_snapshot(before, root=".", expected_baseline_digest=None):
    verify_snapshot(before)
    if not expected_baseline_digest:
        raise ValueError("external baseline digest is required")
    if before["digest"] != expected_baseline_digest:
        raise ValueError("external baseline digest mismatch")
    current = build_snapshot(root, before["scopes"], before["policy"])
    delta = {k: current["metrics"][k] - before["metrics"][k] for k in current["metrics"]}
    improved = [k for k in LOWER_IS_BETTER if delta[k] < 0]
    regressed = [k for k in LOWER_IS_BETTER if delta[k] > 0]
    before_deps, after_deps = set(before["dependencies"]), set(current["dependencies"])
    added_deps = sorted(after_deps - before_deps)
    if added_deps:
        regressed = sorted(set(regressed + ["new_dependencies"]))
    if current["warnings"]:
        regressed = sorted(set(regressed + ["scan_warnings"]))
    before_files = {x["path"]: x["sha256"] for x in before["files"]}
    after_files = {x["path"]: x["sha256"] for x in current["files"]}
    verdict = "REVIEW_REQUIRED" if regressed else ("IMPROVED" if improved else "UNCHANGED")
    payload = {
        "schema": REPORT_SCHEMA,
        "baseline_digest": before["digest"],
        "current_snapshot_digest": current["digest"],
        "policy_digest": before["policy_digest"],
        "metrics_before": before["metrics"],
        "metrics_after": current["metrics"],
        "delta": delta,
        "improved_dimensions": improved,
        "regressed_dimensions": regressed,
        "file_changes": {
            "added": sorted(set(after_files) - set(before_files)),
            "removed": sorted(set(before_files) - set(after_files)),
            "changed": sorted(p for p in set(before_files) & set(after_files) if before_files[p] != after_files[p]),
        },
        "dependency_changes": {
            "added": added_deps,
            "removed": sorted(before_deps - after_deps),
        },
        "warnings": current["warnings"],
        "verdict": verdict,
        "limits": [
            "structural metrics are proxies, not a code-quality score",
            "UNCHANGED does not prove that no simpler implementation exists",
            "behavioral equivalence requires a separate WinCreator proof gate",
        ],
    }
    return {**payload, "digest": digest(payload)}, current


def write_json(path, value):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cmd_snapshot(args):
    try:
        snap = build_snapshot(args.root, args.scope, load_policy(args.policy))
        write_json(args.out, snap)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"[SNAPSHOT] {args.out} sha256={snap['digest']}")
    print(json.dumps(snap["metrics"], sort_keys=True))
    return 0


def cmd_verify(args):
    try:
        snap = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        verify_snapshot(snap)
        if snap["digest"] != args.expect_digest:
            raise ValueError("external baseline digest mismatch")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"[VERIFIED] {args.snapshot} sha256={snap['digest']}")
    return 0


def cmd_compare(args):
    try:
        before = json.loads(Path(args.before).read_text(encoding="utf-8"))
        report, current = compare_snapshot(before, args.root, args.baseline_digest)
        write_json(args.out, report)
        if args.current_out:
            write_json(args.current_out, current)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"[{report['verdict']}] {args.out} sha256={report['digest']}")
    print(json.dumps(report["delta"], sort_keys=True))
    if report["regressed_dimensions"]:
        print("[REVIEW] " + ", ".join(report["regressed_dimensions"]))
    return int(report["verdict"] == "REVIEW_REQUIRED")


def self_test():
    checks = []

    def check(name, ok):
        checks.append((name, bool(ok)))

    with tempfile.TemporaryDirectory(prefix="wincreator-distill-") as tmp:
        root = Path(tmp)
        (root / "package.json").write_text(json.dumps({"dependencies": {"a": "1", "b": "1"}}))
        block = "\n".join([
            "def alpha(value, fallback=0):",
            "    if value is not None and value > fallback:",
            "        normalized = value + 1",
            "        return normalized",
            "    result = fallback",
            "    return result",
        ])
        (root / "a.py").write_text(block + "\n\n" + block + "\n")
        before = build_snapshot(root)
        verify_snapshot(before)
        check("snapshot_digest", True)
        (root / "package.json").write_text(json.dumps({"dependencies": {"a": "1"}}))
        (root / "a.py").write_text(block + "\n")
        report, _ = compare_snapshot(before, root, before["digest"])
        check("improvement", report["verdict"] == "IMPROVED")
        check("dependency_removed", report["delta"]["declared_dependencies"] == -1)
        check("duplication_reduced", report["delta"]["duplicate_fingerprints"] < 0)
        simple = build_snapshot(root)
        (root / "b.py").write_text("print('extra')\n")
        report, _ = compare_snapshot(simple, root, simple["digest"])
        check("regression_review", report["verdict"] == "REVIEW_REQUIRED")
        broken = dict(simple)
        broken["metrics"] = dict(simple["metrics"])
        broken["metrics"]["source_files"] += 1
        try:
            verify_snapshot(broken)
            caught = False
        except ValueError:
            caught = True
        check("tamper_caught", caught)
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"self-test: {sum(ok for _, ok in checks)}/{len(checks)} passed")
    return 0 if all(ok for _, ok in checks) else 2


def build_parser():
    parser = argparse.ArgumentParser(prog="distill_check")
    parser.add_argument("--self-test", action="store_true")
    sub = parser.add_subparsers(dest="command")
    snap = sub.add_parser("snapshot")
    snap.add_argument("--root", default=".")
    snap.add_argument("--scope", action="append", default=[])
    snap.add_argument("--policy")
    snap.add_argument("--out", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--snapshot", required=True)
    verify.add_argument("--expect-digest", required=True)
    comp = sub.add_parser("compare")
    comp.add_argument("--before", required=True)
    comp.add_argument("--baseline-digest", required=True)
    comp.add_argument("--root", default=".")
    comp.add_argument("--out", required=True)
    comp.add_argument("--current-out")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if args.command == "snapshot":
        return cmd_snapshot(args)
    if args.command == "verify":
        return cmd_verify(args)
    if args.command == "compare":
        return cmd_compare(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
