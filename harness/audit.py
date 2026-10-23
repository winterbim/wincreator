"""G00 audit: measured inventory plus the repository's reference gates.

This is not prose about the repository. Every number in the produced report is
derived from the tree at run time, and every reference gate is executed with
its real exit code and output tail retained. A failed gate fails the audit.
"""

import json
import os
import platform
import subprocess
import sys
import time

from harness import RUNTIME_VERSION
from harness.util import file_digest, iso_time, portable_path

AUDIT_SCHEMA = "wincreator.harness.audit/v1"
TAIL_CHARS = 2000
GATE_TIMEOUT_SECONDS = 900

INVENTORY_GLOBS = (
    "skill/wincreator/scripts/*.py",
    "skill/wincreator/schemas/*.json",
    "tools/*.py",
    "harness/*.py",
    "tests/test_*.py",
    "bench/*.py",
    "bench/adapters/*.py",
    "contracts/g02/*.json",
    "tools/veor-pin.json",
)

REFERENCE_GATES = (
    (
        "compile",
        [sys.executable, "-m", "compileall", "-q", "skill/wincreator/scripts",
         "tools", "harness", "tests", "bench"],
    ),
    ("ledger_check_self_test",
     [sys.executable, "skill/wincreator/scripts/ledger_check.py", "--self-test"]),
    ("wincreator_self_test",
     [sys.executable, "skill/wincreator/scripts/wincreator.py", "--self-test"]),
    ("distill_check_self_test",
     [sys.executable, "skill/wincreator/scripts/distill_check.py", "--self-test"]),
    ("adequacy_check_self_test",
     [sys.executable, "skill/wincreator/scripts/adequacy_check.py", "self-test"]),
    ("challenge_packet_self_test",
     [sys.executable, "skill/wincreator/scripts/challenge_packet.py", "self-test"]),
    ("package_check_self_test",
     [sys.executable, "skill/wincreator/scripts/package_check.py", "--self-test"]),
    ("pytest", [sys.executable, "-m", "pytest", "-q"]),
)


def _git(root, *args):
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _line_count(path):
    with open(path, "rb") as handle:
        return handle.read().count(b"\n") + 1


def _inventory(root):
    entries = []
    seen = set()
    for pattern in INVENTORY_GLOBS:
        directory, name_pattern = os.path.split(pattern)
        absolute = os.path.join(root, directory)
        if not os.path.isdir(absolute):
            continue
        for name in sorted(os.listdir(absolute)):
            if not _matches(name, name_pattern):
                continue
            path = os.path.join(absolute, name)
            relative = portable_path(os.path.relpath(path, root))
            if relative in seen or not os.path.isfile(path):
                continue
            seen.add(relative)
            entries.append(
                {
                    "path": relative,
                    "lines": _line_count(path),
                    "sha256": file_digest(path),
                    "bytes": os.path.getsize(path),
                }
            )
    return sorted(entries, key=lambda item: item["path"])


def _matches(name, pattern):
    if pattern == "*.py":
        return name.endswith(".py")
    if pattern == "*.json":
        return name.endswith(".json")
    if pattern == "*.md":
        return name.endswith(".md")
    if pattern.startswith("test_") and pattern.endswith(".py"):
        return name.startswith("test_") and name.endswith(".py")
    return name == pattern


def _read_version(root):
    path = os.path.join(root, "skill", "wincreator", "VERSION")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return handle.read().strip() or None


