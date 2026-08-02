#!/usr/bin/env python3
"""wincreator.py — capture proof instead of narrating it.

`ledger_check.py` grades a *story* about a proof: it reads what a human (or an
agent) typed into an Evidence cell. This tool removes the typing. It runs the
gate itself, captures the raw result, binds it to the current commit, hashes
everything, writes a signable attestation, and only then updates the ledger —
refusing to write EVIDENCED when the command failed.

Stdlib only, no network, no config.

    python3 wincreator.py prove P-014 -- pytest tests/test_export.py -q
    python3 wincreator.py verify                     # re-hash every attestation
    python3 wincreator.py verify --ledger PROOF_LEDGER.md
    python3 wincreator.py --self-test

What `prove` captures, per run:
    the exact argv, exit code, duration, UTC start/end, cwd, host platform and
    python version, git commit + branch + dirty flag, sha256 of stdout, stderr
    and of any --file passed, plus a canonical sha256 digest over all of it
    (optionally HMAC-signed with $WINCREATOR_SIGNING_KEY).

Exit codes:
    prove   0 the gate passed (row written EVIDENCED)
            1 the gate failed (row written DISPROVEN — a retained negative)
            2 usage / ledger row not found / command not executable
    verify  0 every attestation matches its artifacts
            1 at least one mismatch (tampering or edited artifact)
            2 nothing to verify / unreadable
"""
import argparse
import hashlib
import hmac
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

VERSION = "3.0.0"
SCHEMA = "wincreator.attestation/v1"
DEFAULT_ATTEST_DIR = ".wincreator/attestations"
DEFAULT_LEDGER = "PROOF_LEDGER.md"
SIGNING_KEY_ENV = "WINCREATOR_SIGNING_KEY"
TAIL_CHARS = 2000

SPLIT_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")


