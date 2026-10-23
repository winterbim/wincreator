"""Typed task contracts for the harness runtime.

A contract is the frozen, digestible description of one unit of agent work:
what is claimed, at which loop level, which tier of ceremony applies, and the
exact gate command that must be executed through the WinCreator proof kernel.
Parsing is strict: unknown fields are rejected so a typo cannot silently
change what was promised.
"""

from dataclasses import dataclass, field
import re
import shlex
from typing import Any, Dict, Mapping, Optional, Tuple

from harness.util import canonical_json, sha256_text

LEVELS = ("Macro", "Meso", "Micro", "Nano")
TIERS = ("lite", "standard", "regulated")
CONTRACT_SCHEMA = "wincreator.harness.contract/v1"
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_MAX_ATTEMPTS = 20


class ContractError(ValueError):
    """The task contract is malformed or internally inconsistent."""


@dataclass(frozen=True)
class GateSpec:
    """The real command that proves the claim, plus its bound inputs."""

    command: Tuple[str, ...]
    timeout_seconds: Optional[float] = None
    files: Tuple[str, ...] = ()
    optional_files: Tuple[str, ...] = ()

    def command_string(self):
        return shlex.join(self.command)

    def to_dict(self):
        return {
            "command": list(self.command),
            "timeout_seconds": self.timeout_seconds,
            "files": list(self.files),
            "optional_files": list(self.optional_files),
        }


@dataclass(frozen=True)
class TaskContract:
    task_id: str
    name: str
    claim: str
    level: str
    tier: str
    gate: GateSpec
    max_attempts: int = 3
    require_review: Optional[bool] = None

    def __post_init__(self):
        if not isinstance(self.task_id, str) or not _ID_RE.match(self.task_id):
            raise ContractError(
                "task_id must match [A-Za-z0-9][A-Za-z0-9._-]{0,63}: "
                f"{self.task_id!r}"
            )
        if not isinstance(self.name, str) or not self.name.strip():
            raise ContractError("name must be a non-empty string")
        if len(self.name) > 200:
            raise ContractError("name must be at most 200 characters")
        if not isinstance(self.claim, str) or not self.claim.strip():
            raise ContractError("claim must be a non-empty string")
        if "\n" in self.claim or "\r" in self.claim:
            raise ContractError("claim must be a single line")
        if self.level not in LEVELS:
            raise ContractError(f"level must be one of {LEVELS}: {self.level!r}")
        if self.tier not in TIERS:
            raise ContractError(f"tier must be one of {TIERS}: {self.tier!r}")
        if not isinstance(self.gate, GateSpec):
            raise ContractError("gate must be a GateSpec")
        if not self.gate.command:
            raise ContractError("gate.command must not be empty")
        for token in self.gate.command:
            if not isinstance(token, str) or not token or "\x00" in token:
                raise ContractError(f"gate.command token is invalid: {token!r}")
        if self.gate.timeout_seconds is not None and not (
            isinstance(self.gate.timeout_seconds, (int, float))
            and not isinstance(self.gate.timeout_seconds, bool)
            and self.gate.timeout_seconds > 0
        ):
            raise ContractError("gate.timeout_seconds must be a positive number")
        if not isinstance(self.max_attempts, int) or isinstance(self.max_attempts, bool):
            raise ContractError("max_attempts must be an integer")
        if not 1 <= self.max_attempts <= _MAX_ATTEMPTS:
            raise ContractError(f"max_attempts must be between 1 and {_MAX_ATTEMPTS}")
        if self.require_review is None:
            object.__setattr__(
                self, "require_review", self.tier in {"standard", "regulated"}
            )
        elif not isinstance(self.require_review, bool):
            raise ContractError("require_review must be a boolean or null")
        elif self.tier in {"standard", "regulated"} and not self.require_review:
            raise ContractError(
                f"tier {self.tier} cannot disable independent review; "
                "the proof kernel enforces it"
            )

    def to_dict(self):
        return {
            "schema": CONTRACT_SCHEMA,
            "task_id": self.task_id,
            "name": self.name,
            "claim": self.claim,
            "level": self.level,
            "tier": self.tier,
            "gate": self.gate.to_dict(),
            "max_attempts": self.max_attempts,
            "require_review": self.require_review,
        }

    def digest(self):
        return sha256_text(canonical_json(self.to_dict()))

    @classmethod
    def from_dict(cls, document: Mapping[str, Any]):
        if not isinstance(document, Mapping):
            raise ContractError("contract must be a JSON object")
        allowed = {
            "schema", "task_id", "name", "claim", "level", "tier", "gate",
            "max_attempts", "require_review",
        }
        unknown = sorted(set(document) - allowed)
        if unknown:
            raise ContractError("contract has unsupported field(s): " + ", ".join(unknown))
        if "schema" in document and document["schema"] != CONTRACT_SCHEMA:
            raise ContractError(
                f"contract schema must be {CONTRACT_SCHEMA!r}: {document['schema']!r}"
            )
        required = ("task_id", "name", "claim", "level", "tier", "gate")
        missing = [key for key in required if key not in document]
        if missing:
            raise ContractError("contract missing required field(s): " + ", ".join(missing))
        gate_document = document["gate"]
        if not isinstance(gate_document, Mapping):
            raise ContractError("contract gate must be an object")
        gate_allowed = {"command", "timeout_seconds", "files", "optional_files"}
        gate_unknown = sorted(set(gate_document) - gate_allowed)
        if gate_unknown:
            raise ContractError(
                "gate has unsupported field(s): " + ", ".join(gate_unknown)
            )
        command = gate_document.get("command")
        if not isinstance(command, (list, tuple)):
            raise ContractError("gate.command must be a list of strings")
        files = gate_document.get("files", [])
        optional_files = gate_document.get("optional_files", [])
        for label, value in (("gate.files", files), ("gate.optional_files", optional_files)):
            if not isinstance(value, (list, tuple)) or not all(
                isinstance(item, str) and item for item in value
            ):
                raise ContractError(f"{label} must be a list of non-empty strings")
        return cls(
            task_id=document["task_id"],
            name=document["name"],
            claim=document["claim"],
            level=document["level"],
            tier=document["tier"],
            gate=GateSpec(
                command=tuple(command),
                timeout_seconds=gate_document.get("timeout_seconds"),
                files=tuple(files),
                optional_files=tuple(optional_files),
            ),
            max_attempts=document.get("max_attempts", 3),
            require_review=document.get("require_review"),
        )


@dataclass(frozen=True)
class TaskView:
    """Read-only projection of one persisted task."""

    task_id: str
    contract: TaskContract
    state: str
    workspace: str
    ledger_path: str
    attest_dir: str
    created_at: str
    updated_at: str
    attempts: Tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    proof: Optional[Mapping[str, Any]] = None
