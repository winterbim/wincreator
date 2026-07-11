#!/usr/bin/env python3
"""ledger_check.py v2 — mechanical gate for the Proof Ledger.

Parses PROOF_LEDGER.md and exits non-zero if the ledger is not clean.
Stdlib only. CI-friendly.

v2 fixes (each one caught by a real adversarial test, see --self-test):
  A. escaped pipes `\\|` inside cells no longer break cell splitting
     (the format spec REQUIRES escaping pipes; v1 choked on its own spec)
  B. only tables whose header matches the ledger schema are parsed;
     other markdown tables in the same file no longer cause false positives
  C. markdown emphasis around a status (**EVIDENCED**, `PENDING`) is tolerated
  D. EVIDENCED rows must carry an execution marker (command/date/output
     fragment), not just >=10 chars of prose. Heuristic, honestly limited:
     it cannot judge truthfulness — that remains the Skeptic's job.

v2.1 adds --catches: makes the retro-loop itself machine-checkable by
verifying SKEPTIC_CATCHES.md is alive (>=1 well-formed dated catch). Born
from EVO-001: the recurring meta-defect was "a verifier shipped without
being verified" — so the verifier now also checks the file that feeds its
own improvement.

v2.2 EVO-002: the spec's per-status evidence rules are now enforced
symmetrically — PENDING must carry a command marker, WAIVED must carry a
date. v1/v2 enforced this only for EVIDENCED (asymmetric enforcement was a
false-negative: a vague PENDING/WAIVED passed as CLEAN).
v2.3 EVO-003: --catches is schema-gated like the ledger parser, so a foreign
table with an ISO date no longer reads as ALIVE (fix B carried to the newer
surface — the exact "verifier shipped unverified" class, recurring).

Usage:
    python ledger_check.py [PROOF_LEDGER.md]     (default: PROOF_LEDGER.md)
    python ledger_check.py --self-test           (run embedded adversarial suite)
    python ledger_check.py --catches [FILE]      (default: SKEPTIC_CATCHES.md)

Exit codes: 0 clean/alive | 1 violations/stale | 2 file/table missing or self-test failed
"""
import re
import sys

VALID_STATUSES = {"CLAIMED", "EVIDENCED", "PENDING", "WAIVED"}
MIN_EVIDENCE_LEN = 10
EXPECTED_HEADER = ["id", "level", "claim", "gate", "status", "evidence"]

# Markers that suggest an actually-executed proof: a command, a path, a date,
# raw-output fragments, exit codes. Heuristic by design.
EXEC_MARKER = re.compile(
    r"(run[: ]|exec|exit[= ]|->|→|\$ |`.+`|/[\w.\-]+/|\d{4}-\d{2}-\d{2}"
    r"|passed|failed|ok\b.*\d|#\d+|http)", re.IGNORECASE)

SPLIT_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _clean(cell: str) -> str:
    """Unescape pipes and trim whitespace. Emphasis is NOT stripped here —
    only the Status value is de-emphasised (see _strip_emphasis), so that
    Evidence ending in a backtick-wrapped command keeps its execution marker
    (stripping it here was a v2.2 regression the self-test caught)."""
    return cell.strip().replace("\\|", "|")


_EMPHASIS = re.compile(r"^[*_~`]+|[*_~`]+$")


def _strip_emphasis(s: str) -> str:
    """Strip surrounding markdown emphasis (**bold**, _italic_, `code`,
    ~~strike~~) from a short token such as a status."""
    return _EMPHASIS.sub("", s.strip()).strip()


def _split_row(line: str):
    stripped = line.strip()
    if not (stripped.startswith("|") and stripped.endswith("|")):
        return None
    inner = stripped[1:-1]
    return [_clean(c) for c in SPLIT_UNESCAPED_PIPE.split(inner)]


def _is_ledger_header(cells) -> bool:
    if len(cells) < 6:
        return False
    lowered = [c.lower() for c in cells[:6]]
    # 'Gate (what proves it)' → startswith match on the keyword
    return all(l.startswith(k) for l, k in zip(lowered, EXPECTED_HEADER))


def _looks_like_ledger_row(cells) -> bool:
    """A row that carries a valid ledger status in column 5 is almost
    certainly a detached ledger row. Column 5 (index 4) holds the status
    whether or not the Evidence column is present, so >=5 cells suffices —
    this catches a CLAIMED row whose empty Evidence column was omitted."""
    return len(cells) >= 5 and _strip_emphasis(cells[4]).upper() in VALID_STATUSES


