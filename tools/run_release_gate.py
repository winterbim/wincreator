#!/usr/bin/env python3
"""Run every source-tree gate that can be proven before public publication."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(command):
    print("+", " ".join(str(part) for part in command), flush=True)
    subprocess.run([str(part) for part in command], cwd=ROOT, check=True)


def main():
    run([PYTHON, "-m", "compileall", "-q", "skill/wincreator/scripts", "tools", "tests"])
    run([PYTHON, "skill/wincreator/scripts/ledger_check.py", "--self-test"])
    run([PYTHON, "skill/wincreator/scripts/wincreator.py", "--self-test"])
    run([PYTHON, "skill/wincreator/scripts/package_check.py", "--self-test"])
    run([PYTHON, "skill/wincreator/scripts/package_check.py", "skill/wincreator"])
    for ledger in (
        "PROOF_LEDGER.md",
        "PROOF_LEDGER-v2-install.md",
        "PROOF_LEDGER-evolution.md",
    ):
        run([PYTHON, "skill/wincreator/scripts/ledger_check.py", ledger])
    run([PYTHON, "-m", "pytest", "-q"])
    run([PYTHON, "tools/build_package.py", "--source", "skill/wincreator", "dist"])
    print("SOURCE RELEASE GATE: PASS")


if __name__ == "__main__":
    main()
