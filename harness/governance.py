"""Optional VEOR governance sidecar (G02).

VEOR is a Node.js runtime; WinCreator stays Python and stdlib-only. This module
is the only bridge between them. It never decides anything itself: it asks the
pinned VEOR kernel and maps every uncertainty to a refusal.

Fail-closed contract:

- a missing pin, checkout, Node runtime, sidecar entrypoint, malformed response,
  unknown decision or failed receipt verification raises ``GovernanceUnavailable``;
- the caller must treat that as BLOCKED, never as ALLOW;
- nothing here can write a ledger status or a proof verdict. Governance answers
  "may this effect run?", the proof kernel answers "is this claim proven?".

See ``docs/adr/0001-veor-optional-sidecar.md`` and
``docs/adr/0002-single-proof-authority.md``.
"""

from dataclasses import dataclass
import json
import os
import re
import shutil
import subprocess
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from harness.util import canonical_json, sha256_text

PIN_SCHEMA = "wincreator.veor-pin/v1"
DECISIONS = ("ALLOW", "REVIEW", "DENY")
_RECEIPT_KIND = "veor.receipt-verify/v1"
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_PIN_FIELDS = (
    "schema",
    "repository",
    "commit",
    "package_version",
    "node_major",
    "audited_at",
    "audit_document",
    "sidecar",
    "vendored",
)


class GovernanceUnavailable(RuntimeError):
    """Governance cannot be established. Callers must block, never allow."""


@dataclass(frozen=True)
class GovernanceStatus:
    status: str
    reasons: Tuple[str, ...] = ()
    pin_digest: Optional[str] = None
    veor_home: Optional[str] = None
    node: Optional[str] = None

    @property
    def ready(self):
        return self.status == "READY"


@dataclass(frozen=True)
class Decision:
    decision: str
    reasons: Tuple[str, ...]
    policy_digest: str
    raw: Mapping[str, Any]

    @property
    def is_allow(self):
        return self.decision == "ALLOW"

    @property
    def is_deny(self):
        return self.decision == "DENY"


def pin_digest(pin):
    return sha256_text(canonical_json(pin))


def load_pin(path):
    """Load and strictly validate a VEOR pin. Never guesses a default."""
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError) as error:
        raise GovernanceUnavailable(f"cannot read VEOR pin {path}: {error}")
    if not isinstance(document, dict):
        raise GovernanceUnavailable("VEOR pin must be a JSON object")
    missing = [field for field in _PIN_FIELDS if field not in document]
    if missing:
        raise GovernanceUnavailable("VEOR pin missing field(s): " + ", ".join(missing))
    if document["schema"] != PIN_SCHEMA:
        raise GovernanceUnavailable(
            f"VEOR pin schema must be {PIN_SCHEMA!r}: {document['schema']!r}"
        )
    if not _COMMIT_RE.match(str(document["commit"])):
        raise GovernanceUnavailable("VEOR pin commit must be a 40-character git SHA")
    if not isinstance(document["node_major"], int) or document["node_major"] < 18:
        raise GovernanceUnavailable("VEOR pin node_major must be an integer >= 18")
    if not isinstance(document["vendored"], bool):
        raise GovernanceUnavailable("VEOR pin vendored must be a boolean")
    sidecar = document["sidecar"]
    if not isinstance(sidecar, dict):
        raise GovernanceUnavailable("VEOR pin sidecar must be an object")
    for field in ("entrypoint", "protocol", "receipt_verify"):
        if field not in sidecar:
            raise GovernanceUnavailable(f"VEOR pin sidecar missing {field!r}")
    if not isinstance(sidecar["entrypoint"], str) or not sidecar["entrypoint"]:
        raise GovernanceUnavailable("VEOR pin sidecar.entrypoint must be a non-empty string")
    if not isinstance(sidecar["receipt_verify"], list) or not sidecar["receipt_verify"]:
        raise GovernanceUnavailable("VEOR pin sidecar.receipt_verify must be a non-empty list")
    if not all(isinstance(item, str) and item for item in sidecar["receipt_verify"]):
        raise GovernanceUnavailable("VEOR pin sidecar.receipt_verify must contain strings")
    return document