_FENCE = re.compile(r"^\s*(```|~~~)")


def _is_separator(cells) -> bool:
    nonempty = [c for c in cells if c]
    return bool(nonempty) and all(re.fullmatch(r":?-{3,}:?", c) for c in nonempty)


def parse_ledger_rows(text):
    """Yield (line_no, cells, orphan) for data rows. Structurally aware since
    v2.5 (EVO-005), after the v2.4 orphan heuristic proved both too aggressive
    and too lax (a Two-Failure escalation from row-level patch to parser-level):

    - lines inside ``` / ~~~ fenced code blocks are skipped — a ledger example
      in the docs is not a live ledger (fixes false positives incl. the spec
      file mis-parsing its own example);
    - a table starts at a header row followed by a separator; rows under a
      NON-ledger header (a foreign table, even one with a 'Status' column) are
      ignored (fix B) and never trigger the orphan check;
    - a ledger-status-bearing row sitting OUTSIDE any table is flagged as
      orphan, so a CLAIMED row detached by a blank line or a header typo cannot
      escape the audit.
    """
    in_fence = in_ledger = in_foreign = False
    prev = None  # previous content row — a candidate header, confirmed by a separator
    for i, line in enumerate(text.splitlines(), 1):
        if _FENCE.match(line):
            in_fence = not in_fence
            in_ledger = in_foreign = False
            prev = None
            continue
        if in_fence:
            continue
        cells = _split_row(line)
        if cells is None:
            in_ledger = in_foreign = False  # blank/non-table line ends the table
            prev = None
            continue
        if _is_separator(cells):
            if prev is not None:
                if _is_ledger_header(prev):
                    in_ledger, in_foreign = True, False
                else:
                    in_ledger, in_foreign = False, True
            prev = None
            continue
        # a content row
        if in_ledger:
            yield i, cells, False
        elif in_foreign:
            pass  # foreign-table data row — not part of the ledger (fix B)
        elif _looks_like_ledger_row(cells):
            yield i, cells, True  # a ledger-like row floating outside any table
        prev = cells


def check_text(text, label="ledger"):
    violations, rows_seen = [], 0
    for line_no, cells, orphan in parse_ledger_rows(text):
        if orphan:
            rows_seen += 1
            violations.append(
                f"line {line_no} [{cells[0]}]: ledger-like row (status "
                f"'{cells[4]}') OUTSIDE any ledger table — detached by a blank "
                f"line or a header typo, so it was escaping the audit")
            continue
        if len(cells) < 6:
            violations.append(f"line {line_no}: {len(cells)} cells, expected 6")
            continue
        rows_seen += 1
        row_id, _lvl, claim, _gate, status, evidence = cells[:6]
        status_u = _strip_emphasis(status).upper()
        if status_u not in VALID_STATUSES:
            violations.append(f"line {line_no} [{row_id}]: unknown status '{status}'")
        elif status_u == "CLAIMED":
            violations.append(
                f"line {line_no} [{row_id}]: CLAIMED — loop may not report done. "
                f"Claim: {claim[:60]}")
        elif len(evidence) < MIN_EVIDENCE_LEN:
            violations.append(
                f"line {line_no} [{row_id}]: {status_u} but Evidence empty/vague "
                f"('{evidence}')")
        elif status_u == "EVIDENCED" and not EXEC_MARKER.search(evidence):
            violations.append(
                f"line {line_no} [{row_id}]: EVIDENCED but no execution marker "
                f"(command, date, path, output fragment) in Evidence: '{evidence[:60]}' "
                f"— prose alone is not proof")
        elif status_u == "PENDING" and not EXEC_MARKER.search(evidence):
            # v2.2 EVO-002: the spec requires PENDING evidence to hold the exact
            # command handed to the developer. Enforce it like EVIDENCED, not
            # just the >=10-char check (asymmetric enforcement was the defect).
            violations.append(
                f"line {line_no} [{row_id}]: PENDING but no command marker in "
                f"Evidence (spec: hold the exact command handed to the dev): "
                f"'{evidence[:60]}'")
        elif status_u == "WAIVED" and not ISO_DATE.search(evidence):
            # v2.2 EVO-002: the spec requires WAIVED evidence to quote the user's
            # words AND date. ISO date is the structural proxy (honestly limited,
            # like EXEC_MARKER: it checks the date is present, not that the quote
            # is faithful — that stays the Skeptic's job).
            violations.append(
                f"line {line_no} [{row_id}]: WAIVED but no date in Evidence "
                f"(spec: quote the user's words and date): '{evidence[:60]}'")
    return violations, rows_seen


