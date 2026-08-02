#!/usr/bin/env python3
"""Safely migrate known WinCreator v1/v2 Claude Code installations."""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


LEGACY_NAMES = ("Skill_WinCreator", "skill-wincreator")
ACTIVE_NAME = "wincreator"


def _timestamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def _validate_target(skills_root, candidate):
    root = skills_root.resolve()
    parent = candidate.resolve(strict=False).parent
    if parent != root:
        raise ValueError(f"refusing path outside skills root: {candidate}")


def _run_validators(installed):
    commands = (
        [sys.executable, str(installed / "scripts" / "ledger_check.py"), "--self-test"],
        [sys.executable, str(installed / "scripts" / "wincreator.py"), "--self-test"],
        [sys.executable, str(installed / "scripts" / "package_check.py"), "--self-test"],
        [sys.executable, str(installed / "scripts" / "package_check.py"), str(installed)],
    )
    outputs = []
    for command in commands:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        outputs.append(result.stdout)
    return outputs


def migrate(source, skills_root, run_validation=True):
    source = Path(source).resolve()
    skills_root = Path(skills_root).resolve()
    if source.name != ACTIVE_NAME or not (source / "SKILL.md").is_file():
        raise ValueError("source must be a valid wincreator skill directory")
    skills_root.mkdir(parents=True, exist_ok=True)
    targets = [skills_root / name for name in (*LEGACY_NAMES, ACTIVE_NAME)]
    for target in targets:
        _validate_target(skills_root, target)

    backup_root = skills_root / ".wincreator-backups" / _timestamp()
    backups = []
    for target in targets:
        if not target.exists():
            continue
        backup_root.mkdir(parents=True, exist_ok=True)
        archive_base = backup_root / target.name
        backup = Path(
            shutil.make_archive(str(archive_base), "zip", root_dir=target)
        )
        backups.append(backup)

    staging_parent = Path(tempfile.mkdtemp(prefix=".wincreator-install-", dir=skills_root))
    staged = staging_parent / ACTIVE_NAME
    try:
        shutil.copytree(source, staged, symlinks=False)
        for target in targets:
            if target.exists():
                shutil.rmtree(target)
        os.replace(staged, skills_root / ACTIVE_NAME)
    finally:
        shutil.rmtree(staging_parent, ignore_errors=True)

    installed = skills_root / ACTIVE_NAME
    validation = _run_validators(installed) if run_validation else []
    version = subprocess.run(
        [sys.executable, str(installed / "scripts" / "wincreator.py"), "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {
        "installed_name": ACTIVE_NAME,
        "installed_path": installed,
        "backups": backups,
        "validation": validation,
        "version": version,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default=str(Path(__file__).resolve().parents[1] / "skill" / ACTIVE_NAME),
    )
    parser.add_argument(
        "--skills-root",
        default=str(Path.home() / ".claude" / "skills"),
    )
    parser.add_argument("--skip-validation", action="store_true")
    args = parser.parse_args()
    result = migrate(args.source, args.skills_root, not args.skip_validation)
    for backup in result["backups"]:
        print(f"backup: {backup}")
    print(f"installed: {result['installed_path']}")
    print(f"active version: {result['version']}")


if __name__ == "__main__":
    main()
