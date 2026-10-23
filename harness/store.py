"""Persistent runtime state: SQLite tasks, attempts, proofs and event journal.

The store is deliberately small and explicit. It owns three invariants that
the rest of the runtime may not bypass:

1. only the transitions listed in ``TRANSITIONS`` are accepted;
2. a task may not leave ``RUNNING`` while an attempt is still open, and may
   not enter ``RUNNING`` without an attempt row;
3. ``SUCCEEDED`` requires a stored proof whose capture passed and whose review
   verdict is ``EVIDENCED``.

State changes and their journal event commit in one transaction, so an
interrupted process leaves either both or neither.
"""

from contextlib import contextmanager
from datetime import datetime
import json
import os
import re
import sqlite3
from typing import List

from harness import journal
from harness.contracts import ContractError, TaskContract, TaskView
from harness.util import iso_time, sha256_text, utc_now

SCHEMA_VERSION = "1"
HARNESS_DIR = ".harness"
STATES = (
    "PENDING",
    "READY",
    "RUNNING",
    "INTERRUPTED",
    "AWAITING_REVIEW",
    "SUCCEEDED",
    "FAILED",
    "BLOCKED",
)
TERMINAL_STATES = frozenset({"SUCCEEDED"})
BLOCKING_STATES = frozenset({"FAILED", "BLOCKED", "INTERRUPTED", "AWAITING_REVIEW"})
TRANSITIONS = {
    "PENDING": frozenset({"READY"}),
    "READY": frozenset({"RUNNING", "BLOCKED"}),
    "RUNNING": frozenset({"AWAITING_REVIEW", "SUCCEEDED", "FAILED", "BLOCKED", "INTERRUPTED"}),
    "INTERRUPTED": frozenset({"READY"}),
    "AWAITING_REVIEW": frozenset({"SUCCEEDED", "FAILED", "BLOCKED"}),
    "FAILED": frozenset({"READY"}),
    "BLOCKED": frozenset({"READY"}),
    "SUCCEEDED": frozenset(),
}
CAPTURE_STATUSES = ("CAPTURED_PASS", "CAPTURED_FAIL", "CAPTURE_ERROR")
REVIEW_VERDICTS = ("EVIDENCED", "INSUFFICIENT", "DISPROVEN")
ATTESTATION_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    contract_json TEXT NOT NULL,
    contract_sha256 TEXT NOT NULL,
    name TEXT NOT NULL,
    state TEXT NOT NULL,
    workspace TEXT NOT NULL,
    ledger_path TEXT NOT NULL,
    attest_dir TEXT NOT NULL,
    max_attempts INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
    task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    attempt_no INTEGER NOT NULL,
    state TEXT NOT NULL,
    owner_pid INTEGER,
    owner_token TEXT NOT NULL,
    lease_expires_at TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    outcome TEXT,
    detail TEXT,
    PRIMARY KEY (task_id, attempt_no)
);
CREATE TABLE IF NOT EXISTS proofs (
    proof_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    attempt_no INTEGER NOT NULL,
    attestation_path TEXT NOT NULL,
    attestation_digest TEXT NOT NULL,
    capture_status TEXT NOT NULL,
    return_code INTEGER,
    review_verdict TEXT,
    reviewer TEXT,
    review_digest TEXT,
    recorded_at TEXT NOT NULL,
    UNIQUE (task_id, attempt_no)
);
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    type TEXT NOT NULL,
    at TEXT NOT NULL,
    actor TEXT NOT NULL,
    attempt_no INTEGER,
    payload_json TEXT NOT NULL,
    prev_digest TEXT,
    digest TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_task_seq ON events (task_id, seq);
