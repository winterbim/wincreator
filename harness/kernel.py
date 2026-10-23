"""Adapter over the existing WinCreator Proof Kernel.

The runtime does not reimplement capture, attestation, review or ledger
verification: it loads the shipped kernel modules by path and calls their
public functions. ``skill_root`` can be overridden with
``WINCREATOR_SKILL_ROOT`` so an installed skill copy is used verbatim.
"""

import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Dict

from harness.contracts import ContractError, TaskContract

LEDGER_HEADER = (
    "# Harness runtime proof ledger\n\n"
    "Rows are created by `python3 -m harness` and captured through the "
    "WinCreator proof kernel. Do not hand-edit evidence.\n\n"
    "| ID | Level | Claim | Gate (what proves it) | Status | Evidence |\n"
    "|----|-------|-------|------------------------|--------|----------|\n"
)

_MODULES: Dict[str, object] = {}


class KernelUnavailable(RuntimeError):
    """The WinCreator proof kernel could not be located or loaded."""


def skill_root():
    override = os.environ.get("WINCREATOR_SKILL_ROOT")
    if override:
        root = Path(override).expanduser().resolve()
    else:
        root = Path(__file__).resolve().parents[1] / "skill" / "wincreator"
    if not (root / "scripts" / "wincreator.py").is_file():
        raise KernelUnavailable(f"no WinCreator proof kernel under {root}")
    return root


def _load(module_name, public_name):
    if public_name in sys.modules and getattr(
        sys.modules[public_name], "__file__", ""
    ) == str(skill_root() / "scripts" / f"{module_name}.py"):
        return sys.modules[public_name]
    path = skill_root() / "scripts" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(public_name, path)
    if spec is None or spec.loader is None:
        raise KernelUnavailable(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[public_name] = module
    spec.loader.exec_module(module)
    return module


def kernel():
    return _MODULES.setdefault("wincreator", _load("wincreator", "wincreator"))


def challenge_packet():
    # challenge_packet.py imports the module named `wincreator`; load that first.
    kernel()
    return _MODULES.setdefault(
        "challenge_packet", _load("challenge_packet", "wincreator.challenge_packet")
    )


def ledger_check():
    return _MODULES.setdefault(
        "ledger_check", _load("ledger_check", "wincreator.ledger_check")
    )


def ledger_violations(ledger_path):
    """Run the shipped mechanical ledger gate against the runtime ledger."""
    path = Path(ledger_path)
    if not path.is_file():
        return [f"runtime ledger missing: {ledger_path}"]
    text = path.read_text(encoding="utf-8")
    violations, rows = ledger_check().check_text(text, label=str(ledger_path))
    if rows == 0 and not violations:
        return [f"no ledger table found in {ledger_path}"]
    return list(violations)


def ensure_claim(ledger_path, contract: TaskContract):
    """Create the kernel ledger row for a task, refusing silent rewrites."""
    api = kernel()
    path = Path(ledger_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    gate_cell = "`" + contract.gate.command_string() + "`"
    row = (
        "| "
        + " | ".join(
            api.escape_cell(value)
            for value in (
                contract.task_id,
                contract.level,
                contract.claim,
                gate_cell,
                "CLAIMED",
                "",
            )
        )
        + " |\n"
    )
    with api._file_lock(str(path)):
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        if existing.strip():
            try:
                claim = api.read_claim(str(path), contract.task_id)
            except KeyError:
                claim = None
            if claim is not None:
                mismatches = [
                    f"{label}: ledger has {claim[key]!r}, contract says {value!r}"
                    for label, key, value in (
                        ("level", "level", contract.level),
                        ("claim", "text", contract.claim),
                        ("gate", "gate", gate_cell),
                    )
                    if claim[key] != value
                ]
                if mismatches:
                    raise ContractError(
                        f"task {contract.task_id} already has a different ledger row; "
                        "a changed claim needs a new task id or a supersession, not a "
                        "silent rewrite (" + "; ".join(mismatches) + ")"
                    )
                return str(path)
            if not existing.endswith("\n"):
                existing += "\n"
        else:
            existing = LEDGER_HEADER
        mode = (os.stat(path).st_mode & 0o777) if path.is_file() else 0o600
        api._atomic_write(str(path), (existing + row).encode("utf-8"), mode)
    return str(path)


def capture(
    contract: TaskContract,
    ledger_path,
    attest_dir,
    workspace,
    builder=None,
    extra_files=(),
):
    api = kernel()
    return api.run_and_attest(
        contract.task_id,
        list(contract.gate.command),
        ledger=ledger_path,
        files=list(contract.gate.files) + list(extra_files),
        optional_files=list(contract.gate.optional_files),
        attest_dir=attest_dir,
        cwd=workspace,
        timeout=contract.gate.timeout_seconds,
        quiet=True,
        tier=contract.tier,
        builder=builder,
        auto_approve_lite=(contract.tier == "lite" and not contract.require_review),
    )


def capture_review(attestation_path):
    """Return the kernel-written review next to a capture, if any."""
    review_path = os.path.join(os.path.dirname(attestation_path), "review.json")
    if not os.path.isfile(review_path):
        return None, None
    with open(review_path, encoding="utf-8") as handle:
        return json.load(handle), review_path


def review(
    attestation_path,
    verdict,
    reviewer,
    ledger_path,
    challenge,
    packet_path=None,
    automatic=False,
    expected_claim_id=None,
):
    return kernel().review_attestation(
        attestation_path,
        verdict,
        reviewer,
        ledger=ledger_path,
        automatic=automatic,
        expected_claim_id=expected_claim_id,
        challenge=challenge,
        challenge_packet=packet_path,
    )


def write_challenge_packet(attestation_path, out_path):
    api = challenge_packet()
    packet = api.create_packet(attestation_path)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    api.write_packet(packet, out_path)
    return packet, out_path


def verify_attestation(path):
    return kernel().verify_attestation(path)


def verify_review(path, capture_path):
    return kernel().verify_review(path, capture_path)


def verify_ledger(ledger_path):
    return kernel().verify_ledger_references(ledger_path)


def claim_status(ledger_path, task_id):
    return kernel().read_claim(ledger_path, task_id)
