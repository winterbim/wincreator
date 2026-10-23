"""End-to-end governance against the real, pinned VEOR checkout (G02).

These tests need ``VEOR_HOME`` pointing at the checkout pinned in
``tools/veor-pin.json`` and Node.js >= 22; otherwise they skip. Run them with
``python3 tools/veor_gate.py`` to turn a missing checkout into a failure instead
of a skip.

Nothing here simulates a human approval: the test holds an approval key the way
an operator would and signs the challenge out of band. The harness never sees
that private key.
"""

import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import REPO, harness_contract

from harness import governance, governed
from harness.governance import GovernanceUnavailable

NODE = shutil.which("node")
VEOR_HOME = os.environ.get("VEOR_HOME")
REQUIRED = os.environ.get("WINCREATOR_REQUIRE_VEOR") == "1"
PIN_PATH = REPO / "tools" / "veor-pin.json"


def _unavailable_reason():
    if not VEOR_HOME or not os.path.isdir(VEOR_HOME):
        return "VEOR_HOME is not configured"
    if NODE is None:
        return "node is not installed"
    try:
        status = governance.check(str(PIN_PATH), home=VEOR_HOME)
    except GovernanceUnavailable as error:
        return str(error)
    if not status.ready:
        return "; ".join(status.reasons)
    return None


@pytest.fixture(scope="session")
def pinned():
    reason = _unavailable_reason()
    if reason:
        message = f"pinned VEOR is unavailable: {reason}"
        if REQUIRED:
            pytest.fail(message)
        pytest.skip(message)
    return {
        "home": VEOR_HOME,
        "node": NODE,
        "pin": governance.load_pin(str(PIN_PATH)),
        "cli": os.path.join(VEOR_HOME, "src", "cli.js"),
    }


