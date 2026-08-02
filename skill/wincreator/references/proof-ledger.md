# Proof Ledger — format specification

The Proof Ledger is a plain markdown file (default name: `PROOF_LEDGER.md`)
kept at the root of the task or project. It exists so that "it works" is
never a sentence — it is always a row with a status and, when evidenced, a
pointer to a proof that was actually executed.

## Format

One markdown table. Columns are fixed. One row per claim.

```markdown
# Proof Ledger — <task or project name>

| ID | Level | Claim | Gate (what proves it) | Status | Evidence |
|----|-------|-------|------------------------|--------|----------|
| P1 | Meso  | /export endpoint generates a conformant report for all active cases | Run on full real dataset + compare 3 known reference cases | EVIDENCED | run 2026-07-10: `pytest tests/test_export.py -v` → 12 passed; diff vs refs: 0 |
| P2 | Micro | parser rejects malformed input with explicit error | unit test with truncated file | PENDING | command given to dev: `cargo test parser::malformed` — awaiting pasted output |
| P3 | Micro | perf ≥ target on large files | benchmark on real corpus | WAIVED | user 2026-07-10: "ship without the benchmark, we'll measure next sprint" |
```

## Status semantics (exactly seven since v3)

Two statuses block a loop from reporting done: `CLAIMED` and `DISPROVEN`.

- `CLAIMED` — asserted, no evidence yet. A working state only. **No loop may
  report "done" while a CLAIMED row remains.**
- `EVIDENCED` — the Evidence cell must carry an execution trace: an exit
  code, an attestation sha256, a CI run URL, or a named command together
  with a dated/raw result. An empty, vague or purely narrative cell makes the
  row invalid.
- `DISPROVEN` — the gate ran and the claim turned out **false**. Same
  evidence requirement as EVIDENCED: a negative result is a result, and it
  is kept. Blocking, because a false claim is not a finished loop.
