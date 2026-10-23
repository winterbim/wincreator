#!/usr/bin/env python3
"""Check the pinned optional VEOR sidecar without installing or cloning it.

Exit codes: 0 READY | 3 BLOCKED (a normal state, not a crash) | 2 self-test fail.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from harness import governance  # noqa: E402


def _git_repo(home, version):
    os.makedirs(home, exist_ok=True)
    with open(os.path.join(home, "package.json"), "w", encoding="utf-8") as handle:
        json.dump({"name": "veor-runtime", "version": version}, handle)
    env_args = [
        "-c",
        "user.email=veor-check@example.invalid",
        "-c",
        "user.name=veor-check",
    ]
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=home, check=True)
    subprocess.run(["git", *env_args, "add", "package.json"], cwd=home, check=True)
    subprocess.run(
        ["git", *env_args, "commit", "-qm", "fake pinned checkout"], cwd=home, check=True
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=home, capture_output=True, text=True, check=True
    ).stdout.strip()


def _write_pin(path, commit, version="0.4.0-dev.6", entrypoint="src/kernel/stdio.js"):
    document = {
        "schema": governance.PIN_SCHEMA,
        "repository": "https://example.invalid/veor",
        "commit": commit,
        "package_version": version,
        "node_major": 22,
        "audited_at": "2026-10-23",
        "audit_document": "docs/VEOR_GUARDIAN_AUDIT.md",
        "sidecar": {
            "entrypoint": entrypoint,
            "protocol": "json-lines",
            "receipt_verify": ["src/cli.js", "verify", "receipt"],
        },
        "vendored": False,
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2)
    return path


def self_test():
    results = []

    def check(name, condition):
        results.append((name, bool(condition)))

    with tempfile.TemporaryDirectory(prefix="veor-check-") as directory:
        home = os.path.join(directory, "veor")
        commit = _git_repo(home, "0.4.0-dev.6")
        os.makedirs(os.path.join(home, "src", "kernel"))
        open(os.path.join(home, "src", "kernel", "stdio.js"), "w").close()
        pin_path = _write_pin(os.path.join(directory, "pin.json"), commit)

        ready = governance.check(pin_path, home=home, node_version_override="v22.1.0")
        check("ready_when_fully_pinned", ready.ready)

        wrong_version = governance.check(
            _write_pin(os.path.join(directory, "pin-version.json"), commit, version="9.9.9"),
            home=home,
            node_version_override="v22.1.0",
        )
        check(
            "wrong_package_version_blocks",
            not wrong_version.ready
            and any("does not match" in reason for reason in wrong_version.reasons),
        )

        wrong_commit = governance.check(
            _write_pin(os.path.join(directory, "pin-commit.json"), "0" * 40),
            home=home,
            node_version_override="v22.1.0",
        )
        check(
            "wrong_commit_blocks",
            not wrong_commit.ready and any("pinned at" in reason for reason in wrong_commit.reasons),
        )

        missing_entrypoint = governance.check(
            _write_pin(
                os.path.join(directory, "pin-entry.json"),
                commit,
                entrypoint="src/missing.js",
            ),
            home=home,
            node_version_override="v22.1.0",
        )
        check("missing_entrypoint_blocks", not missing_entrypoint.ready)

        no_node = governance.check(pin_path, home=home, node_version_override="")
        check(
            "missing_node_blocks",
            not no_node.ready and any("Node.js" in reason for reason in no_node.reasons),
        )

        no_pin = governance.check(os.path.join(directory, "absent.json"), home=home)
        check("missing_pin_blocks", not no_pin.ready)

        good_receipt = json.dumps(
            {
                "ok": True,
                "kind": "veor.receipt-verify/v1",
                "checks": {"structure": True, "digest": True, "signature": True},
            }
        )
        check(
            "receipt_ok_accepted",
            governance.interpret_receipt_result(0, good_receipt)["ok"] is True,
        )
        try:
            governance.interpret_receipt_result(1, "{}")
        except governance.GovernanceUnavailable:
            check("receipt_failure_rejected", True)
        else:
            check("receipt_failure_rejected", False)

    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    passed = sum(value for _name, value in results)
    print(f"self-test: {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pin", default=os.path.join(ROOT, "tools", "veor-pin.json")
    )
    parser.add_argument("--home")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    status = governance.check(args.pin, home=args.home)
    if args.json:
        print(
            json.dumps(
                {
                    "kind": "wincreator.veor-status/v1",
                    "status": status.status,
                    "reasons": list(status.reasons),
                    "pin_digest": status.pin_digest,
                    "veor_home": status.veor_home,
                    "node": status.node,
                },
                indent=2,
            )
        )
    else:
        print(f"VEOR SIDECAR: {status.status}")
        if status.pin_digest:
            print(f"  pin sha256={status.pin_digest}")
        if status.veor_home:
            print(f"  home={status.veor_home}")
        if status.node:
            print(f"  node={status.node}")
        for reason in status.reasons:
            print(f"  - {reason}")
    return 0 if status.ready else 3


if __name__ == "__main__":
    sys.exit(main())