# --------------------------------------------------------------- primitives
def _utc_now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_digest(payload: dict) -> str:
    """sha256 over a canonical JSON serialization — stable across machines."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")
    return sha256_bytes(blob)


def sign(digest: str):
    """HMAC-SHA256 the digest with $WINCREATOR_SIGNING_KEY, if set.

    Deliberately not public-key signing: a keyed MAC is stdlib-only and enough
    to make a local attestation unforgeable by anyone without the key. A
    Sigstore/in-toto backend is the documented next step, not a claim made here.
    """
    key = os.environ.get(SIGNING_KEY_ENV)
    if not key:
        return None
    key_bytes = key.encode("utf-8")
    return {
        "alg": "HMAC-SHA256",
        "key_id": hashlib.sha256(key_bytes).hexdigest()[:12],
        "value": hmac.new(key_bytes, digest.encode("utf-8"), hashlib.sha256).hexdigest(),
    }


def git_context(cwd: str) -> dict:
    def _git(*args):
        try:
            out = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                                 text=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return None
        return out.stdout.strip() if out.returncode == 0 else None

    commit = _git("rev-parse", "HEAD")
    if commit is None:
        return {"available": False}
    status = _git("status", "--porcelain")
    return {
        "available": True,
        "commit": commit,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(status),
        "remote": _git("config", "--get", "remote.origin.url"),
    }


# ------------------------------------------------------------------- ledger
def escape_cell(text: str) -> str:
    """Make arbitrary captured text safe inside a markdown table cell."""
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def find_row(lines, claim_id: str):
    """Return (index, cells) of the ledger row whose ID cell == claim_id."""
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = SPLIT_UNESCAPED_PIPE.split(stripped[1:-1])
        if len(cells) >= 6 and cells[0].strip() == claim_id:
            return i, cells
    return None, None


def update_ledger(ledger_path: str, claim_id: str, status: str, evidence: str):
    """Rewrite the Status and Evidence cells of one row. Returns the old status."""
    with open(ledger_path, encoding="utf-8") as f:
        text = f.read()
    lines = text.splitlines(keepends=True)
    idx, cells = find_row(lines, claim_id)
    if idx is None:
        raise KeyError(claim_id)
    old_status = cells[4].strip()
    cells[4] = f" {status} "
    cells[5] = f" {escape_cell(evidence)} "
    newline = "\n" if lines[idx].endswith("\n") else ""
    lines[idx] = "|" + "|".join(cells) + "|" + newline
    with open(ledger_path, "w", encoding="utf-8") as f:
        f.write("".join(lines))
    return old_status


# -------------------------------------------------------------------- prove
def run_and_attest(claim_id, command, ledger=None, files=(), attest_dir=DEFAULT_ATTEST_DIR,
                   cwd=None, timeout=None, quiet=False):
    """Execute `command`, capture everything, write the attestation.

    Returns (attestation_dict, attestation_path, exit_code).
    """
    cwd = cwd or os.getcwd()
    started = _utc_now()
    t0 = time.monotonic()
    try:
        proc = subprocess.run(command, cwd=cwd, capture_output=True, timeout=timeout)
    except FileNotFoundError as e:
        raise SystemExit(f"ERROR: cannot execute {command[0]!r}: {e}")
    except subprocess.TimeoutExpired:
        raise SystemExit(f"ERROR: command timed out after {timeout}s: {' '.join(command)}")
    duration_ms = int((time.monotonic() - t0) * 1000)
    finished = _utc_now()

    stdout, stderr = proc.stdout or b"", proc.stderr or b""
    if not quiet:
        sys.stdout.write(stdout.decode("utf-8", "replace"))
        sys.stderr.write(stderr.decode("utf-8", "replace"))

    run_dir = os.path.join(attest_dir, claim_id, started.strftime("%Y%m%dT%H%M%SZ"))
    os.makedirs(run_dir, exist_ok=True)
    for name, blob in (("stdout.log", stdout), ("stderr.log", stderr)):
        with open(os.path.join(run_dir, name), "wb") as f:
            f.write(blob)

    file_hashes = []
    for path in files:
        entry = {"path": path}
        if os.path.isfile(path):
            entry.update(sha256=sha256_file(path), bytes=os.path.getsize(path))
        else:
            entry["missing"] = True
        file_hashes.append(entry)

    verdict = "EVIDENCED" if proc.returncode == 0 else "DISPROVEN"
    payload = {
        "schema": SCHEMA,
        "tool_version": VERSION,
        "claim_id": claim_id,
        "ledger": os.path.relpath(ledger, cwd) if ledger else None,
        "verdict": verdict,
        "command": list(command),
        "command_string": " ".join(command),
        "exit_code": proc.returncode,
        "duration_ms": duration_ms,
        "started_at": _iso(started),
        "finished_at": _iso(finished),
        "cwd": cwd,
        "git": git_context(cwd),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "node": platform.node(),
        },
        "stdout": {
            "path": os.path.join(run_dir, "stdout.log"),
            "sha256": sha256_bytes(stdout),
            "bytes": len(stdout),
            "tail": stdout.decode("utf-8", "replace")[-TAIL_CHARS:],
        },
        "stderr": {
            "path": os.path.join(run_dir, "stderr.log"),
            "sha256": sha256_bytes(stderr),
            "bytes": len(stderr),
            "tail": stderr.decode("utf-8", "replace")[-TAIL_CHARS:],
        },
        "files": file_hashes,
    }
    digest = canonical_digest(payload)
    attestation = {"payload": payload, "digest": {"alg": "sha256", "value": digest}}
    signature = sign(digest)
    if signature:
        attestation["signature"] = signature

    att_path = os.path.join(run_dir, "attestation.json")
    with open(att_path, "w", encoding="utf-8") as f:
        json.dump(attestation, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return attestation, att_path, proc.returncode


def evidence_sentence(payload, att_path, digest) -> str:
    """The Evidence cell text — machine-written, and re-checkable by `verify`."""
    git = payload["git"]
    commit = (git.get("commit") or "")[:12] if git.get("available") else "no-git"
    dirty = "+dirty" if git.get("dirty") else ""
    tail = payload["stdout"]["tail"].strip().splitlines()
    last = tail[-1][:120] if tail else "(no stdout)"
    return (f"wincreator prove {payload['started_at']}: `{payload['command_string']}` "
            f"-> exit={payload['exit_code']} ({payload['duration_ms']} ms); "
            f"stdout tail: {last}; commit {commit}{dirty}; "
            f"attestation {att_path} sha256={digest}")


def cmd_prove(args):
    if not args.command:
        print("ERROR: no command. Usage: wincreator.py prove <ID> [options] "
              "-- <command...>  (the `--` is required: everything after it is "
              "the gate, verbatim)")
        return 2
    ledger = args.ledger
    if not args.no_ledger and not os.path.isfile(ledger):
        print(f"ERROR: ledger not found: {ledger} (use --no-ledger to attest only)")
        return 2
    attestation, att_path, exit_code = run_and_attest(
        args.claim_id, args.command, ledger=None if args.no_ledger else ledger,
        files=args.file, attest_dir=args.attest_dir, timeout=args.timeout)
    payload = attestation["payload"]
    digest = attestation["digest"]["value"]
    verdict = payload["verdict"]
    if not args.no_ledger:
        try:
            old = update_ledger(ledger, args.claim_id, verdict,
                                evidence_sentence(payload, att_path, digest))
        except KeyError:
            print(f"ERROR: no row with ID '{args.claim_id}' in {ledger} — "
                  f"attestation kept at {att_path}, ledger untouched")
            return 2
        print(f"\n[{verdict}] {args.claim_id}: {old} -> {verdict} in {ledger}")
    print(f"[ATTESTATION] {att_path} sha256={digest}"
          + (" (signed)" if "signature" in attestation else ""))
    if verdict == "DISPROVEN":
        print(f"[GATE FAILED] exit={exit_code} — the claim is recorded DISPROVEN, "
              f"not EVIDENCED. A failed gate cannot be written as a proof.")
        return 1
    return 0


# ------------------------------------------------------------------- verify
def verify_attestation(path, check_artifacts=True):
    """Return (ok, [problems]) for one attestation file."""
    problems = []
    try:
        with open(path, encoding="utf-8") as f:
            attestation = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return False, [f"unreadable: {e}"]
    payload = attestation.get("payload")
    recorded = attestation.get("digest", {}).get("value")
    if not payload or not recorded:
        return False, ["malformed attestation (missing payload or digest)"]
    if canonical_digest(payload) != recorded:
        problems.append("digest mismatch — the attestation body was edited")
    signature = attestation.get("signature")
    if signature:
        expected = sign(recorded)
        if expected is None:
            problems.append(f"signed with key_id {signature.get('key_id')} but "
                            f"${SIGNING_KEY_ENV} is not set — cannot verify")
        elif not hmac.compare_digest(expected["value"], signature.get("value", "")):
            problems.append("signature mismatch — wrong key or forged attestation")
    if check_artifacts:
        for stream in ("stdout", "stderr"):
            rec = payload.get(stream, {})
            spath = rec.get("path")
            if not spath or not os.path.isfile(spath):
                problems.append(f"{stream} log missing: {spath}")
            elif sha256_file(spath) != rec.get("sha256"):
                problems.append(f"{stream} log modified since capture: {spath}")
        for entry in payload.get("files", []):
            if entry.get("missing"):
                continue
            if not os.path.isfile(entry["path"]):
                problems.append(f"attested file missing: {entry['path']}")
            elif sha256_file(entry["path"]) != entry["sha256"]:
                problems.append(f"attested file changed since capture: {entry['path']}")
    return not problems, problems


def iter_attestations(attest_dir):
    for root, _dirs, files in os.walk(attest_dir):
        for name in sorted(files):
            if name == "attestation.json":
                yield os.path.join(root, name)


LEDGER_ATTESTATION_REF = re.compile(
    r"attestation\s+(?P<path>\S+?\.json)\s+sha256=(?P<digest>[0-9a-f]{64})")


def verify_ledger_references(ledger_path):
    """Every attestation referenced by the ledger must exist, match, and agree
    with the status the row claims. Hand-editing a row back to EVIDENCED after
    a DISPROVEN run is exactly the move this catches."""
    problems = []
    checked = 0
    try:
        with open(ledger_path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        return 0, [f"cannot read {ledger_path}: {e}"]
    for line in text.splitlines():
        match = LEDGER_ATTESTATION_REF.search(line)
        if not match:
            continue
        checked += 1
        path, digest = match.group("path"), match.group("digest")
        if not os.path.isfile(path):
            problems.append(f"{ledger_path}: referenced attestation missing: {path}")
            continue
        with open(path, encoding="utf-8") as f:
            attestation = json.load(f)
        payload = attestation.get("payload", {})
        # Recomputed, not read: an edited attestation that kept its old digest
        # field would otherwise still match the ledger.
        actual = canonical_digest(payload)
        if actual != digest:
            problems.append(f"{ledger_path}: evidence cites sha256={digest[:12]}… but "
                            f"{path} now hashes to {actual[:12]}… — the attestation "
                            f"was edited after the ledger row was written")
            continue
        cells = SPLIT_UNESCAPED_PIPE.split(line.strip()[1:-1])
        if len(cells) >= 6:
            row_id = cells[0].strip()
            row_status = cells[4].strip().strip("*`_~").upper()
            verdict = payload.get("verdict")
            if row_status != verdict:
                problems.append(
                    f"{ledger_path}: row {row_id} says {row_status} but its "
                    f"attestation recorded {verdict} (exit={payload.get('exit_code')}) "
                    f"— the status was hand-edited away from the captured result")
            expected = escape_cell(evidence_sentence(payload, path, digest))
            if not cells[5].strip().startswith(expected):
                problems.append(
                    f"{ledger_path}: row {row_id} evidence text was rewritten after "
                    f"capture (the captured sentence is machine-owned; append your "
                    f"notes after it instead of editing it)")
    return checked, problems


def cmd_verify(args):
    targets = args.attestations or list(iter_attestations(args.attest_dir))
    problems = []
    if not targets and not args.ledger:
        print(f"ERROR: no attestation found under {args.attest_dir}")
        return 2
    for path in targets:
        ok, issues = verify_attestation(path)
        mark = "OK  " if ok else "FAIL"
        print(f"  [{mark}] {path}")
        for issue in issues:
            print(f"         ✗ {issue}")
        problems.extend(issues)
    if args.ledger:
        checked, ledger_problems = verify_ledger_references(args.ledger)
        print(f"  [LEDGER] {checked} attestation reference(s) in {args.ledger}")
        for issue in ledger_problems:
            print(f"         ✗ {issue}")
        problems.extend(ledger_problems)
    if problems:
        print(f"VERIFY FAILED — {len(problems)} problem(s)")
        return 1
    print(f"VERIFY OK — {len(targets)} attestation(s) match their artifacts")
    return 0


# ---------------------------------------------------------------- self-test
LEDGER_FIXTURE = """# Proof Ledger — self-test

