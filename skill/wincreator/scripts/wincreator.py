#!/usr/bin/env python3
"""Capture, review, and verify evidence for WinCreator proof-ledger claims.

The capture result (CAPTURED_PASS, CAPTURED_FAIL, CAPTURE_ERROR) is mechanical.
The epistemic verdict (EVIDENCED, INSUFFICIENT, DISPROVEN) is a separate review.
All persisted evidence is bound to the exact claim ID, level, text, and gate.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import getpass
import hashlib
import hmac
import json
import os
from pathlib import Path
import platform
import re
import shlex
import subprocess
import sys
import tempfile
import time
import uuid


VERSION = "3.0.0"
ATTESTATION_SCHEMA = "wincreator.attestation/v1"
REVIEW_SCHEMA = "wincreator.review/v1"
DEFAULT_ATTEST_DIR = ".wincreator/attestations"
DEFAULT_LEDGER = "PROOF_LEDGER.md"
SIGNING_KEY_ENV = "WINCREATOR_SIGNING_KEY"
DEFAULT_MAX_OUTPUT_BYTES = 1024 * 1024
TAIL_CHARS = 2000
LEDGER_HEADER = ("id", "level", "claim", "gate", "status", "evidence")
SPLIT_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")
FENCE = re.compile(r"^\s*(```|~~~)")
ATTESTATION_REF = re.compile(
    r"attestation\s+(?P<path>\S+?attestation\.json)\s+sha256=(?P<digest>[0-9a-f]{64})"
)
REVIEW_REF = re.compile(
    r"review\s+(?P<path>\S+?review\.json)\s+sha256=(?P<digest>[0-9a-f]{64})"
)


# ---------------------------------------------------------------- primitives
def utc_now():
    return datetime.now(timezone.utc)


def iso_time(value):
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def portable_path(path):
    """Use forward slashes in persisted paths, including Windows drive paths."""
    return os.fspath(path).replace("\\", "/")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_digest(payload):
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256_bytes(encoded)


def _signature(digest):
    key = os.environ.get(SIGNING_KEY_ENV)
    if not key:
        return None
    key_bytes = key.encode("utf-8")
    return {
        "algorithm": "hmac-sha256",
        "key_id": sha256_bytes(key_bytes)[:12],
        "value": hmac.new(key_bytes, digest.encode("ascii"), hashlib.sha256).hexdigest(),
    }


def _check_signature(document, problems):
    signature = document.get("signature")
    if not signature:
        return
    recorded = document.get("digest", {}).get("value", "")
    expected = _signature(recorded)
    if expected is None:
        problems.append(
            f"signed with key_id {signature.get('key_id')} but ${SIGNING_KEY_ENV} "
            "is not set"
        )
    elif not hmac.compare_digest(expected["value"], signature.get("value", "")):
        problems.append("signature mismatch — wrong key or forged document")


def _atomic_write(path, data, mode=None):
    path = os.path.abspath(path)
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".wincreator-ledger-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
        if hasattr(os, "O_DIRECTORY"):
            directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_json(path, document):
    data = (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    _atomic_write(path, data, 0o600)


@contextmanager
def _file_lock(path):
    lock_root = os.path.join(tempfile.gettempdir(), "wincreator-ledger-locks")
    os.makedirs(lock_root, mode=0o700, exist_ok=True)
    lock_name = sha256_bytes(os.path.abspath(path).encode("utf-8")) + ".lock"
    lock_path = os.path.join(lock_root, lock_name)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if os.name == "nt":  # pragma: no cover - executed by the Windows CI job
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"0")
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        if os.name == "nt":  # pragma: no cover
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


# -------------------------------------------------------------------- ledger
def escape_cell(value):
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def _split_row(line):
    stripped = line.strip()
    if not (stripped.startswith("|") and stripped.endswith("|")):
        return None
    return [part.strip().replace("\\|", "|") for part in SPLIT_UNESCAPED_PIPE.split(stripped[1:-1])]


def _is_separator(cells):
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells if cell)


def _is_ledger_header(cells):
    return len(cells) >= 6 and all(
        cell.lower().startswith(expected)
        for cell, expected in zip(cells[:6], LEDGER_HEADER)
    )


def _ledger_rows(lines):
    in_fence = False
    in_ledger = False
    candidate_header = None
    for index, line in enumerate(lines):
        if FENCE.match(line):
            in_fence = not in_fence
            in_ledger = False
            candidate_header = None
            continue
        if in_fence:
            continue
        cells = _split_row(line)
        if cells is None:
            in_ledger = False
            candidate_header = None
            continue
        if _is_separator(cells):
            in_ledger = candidate_header is not None and _is_ledger_header(candidate_header)
            candidate_header = None
            continue
        if in_ledger:
            yield index, cells
        else:
            candidate_header = cells


def claim_row_sha256(claim):
    identity = {
        "id": claim["id"],
        "level": claim["level"],
        "text": claim["text"],
        "gate": claim["gate"],
    }
    return canonical_digest(identity)


def _read_claim_from_text(text, claim_id):
    lines = text.splitlines(keepends=True)
    matches = []
    for index, cells in _ledger_rows(lines):
        if len(cells) >= 6 and cells[0] == claim_id:
            matches.append((index, cells))
    if not matches:
        raise KeyError(claim_id)
    if len(matches) > 1:
        raise ValueError(f"duplicate claim identifier '{claim_id}' in ledger")
    index, cells = matches[0]
    claim = {
        "id": cells[0],
        "level": cells[1],
        "text": cells[2],
        "gate": cells[3],
        "status": cells[4].strip("*_~` ").upper(),
        "evidence": cells[5],
        "line_index": index,
    }
    claim["row_sha256"] = claim_row_sha256(claim)
    return claim, lines, cells


def read_claim(ledger_path, claim_id):
    text = Path(ledger_path).read_text(encoding="utf-8")
    claim, _lines, _cells = _read_claim_from_text(text, claim_id)
    return claim


def update_ledger(ledger_path, claim_id, status, evidence, expected_row_sha=None):
    with _file_lock(ledger_path):
        text = Path(ledger_path).read_text(encoding="utf-8")
        claim, lines, cells = _read_claim_from_text(text, claim_id)
        if expected_row_sha and claim["row_sha256"] != expected_row_sha:
            raise RuntimeError(
                f"claim {claim_id} changed while its gate was running; ledger not updated"
            )
        old_status = claim["status"]
        cells[4] = status
        cells[5] = evidence
        newline = "\n" if lines[claim["line_index"]].endswith("\n") else ""
        lines[claim["line_index"]] = (
            "| " + " | ".join(escape_cell(cell) for cell in cells) + " |" + newline
        )
        mode = os.stat(ledger_path).st_mode & 0o777
        _atomic_write(ledger_path, "".join(lines).encode("utf-8"), mode)
    return old_status


# ----------------------------------------------------------------------- git
def _git(cwd, *args):
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _untracked_digest(cwd):
    output = _git(cwd, "ls-files", "--others", "--exclude-standard", "-z")
    if output is None:
        return None
    records = []
    for relative in sorted(item for item in output.split("\0") if item):
        path = os.path.join(cwd, relative)
        if os.path.isfile(path):
            records.append([portable_path(relative), sha256_file(path)])
        else:
            records.append([portable_path(relative), None])
    return canonical_digest({"untracked": records})


def git_context(cwd):
    commit = _git(cwd, "rev-parse", "HEAD")
    if commit is None:
        return {"available": False}
    status = _git(cwd, "status", "--porcelain=v1", "--untracked-files=all")
    tree = _git(cwd, "rev-parse", "HEAD^{tree}")
    branch = _git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    submodules = _git(cwd, "submodule", "status", "--recursive")
    untracked_digest = _untracked_digest(cwd)
    if (status is None or tree is None or branch is None
            or submodules is None or untracked_digest is None):
        return {"available": False}
    return {
        "available": True,
        "commit": commit,
        "tree": tree,
        "branch": branch,
        "dirty": bool(status),
        "remote": _git(cwd, "config", "--get", "remote.origin.url"),
        "submodules": submodules,
        "untracked_digest": untracked_digest,
    }


# -------------------------------------------------------------- schema check
def _require(mapping, keys, label):
    if not isinstance(mapping, dict):
        raise ValueError(f"{label} must be an object")
    missing = [key for key in keys if key not in mapping]
    if missing:
        raise ValueError(f"{label} missing required field(s): {', '.join(missing)}")


_ATTESTATION_SCHEMA_CACHE = None


def _schema_type_matches(value, expected):
    checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    return checks.get(expected, lambda _item: False)(value)


def _resolve_schema_ref(root_schema, reference):
    if not reference.startswith("#/"):
        raise ValueError(f"unsupported schema reference: {reference}")
    node = root_schema
    for part in reference[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    return node


def _validate_json_schema(value, schema, root_schema, path="$"):
    if "$ref" in schema:
        return _validate_json_schema(
            value, _resolve_schema_ref(root_schema, schema["$ref"]), root_schema, path
        )
    if "const" in schema and value != schema["const"]:
        raise ValueError(f"{path} must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path} is not one of {schema['enum']!r}")
    expected_types = schema.get("type")
    if expected_types:
        if isinstance(expected_types, str):
            expected_types = [expected_types]
        if not any(_schema_type_matches(value, item) for item in expected_types):
            raise ValueError(f"{path} has invalid type; expected {expected_types!r}")
    if isinstance(value, dict):
        required = schema.get("required", [])
        missing = [key for key in required if key not in value]
        if missing:
            raise ValueError(f"{path} missing required field(s): {', '.join(missing)}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                raise ValueError(f"{path} has unauthorized field(s): {', '.join(extra)}")
        for key, child in value.items():
            if key in properties:
                _validate_json_schema(child, properties[key], root_schema, f"{path}.{key}")
    if isinstance(value, list):
        minimum_items = schema.get("minItems")
        if minimum_items is not None and len(value) < minimum_items:
            raise ValueError(f"{path} must contain at least {minimum_items} item(s)")
        item_schema = schema.get("items")
        if item_schema:
            for index, child in enumerate(value):
                _validate_json_schema(child, item_schema, root_schema, f"{path}[{index}]")
    if isinstance(value, str):
        minimum_length = schema.get("minLength")
        if minimum_length is not None and len(value) < minimum_length:
            raise ValueError(f"{path} must contain at least {minimum_length} character(s)")
        pattern = schema.get("pattern")
        if pattern and not re.search(pattern, value):
            raise ValueError(f"{path} does not match {pattern!r}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if minimum is not None and value < minimum:
            raise ValueError(f"{path} must be >= {minimum}")


def validate_attestation_document(document):
    global _ATTESTATION_SCHEMA_CACHE
    if _ATTESTATION_SCHEMA_CACHE is None:
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "attestation-v1.schema.json"
        _ATTESTATION_SCHEMA_CACHE = json.loads(schema_path.read_text(encoding="utf-8"))
    _validate_json_schema(
        document,
        _ATTESTATION_SCHEMA_CACHE,
        _ATTESTATION_SCHEMA_CACHE,
    )
    return True


# -------------------------------------------------------------- output policy
def _redact_output(raw, literal_values, regex_values):
    text = raw.decode("utf-8", "replace")
    for value in literal_values:
        if value:
            text = text.replace(value, "[REDACTED]")
    for pattern in regex_values:
        text = re.sub(pattern, "[REDACTED]", text)
    return text.encode("utf-8")


def _stream_record(name, run_dir, raw, original_bytes, redactions, regexes, max_bytes, no_body):
    retained = _redact_output(raw, redactions, regexes)
    truncated = len(retained) > max_bytes or original_bytes > len(raw)
    retained = b"" if no_body else retained[:max_bytes]
    path = os.path.join(run_dir, name)
    _atomic_write(path, retained, 0o600)
    return {
        "path": path,
        "sha256": sha256_bytes(retained),
        "original_bytes": original_bytes,
        "stored_bytes": len(retained),
        "truncated": bool(truncated),
        "body_stored": not no_body,
        "tail": retained.decode("utf-8", "replace")[-TAIL_CHARS:],
    }


def _read_bounded(handle, max_bytes):
    handle.flush()
    original = os.fstat(handle.fileno()).st_size
    handle.seek(0)
    # Redaction can alter length, so retain a bounded cushion before truncation.
    limit = min(max(max_bytes * 4, 65536), 8 * 1024 * 1024)
    return handle.read(limit), original


def _recorded_path(path, cwd):
    absolute = os.path.abspath(path)
    try:
        relative = os.path.relpath(absolute, cwd)
    except ValueError:  # different Windows drives
        return portable_path(absolute)
    if relative == ".." or relative.startswith(".." + os.sep):
        return portable_path(absolute)
    return portable_path(relative)


def _resolve_recorded_path(recorded, attestation_path=None):
    native = recorded.replace("/", os.sep)
    if os.path.isabs(native) or re.match(r"^[A-Za-z]:[/\\]", recorded):
        return native
    candidates = []
    if attestation_path:
        current = os.path.abspath(os.path.dirname(attestation_path))
        for _ in range(10):
            candidates.append(os.path.join(current, native))
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent
    candidates.append(os.path.join(os.getcwd(), native))
    return next((candidate for candidate in candidates if os.path.exists(candidate)), candidates[0])


# ------------------------------------------------------------------- capture
def _claim_snapshot(ledger, claim_id, cwd):
    if not ledger:
        return {
            "id": claim_id,
            "level": "",
            "text": "",
            "gate": "",
            "row_sha256": None,
            "ledger_sha256_before": None,
            "status_before": None,
        }
    text = Path(ledger).read_text(encoding="utf-8")
    claim, _lines, _cells = _read_claim_from_text(text, claim_id)
    return {
        "id": claim["id"],
        "level": claim["level"],
        "text": claim["text"],
        "gate": claim["gate"],
        "row_sha256": claim["row_sha256"],
        "ledger_sha256_before": sha256_bytes(text.encode("utf-8")),
        "status_before": claim["status"],
    }


def _new_run_dir(attest_dir, claim_id, private):
    root = Path(attest_dir)
    if private and "private" not in root.name.lower():
        root = root.with_name(root.name + "-private")
    timestamp = utc_now().strftime("%Y%m%dT%H%M%S.%fZ")
    run_dir = root / claim_id / f"{timestamp}-{uuid.uuid4()}"
    os.makedirs(run_dir, mode=0o700, exist_ok=False)
    return str(run_dir)


def _file_entries(required_files, optional_files, cwd):
    missing = [path for path in required_files if not os.path.isfile(path)]
    if missing:
        raise FileNotFoundError(
            "required evidence file missing: " + ", ".join(portable_path(path) for path in missing)
        )
    entries = []
    for path in required_files:
        entries.append(
            {
                "path": _recorded_path(path, cwd),
                "optional": False,
                "missing": False,
                "sha256": sha256_file(path),
                "bytes": os.path.getsize(path),
            }
        )
    for path in optional_files:
        if os.path.isfile(path):
            entries.append(
                {
                    "path": _recorded_path(path, cwd),
                    "optional": True,
                    "missing": False,
                    "sha256": sha256_file(path),
                    "bytes": os.path.getsize(path),
                }
            )
        else:
            entries.append(
                {"path": _recorded_path(path, cwd), "optional": True, "missing": True}
            )
    return entries


def run_and_attest(
    claim_id,
    command,
    ledger=None,
    files=(),
    optional_files=(),
    attest_dir=DEFAULT_ATTEST_DIR,
    cwd=None,
    timeout=None,
    quiet=False,
    tier="standard",
    builder=None,
    allow_dirty=False,
    auto_approve_lite=False,
    redact=(),
    redact_regex=(),
    max_output_bytes=DEFAULT_MAX_OUTPUT_BYTES,
    no_output_body=False,
    private=False,
):
    """Run a gate and write a claim-bound capture attestation."""
    if not command:
        raise ValueError("no gate command supplied")
    tier = tier.lower()
    if tier not in {"lite", "standard", "regulated"}:
        raise ValueError(f"unknown tier: {tier}")
    if auto_approve_lite and tier != "lite":
        raise ValueError("--auto-approve-lite is only valid in Lite mode")
    if max_output_bytes < 0:
        raise ValueError("max_output_bytes must be non-negative")
    cwd = os.path.abspath(cwd or os.getcwd())
    ledger = os.path.abspath(ledger) if ledger else None
    required_files = [os.path.abspath(path) for path in files]
    optional_files = [os.path.abspath(path) for path in optional_files]
    file_entries = _file_entries(required_files, optional_files, cwd)
    claim = _claim_snapshot(ledger, claim_id, cwd)
    git = git_context(cwd)
    if tier == "regulated":
        if allow_dirty:
            raise ValueError("--allow-dirty is forbidden in Regulated mode")
        if not git.get("available") or git.get("dirty"):
            raise ValueError("Regulated capture requires a clean Git tree")
        if not builder:
            raise ValueError("Regulated capture requires --builder")
    if git.get("dirty") and not allow_dirty and tier in {"lite", "standard"}:
        # Dirty captures remain allowed outside Regulated, but the exception is explicit.
        dirty_override = False
    else:
        dirty_override = bool(allow_dirty)
    builder = builder or os.environ.get("WINCREATOR_BUILDER") or getpass.getuser()
    run_dir = _new_run_dir(attest_dir, claim_id, private)
    started = utc_now()
    start_clock = time.monotonic()
    child_env = os.environ.copy()
    child_env.pop(SIGNING_KEY_ENV, None)
    capture_error = None
    return_code = None
    with tempfile.TemporaryFile() as stdout_handle, tempfile.TemporaryFile() as stderr_handle:
        try:
            process = subprocess.Popen(
                list(command),
                cwd=cwd,
                env=child_env,
                stdout=stdout_handle,
                stderr=stderr_handle,
            )
            try:
                return_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                capture_error = f"command timed out after {timeout}s"
        except OSError as error:
            capture_error = f"cannot execute {command[0]!r}: {error}"
            stderr_handle.write(capture_error.encode("utf-8"))
        stdout_raw, stdout_original = _read_bounded(stdout_handle, max_output_bytes)
        stderr_raw, stderr_original = _read_bounded(stderr_handle, max_output_bytes)
    if tier == "regulated":
        git_after = git_context(cwd)
        if not git_after.get("available") or git_after != git:
            capture_error = "Regulated gate changed Git state or Git inspection failed after execution"
    duration_ms = int((time.monotonic() - start_clock) * 1000)
    finished = utc_now()
    stdout_record = _stream_record(
        "stdout.log",
        run_dir,
        stdout_raw,
        stdout_original,
        redact,
        redact_regex,
        max_output_bytes,
        no_output_body,
    )
    stderr_record = _stream_record(
        "stderr.log",
        run_dir,
        stderr_raw,
        stderr_original,
        redact,
        redact_regex,
        max_output_bytes,
        no_output_body,
    )
    if not quiet:
        sys.stdout.write(stdout_record["tail"])
        sys.stderr.write(stderr_record["tail"])
    if capture_error:
        capture_status = "CAPTURE_ERROR"
    elif return_code == 0:
        capture_status = "CAPTURED_PASS"
    else:
        capture_status = "CAPTURED_FAIL"
    for stream in (stdout_record, stderr_record):
        stream["path"] = portable_path(os.path.basename(stream["path"]))
    payload = {
        "tool_version": VERSION,
        "claim": claim,
        "ledger": portable_path(os.path.basename(ledger)) if ledger else None,
        "builder": builder,
        "command": list(command),
        "command_string": shlex.join(list(command)),
        "capture": {
            "status": capture_status,
            "exit_code": return_code,
            "error": capture_error,
        },
        "started_at": iso_time(started),
        "finished_at": iso_time(finished),
        "duration_ms": duration_ms,
        "stdout": stdout_record,
        "stderr": stderr_record,
        "files": file_entries,
        "git": git,
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "hostname": platform.node(),
            "cwd": portable_path(cwd),
            "ci": os.environ.get("CI", ""),
            "user": getpass.getuser(),
        },
        "policy": {
            "tier": tier,
            "dirty_override": dirty_override,
            "private": bool(private),
            "redaction_literals": len(tuple(redact)),
            "redaction_regexes": len(tuple(redact_regex)),
            "max_output_bytes": max_output_bytes,
            "no_output_body": bool(no_output_body),
        },
    }
    digest = canonical_digest(payload)
    attestation = {
        "schema": ATTESTATION_SCHEMA,
        "payload": payload,
        "digest": {
            "algorithm": "sha256",
            "canonicalization": "json/sorted-compact/utf-8",
            "value": digest,
        },
    }
    signature = _signature(digest)
    if signature:
        attestation["signature"] = signature
    validate_attestation_document(attestation)
    attestation_path = os.path.join(run_dir, "attestation.json")
    _atomic_json(attestation_path, attestation)

    if ledger:
        evidence = capture_evidence_sentence(payload, attestation_path, digest, cwd)
        if capture_status == "CAPTURED_PASS":
            ledger_status = "PENDING"
        elif capture_status == "CAPTURED_FAIL":
            ledger_status = "DISPROVEN"
        else:
            ledger_status = "BLOCKED"
        update_ledger(
            ledger,
            claim_id,
            ledger_status,
            evidence,
            expected_row_sha=claim["row_sha256"],
        )
    if capture_status == "CAPTURED_PASS" and auto_approve_lite:
        if ledger:
            review_attestation(
                attestation_path,
                "EVIDENCED",
                "auto-approve-lite",
                ledger,
                automatic=True,
            )
    effective_code = 0 if capture_status == "CAPTURED_PASS" else (return_code or 2)
    return attestation, attestation_path, effective_code


def capture_evidence_sentence(payload, attestation_path, digest, cwd=None):
    cwd = cwd or os.getcwd()
    path = _recorded_path(attestation_path, cwd)
    capture = payload["capture"]
    exit_value = "none" if capture["exit_code"] is None else capture["exit_code"]
    return (
        f"wincreator capture {payload['started_at']}: `{payload['command_string']}` "
        f"-> {capture['status']} exit={exit_value} ({payload['duration_ms']} ms); "
        f"claim_sha256={payload['claim']['row_sha256']}; "
        f"attestation {path} sha256={digest}"
    )


# -------------------------------------------------------------------- review
def _load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def review_attestation(attestation_path, verdict, reviewer, ledger=None, automatic=False):
    verdict = verdict.upper()
    if verdict not in {"EVIDENCED", "INSUFFICIENT", "DISPROVEN"}:
        raise ValueError(f"invalid review verdict: {verdict}")
    ok, problems = verify_attestation(attestation_path)
    if not ok:
        raise ValueError("capture failed verification: " + "; ".join(problems))
    attestation = _load_json(attestation_path)
    payload = attestation["payload"]
    capture_status = payload["capture"]["status"]
    if capture_status == "CAPTURED_FAIL" and verdict == "EVIDENCED":
        raise ValueError("CAPTURED_FAIL can never become EVIDENCED")
    if capture_status == "CAPTURE_ERROR" and verdict != "INSUFFICIENT":
        raise ValueError("CAPTURE_ERROR can only be reviewed INSUFFICIENT")
    if capture_status == "CAPTURED_PASS" and verdict == "DISPROVEN":
        # A reviewer can disprove the claim when the gate passed for the wrong reason.
        pass
    if payload["policy"]["tier"] == "regulated" and reviewer == payload["builder"]:
        raise ValueError("Regulated builder and reviewer must differ")
    reviewed_at = iso_time(utc_now())
    review_payload = {
        "tool_version": VERSION,
        "claim": payload["claim"],
        "capture_digest": attestation["digest"]["value"],
        "capture_path": portable_path(os.path.basename(attestation_path)),
        "capture_status": capture_status,
        "verdict": verdict,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "automatic": bool(automatic),
    }
    digest = canonical_digest(review_payload)
    review = {
        "schema": REVIEW_SCHEMA,
        "payload": review_payload,
        "digest": {
            "algorithm": "sha256",
            "canonicalization": "json/sorted-compact/utf-8",
            "value": digest,
        },
    }
    signature = _signature(digest)
    if signature:
        review["signature"] = signature
    review_path = os.path.join(os.path.dirname(attestation_path), "review.json")
    _atomic_json(review_path, review)
    if ledger:
        ledger = os.path.abspath(ledger)
        status = {
            "EVIDENCED": "EVIDENCED",
            "INSUFFICIENT": "INSUFFICIENT",
            "DISPROVEN": "DISPROVEN",
        }[verdict]
        evidence = review_evidence_sentence(
            payload, attestation_path, attestation["digest"]["value"], review, review_path, os.path.dirname(ledger)
        )
        update_ledger(
            ledger,
            payload["claim"]["id"],
            status,
            evidence,
            expected_row_sha=payload["claim"]["row_sha256"],
        )
    return review, review_path


def review_evidence_sentence(payload, attestation_path, attestation_digest, review, review_path, cwd=None):
    cwd = cwd or os.getcwd()
    capture_sentence = capture_evidence_sentence(payload, attestation_path, attestation_digest, cwd)
    review_payload = review["payload"]
    return (
        f"{capture_sentence}; review {_recorded_path(review_path, cwd)} "
        f"verdict={review_payload['verdict']} reviewer={review_payload['reviewer']} "
        f"reviewed_at={review_payload['reviewed_at']} "
        f"sha256={review['digest']['value']}"
    )


# -------------------------------------------------------------------- verify
def verify_attestation(path, check_artifacts=True):
    problems = []
    try:
        document = _load_json(path)
        validate_attestation_document(document)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        return False, [f"unreadable or schema-invalid: {error}"]
    payload = document["payload"]
    recorded = document["digest"]["value"]
    if document["digest"].get("algorithm") != "sha256":
        problems.append("unsupported digest algorithm")
    if canonical_digest(payload) != recorded:
        problems.append("digest mismatch — the attestation body was edited")
    _check_signature(document, problems)
    if payload["claim"]["row_sha256"] and claim_row_sha256(payload["claim"]) != payload["claim"]["row_sha256"]:
        problems.append("claim row digest mismatch")
    if check_artifacts:
        for stream_name in ("stdout", "stderr"):
            stream = payload[stream_name]
            resolved = _resolve_recorded_path(stream["path"], path)
            if not os.path.isfile(resolved):
                problems.append(f"{stream_name} log missing: {stream['path']}")
            elif sha256_file(resolved) != stream["sha256"]:
                problems.append(f"{stream_name} log modified since capture: {stream['path']}")
        for entry in payload["files"]:
            if entry.get("optional") and entry.get("missing"):
                continue
            if entry.get("missing"):
                problems.append(f"required attested file was missing: {entry.get('path')}")
                continue
            resolved = _resolve_recorded_path(entry["path"], path)
            if not os.path.isfile(resolved):
                problems.append(f"attested file missing: {entry['path']}")
            elif sha256_file(resolved) != entry["sha256"]:
                problems.append(f"attested file changed since capture: {entry['path']}")
    return not problems, problems


def verify_review(path, capture_path=None):
    problems = []
    try:
        review = _load_json(path)
    except (OSError, json.JSONDecodeError) as error:
        return False, [f"unreadable review: {error}"]
    if review.get("schema") != REVIEW_SCHEMA:
        return False, ["unsupported review schema"]
    payload = review.get("payload")
    digest = review.get("digest", {}).get("value")
    if not isinstance(payload, dict) or not digest:
        return False, ["malformed review"]
    if canonical_digest(payload) != digest:
        problems.append("review digest mismatch")
    _check_signature(review, problems)
    if capture_path:
        capture = _load_json(capture_path)
        if payload.get("capture_digest") != capture.get("digest", {}).get("value"):
            problems.append("review does not reference this capture digest")
        if payload.get("claim") != capture.get("payload", {}).get("claim"):
            problems.append("review claim does not match capture claim")
        if capture.get("payload", {}).get("capture", {}).get("status") == "CAPTURED_FAIL" and payload.get("verdict") == "EVIDENCED":
            problems.append("CAPTURED_FAIL was laundered into EVIDENCED")
    return not problems, problems


def iter_attestations(attest_dir):
    for root, directories, files in os.walk(attest_dir):
        directories[:] = [name for name in directories if name not in {".git", "dist", "__pycache__"}]
        if "attestation.json" in files:
            yield os.path.join(root, "attestation.json")


def _discover_ledger_attestations(ledger_path):
    root = os.path.dirname(os.path.abspath(ledger_path))
    matches = []
    for current, directories, files in os.walk(root):
        directories[:] = [name for name in directories if name not in {".git", "dist", "__pycache__"}]
        if "attestation.json" not in files:
            continue
        path = os.path.join(current, "attestation.json")
        try:
            document = _load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        recorded = document.get("payload", {}).get("ledger")
        if recorded and os.path.basename(recorded) == os.path.basename(ledger_path):
            matches.append(path)
    return matches


def verify_ledger_references(ledger_path):
    problems = []
    checked = 0
    try:
        ledger_text = Path(ledger_path).read_text(encoding="utf-8")
    except OSError as error:
        return 0, [f"cannot read {ledger_path}: {error}"]
    referenced = [match.group("path") for match in ATTESTATION_REF.finditer(ledger_text)]
    capture_paths = []
    for recorded in referenced:
        capture_paths.append(_resolve_recorded_path(recorded, ledger_path))
    capture_paths.extend(_discover_ledger_attestations(ledger_path))
    unique = []
    seen = set()
    for path in capture_paths:
        real = os.path.realpath(path)
        if real not in seen:
            seen.add(real)
            unique.append(path)
    for capture_path in unique:
        checked += 1
        ok, capture_problems = verify_attestation(capture_path)
        if not ok:
            problems.extend(f"{capture_path}: {problem}" for problem in capture_problems)
            continue
        capture = _load_json(capture_path)
        payload = capture["payload"]
        claim = payload["claim"]
        try:
            current = read_claim(ledger_path, claim["id"])
        except (KeyError, ValueError) as error:
            problems.append(f"{ledger_path}: captured claim {claim['id']} not uniquely present: {error}")
            continue
        for key, current_key in (("id", "id"), ("level", "level"), ("text", "text"), ("gate", "gate")):
            if claim[key] != current[current_key]:
                problems.append(f"{ledger_path}: row {claim['id']} {key} changed after capture")
        if current["row_sha256"] != claim["row_sha256"]:
            problems.append(f"{ledger_path}: row {claim['id']} hash changed after capture")
        review_path = os.path.join(os.path.dirname(capture_path), "review.json")
        if os.path.isfile(review_path):
            review_ok, review_problems = verify_review(review_path, capture_path)
            if not review_ok:
                problems.extend(f"{review_path}: {problem}" for problem in review_problems)
                continue
            review = _load_json(review_path)
            verdict = review["payload"]["verdict"]
            expected_status = {
                "EVIDENCED": "EVIDENCED",
                "INSUFFICIENT": "INSUFFICIENT",
                "DISPROVEN": "DISPROVEN",
            }[verdict]
            expected_evidence = review_evidence_sentence(
                payload,
                capture_path,
                capture["digest"]["value"],
                review,
                review_path,
                os.path.dirname(os.path.abspath(ledger_path)),
            )
        else:
            expected_status = {
                "CAPTURED_PASS": "PENDING",
                "CAPTURED_FAIL": "DISPROVEN",
                "CAPTURE_ERROR": "BLOCKED",
            }[payload["capture"]["status"]]
            expected_evidence = capture_evidence_sentence(
                payload,
                capture_path,
                capture["digest"]["value"],
                os.path.dirname(os.path.abspath(ledger_path)),
            )
        if current["status"] != expected_status:
            problems.append(
                f"{ledger_path}: row {claim['id']} status {current['status']} does not match "
                f"capture/review status {expected_status}"
            )
        if not current["evidence"].startswith(expected_evidence):
            problems.append(f"{ledger_path}: row {claim['id']} evidence was rewritten after capture/review")
        if expected_status != "EVIDENCED":
            problems.append(
                f"{ledger_path}: row {claim['id']} is {expected_status}; "
                "capture integrity is valid but the claim is not evidenced"
            )
    return checked, problems


# ---------------------------------------------------------------------- CLI
def _latest_attestation(attest_dir, claim_id):
    root = os.path.join(attest_dir, claim_id)
    paths = sorted(iter_attestations(root)) if os.path.isdir(root) else []
    if not paths:
        raise FileNotFoundError(f"no attestation found for {claim_id} under {attest_dir}")
    return paths[-1]


def cmd_prove(args):
    try:
        attestation, path, code = run_and_attest(
            args.claim_id,
            args.command,
            ledger=None if args.no_ledger else args.ledger,
            files=args.file,
            optional_files=args.optional_file,
            attest_dir=args.attest_dir,
            timeout=args.timeout,
            tier=args.tier,
            builder=args.builder,
            allow_dirty=args.allow_dirty,
            auto_approve_lite=args.auto_approve_lite,
            redact=args.redact,
            redact_regex=args.redact_regex,
            max_output_bytes=args.max_output_bytes,
            no_output_body=args.no_output_body,
            private=args.private,
        )
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    capture = attestation["payload"]["capture"]
    print(f"[{capture['status']}] {args.claim_id} exit={capture['exit_code']}")
    print(f"[ATTESTATION] {path} sha256={attestation['digest']['value']}")
    payload = attestation["payload"]
    if (payload["policy"]["tier"] == "standard"
            and not payload["git"].get("available")
            and not payload["files"]):
        print(
            "[WARNING] Standard capture has no Git snapshot or attested files; "
            "use --file for source inputs that must be bound to the claim."
        )
    if capture["status"] == "CAPTURED_PASS" and not args.auto_approve_lite:
        print("[REVIEW REQUIRED] run `wincreator review` before claiming EVIDENCED")
    return code


def cmd_review(args):
    try:
        path = args.attestation or _latest_attestation(args.attest_dir, args.claim_id)
        review, review_path = review_attestation(
            path,
            args.verdict,
            args.reviewer,
            ledger=None if args.no_ledger else args.ledger,
            automatic=args.automatic,
        )
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(
        f"[{review['payload']['verdict']}] {args.claim_id} reviewed by "
        f"{review['payload']['reviewer']}"
    )
    print(f"[REVIEW] {review_path} sha256={review['digest']['value']}")
    return 0


def cmd_verify(args):
    targets = list(args.attestations)
    if not targets and args.attest_dir:
        targets = list(iter_attestations(args.attest_dir))
    all_problems = []
    for path in targets:
        ok, problems = verify_attestation(path)
        print(f"  [{'OK' if ok else 'FAIL'}] {path}")
        for problem in problems:
            print(f"       - {problem}")
        all_problems.extend(problems)
    checked = 0
    if args.ledger:
        checked, problems = verify_ledger_references(args.ledger)
        print(f"  [LEDGER] {checked} capture(s) checked in {args.ledger}")
        for problem in problems:
            print(f"       - {problem}")
        all_problems.extend(problems)
        if checked == 0:
            all_problems.append(
                f"{args.ledger}: no capture attestation references were found"
            )
    if not targets and not args.ledger:
        print("ERROR: no attestation or ledger supplied", file=sys.stderr)
        return 2
    if all_problems:
        for problem in all_problems:
            if problem.endswith("no capture attestation references were found"):
                print(f"       - {problem}")
        print(f"VERIFY FAILED — {len(all_problems)} problem(s)")
        return 1
    print(f"VERIFY OK — {len(targets) + checked} verification target(s)")
    return 0


def self_test():
    results = []

    def check(name, condition):
        results.append((name, bool(condition)))

    with tempfile.TemporaryDirectory(prefix="wincreator-selftest-") as directory:
        ledger = os.path.join(directory, "PROOF_LEDGER.md")
        Path(ledger).write_text(
            "| ID | Level | Claim | Gate (what proves it) | Status | Evidence |\n"
            "|----|-------|-------|------------------------|--------|----------|\n"
            "| P1 | Micro | command succeeds | `python -c pass` | CLAIMED | |\n",
            encoding="utf-8",
        )
        attestation, path, code = run_and_attest(
            "P1",
            [sys.executable, "-c", "print('ok')"],
            ledger=ledger,
            attest_dir=os.path.join(directory, "attestations"),
            cwd=directory,
            quiet=True,
            tier="standard",
        )
        check("capture_pass", code == 0 and attestation["payload"]["capture"]["status"] == "CAPTURED_PASS")
        check("review_required", read_claim(ledger, "P1")["status"] == "PENDING")
        review_attestation(path, "EVIDENCED", "skeptic", ledger)
        check("review_evidenced", read_claim(ledger, "P1")["status"] == "EVIDENCED")
        _checked, problems = verify_ledger_references(ledger)
        check("verify_round_trip", not problems)
        saved_key = os.environ.get(SIGNING_KEY_ENV)
        os.environ[SIGNING_KEY_ENV] = "self-test-key"
        try:
            signed, signed_path, signed_code = run_and_attest(
                "NOLEDGER",
                [sys.executable, "-c", "import os,sys; sys.exit(bool(os.getenv('WINCREATOR_SIGNING_KEY')))"],
                ledger=None,
                attest_dir=os.path.join(directory, "signed"),
                cwd=directory,
                quiet=True,
                tier="lite",
            )
            check("key_hidden_from_gate", signed_code == 0)
            check("capture_signed_after_gate", "signature" in signed)
        finally:
            if saved_key is None:
                os.environ.pop(SIGNING_KEY_ENV, None)
            else:
                os.environ[SIGNING_KEY_ENV] = saved_key
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    passed = sum(value for _name, value in results)
    print(f"self-test: {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 2


def build_parser():
    parser = argparse.ArgumentParser(prog="wincreator")
    parser.add_argument("--version", action="version", version=f"wincreator {VERSION}")
    parser.add_argument("--self-test", action="store_true")
    subparsers = parser.add_subparsers(dest="command_name")

    prove = subparsers.add_parser("prove", help="execute and capture a claim gate")
    prove.add_argument("claim_id")
    prove.add_argument("--ledger", default=DEFAULT_LEDGER)
    prove.add_argument("--no-ledger", action="store_true")
    prove.add_argument("--file", action="append", default=[])
    prove.add_argument("--optional-file", action="append", default=[])
    prove.add_argument("--attest-dir", default=DEFAULT_ATTEST_DIR)
    prove.add_argument("--timeout", type=float)
    prove.add_argument("--tier", choices=("lite", "standard", "regulated"), default="standard")
    prove.add_argument("--builder")
    prove.add_argument("--allow-dirty", action="store_true")
    prove.add_argument("--auto-approve-lite", action="store_true")
    prove.add_argument("--redact", action="append", default=[])
    prove.add_argument("--redact-regex", action="append", default=[])
    prove.add_argument("--max-output-bytes", type=int, default=DEFAULT_MAX_OUTPUT_BYTES)
    prove.add_argument("--no-output-body", action="store_true")
    prove.add_argument("--private", action="store_true")
    prove.add_argument("gate", nargs="*")

    review = subparsers.add_parser("review", help="review a captured gate")
    review.add_argument("claim_id")
    review.add_argument("--verdict", required=True, choices=("evidenced", "insufficient", "disproven"))
    review.add_argument("--reviewer", required=True)
    review.add_argument("--attestation")
    review.add_argument("--attest-dir", default=DEFAULT_ATTEST_DIR)
    review.add_argument("--ledger", default=DEFAULT_LEDGER)
    review.add_argument("--no-ledger", action="store_true")
    review.add_argument(
        "--automatic",
        action="store_true",
        help="mark a CI/tool review as automatic rather than independent human sign-off",
    )

    verify = subparsers.add_parser("verify", help="verify captures, reviews, and ledger bindings")
    verify.add_argument("attestations", nargs="*")
    verify.add_argument("--attest-dir", default=DEFAULT_ATTEST_DIR)
    verify.add_argument("--ledger")
    return parser


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    gate = None
    if "--" in argv:
        separator = argv.index("--")
        argv, gate = argv[:separator], argv[separator + 1 :]
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if args.command_name == "prove":
        args.command = gate if gate is not None else args.gate
        return cmd_prove(args)
    if args.command_name == "review":
        return cmd_review(args)
    if args.command_name == "verify":
        return cmd_verify(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
