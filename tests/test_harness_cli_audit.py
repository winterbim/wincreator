import json
import os
import subprocess
import sys

from conftest import REPO


def _cli(root, *args):
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(REPO) + os.pathsep + environment.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "harness", "--root", str(root), *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=environment,
    )


def test_cli_init_add_run_status_verify(tmp_path):
    assert _cli(tmp_path, "init").returncode == 0
    added = _cli(
        tmp_path,
        "add",
        "--id",
        "C1",
        "--name",
        "cli lite task",
        "--claim",
        "the cli gate executes through the proof kernel",
        "--level",
        "Micro",
        "--tier",
        "lite",
        "--",
        sys.executable,
        "-c",
        "print('cli ok')",
    )
    assert added.returncode == 0, added.stderr
    assert "[REGISTERED] C1" in added.stdout

    status = _cli(tmp_path, "status")
    assert status.returncode == 0
    assert "C1" in status.stdout

    ran = _cli(tmp_path, "run", "C1")
    assert ran.returncode == 0, ran.stderr
    assert "[SUCCEEDED] C1" in ran.stdout

    verified = _cli(tmp_path, "verify", "--require-complete")
    assert verified.returncode == 0, verified.stdout
    assert "VERIFY OK" in verified.stdout


def test_cli_standard_task_reports_review_gate(tmp_path):
    assert _cli(tmp_path, "init").returncode == 0
    added = _cli(
        tmp_path,
        "add",
        "--id",
        "C2",
        "--name",
        "cli standard task",
        "--claim",
        "a standard task needs an independent review",
        "--tier",
        "standard",
        "--",
        sys.executable,
        "-c",
        "print('standard ok')",
    )
    assert added.returncode == 0, added.stderr

    ran = _cli(tmp_path, "run", "C2")

    assert ran.returncode == 3
    assert "AWAITING_REVIEW" in ran.stdout
    assert "harness review" in ran.stdout
    assert _cli(tmp_path, "verify").returncode == 0
    assert _cli(tmp_path, "verify", "--require-complete").returncode == 1


def test_cli_reports_missing_store(tmp_path):
    result = _cli(tmp_path, "verify")

    assert result.returncode == 2
    assert "no harness store" in result.stderr


def test_cli_rejects_unknown_contract_field(tmp_path):
    assert _cli(tmp_path, "init").returncode == 0
    contract = tmp_path / "contract.json"
    contract.write_text(
        json.dumps(
            {
                "task_id": "C3",
                "name": "bad",
                "claim": "bad contract",
                "level": "Micro",
                "tier": "lite",
                "gate": {"command": [sys.executable, "-c", "print(1)"]},
                "surprise": True,
            }
        ),
        encoding="utf-8",
    )

    result = _cli(tmp_path, "add", "--contract", str(contract))

    assert result.returncode == 2
    assert "unsupported field" in result.stderr


def test_audit_without_gates_writes_measured_inventory(tmp_path):
    out = tmp_path / "audit.json"
    markdown = tmp_path / "audit.md"

    result = _cli(
        REPO,
        "audit",
        "--no-gates",
        "--out",
        str(out),
        "--markdown",
        str(markdown),
        "--quiet",
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(out.read_text(encoding="utf-8"))
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(REPO), capture_output=True, text=True
    ).stdout.strip()
    assert report["schema"] == "wincreator.harness.audit/v1"
    assert report["facts"]["git"]["commit"] == commit
    assert report["reference_gates"] == []
    paths = {item["path"] for item in report["facts"]["inventory"]}
    assert "skill/wincreator/scripts/wincreator.py" in paths
    assert "harness/store.py" in paths
    assert "harness/journal.py" in paths
    assert "G00 audit snapshot" in markdown.read_text(encoding="utf-8")