| ID | Level | Claim | Gate (what proves it) | Status | Evidence |
|----|-------|-------|------------------------|--------|----------|
| P1 | Micro | the good command succeeds | run it | CLAIMED | |
| P2 | Micro | the bad command succeeds | run it | CLAIMED | |
"""


def _row_status(ledger_path, claim_id):
    with open(ledger_path, encoding="utf-8") as f:
        lines = f.read().splitlines(keepends=True)
    _idx, cells = find_row(lines, claim_id)
    return (cells[4].strip(), cells[5].strip()) if cells else (None, None)


def self_test():
    """Adversarial suite for the capture layer itself — the same law the skill
    applies to everything else: a verifier that was never attacked is an
    unverified claim."""
    results = []

    def check(name, condition, detail=""):
        results.append((name, bool(condition), detail))

    workdir = tempfile.mkdtemp(prefix="wincreator-selftest-")
    old_cwd = os.getcwd()
    old_key = os.environ.get(SIGNING_KEY_ENV)
    try:
        os.chdir(workdir)
        ledger = os.path.join(workdir, "PROOF_LEDGER.md")
        with open(ledger, "w", encoding="utf-8") as f:
            f.write(LEDGER_FIXTURE)
        attest_dir = os.path.join(workdir, DEFAULT_ATTEST_DIR)

        # 1. a passing gate becomes EVIDENCED, with a real captured tail
        att, path, code = run_and_attest(
            "P1", [sys.executable, "-c", "print('42 rows exported')"],
            ledger=ledger, attest_dir=attest_dir, quiet=True)
        digest = att["digest"]["value"]
        update_ledger(ledger, "P1", att["payload"]["verdict"],
                      evidence_sentence(att["payload"], path, digest))
        status, evidence = _row_status(ledger, "P1")
        check("passing_gate_is_evidenced", status == "EVIDENCED", status)
        check("evidence_carries_exit_code", "exit=0" in evidence)
        check("evidence_carries_attestation_digest", digest in evidence)
        check("stdout_captured", "42 rows exported" in att["payload"]["stdout"]["tail"])
        check("exit_code_recorded", code == 0 and att["payload"]["exit_code"] == 0)

        # 2. a failing gate can NEVER be written EVIDENCED
        att2, path2, code2 = run_and_attest(
            "P2", [sys.executable, "-c",
                   "import sys; sys.stderr.write('boom'); sys.exit(3)"],
            ledger=ledger, attest_dir=attest_dir, quiet=True)
        update_ledger(ledger, "P2", att2["payload"]["verdict"],
                      evidence_sentence(att2["payload"], path2, att2["digest"]["value"]))
        status2, _ = _row_status(ledger, "P2")
        check("failing_gate_is_disproven", status2 == "DISPROVEN", status2)
        check("failing_gate_never_evidenced", att2["payload"]["verdict"] != "EVIDENCED")
        check("failing_exit_code_recorded", code2 == 3)
        check("stderr_captured", "boom" in att2["payload"]["stderr"]["tail"])

        # 3. the resulting ledger is parseable by the mechanical gate
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import ledger_check
            violations, rows = ledger_check.check_text(open(ledger, encoding="utf-8").read())
            check("ledger_gate_sees_both_rows", rows == 2, f"rows={rows}")
            check("ledger_gate_accepts_captured_evidence",
                  not any("P1" in v for v in violations), str(violations))
            check("ledger_gate_blocks_on_disproven",
                  any("P2" in v and "DISPROVEN" in v for v in violations), str(violations))
        except ImportError as e:  # pragma: no cover
            check("ledger_check_importable", False, str(e))

        # 4. pipes and newlines in captured output cannot break the table
        att3, path3, _ = run_and_attest(
            "P1", [sys.executable, "-c", r"print('a | b'); print('second line')"],
            ledger=ledger, attest_dir=attest_dir, quiet=True)
        update_ledger(ledger, "P1", att3["payload"]["verdict"],
                      evidence_sentence(att3["payload"], path3, att3["digest"]["value"]))
        with open(ledger, encoding="utf-8") as f:
            ledger_text = f.read()
        row = [l for l in ledger_text.splitlines() if l.startswith("| P1 ")][0]
        check("pipe_in_output_escaped", len(SPLIT_UNESCAPED_PIPE.split(row)) == 8,
              str(len(SPLIT_UNESCAPED_PIPE.split(row))))
        check("newline_in_output_flattened", "\n" not in row)

        # 5. verify passes on untouched artifacts...
        ok, issues = verify_attestation(path2)
        check("verify_ok_on_untouched", ok, str(issues))

        # 6. ...and catches a tampered log, a tampered body, and the ledger link
        with open(att2["payload"]["stderr"]["path"], "w", encoding="utf-8") as f:
            f.write("all good actually")
        ok, issues = verify_attestation(path2)
        check("verify_catches_tampered_log",
              not ok and any("modified since capture" in i for i in issues), str(issues))

        with open(path2, encoding="utf-8") as f:
            forged = json.load(f)
        forged["payload"]["exit_code"] = 0
        forged["payload"]["verdict"] = "EVIDENCED"
        with open(path2, "w", encoding="utf-8") as f:
            json.dump(forged, f)
        ok, issues = verify_attestation(path2)
        check("verify_catches_forged_verdict",
              not ok and any("digest mismatch" in i for i in issues), str(issues))

        _checked, ledger_problems = verify_ledger_references(ledger)
        check("verify_catches_broken_ledger_reference",
              any("was edited after the ledger row" in p for p in ledger_problems),
              str(ledger_problems))

        # 6b. a DISPROVEN row hand-edited back to EVIDENCED is caught
        att5, path5, _ = run_and_attest(
            "P2", [sys.executable, "-c", "import sys; sys.exit(4)"],
            ledger=ledger, attest_dir=attest_dir, quiet=True)
        update_ledger(ledger, "P2", att5["payload"]["verdict"],
                      evidence_sentence(att5["payload"], path5, att5["digest"]["value"]))
        update_ledger(ledger, "P2", "EVIDENCED", _row_status(ledger, "P2")[1])
        _checked, ledger_problems = verify_ledger_references(ledger)
        check("verify_catches_status_laundering",
              any("hand-edited away from the captured result" in p
                  for p in ledger_problems), str(ledger_problems))

        # 6c. rewriting the captured sentence is caught; appending notes is not
        att6, path6, _ = run_and_attest(
            "P1", [sys.executable, "-c", "print('nominal run')"],
            ledger=ledger, attest_dir=attest_dir, quiet=True)
        captured = evidence_sentence(att6["payload"], path6, att6["digest"]["value"])
        update_ledger(ledger, "P1", "EVIDENCED", captured + " — reviewed by wina")
        _checked, ledger_problems = verify_ledger_references(ledger)
        check("appending_a_note_is_allowed",
              not any("row P1" in p for p in ledger_problems), str(ledger_problems))
        update_ledger(ledger, "P1", "EVIDENCED",
                      captured.replace("nominal run", "everything is fine"))
        _checked, ledger_problems = verify_ledger_references(ledger)
        check("verify_catches_rewritten_evidence",
              any("evidence text was rewritten" in p for p in ledger_problems),
              str(ledger_problems))

        # 6d. options may follow the claim id; only what is after `--` is the gate
        rc = main(["prove", "P1", "--ledger", ledger, "--attest-dir", attest_dir,
                   "--", sys.executable, "-c", "print('flags parsed')"])
        check("options_after_claim_id_are_not_swallowed", rc == 0, f"rc={rc}")

        # 7. signing round-trip, and detection of a wrong key
        os.environ[SIGNING_KEY_ENV] = "self-test-key"
        att4, path4, _ = run_and_attest("P1", [sys.executable, "-c", "print('signed')"],
                                        ledger=None, attest_dir=attest_dir, quiet=True)
        check("attestation_signed_when_key_set", "signature" in att4)
        ok, issues = verify_attestation(path4)
        check("signature_verifies_with_right_key", ok, str(issues))
        os.environ[SIGNING_KEY_ENV] = "another-key"
        ok, issues = verify_attestation(path4)
        check("signature_fails_with_wrong_key",
              not ok and any("signature mismatch" in i for i in issues), str(issues))

        # 8. a claim id absent from the ledger must not silently pass
        try:
            update_ledger(ledger, "NOPE", "EVIDENCED", "x")
            check("unknown_claim_id_raises", False)
        except KeyError:
            check("unknown_claim_id_raises", True)
    finally:
        os.chdir(old_cwd)
        if old_key is None:
            os.environ.pop(SIGNING_KEY_ENV, None)
        else:
            os.environ[SIGNING_KEY_ENV] = old_key
        shutil.rmtree(workdir, ignore_errors=True)

    failed = 0
    for name, ok, detail in results:
        if not ok:
            failed += 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" ({detail})" if detail and not ok else ""))
    print(f"self-test: {len(results)-failed}/{len(results)} passed")
    return 2 if failed else 0


# ------------------------------------------------------------------- parser
def build_parser():
    parser = argparse.ArgumentParser(
        prog="wincreator", description="capture proof instead of narrating it")
    parser.add_argument("--version", action="version", version=f"wincreator {VERSION}")
    parser.add_argument("--self-test", action="store_true",
                        help="run the embedded adversarial suite")
    sub = parser.add_subparsers(dest="cmd")

    prove = sub.add_parser("prove", help="run a gate and attest its result")
    prove.add_argument("claim_id", help="the ledger row ID to update, e.g. P-014")
    prove.add_argument("--ledger", default=DEFAULT_LEDGER)
    prove.add_argument("--no-ledger", action="store_true",
                       help="attest only, do not touch any ledger")
    prove.add_argument("--file", action="append", default=[],
                       help="hash this file into the attestation (repeatable)")
    prove.add_argument("--attest-dir", default=DEFAULT_ATTEST_DIR)
    prove.add_argument("--timeout", type=int, default=None)
    prove.add_argument("command", nargs="*",
                       help="-- followed by the command to execute")

    verify = sub.add_parser("verify", help="re-hash attestations and their artifacts")
    verify.add_argument("attestations", nargs="*")
    verify.add_argument("--attest-dir", default=DEFAULT_ATTEST_DIR)
    verify.add_argument("--ledger", default=None,
                        help="also check every attestation referenced by this ledger")
    return parser


def main(argv):
    parser = build_parser()
    # Everything after the first bare `--` is the gate, verbatim; everything
    # before it is ours. Splitting before argparse is what lets the gate keep
    # its own flags (`pytest -q --tb=short`) without them being read as
    # wincreator's, in either order.
    gate = None
    if "--" in argv:
        cut = argv.index("--")
        argv, gate = argv[:cut], argv[cut + 1:]
    args = parser.parse_args(argv)
    if gate is not None and getattr(args, "cmd", None) == "prove":
        args.command = gate
    if args.self_test:
        return self_test()
    if args.cmd == "prove":
        if args.command and args.command[0] == "--":
            args.command = args.command[1:]
        return cmd_prove(args)
    if args.cmd == "verify":
        return cmd_verify(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
