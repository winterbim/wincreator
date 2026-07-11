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

## Status semantics (exactly four)

- `CLAIMED` — asserted, no evidence yet. A working state only. **No loop may
  report "done" while a CLAIMED row remains.**
- `EVIDENCED` — the Evidence cell must contain the command/action that was
  actually executed AND a reference to its raw result (inline summary of the
  raw output, a file path, a CI run link). An empty or vague Evidence cell
  makes the row invalid.
- `PENDING` — the proof is defined but cannot be executed in the current
  context (no execution tool; runs on the developer's machine). The Evidence
  cell must contain the exact command handed to the developer.
- `WAIVED` — the user explicitly accepted proceeding without proof. The
  Evidence cell must quote or closely paraphrase the user's words and date.
  Waivers are visible debt, never a silent pass.

## Rules

1. Only the Skeptic role writes or changes a Status (see
   `references/agents.md`).
2. Statuses only move forward within a loop: CLAIMED → (EVIDENCED | PENDING |
   WAIVED). A PENDING row becomes EVIDENCED only when the raw result arrives
   and is inspected.
3. If new evidence contradicts an EVIDENCED row (a regression), the row goes
   back to CLAIMED and the loop that owned it reopens. Note the regression in
   the Evidence cell history rather than deleting it.
4. At the end of every Meso loop, run the mechanical check:

   ```
   python scripts/ledger_check.py PROOF_LEDGER.md
   ```

   Exit code 0 = ledger clean (no CLAIMED rows, all EVIDENCED rows carry
   evidence). Non-zero = the loop is not allowed to report "done". This is
   deliberately CI-friendly: add it to your pipeline if you have one.

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

Both are structural proxies, honestly limited like the EVIDENCED marker:
they check the required element is present, not that it is faithful — that
stays the Skeptic's job. Since v2.3 (EVO-003), `--catches` is schema-gated
the same way the ledger parser is: only rows under a real catches header
(`Date | Class(e)…`) count, so a foreign table with an ISO date no longer
reads as a live catch.

Since v2.4 (EVO-004), keep all ledger rows in ONE contiguous table: a blank
line ends the table (that is how foreign tables stay isolated). A row that
carries a valid status in its Status column but sits outside the table —
detached by a blank line, or orphaned by a header typo — is flagged rather
than silently skipped, so a `CLAIMED` row can never escape the audit by
being visually separated.