def check(path):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"ERROR: cannot read {path}: {e}")
        return 2
    violations, rows_seen = check_text(text)
    if rows_seen == 0 and not violations:
        print(f"ERROR: no ledger table found in {path} "
              "(header must be: ID | Level | Claim | Gate... | Status | Evidence)")
        return 2
    if violations:
        print(f"LEDGER NOT CLEAN — {len(violations)} violation(s):")
        for v in violations:
            print(f"  ✗ {v}")
        return 1
    print(f"LEDGER CLEAN — {rows_seen} row(s) verified in {path}")
    return 0


# ------------------------------------------------------ retro-loop (--catches)
def _is_catch_header(cells) -> bool:
    """A catches table starts with 'Date | Class(e)...' (EN or FR)."""
    return (len(cells) >= 2 and cells[0].lower().startswith("date")
            and cells[1].lower().startswith("class"))


def check_catches_text(text):
    """Return (alive, rows). The retro-loop is 'alive' if the catches file
    holds >=1 well-formed dated catch row (ISO date + non-empty class).
    Stateless proxy for 'the file exists and grows', honestly limited:
    it proves the loop is being fed, not that the catches are insightful.

    v2.3 EVO-003: schema-gated like the ledger parser — only rows under a real
    catches header (Date | Class(e)...) are counted, so a foreign table that
    happens to carry an ISO date in column 0 no longer reads as ALIVE (the v2
    fix B hardening, finally carried over to this newer surface).
    v2.5 EVO-005: skip fenced code blocks; a catch row needs only >=2 cells
    (date + class) to match the >=2 header rule (the >=4 requirement rejected a
    valid 3-column catches table — an internal inconsistency)."""
    rows = 0
    in_catches = in_fence = False
    for line in text.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
            in_catches = False
            continue
        if in_fence:
            continue
        cells = _split_row(line)
        if cells is None:
            in_catches = False  # blank/non-table line ends the table
            continue
        if _is_separator(cells):
            continue  # separator row: keep table state
        if _is_catch_header(cells):
            in_catches = True
            continue
        if in_catches and len(cells) >= 2 and ISO_DATE.search(cells[0]) and cells[1].strip():
            rows += 1
    return rows >= 1, rows


def check_catches(path):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"ERROR: cannot read {path}: {e}")
        return 2
    alive, rows = check_catches_text(text)
    if alive:
        print(f"CATCHES ALIVE — {rows} well-formed catch(es) in {path}")
        return 0
    print(f"CATCHES STALE — no well-formed dated catch row in {path} "
          "(retro-loop not being fed)")
    return 1


# ---------------------------------------------------------------- self-test
HDR = "| ID | Level | Claim | Gate (what proves it) | Status | Evidence |\n" \
      "|----|-------|-------|------------------------|--------|----------|\n"