"""


class StoreError(RuntimeError):
    """The store is missing, unreadable, or inconsistent."""


class UnknownTask(StoreError, KeyError):
    """No task with this identifier is registered."""


class InvalidTransition(StoreError):
    """The requested state change is not part of the state machine."""


class Store:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.harness_dir = os.path.join(self.root, HARNESS_DIR)
        self.db_path = os.path.join(self.harness_dir, "harness.db")
        # The proof kernel records attestation paths relative to the gate cwd and
        # later re-derives them relative to the ledger's directory. Keeping the
        # ledger at the project root keeps those two bases identical; a ledger
        # nested under .harness/ would make every verification look detached.
        self.ledger_path = os.path.join(self.root, "HARNESS_PROOF_LEDGER.md")
        self.attest_dir = os.path.join(self.harness_dir, "attestations")
        self.packet_dir = os.path.join(self.harness_dir, "packets")

    # ----------------------------------------------------------- connection
    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=15, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=15000")
        return connection

    @contextmanager
    def _read(self):
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _write(self):
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.execute("COMMIT")
        except BaseException:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            connection.close()

    # ------------------------------------------------------------- lifecycle
    def initialize(self):
        os.makedirs(self.harness_dir, exist_ok=True)
        os.makedirs(self.attest_dir, exist_ok=True)
        # executescript commits implicitly, so it cannot run inside _write().
        connection = self._connect()
        try:
            connection.executescript(_SCHEMA)
        finally:
            connection.close()
        with self._write() as connection:
            row = connection.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO meta(key, value) VALUES('schema_version', ?)",
                    (SCHEMA_VERSION,),
                )
            elif row["value"] != SCHEMA_VERSION:
                raise StoreError(
                    f"store schema version {row['value']} is not supported "
                    f"(this runtime expects {SCHEMA_VERSION})"
                )
        return self

    def ensure_initialized(self):
        if not os.path.isfile(self.db_path):
            raise StoreError(
                f"no harness store at {self.db_path}; run `python3 -m harness init` first"
            )
        return self

    def schema_version(self):
        self.ensure_initialized()
        with self._read() as connection:
            row = connection.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()
        return row["value"] if row else None

    # ----------------------------------------------------------------- tasks
    def register_task(self, contract: TaskContract, actor="builder"):
        now = iso_time()
        document = contract.to_dict()
        digest = contract.digest()
        with self._write() as connection:
            existing = connection.execute(
                "SELECT * FROM tasks WHERE task_id=?", (contract.task_id,)
            ).fetchone()
            if existing is not None:
                if existing["contract_sha256"] != digest:
                    raise ContractError(
                        f"task {contract.task_id} is already registered with a different "
                        "contract; a changed claim needs a new task id or an explicit "
                        "supersession, never a silent rewrite"
                    )
                return self._task_view(connection, existing["task_id"])
            connection.execute(
                "INSERT INTO tasks(task_id, contract_json, contract_sha256, name, state,"
                " workspace, ledger_path, attest_dir, max_attempts, created_at, updated_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    contract.task_id,
                    json.dumps(document, sort_keys=True),
                    digest,
                    contract.name,
                    "PENDING",
                    self.root,
                    self.ledger_path,
                    self.attest_dir,
                    contract.max_attempts,
                    now,
                    now,
                ),
            )
            self._append_event(
                connection,
                contract.task_id,
                "task_registered",
                actor,
                None,
                {"contract_sha256": digest, "tier": contract.tier, "level": contract.level},
                at=now,
            )
            return self._task_view(connection, contract.task_id)

    def get_task(self, task_id):
        with self._read() as connection:
            return self._task_view(connection, task_id)

    def list_tasks(self, state=None):
        with self._read() as connection:
            if state is None:
                rows = connection.execute(
                    "SELECT task_id FROM tasks ORDER BY created_at, task_id"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT task_id FROM tasks WHERE state=? ORDER BY created_at, task_id",
                    (state,),
                ).fetchall()
            return [self._task_view(connection, row["task_id"]) for row in rows]

    def _task_row(self, connection, task_id):
        row = connection.execute(
            "SELECT * FROM tasks WHERE task_id=?", (task_id,)
        ).fetchone()
        if row is None:
            raise UnknownTask(task_id)
        return row

    def _task_view(self, connection, task_id):
        row = self._task_row(connection, task_id)
        try:
            contract = TaskContract.from_dict(json.loads(row["contract_json"]))
        except (ValueError, TypeError) as error:
            raise StoreError(f"task {task_id} has an unreadable contract: {error}")
        attempts = tuple(
            dict(item)
            for item in connection.execute(
                "SELECT * FROM attempts WHERE task_id=? ORDER BY attempt_no",
                (task_id,),
            ).fetchall()
        )
        proof = connection.execute(
            "SELECT * FROM proofs WHERE task_id=? ORDER BY attempt_no DESC LIMIT 1",
            (task_id,),
        ).fetchone()
        return TaskView(
            task_id=row["task_id"],
            contract=contract,
            state=row["state"],
            workspace=row["workspace"],
            ledger_path=row["ledger_path"],
            attest_dir=row["attest_dir"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            attempts=attempts,
            proof=dict(proof) if proof else None,
        )

    # ------------------------------------------------------------ transitions
    def transition(self, task_id, new_state, actor="runtime", reason=None, expect_state=None):
        if new_state not in STATES:
            raise InvalidTransition(f"unknown target state {new_state!r}")
        with self._write() as connection:
            return self._transition(
                connection, task_id, new_state, actor, reason, expect_state
            )

    def _transition(self, connection, task_id, new_state, actor, reason, expect_state):
        row = self._task_row(connection, task_id)
        current = row["state"]
        if expect_state is not None and current != expect_state:
            raise InvalidTransition(
                f"task {task_id} is {current}, expected {expect_state} for this operation"
            )
        if new_state not in TRANSITIONS.get(current, frozenset()):
            raise InvalidTransition(
                f"task {task_id}: {current} -> {new_state} is not an allowed transition"
            )
        open_attempt = connection.execute(
            "SELECT COUNT(*) AS total FROM attempts WHERE task_id=? AND state='RUNNING'",
            (task_id,),
        ).fetchone()["total"]
        if new_state == "RUNNING" and open_attempt != 1:
            raise InvalidTransition(
                f"task {task_id} cannot enter RUNNING without exactly one open attempt"
            )
        if current == "RUNNING" and new_state != "RUNNING" and open_attempt != 0:
            raise InvalidTransition(
                f"task {task_id} cannot leave RUNNING while an attempt is still open"
            )
        if new_state == "SUCCEEDED":
            self._require_evidenced_proof(connection, task_id)
        now = iso_time()
        connection.execute(
            "UPDATE tasks SET state=?, updated_at=? WHERE task_id=?",
            (new_state, now, task_id),
        )
        self._append_event(
            connection,
            task_id,
            "state_changed",
            actor,
            None,
            {"from": current, "to": new_state, "reason": reason},
            at=now,
        )
        return current

    def _require_evidenced_proof(self, connection, task_id):
        proof = connection.execute(
            "SELECT * FROM proofs WHERE task_id=? ORDER BY attempt_no DESC LIMIT 1",
            (task_id,),
        ).fetchone()
        if proof is None:
            raise InvalidTransition(
                f"task {task_id} cannot be SUCCEEDED without a captured proof"
            )
        if proof["capture_status"] != "CAPTURED_PASS":
            raise InvalidTransition(
                f"task {task_id} capture is {proof['capture_status']}; SUCCEEDED requires "
                "CAPTURED_PASS"
            )
        if proof["review_verdict"] != "EVIDENCED":
            raise InvalidTransition(
                f"task {task_id} has no EVIDENCED review; a passing gate alone is not "
                "a proven claim"
            )

    # -------------------------------------------------------------- attempts
    def begin_attempt(self, task_id, owner_pid=None, lease_seconds=900, actor="runtime"):
        now = utc_now()
        with self._write() as connection:
            row = self._task_row(connection, task_id)
            if row["state"] != "READY":
                raise InvalidTransition(
                    f"task {task_id} is {row['state']}; only READY tasks can start an attempt"
                )
            used = connection.execute(
                "SELECT COUNT(*) AS total FROM attempts WHERE task_id=?", (task_id,)
            ).fetchone()["total"]
            if used >= row["max_attempts"]:
                raise InvalidTransition(
                    f"task {task_id} exhausted its {row['max_attempts']} attempt(s)"
                )
            attempt_no = used + 1
            lease_expires = iso_time(
                datetime.fromtimestamp(now.timestamp() + lease_seconds, now.tzinfo)
            )
            connection.execute(
                "INSERT INTO attempts(task_id, attempt_no, state, owner_pid, owner_token,"
                " lease_expires_at, started_at) VALUES(?,?,?,?,?,?,?)",
                (
                    task_id,
                    attempt_no,
                    "RUNNING",
                    owner_pid,
                    sha256_text(f"{task_id}:{attempt_no}:{now.timestamp()}:{os.getpid()}")[:32],
                    lease_expires,
                    iso_time(now),
                ),
            )
            self._append_event(
                connection,
                task_id,
                "attempt_started",
                actor,
                attempt_no,
                {"owner_pid": owner_pid, "lease_seconds": lease_seconds},
                at=iso_time(now),
            )
            self._transition(connection, task_id, "RUNNING", actor, None, expect_state="READY")
            return attempt_no

    def _attempt_row(self, connection, task_id, attempt_no):
        row = connection.execute(
            "SELECT * FROM attempts WHERE task_id=? AND attempt_no=?",
            (task_id, attempt_no),
        ).fetchone()
        if row is None:
            raise StoreError(f"task {task_id} has no attempt {attempt_no}")
        return row

    def finish_attempt(
        self,
        task_id,
        attempt_no,
        outcome,
        state,
        reason=None,
        detail=None,
        actor="runtime",
    ):
        if state not in TRANSITIONS["RUNNING"]:
            raise InvalidTransition(
                f"finishing an attempt must land on one of {sorted(TRANSITIONS['RUNNING'])}, "
                f"not {state}"
            )
        now = iso_time()
        with self._write() as connection:
            attempt = self._attempt_row(connection, task_id, attempt_no)
            if attempt["state"] != "RUNNING":
                raise InvalidTransition(
                    f"attempt {attempt_no} of {task_id} is already {attempt['state']}"
                )
            connection.execute(
                "UPDATE attempts SET state=?, finished_at=?, outcome=?, detail=?"
                " WHERE task_id=? AND attempt_no=?",
                (
                    "COMPLETED" if state != "INTERRUPTED" else "ABANDONED",
                    now,
                    outcome,
                    detail,
                    task_id,
                    attempt_no,
                ),
            )
            self._append_event(
                connection,
                task_id,
                "attempt_finished",
                actor,
                attempt_no,
                {"outcome": outcome, "state": state, "detail": detail},
                at=now,
            )
            self._transition(connection, task_id, state, actor, reason, expect_state="RUNNING")

    def abandon_attempt(self, task_id, attempt_no, reason, actor="resume"):
        with self._write() as connection:
            attempt = self._attempt_row(connection, task_id, attempt_no)
            if attempt["state"] != "RUNNING":
                raise InvalidTransition(
                    f"attempt {attempt_no} of {task_id} is already {attempt['state']}"
                )
            now = iso_time()
            connection.execute(
                "UPDATE attempts SET state='ABANDONED', finished_at=?, outcome='INTERRUPTED',"
                " detail=? WHERE task_id=? AND attempt_no=?",
                (now, reason, task_id, attempt_no),
            )
            self._append_event(
                connection,
                task_id,
                "attempt_abandoned",
                actor,
                attempt_no,
                {"reason": reason},
                at=now,
            )
            self._transition(
                connection, task_id, "INTERRUPTED", actor, reason, expect_state="RUNNING"
            )

    def retry(self, task_id, reason, actor="runtime"):
        with self._write() as connection:
            row = self._task_row(connection, task_id)
            if row["state"] not in {"FAILED", "BLOCKED", "INTERRUPTED"}:
                raise InvalidTransition(
                    f"task {task_id} is {row['state']}; retry needs FAILED, BLOCKED or "
                    "INTERRUPTED"
                )
            used = connection.execute(
                "SELECT COUNT(*) AS total FROM attempts WHERE task_id=?", (task_id,)
            ).fetchone()["total"]
            if used >= row["max_attempts"]:
                raise InvalidTransition(
                    f"task {task_id} exhausted its {row['max_attempts']} attempt(s)"
                )
            previous = row["state"]
            self._transition(connection, task_id, "READY", actor, reason, expect_state=previous)
            self._append_event(
                connection, task_id, "retry_scheduled", actor, None, {"reason": reason}
            )
            return previous

    def current_attempt(self, task_id):
        with self._read() as connection:
            row = connection.execute(
                "SELECT * FROM attempts WHERE task_id=? ORDER BY attempt_no DESC LIMIT 1",
                (task_id,),
            ).fetchone()
        return dict(row) if row else None

    def open_attempt(self, task_id):
        with self._read() as connection:
            row = connection.execute(
                "SELECT * FROM attempts WHERE task_id=? AND state='RUNNING'"
                " ORDER BY attempt_no DESC LIMIT 1",
                (task_id,),
            ).fetchone()
        return dict(row) if row else None

    # ----------------------------------------------------------------- proofs
    def record_proof(
        self,
        task_id,
        attempt_no,
        attestation_path,
        attestation_digest,
        capture_status,
        return_code=None,
        review_verdict=None,
        reviewer=None,
        review_digest=None,
        actor="runtime",
    ):
        if capture_status not in CAPTURE_STATUSES:
            raise StoreError(f"invalid capture status {capture_status!r}")
        if review_verdict is not None and review_verdict not in REVIEW_VERDICTS:
            raise StoreError(f"invalid review verdict {review_verdict!r}")
        if not ATTESTATION_DIGEST_RE.match(str(attestation_digest or "")):
            raise StoreError("attestation digest must be a sha256 hex digest")
        now = iso_time()
        with self._write() as connection:
            self._attempt_row(connection, task_id, attempt_no)
            connection.execute(
                "INSERT INTO proofs(task_id, attempt_no, attestation_path, attestation_digest,"
                " capture_status, return_code, review_verdict, reviewer, review_digest,"
                " recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    task_id,
                    attempt_no,
                    attestation_path,
                    attestation_digest,
                    capture_status,
                    return_code,
                    review_verdict,
                    reviewer,
                    review_digest,
                    now,
                ),
            )
            self._append_event(
                connection,
                task_id,
                "proof_recorded",
                actor,
                attempt_no,
                {
                    "attestation_path": attestation_path,
                    "attestation_digest": attestation_digest,
                    "capture_status": capture_status,
                    "review_verdict": review_verdict,
                },
                at=now,
            )

    def record_review(self, task_id, attempt_no, verdict, reviewer, review_digest, actor=None):
        if verdict not in REVIEW_VERDICTS:
            raise StoreError(f"invalid review verdict {verdict!r}")
        now = iso_time()
        with self._write() as connection:
            row = connection.execute(
                "SELECT * FROM proofs WHERE task_id=? AND attempt_no=?",
                (task_id, attempt_no),
            ).fetchone()
            if row is None:
                raise StoreError(f"task {task_id} has no proof for attempt {attempt_no}")
            if row["review_verdict"] is not None:
                raise StoreError(
                    f"task {task_id} attempt {attempt_no} already has an immutable review"
                )
            connection.execute(
                "UPDATE proofs SET review_verdict=?, reviewer=?, review_digest=?"
                " WHERE task_id=? AND attempt_no=?",
                (verdict, reviewer, review_digest, task_id, attempt_no),
            )
            self._append_event(
                connection,
                task_id,
                "review_recorded",
                actor or reviewer,
                attempt_no,
                {"verdict": verdict, "reviewer": reviewer, "review_digest": review_digest},
                at=now,
            )

    def latest_proof(self, task_id):
        with self._read() as connection:
            row = connection.execute(
                "SELECT * FROM proofs WHERE task_id=? ORDER BY attempt_no DESC LIMIT 1",
                (task_id,),
            ).fetchone()
        return dict(row) if row else None

    # ---------------------------------------------------------------- journal
    def _append_event(
        self, connection, task_id, event_type, actor, attempt_no, payload, at=None
    ):
        at = at or iso_time()
        previous = connection.execute(
            "SELECT digest FROM events WHERE task_id=? ORDER BY seq DESC LIMIT 1",
            (task_id,),
        ).fetchone()
        prev_digest = previous["digest"] if previous else None
        digest = journal.event_digest(
            task_id, event_type, at, actor, attempt_no, payload, prev_digest
        )
        connection.execute(
            "INSERT INTO events(task_id, type, at, actor, attempt_no, payload_json,"
            " prev_digest, digest) VALUES(?,?,?,?,?,?,?,?)",
            (
                task_id,
                event_type,
                at,
                actor,
                attempt_no,
                json.dumps(payload, sort_keys=True, ensure_ascii=False),
                prev_digest,
                digest,
            ),
        )

    def record_governance_event(
        self, task_id, attempt_no, payload, actor="governance", event_type="governance_bound"
    ):
        """Journal-only record; it never writes a proof verdict or a status."""
        if not isinstance(payload, dict):
            raise StoreError("governance payload must be an object")
        if not str(event_type).startswith("governance_"):
            raise StoreError(f"invalid governance event type: {event_type!r}")
        with self._write() as connection:
            self._task_row(connection, task_id)
            self._append_event(
                connection, task_id, event_type, actor, attempt_no, payload
            )

    def events(self, task_id=None):
        with self._read() as connection:
            if task_id is None:
                rows = connection.execute(
                    "SELECT * FROM events ORDER BY seq"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM events WHERE task_id=? ORDER BY seq", (task_id,)
                ).fetchall()
        return journal.decode_rows(rows)

    # ----------------------------------------------------------- verification
    def verify_integrity(self):
        problems: List[str] = []
        if not os.path.isfile(self.db_path):
            return [f"store missing: {self.db_path}"]
        with self._read() as connection:
            meta = connection.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()
            if meta is None or meta["value"] != SCHEMA_VERSION:
                problems.append(
                    f"store schema version is {meta['value'] if meta else None}, "
                    f"expected {SCHEMA_VERSION}"
                )
            task_ids = [
                row["task_id"]
                for row in connection.execute("SELECT task_id FROM tasks ORDER BY task_id")
            ]
            for task_id in task_ids:
                problems.extend(self._verify_task(connection, task_id))
        return problems

    def _verify_task(self, connection, task_id):
        problems: List[str] = []
        row = self._task_row(connection, task_id)
        if row["state"] not in STATES:
            problems.append(f"{task_id}: unknown persisted state {row['state']!r}")
        try:
            contract = TaskContract.from_dict(json.loads(row["contract_json"]))
        except (ValueError, TypeError) as error:
            problems.append(f"{task_id}: unreadable contract: {error}")
            return problems
        if contract.digest() != row["contract_sha256"]:
            problems.append(f"{task_id}: contract_json does not match its stored digest")
        attempts = connection.execute(
            "SELECT * FROM attempts WHERE task_id=? ORDER BY attempt_no", (task_id,)
        ).fetchall()
        if len(attempts) > row["max_attempts"]:
            problems.append(
                f"{task_id}: {len(attempts)} attempts exceed max_attempts={row['max_attempts']}"
            )
        for index, attempt in enumerate(attempts, start=1):
            if attempt["attempt_no"] != index:
                problems.append(
                    f"{task_id}: attempt numbering is not contiguous at {attempt['attempt_no']}"
                )
        open_attempts = [item for item in attempts if item["state"] == "RUNNING"]
        if row["state"] == "RUNNING":
            if len(open_attempts) != 1:
                problems.append(
                    f"{task_id}: RUNNING task has {len(open_attempts)} open attempt(s)"
                )
        elif open_attempts:
            problems.append(
                f"{task_id}: {row['state']} task still has an open attempt"
            )
        proofs = connection.execute(
            "SELECT * FROM proofs WHERE task_id=? ORDER BY attempt_no", (task_id,)
        ).fetchall()
        for proof in proofs:
            if not ATTESTATION_DIGEST_RE.match(proof["attestation_digest"] or ""):
                problems.append(
                    f"{task_id}: proof {proof['attempt_no']} has a malformed attestation digest"
                )
            if proof["capture_status"] not in CAPTURE_STATUSES:
                problems.append(
                    f"{task_id}: proof {proof['attempt_no']} has an unknown capture status"
                )
            if proof["review_verdict"] is not None and proof["review_verdict"] not in REVIEW_VERDICTS:
                problems.append(
                    f"{task_id}: proof {proof['attempt_no']} has an unknown review verdict"
                )
        if row["state"] == "SUCCEEDED":
            latest = proofs[-1] if proofs else None
            if latest is None:
                problems.append(f"{task_id}: SUCCEEDED without any stored proof")
            elif latest["capture_status"] != "CAPTURED_PASS" or latest["review_verdict"] != "EVIDENCED":
                problems.append(
                    f"{task_id}: SUCCEEDED without CAPTURED_PASS + EVIDENCED proof"
                )
        events = journal.decode_rows(
            connection.execute(
                "SELECT * FROM events WHERE task_id=? ORDER BY seq", (task_id,)
            ).fetchall()
        )
        if not events:
            problems.append(f"{task_id}: no journal events")
        problems.extend(f"{task_id}: {item}" for item in journal.verify_chain(events))
        return problems
