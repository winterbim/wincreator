"""Append-only event journal with a per-task hash chain.

Every state change of a task is recorded as one event whose digest binds the
event body and the digest of the previous event of the same task. Editing or
deleting an event breaks the chain, which ``verify`` recomputes from scratch.
The journal is written in the same SQLite transaction as the state change, so
a crash can never leave a state change without its event.
"""

import json
from typing import Any, Dict, Iterable, List, Mapping

from harness.util import canonical_json, sha256_text

EVENT_SCHEMA = "wincreator.harness.event/v1"


def event_body(
    task_id: str,
    event_type: str,
    at: str,
    actor: str,
    attempt_no: Any,
    payload: Mapping[str, Any],
    prev_digest: Any,
):
    return {
        "schema": EVENT_SCHEMA,
        "task_id": task_id,
        "type": event_type,
        "at": at,
        "actor": actor,
        "attempt_no": attempt_no,
        "payload": dict(payload),
        "prev_digest": prev_digest,
    }


def event_digest(
    task_id: str,
    event_type: str,
    at: str,
    actor: str,
    attempt_no: Any,
    payload: Mapping[str, Any],
    prev_digest: Any,
):
    return sha256_text(
        canonical_json(event_body(task_id, event_type, at, actor, attempt_no, payload, prev_digest))
    )


def decode_rows(rows: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    decoded = []
    for row in rows:
        item = dict(row)
        try:
            item["payload"] = json.loads(item.pop("payload_json"))
        except (TypeError, ValueError) as error:
            raise ValueError(f"event {item.get('seq')} payload is not valid JSON: {error}")
        decoded.append(item)
    return decoded


def verify_chain(rows: Iterable[Mapping[str, Any]]) -> List[str]:
    """Recompute one task's chain. ``rows`` must be in ascending seq order."""
    problems: List[str] = []
    previous_digest = None
    previous_seq = None
    for row in rows:
        seq = row.get("seq")
        task_id = row.get("task_id")
        if previous_seq is not None and seq is not None and seq <= previous_seq:
            problems.append(f"event seq {seq} is not strictly increasing")
        if row.get("prev_digest") != previous_digest:
            problems.append(f"event seq {seq}: prev_digest does not link to its predecessor")
        expected = event_digest(
            task_id,
            row.get("type"),
            row.get("at"),
            row.get("actor"),
            row.get("attempt_no"),
            row.get("payload") or {},
            row.get("prev_digest"),
        )
        if row.get("digest") != expected:
            problems.append(f"event seq {seq}: digest mismatch — the event body was edited")
        previous_digest = row.get("digest")
        previous_seq = seq
    return problems
