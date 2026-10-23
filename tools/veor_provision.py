#!/usr/bin/env python3
"""Provision the pinned VEOR checkout at its exact commit.

WinCreator never clones or installs VEOR on its own: a governed run only
consumes a checkout provided through ``VEOR_HOME``. This tool is the explicit,
operator-invoked way to create that checkout reproducibly:

1. clone the pin's repository (or an operator-supplied mirror);
2. check out the pinned commit and refuse any other HEAD;
3. refuse a dirty tree, a different package version or a missing entrypoint;
4. optionally install the lockfile dependencies and run VEOR's own tests,
   requiring the pinned test count.

It does not run VEOR, does not write the pin, and never touches an existing
non-empty destination.

Exit codes: 0 PROVISIONED | 2 refused/failed | 0 self-test pass.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from harness import governance  # noqa: E402

PASS_COUNT = re.compile(r"(?:#|\u2139)\s*pass\s+(\d+)")


class ProvisionError(RuntimeError):
    """Provisioning refused or failed; nothing should be trusted."""


def _run(argv, cwd=None, timeout=900):
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "npm_config_audit": "false", "npm_config_fund": "false"},
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ProvisionError(f"cannot run {argv[0]}: {error}")


def _checked(argv, cwd=None, timeout=900):
    result = _run(argv, cwd=cwd, timeout=timeout)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip()[-500:]
        raise ProvisionError(
            f"{' '.join(argv)} exited {result.returncode}: {tail or 'no output'}"
        )
    return result.stdout or ""


def _version(destination):
    path = os.path.join(destination, "package.json")
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle).get("version")
    except (OSError, ValueError) as error:
        raise ProvisionError(f"cannot read {path}: {error}")


def _pass_count(output):
    counts = [int(match.group(1)) for match in PASS_COUNT.finditer(output or "")]
    return max(counts) if counts else None


def provision(
    pin_path,
    destination,
    source=None,
    install=True,
    run_tests=False,
    timeout=900,
):
    """Create a checkout at the pin's exact commit and prove it is that commit."""
    pin = governance.load_pin(pin_path)
    destination = os.path.abspath(destination)
    if os.path.exists(destination) and os.listdir(destination):
        raise ProvisionError(
            f"destination is not empty: {destination}; refusing to overwrite it"
        )
    if os.path.exists(destination) and not os.path.isdir(destination):
        raise ProvisionError(f"destination is not a directory: {destination}")
    checkout_source = source or pin["repository"]

    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
    _checked(["git", "clone", "--quiet", "--no-checkout", checkout_source, destination])
    _checked(["git", "checkout", "--quiet", "--detach", pin["commit"]], cwd=destination)

    head = _checked(["git", "rev-parse", "HEAD"], cwd=destination).strip()
    if head != pin["commit"]:
        raise ProvisionError(f"checkout is at {head}, pinned at {pin['commit']}")
    status = _checked(["git", "status", "--porcelain=v1"], cwd=destination).strip()
    if status:
        raise ProvisionError(
            "the provisioned checkout is dirty, so the pinned commit no longer "
            "describes the code that would run"
        )
    version = _version(destination)
    if version != pin["package_version"]:
        raise ProvisionError(
            f"package version {version} does not match pinned {pin['package_version']}"
        )
    entrypoint = os.path.join(destination, pin["sidecar"]["entrypoint"])
    if not os.path.isfile(entrypoint):
        raise ProvisionError(f"sidecar entrypoint missing: {pin['sidecar']['entrypoint']}")

    installed = False
    if install:
        if not shutil.which("npm"):
            raise ProvisionError("npm is not available; pass --skip-install")
        if not os.path.isfile(os.path.join(destination, "package-lock.json")):
            raise ProvisionError("package-lock.json is missing; cannot install reproducibly")
        _checked(
            ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
            cwd=destination,
            timeout=timeout,
        )
        installed = True

    tests = None
    if run_tests:
        if not shutil.which("node"):
            raise ProvisionError("node is not available; cannot run VEOR's tests")
        result = _run(["node", "--test"], cwd=destination, timeout=timeout)
        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "").strip()[-500:]
            raise ProvisionError(
                f"VEOR tests exited {result.returncode}: {tail or 'no output'}"
            )
        tests = _pass_count(result.stdout)
        expected = pin.get("expected_tests")
        if expected is not None and tests != expected:
            raise ProvisionError(
                f"VEOR reported {tests!r} passing tests, pinned {expected}"
            )

    return {
        "kind": "veor-provision/v1",
        "source": checkout_source,
        "commit": head,
        "package_version": version,
        "destination": destination,
        "clean": True,
        "installed": installed,
        "tests": tests,
        "pin_sha256": governance.pin_digest(pin),
    }