SELF_TESTS = [
    # (name, text, expect_violations: bool)
    ("escaped_pipe_ok", HDR +
     "| P1 | Micro | handles `a \\| b` | test executed | EVIDENCED | run 2026-07-11: pytest -> 4 passed |\n", False),
    ("foreign_table_ignored",
     "| Option | Avantage |\n|---|---|\n| Rust | rapide |\n\n" + HDR +
     "| P1 | Micro | ok | test | EVIDENCED | run: pytest -> 6 passed |\n", False),
    ("bold_status_ok", HDR +
     "| P1 | Micro | ok | test | **EVIDENCED** | run: pytest -> 6 passed |\n", False),
    ("vague_evidence_caught", HDR +
     "| P1 | Micro | ok | test | EVIDENCED | ça marche bien |\n", True),
    ("claimed_caught", HDR +
     "| P1 | Micro | ok | test | CLAIMED | |\n", True),
    ("pending_with_command_ok", HDR +
     "| P2 | Micro | perf ok | bench | PENDING | command given: `cargo test parser` |\n", False),
    ("empty_evidence_caught", HDR +
     "| P3 | Micro | ok | test | WAIVED | ok |\n", True),
    # v2.2 EVO-002: PENDING/WAIVED evidence rules enforced symmetrically.
    ("pending_no_command_caught", HDR +
     "| P4 | Micro | perf ok | bench | PENDING | we will get to it later, promise it is fine |\n", True),
    ("pending_with_command_still_ok", HDR +
     "| P4 | Micro | perf ok | bench | PENDING | command given: `cargo test parser::malformed` |\n", False),
    ("waived_no_date_caught", HDR +
     "| P5 | Micro | perf | bench | WAIVED | user said just skip it for now, no need to bother |\n", True),
    ("waived_with_date_ok", HDR +
     "| P6 | Micro | perf | bench | WAIVED | user 2026-07-11: \"ship without the benchmark\" |\n", False),
    # v2.4 EVO-002... EVO-004: an orphan ledger row detached by a blank line
    # must NOT silently read CLEAN.
    ("orphan_ledger_row_caught", HDR +
     "| P1 | Micro | ok | test | EVIDENCED | run 2026-07-11 -> passed |\n\n"
     "| P2 | Micro | orphan | test | CLAIMED | |\n", True),
    ("foreign_6col_not_orphan",
     "| A | B | C | D | E | F |\n|--|--|--|--|--|--|\n| 1 | 2 | 3 | 4 | 5 | 6 |\n\n" + HDR +
     "| P1 | Micro | ok | test | EVIDENCED | run 2026-07-11 -> passed |\n", False),
    # v2.5 EVO-005: parser-level fixes after the v2.4 orphan heuristic proved
    # both too aggressive (foreign 'Status' column) and too lax (5-cell / fenced).
    ("foreign_status_col_not_orphan",
     "| Task | Owner | Priority | Due | Status | Notes |\n"
     "|------|-------|----------|-----|--------|-------|\n"
     "| Rewrite | wina | high | Q3 | PENDING | later |\n\n" + HDR +
     "| P1 | Micro | ok | test | EVIDENCED | run 2026-07-11 -> passed |\n", False),
    ("orphan_5cell_caught", HDR +
     "| P1 | Micro | ok | test | EVIDENCED | run 2026-07-11 -> passed |\n\n"
     "| P2 | Micro | broken | test | CLAIMED |\n", True),
    ("fenced_example_ignored",
     "```markdown\n| EX | Micro | demo | test | CLAIMED | |\n```\n\n" + HDR +
     "| P1 | Micro | ok | test | EVIDENCED | run 2026-07-11 -> passed |\n", False),
]

# v2.1 EVO-001: cover the --catches retro-loop checker in the same suite.
CATCH_HDR = "| Date | Classe | Comment raté | Question |\n" \
            "|------|--------|--------------|----------|\n"
CATCH_TESTS = [
    # (name, text, expect_alive: bool)
    ("catches_alive_ok", CATCH_HDR +
     "| 2026-07-11 | doc↔outil | jamais exécuté | l'outil a-t-il été attaqué ? |\n", True),
    ("catches_stale_caught", CATCH_HDR, False),  # header only, no dated catch
    # v2.3 EVO-003: a foreign table with an ISO date in col 0 must read STALE.
    ("catches_foreign_table_stale",
     "| Date | Event | Who | Notes |\n|------|-------|-----|-------|\n"
     "| 2026-07-11 | shipped | wina | not a skeptic catch at all |\n", False),
    # v2.5 EVO-005: a valid 3-column catches table must read ALIVE (was STALE
    # due to the >=4-cell inconsistency).
    ("catches_3col_alive",
     "| Date | Classe | Comment |\n|------|--------|---------|\n"
     "| 2026-07-11 | doc | note |\n", True),
]


def self_test():
    failed = 0
    for name, text, expect_bad in SELF_TESTS:
        violations, _ = check_text(text)
        got_bad = bool(violations)
        status = "PASS" if got_bad == expect_bad else "FAIL"
        if status == "FAIL":
            failed += 1
        print(f"  [{status}] {name} (expected {'violations' if expect_bad else 'clean'}, "
              f"got {len(violations)})")
    for name, text, expect_alive in CATCH_TESTS:
        alive, rows = check_catches_text(text)
        status = "PASS" if alive == expect_alive else "FAIL"
        if status == "FAIL":
            failed += 1
        print(f"  [{status}] {name} (expected {'alive' if expect_alive else 'stale'}, "
              f"got {'alive' if alive else 'stale'})")
    total = len(SELF_TESTS) + len(CATCH_TESTS)
    print(f"self-test: {total-failed}/{total} passed")
    return 2 if failed else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--self-test":
        sys.exit(self_test())
    if args and args[0] == "--catches":
        sys.exit(check_catches(args[1] if len(args) > 1 else "SKEPTIC_CATCHES.md"))
    sys.exit(check(args[0] if args else "PROOF_LEDGER.md"))