@pytest.fixture
def veor(tmp_path, pinned):
    home = tmp_path / "runtime"
    (home / "policies").mkdir(parents=True)
    policy = home / "policies" / "wincreator.policy.json"
    policy.write_text(
        json.dumps(
            {
                "kind": "veor.policy/v1",
                "name": "wincreator-g02",
                "filesystem": {
                    "readRoots": [str(tmp_path)],
                    "writeRoots": [str(tmp_path)],
                },
                "mcp": {
                    "denyUnknownTools": True,
                    "tools": {
                        governed.GATE_TOOL: {
                            "decision": "ALLOW",
                            "capability": "wincreator.gate.execute",
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    keys = tmp_path / "keys"
    keys.mkdir()
    for kind in ("receipt", "approval"):
        subprocess.run(
            [
                pinned["node"],
                pinned["cli"],
                "keygen",
                kind,
                "--private",
                str(keys / f"{kind}.key"),
                "--public",
                str(keys / f"{kind}.pub.pem"),
            ],
            check=True,
            capture_output=True,
        )
    runtime_dir = tmp_path / "veor-runtime"
    env = {
        "VEOR_POLICY": str(policy),
        "VEOR_RUNTIME_DIR": str(runtime_dir),
        "VEOR_APPROVAL_PUBLIC_KEY": str(keys / "approval.pub.pem"),
        "VEOR_RECEIPT_PRIVATE_KEY": str(keys / "receipt.key"),
    }
    config = governed.GovernanceConfig.for_root(
        REPO,
        pin=str(PIN_PATH),
        home=VEOR_HOME,
        node=pinned["node"],
        receipt_public_key=str(keys / "receipt.pub.pem"),
        sidecar_env=env,
    )
    return {
        "config": config,
        "pinned": pinned,
        "env": env,
        "keys": keys,
        "pending": runtime_dir / "approvals" / "pending",
    }


def _pending_challenge(veor):
    files = sorted(veor["pending"].glob("*.json"))
    assert files, "VEOR wrote no pending challenge to approve"
    return files[0]


def _approve(veor, challenge_path):
    subprocess.run(
        [
            veor["pinned"]["node"],
            veor["pinned"]["cli"],
            "approve",
            str(challenge_path),
            "--private",
            str(veor["keys"] / "approval.key"),
        ],
        check=True,
        capture_output=True,
    )
    return json.loads(challenge_path.read_text(encoding="utf-8"))


def _lite(executor, command=None):
    return executor.register(
        harness_contract(
            tier="lite",
            command=command or [sys.executable, "-c", "print('governed gate ok')"],
        )
    )


def _governed(note):
    return [
        event
        for event in note.store.events("H1")
        if event["type"] == "governance_bound"
    ]


# ----------------------------------------------------------------------- tests
def test_pinned_checkout_is_the_audited_one(pinned):
    status = governance.check(str(PIN_PATH), home=pinned["home"])

    assert status.ready, status.reasons
    assert status.pin_digest
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=pinned["home"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert head == pinned["pin"]["commit"]
    assert governance.node_major(status.node) >= pinned["pin"]["node_major"]


def test_review_then_one_shot_approval_then_verified_receipt(
    harness_executor, veor
):
    _lite(harness_executor)

    with pytest.raises(governed.GovernanceDenied) as denied:
        governed.run(harness_executor, "H1", veor["config"])
    assert "REVIEW" in str(denied.value)
    assert harness_executor.store.latest_proof("H1") is None
    blocked = harness_executor.store.events("H1")[-1]["payload"]
    assert blocked["code"] == "DECISION_REVIEW"
    assert blocked["challenge_id"]

    challenge = _approve(veor, _pending_challenge(veor))
    assert challenge["tool"] == governed.GATE_TOOL

    result = governed.run(harness_executor, "H1", veor["config"])

    assert result["state"] == "SUCCEEDED"
    summary = result["governance"]
    assert summary["checks"]["signature"] is True
    assert summary["checks"]["digest"] is True
    bound = _governed(harness_executor)[0]["payload"]
    assert bound["verification"]["checks"]["signature"] is True
    assert bound["sandbox"]["os_enforced"] is False
    decision_path = bound["decision_path"]
    with open(decision_path, encoding="utf-8") as handle:
        document = json.load(handle)
    assert document["decision"] == "ALLOW"
    assert "ONE_SHOT_APPROVAL" in document["reasons"]
    assert document["approval"] == "CONSUMED"
    assert document["veor_commit"] == veor["pinned"]["pin"]["commit"]

    # VEOR's own verifier, invoked by hand, agrees with the journaled verdict.
    verified = subprocess.run(
        [
            veor["pinned"]["node"],
            veor["pinned"]["cli"],
            "verify",
            "receipt",
            bound["receipt_path"],
            "--public",
            str(veor["keys"] / "receipt.pub.pem"),
        ],
        capture_output=True,
        text=True,
    )
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["checks"]["signature"] is True

    problems, _summary = harness_executor.verify(governance_config=veor["config"])
    assert problems == []


def test_the_approval_is_consumed_exactly_once(harness_executor, veor):
    _lite(harness_executor)
    with pytest.raises(governed.GovernanceDenied):
        governed.run(harness_executor, "H1", veor["config"])
    _approve(veor, _pending_challenge(veor))
    assert governed.run(harness_executor, "H1", veor["config"])["state"] == "SUCCEEDED"
    attempts = len(harness_executor.store.get_task("H1").attempts)

    with pytest.raises(governed.GovernanceDenied):
        governed.run(harness_executor, "H1", veor["config"], retry_reason="second run")

    assert len(harness_executor.store.get_task("H1").attempts) == attempts
    assert harness_executor.store.events("H1")[-1]["payload"]["code"] == (
        "DECISION_REVIEW"
    )


def test_a_consumed_approval_cannot_be_replayed(harness_executor, veor):
    _lite(harness_executor)
    with pytest.raises(governed.GovernanceDenied):
        governed.run(harness_executor, "H1", veor["config"])
    challenge_path = _pending_challenge(veor)
    _approve(veor, challenge_path)
    challenge_bytes = challenge_path.read_bytes()
    signed_path = veor["pending"].parent / "approved" / challenge_path.name
    signed_bytes = signed_path.read_bytes()
    assert governed.run(harness_executor, "H1", veor["config"])["state"] == "SUCCEEDED"

    # Put the challenge and its signature back exactly as they were.
    challenge_path.write_bytes(challenge_bytes)
    signed_path.write_bytes(signed_bytes)
    with pytest.raises(governed.GovernanceDenied):
        governed.run(harness_executor, "H1", veor["config"], retry_reason="replay")
    assert harness_executor.store.events("H1")[-1]["payload"]["code"] == (
        "DECISION_REVIEW"
    )


def test_a_tampered_receipt_fails_real_signature_verification(harness_executor, veor):
    _lite(harness_executor)
    with pytest.raises(governed.GovernanceDenied):
        governed.run(harness_executor, "H1", veor["config"])
    _approve(veor, _pending_challenge(veor))
    governed.run(harness_executor, "H1", veor["config"])
    receipt_path = _governed(harness_executor)[0]["payload"]["receipt_path"]

    with open(receipt_path, encoding="utf-8") as handle:
        original = json.load(handle)

    def verify_file():
        return subprocess.run(
            [
                veor["pinned"]["node"],
                veor["pinned"]["cli"],
                "verify",
                "receipt",
                receipt_path,
                "--public",
                str(veor["keys"] / "receipt.pub.pem"),
            ],
            capture_output=True,
            text=True,
        )

    # A changed body breaks the body digest.
    tampered = json.loads(json.dumps(original))
    tampered["body"]["executed"] = False
    with open(receipt_path, "w", encoding="utf-8") as handle:
        json.dump(tampered, handle)
    verified = verify_file()
    assert verified.returncode == 1
    document = json.loads(verified.stdout)
    assert document["ok"] is False
    assert "DIGEST_MISMATCH" in document["reasons"]

    # A flipped signature byte keeps the digest and still fails the signature.
    flipped = json.loads(json.dumps(original))
    signature = flipped["signature"]
    # The last base64url character only carries padding bits, so flip the first.
    flipped["signature"] = ("A" if signature[0] != "A" else "B") + signature[1:]
    with open(receipt_path, "w", encoding="utf-8") as handle:
        json.dump(flipped, handle)
    verified = verify_file()
    assert verified.returncode == 1
    document = json.loads(verified.stdout)
    assert document["reasons"] == ["BAD_SIGNATURE"]

    problems, _summary = harness_executor.verify(governance_config=veor["config"])
    assert any("governance:" in problem for problem in problems)


def test_a_validly_signed_receipt_for_another_capture_is_still_refused(
    harness_executor, veor
):
    _lite(harness_executor)
    with pytest.raises(governed.GovernanceDenied):
        governed.run(harness_executor, "H1", veor["config"])
    _approve(veor, _pending_challenge(veor))
    governed.run(harness_executor, "H1", veor["config"])
    bound = _governed(harness_executor)[0]["payload"]
    with open(bound["decision_path"], encoding="utf-8") as handle:
        document = json.load(handle)

    # A real signature over the real tool/args, but a different result digest.
    sidecar = governance.Sidecar(
        veor["pinned"]["home"],
        veor["pinned"]["pin"],
        node=veor["pinned"]["node"],
        env=veor["env"],
    )
    forged = sidecar.receipt(
        {
            "at": document["at"],
            "tool": document["tool"],
            "argsDigest": document["args_digest"],
            "decision": "ALLOW",
            "policyDigest": document["policy_digest"],
        },
        "e" * 64,
        executed=True,
    )
    assert forged["signature"]
    with open(bound["receipt_path"], "w", encoding="utf-8") as handle:
        json.dump(forged, handle)

    problems, _summary = harness_executor.verify(governance_config=veor["config"])
    assert problems
    assert any("RESULT_DIGEST_MISMATCH" in problem for problem in problems)


def test_decision_artifact_carries_no_raw_arguments(harness_executor, veor):
    _lite(
        harness_executor,
        command=[sys.executable, "-c", "print('ok')", "--token=SECRET-VALUE-42"],
    )
    with pytest.raises(governed.GovernanceDenied):
        governed.run(harness_executor, "H1", veor["config"])
    _approve(veor, _pending_challenge(veor))
    governed.run(harness_executor, "H1", veor["config"])

    bound = _governed(harness_executor)[0]["payload"]
    with open(bound["decision_path"], encoding="utf-8") as handle:
        text = handle.read()

    assert "SECRET-VALUE-42" not in text
    assert "args_digest" in text
