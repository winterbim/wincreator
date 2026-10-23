import ast
import dataclasses
import json
import shutil
import subprocess

import pytest

from conftest import REPO

from harness import governance

PIN_TEMPLATE = {
    "schema": "wincreator.veor-pin/v1",
    "repository": "https://example.invalid/veor",
    "commit": "0" * 40,
    "package_version": "0.4.0-dev.6",
    "node_major": 22,
    "audited_at": "2026-10-23",
    "audit_document": "docs/VEOR_GUARDIAN_AUDIT.md",
    "sidecar": {
        "entrypoint": "src/kernel/stdio.js",
        "protocol": "json-lines",
        "receipt_verify": ["src/cli.js", "verify", "receipt"],
    },
    "vendored": False,
}


def _checkout(tmp_path, version="0.4.0-dev.6"):
    home = tmp_path / "veor"
    (home / "src" / "kernel").mkdir(parents=True)
    (home / "package.json").write_text(
        json.dumps({"name": "veor-runtime", "version": version}), encoding="utf-8"
    )
    (home / "src" / "kernel" / "stdio.js").write_text("// fake\n", encoding="utf-8")
    identity = [
        "-c",
        "user.email=tests@example.invalid",
        "-c",
        "user.name=WinCreator Tests",
    ]
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=home, check=True)
    subprocess.run(["git", *identity, "add", "."], cwd=home, check=True)
    subprocess.run(
        ["git", *identity, "commit", "-qm", "seed"], cwd=home, check=True
    )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=home, capture_output=True, text=True, check=True
    ).stdout.strip()
    return home, commit


def _pin_file(tmp_path, commit, **overrides):
    document = dict(PIN_TEMPLATE)
    document["commit"] = commit
    document.update(overrides)
    path = tmp_path / "pin.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _sidecar(tmp_path, response=None, seen=None):
    home, commit = _checkout(tmp_path)
    pin = governance.load_pin(str(_pin_file(tmp_path, commit)))
    sidecar = governance.Sidecar(str(home), pin)

    def fake_request(method, params):
        if seen is not None:
            seen["method"] = method
            seen["params"] = params
        return response

    sidecar._request = fake_request
    return sidecar


def test_status_ready_only_when_every_prerequisite_matches(tmp_path):
    home, commit = _checkout(tmp_path)
    status = governance.check(
        str(_pin_file(tmp_path, commit)), home=str(home), node_version_override="v22.1.0"
    )

    assert status.ready
    assert status.pin_digest
    assert status.reasons == ()


def test_status_blocks_when_checkout_is_absent(tmp_path):
    status = governance.check(
        str(_pin_file(tmp_path, "a" * 40)),
        home=str(tmp_path / "absent"),
        node_version_override="v22.1.0",
    )

    assert not status.ready
    assert any("not configured" in reason for reason in status.reasons)


def test_status_blocks_when_package_version_differs(tmp_path):
    home, commit = _checkout(tmp_path, version="0.3.0")
    status = governance.check(
        str(_pin_file(tmp_path, commit)), home=str(home), node_version_override="v22.1.0"
    )

    assert not status.ready
    assert any("does not match pinned" in reason for reason in status.reasons)


def test_status_blocks_when_pinned_commit_differs(tmp_path):
    home, _commit = _checkout(tmp_path)
    status = governance.check(
        str(_pin_file(tmp_path, "b" * 40)),
        home=str(home),
        node_version_override="v22.1.0",
    )

    assert not status.ready
    assert any("pinned at" in reason for reason in status.reasons)


def test_status_blocks_when_the_checkout_is_modified(tmp_path):
    home, commit = _checkout(tmp_path)
    (home / "src" / "kernel" / "stdio.js").write_text(
        "// patched after the audit\n", encoding="utf-8"
    )

    status = governance.check(
        str(_pin_file(tmp_path, commit)), home=str(home), node_version_override="v22.1.0"
    )

    assert not status.ready
    assert any("local modifications" in reason for reason in status.reasons)


def test_status_blocks_without_git_metadata(tmp_path):
    home, commit = _checkout(tmp_path)
    shutil.rmtree(home / ".git")
    status = governance.check(
        str(_pin_file(tmp_path, commit)), home=str(home), node_version_override="v22.1.0"
    )

    assert not status.ready
    assert any("no git metadata" in reason for reason in status.reasons)


def test_status_blocks_when_node_is_missing(tmp_path):
    home, commit = _checkout(tmp_path)
    status = governance.check(
        str(_pin_file(tmp_path, commit)), home=str(home), node_version_override=""
    )

    assert not status.ready
    assert any("Node.js" in reason for reason in status.reasons)


