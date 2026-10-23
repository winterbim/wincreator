"""Small stdlib-only primitives shared by the harness runtime.

Timestamps are UTC with microseconds and a trailing ``Z`` so they sort as
strings and match the format already used by the WinCreator proof kernel.
"""

from datetime import datetime, timezone
import hashlib
import json
import os


def utc_now():
    return datetime.now(timezone.utc)


def iso_time(value=None):
    value = utc_now() if value is None else value
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_iso(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def digests_equal(left, right):
    return bool(left) and bool(right) and left == right


def file_digest(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def portable_path(path):
    """Persist forward slashes, including Windows drive paths."""
    return os.fspath(path).replace("\\", "/")


def atomic_write_json(path, document):
    """Write JSON at mode 0600 through a same-directory temporary file."""
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    temporary = f"{path}.{os.getpid()}.tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
    return path


def pid_alive(pid):
    """Best-effort liveness probe for a run owner.

    On Windows there is no stdlib-only probe that avoids ctypes, so the lease
    alone decides there; the caller documents that limit.
    """
    if pid is None:
        return False
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":  # pragma: no cover - exercised by the Windows CI job
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True
