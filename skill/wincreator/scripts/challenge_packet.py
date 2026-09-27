#!/usr/bin/env python3
"""Create a blind-safe reviewer packet from a WinCreator capture."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import wincreator

PACKET_SCHEMA = "wincreator.challenge-packet/v1"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _stream_view(stream):
    return {
        "sha256": stream.get("sha256"),
        "original_bytes": stream.get("original_bytes"),
        "stored_bytes": stream.get("stored_bytes"),
        "truncated": stream.get("truncated"),
        "body_stored": stream.get("body_stored"),
        "tail": stream.get("tail", ""),
    }


def _git_view(git):
    keys = (
        "available", "commit", "tree", "branch", "dirty", "submodules",
        "untracked_digest", "worktree_digest",
    )
    return {key: git.get(key) for key in keys if key in git}


def create_packet(attestation_path):
    ok, problems = wincreator.verify_attestation(attestation_path)
    if not ok:
        raise ValueError("capture failed verification: " + "; ".join(problems))
    document = json.loads(Path(attestation_path).read_text(encoding="utf-8"))
    payload = document["payload"]
    packet_payload = {
        "attestation_digest": document["digest"]["value"],
        "claim": payload["claim"],
        "capture": payload["capture"],
        "command": payload["command"],
        "stdout": _stream_view(payload["stdout"]),
        "stderr": _stream_view(payload["stderr"]),
        "files": payload.get("files", []),
        "git": _git_view(payload.get("git", {})),
        "policy": {
            "tier": payload.get("policy", {}).get("tier"),
            "private": payload.get("policy", {}).get("private"),
        },
    }
    return {
        "schema": PACKET_SCHEMA,
        "payload": packet_payload,
        "digest": digest(packet_payload),
    }


def verify_packet(packet, attestation_path=None):
    if packet.get("schema") != PACKET_SCHEMA:
        raise ValueError("invalid challenge packet schema")
    payload = packet.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("challenge packet payload must be an object")
    if packet.get("digest") != digest(payload):
        raise ValueError("challenge packet digest mismatch")
    if "builder" in payload or "environment" in payload or "ledger" in payload:
        raise ValueError("challenge packet leaks builder-context metadata")
    if attestation_path:
        ok, problems = wincreator.verify_attestation(attestation_path)
        if not ok:
            raise ValueError("capture failed verification: " + "; ".join(problems))
        capture = json.loads(Path(attestation_path).read_text(encoding="utf-8"))
        if payload.get("attestation_digest") != capture["digest"]["value"]:
            raise ValueError("challenge packet does not bind this capture")
        if payload.get("claim") != capture["payload"]["claim"]:
            raise ValueError("challenge packet claim does not match capture")
    return True


def load_packet(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_packet(packet, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(packet, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def self_test():
    results = []

    def check(name, value):
        results.append((name, bool(value)))

    import tempfile

    with tempfile.TemporaryDirectory(prefix="wincreator-packet-") as directory:
        ledger = Path(directory) / "PROOF_LEDGER.md"
        ledger.write_text(
            "| ID | Level | Claim | Gate (what proves it) | Status | Evidence |\n"
            "|----|-------|-------|------------------------|--------|----------|\n"
            "| P1 | Micro | command succeeds | python | CLAIMED | |\n",
            encoding="utf-8",
        )
        attestation, path, code = wincreator.run_and_attest(
            "P1",
            [sys.executable, "-c", "print('evidence')"],
            ledger=str(ledger),
            attest_dir=str(Path(directory) / "attestations"),
            cwd=directory,
            quiet=True,
            tier="standard",
            builder="builder-secret",
        )
        check("capture_pass", code == 0)
        packet = create_packet(path)
        check("packet_verifies", verify_packet(packet, path))
        check("builder_hidden", "builder" not in packet["payload"])
        check("environment_hidden", "environment" not in packet["payload"])
        packet["payload"]["capture"]["status"] = "CAPTURED_FAIL"
        try:
            verify_packet(packet, path)
        except ValueError:
            check("tamper_caught", True)
        else:
            check("tamper_caught", False)

    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    passed = sum(value for _name, value in results)
    print(f"self-test: {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("--attestation", required=True)
    create.add_argument("--out", required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("--packet", required=True)
    verify.add_argument("--attestation")

    sub.add_parser("self-test")

    args = parser.parse_args(argv)
    if args.command == "self-test":
        return self_test()
    if args.command == "create":
        try:
            packet = create_packet(args.attestation)
            write_packet(packet, args.out)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(f"CHALLENGE PACKET: {args.out} sha256={packet['digest']}")
        return 0
    try:
        verify_packet(load_packet(args.packet), args.attestation)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print("CHALLENGE PACKET: VERIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