def test_status_blocks_when_node_is_too_old(tmp_path):
    home, commit = _checkout(tmp_path)
    status = governance.check(
        str(_pin_file(tmp_path, commit)), home=str(home), node_version_override="v18.19.0"
    )

    assert not status.ready
    assert any("older than" in reason for reason in status.reasons)


@pytest.mark.parametrize(
    "field", ["schema", "commit", "package_version", "node_major", "sidecar", "vendored"]
)
def test_pin_load_rejects_missing_field(tmp_path, field):
    document = dict(PIN_TEMPLATE)
    document.pop(field)
    path = tmp_path / "pin.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(governance.GovernanceUnavailable, match="missing field"):
        governance.load_pin(str(path))


def test_pin_load_rejects_unknown_schema_and_bad_commit(tmp_path):
    path = tmp_path / "pin.json"
    path.write_text(json.dumps({**PIN_TEMPLATE, "schema": "nope"}), encoding="utf-8")
    with pytest.raises(governance.GovernanceUnavailable, match="schema"):
        governance.load_pin(str(path))

    path.write_text(json.dumps({**PIN_TEMPLATE, "commit": "abc"}), encoding="utf-8")
    with pytest.raises(governance.GovernanceUnavailable, match="40-character"):
        governance.load_pin(str(path))


def test_sidecar_returns_a_deny_without_becoming_allow(tmp_path):
    sidecar = _sidecar(
        tmp_path,
        response={
            "decision": "DENY",
            "reasons": ["UNKNOWN_TOOL"],
            "policyDigest": "a" * 64,
        },
    )

    decision = sidecar.decide("filesystem.write_file", {"path": "x"})

    assert decision.decision == "DENY"
    assert decision.is_deny and not decision.is_allow
    assert decision.reasons == ("UNKNOWN_TOOL",)


def test_sidecar_default_annotations_are_fail_closed(tmp_path):
    seen = {}
    sidecar = _sidecar(
        tmp_path,
        response={"decision": "REVIEW", "reasons": ["MCP_SIDE_EFFECT_HINT"], "policyDigest": "b" * 64},
        seen=seen,
    )

    sidecar.decide("filesystem.write_file", {"path": "x"})

    assert seen["method"] == "decide"
    assert seen["params"]["tool"]["annotations"] == {
        "readOnlyHint": False,
        "destructiveHint": True,
    }


@pytest.mark.parametrize(
    "response",
    [
        {"decision": "ALLOW_ALL", "reasons": [], "policyDigest": "a" * 64},
        {"decision": "ALLOW", "reasons": [], "policyDigest": None},
        {"decision": "ALLOW", "reasons": "not-a-list", "policyDigest": "a" * 64},
        {"decision": None, "reasons": [], "policyDigest": "a" * 64},
        {},
    ],
)
def test_sidecar_malformed_response_blocks(tmp_path, response):
    sidecar = _sidecar(tmp_path, response=response)

    with pytest.raises(governance.GovernanceUnavailable):
        sidecar.decide("filesystem.read_file", {"path": "x"})


def test_sidecar_parse_rejects_garbage_and_errors():
    with pytest.raises(governance.GovernanceUnavailable, match="no matching JSON"):
        governance.Sidecar._parse("not json\n")
    with pytest.raises(governance.GovernanceUnavailable, match="sidecar error"):
        governance.Sidecar._parse('{"id":1,"error":{"code":"KERNEL_ERROR"}}\n')


def test_sidecar_unknown_advisory_blocks(tmp_path):
    sidecar = _sidecar(tmp_path, response={"decision": "ALLOW", "reasons": [], "policyDigest": "a" * 64})

    with pytest.raises(governance.GovernanceUnavailable, match="unknown advisory"):
        sidecar.decide("filesystem.read_file", {}, advisory="MAYBE")


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_sidecar_timeout_blocks_instead_of_allowing(tmp_path):
    home, commit = _checkout(tmp_path)
    (home / "src" / "kernel" / "stdio.js").write_text(
        "setTimeout(() => {}, 30000);\n", encoding="utf-8"
    )
    pin = governance.load_pin(str(_pin_file(tmp_path, commit)))

    with pytest.raises(governance.GovernanceUnavailable, match="cannot run VEOR sidecar"):
        governance.Sidecar(str(home), pin, timeout=0.4).decide(
            "filesystem.read_file", {"path": "x"}
        )


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_sidecar_node_protocol_end_to_end(tmp_path):
    home, commit = _checkout(tmp_path)
    script = home / "src" / "kernel" / "stdio.js"
    script.write_text(
        "\n".join(
            [
                "const readline = require('node:readline');",
                "const rl = readline.createInterface({ input: process.stdin });",
                "rl.on('line', (line) => {",
                "  const message = JSON.parse(line);",
                "  if (message.method === 'decide') {",
                "    process.stdout.write(JSON.stringify({ id: message.id, result: {",
                "      decision: 'DENY',",
                "      reasons: ['UNKNOWN_TOOL'],",
                "      policyDigest: 'c'.repeat(64),",
                "    } }) + '\\n');",
                "  }",
                "});",
                "",
            ]
        ),
        encoding="utf-8",
    )
    pin = governance.load_pin(str(_pin_file(tmp_path, commit)))

    decision = governance.Sidecar(str(home), pin).decide(
        "veor.self.delete", {"path": "CONSTITUTION.md"}
    )

    assert decision.decision == "DENY"
    assert decision.policy_digest == "c" * 64