def node_version():
    node = shutil.which("node")
    if not node:
        return None
    try:
        result = subprocess.run(
            [node, "--version"], capture_output=True, text=True, timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return (result.stdout or "").strip() or None


def node_major(version):
    if not version:
        return None
    match = re.match(r"^v?(\d+)\.", version.strip())
    return int(match.group(1)) if match else None


def resolve_home(pin_path, home=None, env=None):
    env = os.environ if env is None else env
    if home:
        return os.path.abspath(home)
    configured = env.get("VEOR_HOME")
    if configured:
        return os.path.abspath(configured)
    default = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(pin_path))), "vendor", "veor")
    return os.path.abspath(default)


def _checkout_commit(home):
    git_directory = os.path.join(home, ".git")
    if not os.path.isdir(git_directory):
        return None, "checkout has no git metadata, so its commit cannot be proven"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=home,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return None, f"cannot read checkout commit: {error}"
    if result.returncode != 0:
        return None, "cannot read checkout commit"
    return (result.stdout or "").strip(), None


def _package_version(home):
    path = os.path.join(home, "package.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle).get("version")
    except (OSError, ValueError):
        return None


def check(pin_path=None, home=None, env=None, node=None, node_version_override=None):
    """Return READY only when every prerequisite is provably satisfied."""
    pin_path = pin_path or os.path.join("tools", "veor-pin.json")
    try:
        pin = load_pin(pin_path)
    except GovernanceUnavailable as error:
        return GovernanceStatus("BLOCKED", (str(error),))
    resolved_home = resolve_home(pin_path, home=home, env=env)
    digest = pin_digest(pin)
    reasons: List[str] = []
    if not os.path.isdir(resolved_home):
        reasons.append(
            f"VEOR checkout not configured: set VEOR_HOME or place the pinned "
            f"checkout at {resolved_home}"
        )
        return GovernanceStatus("BLOCKED", tuple(reasons), digest, resolved_home, None)
    version = _package_version(resolved_home)
    if version is None:
        reasons.append("VEOR package.json is missing or unreadable")
    elif version != pin["package_version"]:
        reasons.append(
            f"VEOR package version {version} does not match pinned {pin['package_version']}"
        )
    commit, commit_problem = _checkout_commit(resolved_home)
    if commit_problem:
        reasons.append(commit_problem)
    elif commit != pin["commit"]:
        reasons.append(
            f"VEOR checkout is at {commit}, pinned at {pin['commit']}"
        )
    entrypoint = os.path.join(resolved_home, pin["sidecar"]["entrypoint"])
    if not os.path.isfile(entrypoint):
        reasons.append(f"sidecar entrypoint missing: {pin['sidecar']['entrypoint']}")
    detected_node = node_version_override if node_version_override is not None else (node if node is not None else node_version())
    major = node_major(detected_node)
    if major is None:
        reasons.append("Node.js is not available; governance stays blocked rather than allowing")
    elif major < pin["node_major"]:
        reasons.append(
            f"Node.js {detected_node} is older than the pinned minimum v{pin['node_major']}"
        )
    if reasons:
        return GovernanceStatus("BLOCKED", tuple(reasons), digest, resolved_home, detected_node)
    return GovernanceStatus("READY", (), digest, resolved_home, detected_node)


class Sidecar:
    """One-shot JSON-lines client for the pinned VEOR decision kernel."""

    def __init__(self, home, pin, node="node", timeout=60):
        self.home = os.path.abspath(home)
        self.pin = pin
        self.node = node
        self.timeout = timeout
        self.entrypoint = os.path.join(self.home, pin["sidecar"]["entrypoint"])

    def _request(self, method, params):
        request = json.dumps({"id": 1, "method": method, "params": params})
        try:
            result = subprocess.run(
                [self.node, self.entrypoint],
                cwd=self.home,
                input=request + "\n",
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise GovernanceUnavailable(f"cannot run VEOR sidecar: {error}")
        if result.returncode != 0:
            tail = (result.stderr or "").strip()[-400:]
            raise GovernanceUnavailable(
                f"VEOR sidecar exited {result.returncode}: {tail or 'no stderr'}"
            )
        return self._parse(result.stdout)

    @staticmethod
    def _parse(stdout):
        for line in (stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if not isinstance(message, dict) or message.get("id") != 1:
                continue
            if "error" in message:
                raise GovernanceUnavailable(f"VEOR sidecar error: {message['error']}")
            result = message.get("result")
            if not isinstance(result, dict):
                raise GovernanceUnavailable("VEOR sidecar result is not an object")
            return result
        raise GovernanceUnavailable("VEOR sidecar returned no matching JSON response")

    def decide(
        self,
        tool,
        args=None,
        annotations=None,
        advisory="ALLOW",
        catalog_fingerprint=None,
    ):
        if not isinstance(tool, str) or not tool:
            raise GovernanceUnavailable("tool name must be a non-empty string")
        if advisory not in DECISIONS:
            raise GovernanceUnavailable(f"unknown advisory decision: {advisory!r}")
        # Fail-closed default: an unannotated tool is treated as side-effecting.
        effective_annotations = annotations or {
            "readOnlyHint": False,
            "destructiveHint": True,
        }
        result = self._request(
            "decide",
            {
                "tool": {"name": tool, "annotations": effective_annotations},
                "args": args or {},
                "advisoryDecision": advisory,
                "catalogFingerprint": catalog_fingerprint,
            },
        )
        decision = result.get("decision")
        if decision not in DECISIONS:
            raise GovernanceUnavailable(
                f"VEOR returned an unknown decision: {decision!r}"
            )
        reasons = result.get("reasons") or []
        if not isinstance(reasons, list) or not all(
            isinstance(item, str) for item in reasons
        ):
            raise GovernanceUnavailable("VEOR returned malformed reasons")
        policy_digest = result.get("policyDigest")
        if not isinstance(policy_digest, str) or not policy_digest:
            raise GovernanceUnavailable("VEOR returned no policy digest")
        return Decision(decision, tuple(reasons), policy_digest, result)


def bind_result(attestation_digest, return_code, stdout_sha256, stderr_sha256):
    """Deterministic payload a VEOR receipt binds for a WinCreator capture.

    The receipt does not embed the capture; it commits to a digest of these four
    fields, so the two artifacts can be checked against each other later.
    """
    if not _DIGEST_RE.match(str(attestation_digest or "")):
        raise GovernanceUnavailable("attestation_digest must be a sha256 hex digest")
    for label, value in (("stdout_sha256", stdout_sha256), ("stderr_sha256", stderr_sha256)):
        if not _DIGEST_RE.match(str(value or "")):
            raise GovernanceUnavailable(f"{label} must be a sha256 hex digest")
    if return_code is not None and not isinstance(return_code, int):
        raise GovernanceUnavailable("return_code must be an integer or null")
    payload = {
        "attestation_digest": attestation_digest,
        "return_code": return_code,
        "stdout_sha256": stdout_sha256,
        "stderr_sha256": stderr_sha256,
    }
    return {"payload": payload, "digest": sha256_text(canonical_json(payload))}


def interpret_receipt_result(returncode, stdout, stderr=""):
    """Accept only a clean, positive offline verification from VEOR's own CLI."""
    if returncode != 0:
        tail = (stderr or stdout or "").strip()[-400:]
        raise GovernanceUnavailable(
            f"VEOR receipt verification failed with exit {returncode}: {tail or 'no output'}"
        )
    try:
        document = json.loads((stdout or "").strip())
    except ValueError as error:
        raise GovernanceUnavailable(f"VEOR receipt verification output is not JSON: {error}")
    if not isinstance(document, dict):
        raise GovernanceUnavailable("VEOR receipt verification output is not an object")
    if document.get("kind") != _RECEIPT_KIND:
        raise GovernanceUnavailable(
            f"unexpected receipt verification kind: {document.get('kind')!r}"
        )
    if document.get("ok") is not True:
        raise GovernanceUnavailable("VEOR receipt verification did not return ok=true")
    checks = document.get("checks")
    if not isinstance(checks, dict) or checks.get("digest") is not True or checks.get("signature") is not True:
        raise GovernanceUnavailable("VEOR receipt verification did not confirm digest and signature")
    return document


def verify_receipt(home, pin, receipt_path, public_key_path, node="node", timeout=60):
    # The pin lists the verifier entrypoint first, then its fixed sub-command.
    verifier = pin["sidecar"]["receipt_verify"]
    argv = [
        node,
        os.path.join(os.path.abspath(home), verifier[0]),
        *verifier[1:],
        receipt_path,
        "--public",
        public_key_path,
    ]
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as error:
        raise GovernanceUnavailable(f"cannot run VEOR receipt verifier: {error}")
    return interpret_receipt_result(result.returncode, result.stdout, result.stderr)
