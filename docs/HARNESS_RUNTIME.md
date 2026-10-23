# Harness runtime (G01)

`harness/` is a small execution engine for agent work whose result must stay
auditable: typed task contracts, SQLite state, an append-only event journal,
crash-safe resume, and proofs produced by the existing WinCreator kernel.

It does **not** replace or reimplement the proof kernel. Capture, attestation,
review, ledger parsing and verification stay in
`skill/wincreator/scripts/wincreator.py`; the runtime loads it by path and calls
it.

## What it guarantees

1. **No transition outside the declared graph.** `store.TRANSITIONS` is the only
   authority; an illegal edge raises `InvalidTransition` and leaves the store
   unchanged.
2. **`SUCCEEDED` means proven.** The store refuses that state unless a stored
   proof is `CAPTURED_PASS` *and* its review verdict is `EVIDENCED`. A green
   command alone lands in `AWAITING_REVIEW`, never in `SUCCEEDED`.
3. **State and journal commit together.** Every state change writes its event in
   the same SQLite transaction; a killed process leaves both or neither.
4. **The journal is tamper-evident per task.** Each event digest binds the event
   body and the previous event digest. Editing or deleting an event is reported
   by `verify`.
5. **Frozen contracts.** A task's contract digest is stored; re-registering the
   same id with a different claim/gate is refused, and editing `contract_json`
   behind the store's back is detected.

## Quickstart

```bash
python3 -m harness init

python3 -m harness add --id H1 --name "parser rejects malformed input" \
  --claim "parser rejects malformed input" --level Micro --tier lite \
  -- python3 -m pytest -q tests/test_parser.py

python3 -m harness run H1
python3 -m harness status
python3 -m harness verify --require-complete
```

Standard tier stops at `AWAITING_REVIEW`; the review is a separate command and a
separate identity:

```bash
python3 -m harness review H1 --verdict evidenced --reviewer skeptic-01 \
  --challenge "attack whether the captured gate exercises the error path in the claim"
```

A contract can also be supplied as JSON:

```json
{
  "task_id": "H2",
  "name": "export preserves every row",
  "claim": "export preserves every row on the 482-row fixture",
  "level": "Meso",
  "tier": "standard",
  "gate": {
    "command": ["python3", "tests/check_export.py"],
    "timeout_seconds": 300,
    "files": ["tests/check_export.py"],
    "optional_files": ["fixtures/export-expected.csv"]
  },
  "max_attempts": 2
}
```

```bash
python3 -m harness add --contract contracts/H2.json
```

## States

| State | Meaning | Allowed next |
|---|---|---|
| `PENDING` | registered, not admitted | `READY` |
| `READY` | may start an attempt | `RUNNING` |
| `RUNNING` | an attempt owns the task | `SUCCEEDED`, `AWAITING_REVIEW`, `FAILED`, `BLOCKED`, `INTERRUPTED` |
| `INTERRUPTED` | owner died or lease expired | `READY` (retry) |
| `AWAITING_REVIEW` | capture passed, no verdict yet | `SUCCEEDED`, `FAILED`, `BLOCKED` |
| `SUCCEEDED` | `CAPTURED_PASS` + `EVIDENCED` review | terminal |
| `FAILED` | gate failed, disproven, or could not run | `READY` (retry, budget permitting) |
| `BLOCKED` | capture error or `INSUFFICIENT` review | `READY` (retry, budget permitting) |

`retry` requires a stated reason and remaining attempt budget. Every attempt is
persisted before the gate starts.

## Crash safety and at-least-once execution

An attempt row is committed *before* the gate runs, carrying the owner pid and a
lease. `resume` closes an open attempt when its owner process is gone, or when
its lease expired, records an `attempt_abandoned` event, then schedules a retry
if budget remains:

```bash
python3 -m harness resume
python3 -m harness resume --no-retry   # close the attempt, leave it INTERRUPTED
```

Consequences, stated rather than hidden:

- gates are **at-least-once**: an interrupted gate may run twice, so a gate with
  non-idempotent side effects must be made safe or bounded by `max_attempts`;
- a probe for a live owner uses `kill(pid, 0)` on POSIX and `OpenProcess` on
  Windows; if liveness cannot be determined, the lease alone decides;
- a live process whose lease expired may be reaped — this is what a lease means,
  so keep `--lease-seconds` above the longest expected gate.

## Proof integration

For each task the runtime:

1. appends the claim row to `HARNESS_PROOF_LEDGER.md` (refusing silent rewrites of
   an existing row with a different contract);
2. executes the gate through `run_and_attest`, binding claim id, level, text and
   gate;
3. stores the attestation path and digest, plus the review verdict when the
   kernel wrote one (Lite auto-approval);
4. maps the capture to a state: pass + review-required → `AWAITING_REVIEW`,
   pass + `EVIDENCED` → `SUCCEEDED`, fail → `FAILED`, capture error → `BLOCKED`.

`verify` re-checks, from disk and from the ledger:

- the store's own invariants and the event chain of every task;
- every retained attestation (digest, stdout/stderr hashes, attested files);
- every retained review (signature link, capture digest, builder ≠ reviewer);
- that a `SUCCEEDED` task's ledger row is `EVIDENCED` and references the stored
  attestation digest;
- with `--require-complete`, the whole ledger through the kernel and the
  repository's `ledger_check` rules.

Tampering with the database, an attestation, a review, or the journal therefore
fails verification instead of silently passing.

## Layout