def test_receipt_accepts_only_a_clean_verifier_result():
    document = governance.interpret_receipt_result(
        0,
        json.dumps(
            {
                "ok": True,
                "kind": "veor.receipt-verify/v1",
                "checks": {"structure": True, "digest": True, "signature": True},
            }
        ),
    )

    assert document["ok"] is True


@pytest.mark.parametrize(
    "returncode, stdout",
    [
        (1, '{"ok": false, "kind": "veor.receipt-verify/v1", "checks": {"digest": true, "signature": true}}'),
        (0, "not json"),
        (0, '{"ok": true, "kind": "veor.receipt-verify/v1", "checks": {"digest": true, "signature": false}}'),
        (0, '{"ok": true, "kind": "veor.receipt-verify/v1", "checks": {"digest": false, "signature": true}}'),
        (0, '{"ok": false, "kind": "veor.receipt-verify/v1"}'),
    ],
)
def test_receipt_rejects_every_non_positive_result(returncode, stdout):
    with pytest.raises(governance.GovernanceUnavailable):
        governance.interpret_receipt_result(returncode, stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_receipt_verifier_cli_is_invoked_and_parsed(tmp_path):
    home, commit = _checkout(tmp_path)
    (home / "src" / "cli.js").write_text(
        "process.stdout.write(JSON.stringify({ ok: true, kind: 'veor.receipt-verify/v1',"
        " checks: { structure: true, digest: true, signature: true } }) + '\\n');\n",
        encoding="utf-8",
    )
    pin = governance.load_pin(str(_pin_file(tmp_path, commit)))
    receipt = tmp_path / "receipt.json"
    receipt.write_text("{}", encoding="utf-8")
    public_key = tmp_path / "receipt.pub.pem"
    public_key.write_text("-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----\n")

    document = governance.verify_receipt(
        str(home), pin, str(receipt), str(public_key)
    )

    assert document["ok"] is True


def test_bind_result_is_deterministic_and_changes_with_the_capture():
    first = governance.bind_result("a" * 64, 0, "b" * 64, "c" * 64)
    second = governance.bind_result("a" * 64, 0, "b" * 64, "c" * 64)
    other = governance.bind_result("d" * 64, 0, "b" * 64, "c" * 64)

    assert first == second
    assert first["digest"] != other["digest"]
    assert first["payload"]["attestation_digest"] == "a" * 64


def test_bind_result_rejects_malformed_digests():
    with pytest.raises(governance.GovernanceUnavailable):
        governance.bind_result("short", 0, "b" * 64, "c" * 64)
    with pytest.raises(governance.GovernanceUnavailable):
        governance.bind_result("a" * 64, 0, "b" * 64, "not-a-digest")


def test_authority_and_imports_governance_cannot_touch_the_ledger():
    source = (REPO / "harness" / "governance.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)

    forbidden = {
        module
        for module in imported
        if module.startswith(("harness.store", "harness.kernel", "harness.journal"))
        or module == "wincreator"
    }
    assert forbidden == set()
    assert "update_ledger" not in source
    assert "review_attestation" not in source
    assert "record_review" not in source


def test_authority_decision_cannot_carry_a_ledger_status():
    fields = {field.name for field in dataclasses.fields(governance.Decision)}

    assert fields == {"decision", "reasons", "policy_digest", "raw"}
    assert "status" not in fields


@pytest.mark.parametrize(
    "name",
    [
        "G02-01.json",
        "G02-02.json",
        "G02-03.json",
        "G02-04.json",
        "G02-05.json",
        "G02-06.json",
    ],
)
def test_g02_contracts_parse_and_bind_existing_files(name):
    from harness.contracts import TaskContract

    path = REPO / "contracts" / "g02" / name
    contract = TaskContract.from_dict(json.loads(path.read_text(encoding="utf-8")))

    assert contract.task_id == path.stem
    assert contract.require_review is True
    assert contract.max_attempts == 2
    for relative in contract.gate.files:
        assert (REPO / relative).is_file(), relative