def _pin_file(directory, commit, version):
    document = {
        "schema": governance.PIN_SCHEMA,
        "repository": "https://example.invalid/veor",
        "commit": commit,
        "package_version": version,
        "node_major": 22,
        "audited_at": "2026-10-24",
        "audit_document": "docs/VEOR_GUARDIAN_AUDIT.md",
        "sidecar": {
            "entrypoint": "src/kernel/stdio.js",
            "protocol": "json-lines",
            "receipt_verify": ["src/cli.js", "verify", "receipt"],
        },
        "vendored": False,
    }
    path = os.path.join(directory, "pin.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2)
        handle.write("\n")
    return path


def _seed_repository(directory, version):
    os.makedirs(os.path.join(directory, "src", "kernel"))
    with open(os.path.join(directory, "package.json"), "w", encoding="utf-8") as handle:
        json.dump({"name": "veor-runtime", "version": version}, handle)
    open(os.path.join(directory, "src", "kernel", "stdio.js"), "w").close()
    identity = ["-c", "user.email=veor@example.invalid", "-c", "user.name=veor"]
    _checked(["git", "init", "-q", "-b", "main"], cwd=directory)
    _checked(["git", *identity, "add", "-A"], cwd=directory)
    _checked(["git", *identity, "commit", "-qm", "seed"], cwd=directory)
    return _checked(["git", "rev-parse", "HEAD"], cwd=directory).strip()


def self_test():
    results = []

    def check(name, condition):
        results.append((name, bool(condition)))

    with tempfile.TemporaryDirectory(prefix="veor-provision-") as directory:
        source = os.path.join(directory, "source")
        os.makedirs(source)
        commit = _seed_repository(source, "0.4.0-dev.6")
        pin = _pin_file(directory, commit, "0.4.0-dev.6")

        destination = os.path.join(directory, "checkout")
        summary = provision(pin, destination, source=source, install=False)
        check("provisions_the_pinned_commit", summary["commit"] == commit)
        check("records_a_clean_checkout", summary["clean"] is True)
        check(
            "refuses_a_non_empty_destination",
            _raises(lambda: provision(pin, destination, source=source, install=False)),
        )

        wrong_version = _pin_file(directory, commit, "9.9.9")
        check(
            "refuses_a_wrong_package_version",
            _raises(
                lambda: provision(
                    wrong_version,
                    os.path.join(directory, "wrong-version"),
                    source=source,
                    install=False,
                )
            ),
        )

        wrong_commit = _pin_file(directory, "0" * 40, "0.4.0-dev.6")
        check(
            "refuses_a_wrong_commit",
            _raises(
                lambda: provision(
                    wrong_commit,
                    os.path.join(directory, "wrong-commit"),
                    source=source,
                    install=False,
                )
            ),
        )

    passed = sum(1 for _name, ok in results if ok)
    for name, ok in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"self-test: {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


def _raises(callback):
    try:
        callback()
    except ProvisionError:
        return True
    return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pin", default=os.path.join(ROOT, "tools", "veor-pin.json"))
    parser.add_argument("--dest", help="empty directory to create the checkout in")
    parser.add_argument(
        "--source",
        default=None,
        help="git URL or local mirror to clone; defaults to the pin's repository",
    )
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--out", default=None, help="write the summary JSON here")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()
    if not args.dest:
        parser.error("--dest is required unless --self-test is used")
    try:
        summary = provision(
            args.pin,
            args.dest,
            source=args.source,
            install=not args.skip_install,
            run_tests=args.run_tests,
        )
    except ProvisionError as error:
        print(f"VEOR PROVISION REFUSED: {error}", file=sys.stderr)
        return 2
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
            handle.write("\n")
    print(
        f"VEOR PROVISIONED: commit={summary['commit']} "
        f"version={summary['package_version']} dest={summary['destination']} "
        f"installed={summary['installed']} tests={summary['tests']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
