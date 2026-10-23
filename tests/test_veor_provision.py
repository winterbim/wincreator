"""Hermetic tests for exact-commit VEOR provisioning.

These build a throwaway git repository, so they need no network and never touch
the pinned checkout used by the integration suite.
"""

import json
import subprocess

import pytest


def _seed(tmp_path, version="0.4.0-dev.6", entrypoint=True):
    source = tmp_path / "source"
    (source / "src" / "kernel").mkdir(parents=True)
    (source / "package.json").write_text(
        json.dumps({"name": "veor-runtime", "version": version}), encoding="utf-8"
    )
    if entrypoint:
        (source / "src" / "kernel" / "stdio.js").write_text("// sidecar\n", encoding="utf-8")
    identity = ["-c", "user.email=t@example.invalid", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=source, check=True)
    subprocess.run(["git", *identity, "add", "-A"], cwd=source, check=True)
    subprocess.run(["git", *identity, "commit", "-qm", "seed"], cwd=source, check=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=source, capture_output=True, text=True, check=True
    ).stdout.strip()
    return source, commit


def _pin(tmp_path, commit, version="0.4.0-dev.6", entrypoint="src/kernel/stdio.js"):
    path = tmp_path / "pin.json"
    path.write_text(
        json.dumps(
            {
                "schema": "wincreator.veor-pin/v1",
                "repository": "https://example.invalid/veor",
                "commit": commit,
                "package_version": version,
                "node_major": 22,
                "audited_at": "2026-10-24",
                "audit_document": "docs/VEOR_GUARDIAN_AUDIT.md",
                "sidecar": {
                    "entrypoint": entrypoint,
                    "protocol": "json-lines",
                    "receipt_verify": ["src/cli.js", "verify", "receipt"],
                },
                "vendored": False,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_provision_checks_out_the_exact_pinned_commit(veor_provision, tmp_path):
    source, commit = _seed(tmp_path)
    pin = _pin(tmp_path, commit)
    destination = tmp_path / "checkout"

    summary = veor_provision.provision(
        str(pin), str(destination), source=str(source), install=False
    )

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=destination,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert summary["commit"] == commit
    assert head == commit
    assert summary["clean"] is True
    assert summary["installed"] is False


def test_provision_refuses_a_non_empty_destination(veor_provision, tmp_path):
    source, commit = _seed(tmp_path)
    pin = _pin(tmp_path, commit)
    destination = tmp_path / "occupied"
    destination.mkdir()
    (destination / "keep.txt").write_text("do not overwrite", encoding="utf-8")

    with pytest.raises(veor_provision.ProvisionError, match="not empty"):
        veor_provision.provision(
            str(pin), str(destination), source=str(source), install=False
        )

    assert (destination / "keep.txt").read_text(encoding="utf-8") == "do not overwrite"


def test_provision_refuses_a_wrong_package_version(veor_provision, tmp_path):
    source, commit = _seed(tmp_path)
    pin = _pin(tmp_path, commit, version="9.9.9")

    with pytest.raises(veor_provision.ProvisionError, match="does not match"):
        veor_provision.provision(
            str(pin), str(tmp_path / "checkout"), source=str(source), install=False
        )


def test_provision_refuses_a_missing_entrypoint(veor_provision, tmp_path):
    source, commit = _seed(tmp_path, entrypoint=False)
    pin = _pin(tmp_path, commit)

    with pytest.raises(veor_provision.ProvisionError, match="entrypoint missing"):
        veor_provision.provision(
            str(pin), str(tmp_path / "checkout"), source=str(source), install=False
        )
