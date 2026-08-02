import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skill" / "wincreator"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def wincreator():
    return load_module("wincreator_under_test", SKILL / "scripts" / "wincreator.py")


@pytest.fixture(scope="session")
def package_check():
    return load_module("package_check_under_test", SKILL / "scripts" / "package_check.py")


@pytest.fixture(scope="session")
def ledger_check():
    return load_module("ledger_check_under_test", SKILL / "scripts" / "ledger_check.py")


@pytest.fixture(scope="session")
def package_builder():
    return load_module("package_builder_under_test", REPO / "tools" / "build_package.py")


@pytest.fixture(scope="session")
def migration_tool():
    return load_module("migration_tool_under_test", REPO / "tools" / "migrate_v2_to_v3.py")


@pytest.fixture(scope="session")
def release_policy():
    return load_module("release_policy_under_test", REPO / "tools" / "release_policy.py")


@pytest.fixture(scope="session")
def release_deprecation_tool():
    return load_module(
        "release_deprecation_tool_under_test",
        REPO / "tools" / "deprecate_old_releases.py",
    )


@pytest.fixture
def ledger(tmp_path):
    path = tmp_path / "PROOF_LEDGER.md"
    path.write_text(
        "# Test ledger\n\n"
        "| ID | Level | Claim | Gate (what proves it) | Status | Evidence |\n"
        "|----|-------|-------|------------------------|--------|----------|\n"
        "| P1 | Micro | parser rejects malformed input | `python check_parser.py` | CLAIMED | |\n"
        "| P2 | Meso | export preserves every row | `python check_export.py` | CLAIMED | |\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def clean_git_repo(tmp_path):
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "WinCreator Tests"], cwd=tmp_path, check=True)
    (tmp_path / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "seed.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=tmp_path, check=True)
    return tmp_path


def create_ledger(path, rows):
    body = [
        "| ID | Level | Claim | Gate (what proves it) | Status | Evidence |",
        "|----|-------|-------|------------------------|--------|----------|",
    ]
    body.extend(rows)
    Path(path).write_text("\n".join(body) + "\n", encoding="utf-8")


def prove(wincreator, ledger, tmp_path, command=None, **kwargs):
    command = command or [sys.executable, "-c", "print('gate passed')"]
    return wincreator.run_and_attest(
        "P1",
        command,
        ledger=str(ledger),
        attest_dir=str(tmp_path / "attestations"),
        cwd=str(tmp_path),
        quiet=True,
        tier=kwargs.pop("tier", "standard"),
        **kwargs,
    )