```
HARNESS_PROOF_LEDGER.md        # kernel ledger for runtime tasks (project root)
.harness/harness.db            # tasks, attempts, proofs, events
.harness/attestations/<task>/  # kernel captures (stdout, stderr, attestation, review)
.harness/packets/              # blind-safe reviewer packets
```

The ledger sits at the project root on purpose: the kernel records attestation
paths relative to the gate working directory and re-derives them relative to the
ledger directory. A ledger nested under `.harness/` makes every check look
detached.

## G00 audit

```bash
python3 -m harness audit \
  --out .harness-artifacts/g00-audit.json \
  --markdown docs/HARNESS_AUDIT_G00.md
```

The audit derives its inventory from the working tree (paths, line counts,
hashes, git commit, dirty state, versions) and **executes** the repository's
reference gates (`compileall`, the embedded adversarial suites, `pytest`). Any
failing gate fails the audit. The Markdown file is a snapshot, not a standing
claim: regenerate it.

## Governed execution (G02, optional)

When a pinned VEOR sidecar is provisioned, a task can be executed through the
governance path instead of the plain one:

```bash
export VEOR_HOME=/path/to/veor-at-pinned-commit
export VEOR_RECEIPT_PUBLIC_KEY=/secure/veor-receipt.pub.pem
export VEOR_POLICY=/secure/wincreator.policy.json
export VEOR_RUNTIME_DIR=/secure/veor-state
export VEOR_APPROVAL_PUBLIC_KEY=/secure/veor-approval.pub.pem
# VEOR_RECEIPT_PRIVATE_KEY is read by the VEOR process only

python3 tools/veor_check.py                      # 0 READY, 3 BLOCKED
python3 -m harness run-governed G02-01
python3 -m harness verify --require-complete     # re-verifies receipts too
```

The order is the guarantee, and each step refuses to skip the previous one:

1. the pin, package version, git HEAD, dirty state, entrypoint and Node floor
   must match, or nothing runs;
2. VEOR decides on the proposed effect (`wincreator.gate.execute` with the
   contract digest and gate command); `DENY`, `REVIEW` without a consumed
   one-shot approval, a timeout or a malformed answer ends the run with a
   journaled `governance_blocked` event and no gate execution;
3. the decision is written as `governance-decision.json` and passed to the
   kernel as a hashed input, so the attestation commits to the authorization
   that preceded it;
4. the gate runs through the proof kernel exactly as an ungoverned task would;
5. VEOR signs an Ed25519 receipt binding tool, args digest, policy digest,
   decision and a digest of the capture (attestation digest, exit code, stream
   hashes); the receipt is accepted only after VEOR's own verifier exits zero
   with `ok=true`, digest and signature checks, and every bound field matches;
6. the verified receipt is journaled as a `governance_bound` event. It never
   writes a ledger status or a proof verdict.

A task that entered the governance path cannot leave it: `run`, `retry`,
`resume` and `run_ready` refuse or skip it, so a gate can never be re-executed
without a fresh decision. `python3 -m harness verify` re-runs the receipt
verifier and fails if a governed proof has no valid receipt or if any bound
digest no longer matches.

## Honest limits

- Local-only. No remote attestation, no transparency log, no revocation.
- The runtime executes gates with the privileges of the invoking user; there is
  no sandbox. Sandboxed gates are a later gate (see the VEOR decision in
  `docs/VEOR_GUARDIAN_AUDIT.md`).
- Gates are re-run on retry; the runtime does not know how to resume a
  half-executed external process.
- A `CAPTURE_ERROR` (for example a missing attested file) is `BLOCKED`, not
  `FAILED`: the claim was neither proven nor disproven.
- Reaping by lease is a liveness heuristic, not a consensus protocol. Two
  runtimes sharing one store are serialized by SQLite, not coordinated.
- The journal chain is unkeyed, like the kernel's ledger: it detects edits to
  retained events and deletion of an event that has a successor. It does **not**
  resist an attacker who rewrites the whole chain, and it has no external head,
  so truncating trailing events is not detected. Signing or anchoring the chain
  is a later gate, not a claimed property.
- Lite-tier captures are auto-reviewed by the kernel (`auto-approve-lite`).
  `EVIDENCED` there means the mechanical gate passed, not that an independent
  identity reviewed the claim.
- The runtime does not decide whether an action is allowed. In the governed
  path that decision belongs to the pinned VEOR sidecar
  (`harness/governed.py`); the ungoverned path has no governance at all, by
  design, and works with no Node.js installed.
- `harness/` is a repository-local package, not an installed one: run
  `python3 -m harness` from the repository root, or put the root on
  `PYTHONPATH`. Packaging it is a release decision, not a silent side effect.

Governed path (G02) specifically:

- a governed gate still runs as a plain child process: no sandbox, no OS
  isolation. The receipt says `sandbox: none / os_enforced: false`, and the
  decision artifact records the same, because it is true.
- the receipt proves that the holder of the receipt key decided and executed
  this args digest. It does not prove *which* checkout signed it, and there is no
  remote attestation.
- same-user model: the process that runs `run-governed` could in principle read
  the receipt key file. Custody is a filesystem/OS boundary (ADR 0003), not a
  cryptographic one.
- the harness never signs an approval. A `REVIEW` blocks until an operator signs
  the pending challenge with the approval key, out of band. The test suite does
  this itself and is therefore a *test fixture*, not evidence of human approval.
- only the harness surface is governed. A same-user shell can still run the same
  commands directly; VEOR cannot see that, and this delivery claims nothing
  about it.