def collect_facts(root):
    inventory = _inventory(root)
    status = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    return {
        "root": portable_path(os.path.abspath(root)),
        "generated_at": iso_time(),
        "runtime_version": RUNTIME_VERSION,
        "skill_version": _read_version(root),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "node": _node_version(),
        "git": {
            "available": status is not None,
            "commit": _git(root, "rev-parse", "HEAD"),
            "branch": _git(root, "rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(status) if status is not None else None,
        },
        "counts": {
            "inventory_files": len(inventory),
            "python_files": sum(1 for item in inventory if item["path"].endswith(".py")),
            "test_files": sum(
                1 for item in inventory if os.path.basename(item["path"]).startswith("test_")
            ),
            "schema_files": sum(1 for item in inventory if item["path"].endswith(".json")),
        },
        "inventory": inventory,
    }


def _node_version():
    try:
        result = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _run_gate(root, name, argv):
    started = time.monotonic()
    try:
        result = subprocess.run(
            argv, cwd=root, capture_output=True, text=True, timeout=GATE_TIMEOUT_SECONDS
        )
        exit_code = result.returncode
        stdout = result.stdout or ""
        stderr = result.stderr or ""
    except subprocess.TimeoutExpired:
        exit_code = 124
        stdout = ""
        stderr = f"gate timed out after {GATE_TIMEOUT_SECONDS}s"
    except OSError as error:
        exit_code = 127
        stdout = ""
        stderr = f"cannot execute gate: {error}"
    return {
        "name": name,
        "argv": list(argv),
        "exit_code": exit_code,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "stdout_tail": stdout[-TAIL_CHARS:],
        "stderr_tail": stderr[-TAIL_CHARS:],
    }


def run_audit(root, include_gates=True):
    root = os.path.abspath(root)
    facts = collect_facts(root)
    gates = [
        _run_gate(root, name, argv) for name, argv in REFERENCE_GATES
    ] if include_gates else []
    return {
        "schema": AUDIT_SCHEMA,
        "facts": facts,
        "reference_gates": gates,
        "summary": {
            "gates_run": len(gates),
            "gates_passed": sum(1 for gate in gates if gate["exit_code"] == 0),
            "gates_failed": sum(1 for gate in gates if gate["exit_code"] != 0),
        },
    }


def render_markdown(report):
    facts = report["facts"]
    git = facts["git"]
    summary = report["summary"]
    lines = [
        "# G00 audit snapshot — harness runtime",
        "",
        "Generated by `python3 -m harness audit`. This file is a **snapshot**, not a",
        "standing claim: every value below was derived from the tree at generation",
        "time. Regenerate it rather than trusting a stale copy.",
        "",
        f"- generated_at: `{facts['generated_at']}`",
        f"- branch / commit: `{git['branch'] or 'n/a'}` / `{git['commit'] or 'n/a'}`",
        f"- working tree dirty: `{git['dirty']}`",
        f"- skill VERSION: `{facts['skill_version']}`",
        f"- harness runtime: `{facts['runtime_version']}`",
        f"- python: `{facts['python']}` — node: `{facts['node'] or 'absent'}`",
        f"- platform: `{facts['platform']}`",
        "",
        "## Reference gates (executed)",
        "",
        "| Gate | Exit | Duration |",
        "|---|---|---|",
    ]
    for gate in report["reference_gates"]:
        lines.append(
            f"| `{gate['name']}` | {gate['exit_code']} | {gate['duration_ms']} ms |"
        )
    lines += [
        "",
        f"Executed: {summary['gates_run']} — passed: {summary['gates_passed']} — "
        f"failed: {summary['gates_failed']}",
        "",
        "## Inventory",
        "",
        f"{facts['counts']['inventory_files']} files "
        f"({facts['counts']['python_files']} Python, "
        f"{facts['counts']['test_files']} test files, "
        f"{facts['counts']['schema_files']} schemas).",
        "",
        "| File | Lines | sha256 (12) |",
        "|---|---|---|",
    ]
    for item in facts["inventory"]:
        lines.append(f"| `{item['path']}` | {item['lines']} | `{item['sha256'][:12]}` |")
    lines += [
        "",
        "## Reproduce",
        "",
        "```bash",
        "python3 -m harness audit --out .harness-artifacts/g00-audit.json "
        "--markdown docs/HARNESS_AUDIT_G00.md",
        "```",
        "",
        "## Honest limits",
        "",
        "- The audit runs gates; it does not judge whether those gates prove a claim.",
        "- A dirty tree is recorded as dirty: the snapshot describes the working tree,",
        "  not a released commit.",
        "- Node is recorded only because the VEOR sidecar decision depends on it, not",
        "  because the runtime requires it.",
        "",
    ]
    return "\n".join(lines)


def write_report(report, json_path, markdown_path=None):
    json_path = os.path.abspath(json_path)
    os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=False)
        handle.write("\n")
    if markdown_path:
        markdown_path = os.path.abspath(markdown_path)
        os.makedirs(os.path.dirname(markdown_path) or ".", exist_ok=True)
        with open(markdown_path, "w", encoding="utf-8") as handle:
            handle.write(render_markdown(report))
    return json_path, markdown_path