- `PENDING` — the proof is defined but cannot be executed in the current
  context (no execution tool; runs on the developer's machine). The Evidence
  cell must contain the exact command handed to the developer.
- `BLOCKED` — the gate cannot run because of an external dependency. The
  Evidence cell must **name** the blocker (who/what is awaited) and carry a
  date. "Blocked" without a named blocker is an excuse, not a status.
- `WAIVED` — the user explicitly accepted proceeding without proof. The
  Evidence cell must quote or closely paraphrase the user's words and date.
  Waivers are visible debt, never a silent pass.
- `SUPERSEDED` — the claim was replaced by a reformulated one. The Evidence
  cell must name the successor row (`superseded by P-014`), so the trail is
  never broken by a rewrite.

## Rules

1. Only the Skeptic role writes or changes a Status (see
   `references/agents.md`).
2. Statuses only move forward within a loop: CLAIMED → (EVIDENCED |
   DISPROVEN | PENDING | BLOCKED | WAIVED). A PENDING or BLOCKED row becomes
   EVIDENCED only when the raw result arrives and is inspected.
3. If new evidence contradicts an EVIDENCED row (a regression), the row goes
   to DISPROVEN and the loop that owned it reopens. Never delete a DISPROVEN
   row and never quietly downgrade it: fix the thing and re-prove it, or
   reformulate the claim in a new row and mark the old one SUPERSEDED.
4. At the end of every Meso loop, run the mechanical check:

   ```
   python scripts/ledger_check.py PROOF_LEDGER.md
   ```

   Exit code 0 = ledger clean (no CLAIMED or DISPROVEN rows, every row
   carrying what its status requires). Non-zero = the loop is not allowed to
   report "done". This is deliberately CI-friendly: add it to your pipeline
   if you have one. `--strict-attestation` additionally requires every
   EVIDENCED/DISPROVEN row to cite a captured attestation — the Regulated
   tier.

5. Whenever the gate is a command you can actually run, do not write the
   Evidence cell at all — capture it:

   ```
   python3 scripts/wincreator.py prove P2 -- pytest tests/test_export.py -q
   ```

   The captured sentence is machine-owned: append your notes after it, never
   rewrite it. `wincreator.py verify --ledger PROOF_LEDGER.md` re-derives it
   from the attestation and reports any row whose status or text drifted
   from what was actually captured.

## Why this exists

Every AI-assisted workflow eventually hits the same failure: the assistant
(or the tired developer) writes "done, tested" and the claim is never
auditable afterwards. The ledger borrows segregation-of-duties from financial
auditing: the record of what is proven is separate from the person proving
it, machine-checkable, and cheap enough (one table) to actually be kept.

## Known limits of the mechanical check

`ledger_check.py` is a first-line structural gate, not a semantic judge. It
catches forgotten CLAIMED rows, empty evidence, and invalid statuses — the
common, silent failures. It cannot tell whether the evidence text is
truthful; that is exactly the Skeptic role's job (`references/agents.md`).
What it DOES enforce since v2 (each rule born from a real adversarial test,
replayable via `ledger_check.py --self-test`):

- pipes inside cells escaped as `\|` are parsed correctly (v1 choked on
  the very escaping this spec requires — a doc↔tool contradiction);
- only tables matching the ledger header are checked, so a ledger can live
  in a file containing other markdown tables;
- `**EVIDENCED**` and other emphasis around statuses is tolerated;
- an EVIDENCED row must contain an execution marker (command, date, path,
  output fragment). "ça marche bien" is 14 characters of nothing: prose
  alone is not proof.

Since v2.2 (EVO-002), the per-status "must contain" rules are enforced
symmetrically, not only for EVIDENCED:

- a PENDING row must contain a command marker (the exact command handed to
  the developer). A vague "we'll get to it later" is rejected.
- a WAIVED row must contain a date (the ISO date of the user's decision).
  A dateless "user said skip it" is rejected.

Since v3.0 (the audit of 2026-08-02), each status is checked against its own
marker instead of one shared heuristic — the old `EXEC_MARKER` let a bare
date satisfy a PENDING row that was supposed to carry a command. EVIDENCED
and DISPROVEN now need an execution trace (exit code, attestation digest, CI
run URL, or a named command *plus* a dated/raw result); a lone date, a lone
URL or "test passed" prose no longer qualifies. SUPERSEDED needs a named
successor, BLOCKED a named blocker and a date.

These remain structural proxies, honestly limited: they check the required
element is present, not that it is faithful — that stays the Skeptic's job,
unless the row was produced by `wincreator prove`, in which case the exit
code and the hashes carry it instead. Since v2.3 (EVO-003), `--catches` is schema-gated
the same way the ledger parser is: only rows under a real catches header
(`Date | Class(e)…`) count, so a foreign table with an ISO date no longer
reads as a live catch.

Since v2.4 (EVO-004), keep all ledger rows in ONE contiguous table: a blank
line ends the table (that is how foreign tables stay isolated). A row that
carries a valid status in its Status column but sits outside the table —
detached by a blank line, or orphaned by a header typo — is flagged rather
than silently skipped, so a `CLAIMED` row can never escape the audit by
being visually separated.

Since v2.5 (EVO-005), the parser is structurally aware:

- lines inside ``` or ~~~ fenced code blocks are skipped, so a ledger example
  written in the documentation is not mistaken for a live ledger;
- a foreign table is recognized by its header+separator, so a non-ledger
  table that happens to have a column named "Status" (a roadmap, a kanban)
  does NOT trip the orphan check — its rows belong to their own table;
- orphan detection needs only the Status column, so a `CLAIMED` row whose
  empty Evidence column was omitted (5 cells) is still caught.

**Format requirement (documented limit):** a ledger row must use both a
leading and a trailing pipe (`| … |`). A row missing an edge pipe is not
recognized as a table row and is skipped — the tool does not parse pipe-less
lines, because that would mis-read ordinary prose containing "|". If a row
seems ignored, check its edge pipes first.

**Best-effort orphan detection (documented limit).** Distinguishing a
detached ledger row from a row belonging to another table cannot be decided
from a single row's shape. The gate does its best (blank-line and header
tracking), but a ledger row glued with NO blank line directly under a foreign
table is read as part of that table and will not be audited. Practical rule:
**keep the ledger as one contiguous table, and separate it from any other
table with a blank line.** Do not append ledger rows onto an unrelated table.
This is a deliberate stopping point: two prior attempts to make the heuristic
airtight each traded one false verdict for its opposite, so the project
declined to add further positional heuristics. The Skeptic remains the
backstop for anything the structural gate cannot see — as it is meant to be.
