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


def _clean(cell: str) -> str:
    """Strip markdown emphasis/code wrapping and unescape pipes."""
    c = cell.strip()
    c = re.sub(r"^[*_`]+|[*_`]+$", "", c).strip()
    return c.replace("\\|", "|")


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


def parse_ledger_rows(text):
    """Yield (line_no, cells) only for data rows of *ledger* tables."""
    in_ledger = False
    for i, line in enumerate(text.splitlines(), 1):
        cells = _split_row(line)
        if cells is None:
            in_ledger = False  # blank/non-table line ends the table
            continue
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
            continue  # separator row: keep current table state
        if _is_ledger_header(cells):
            in_ledger = True
            continue
        if in_ledger:
            yield i, cells


def check_text(text, label="ledger"):
    violations, rows_seen = [], 0
    for line_no, cells in parse_ledger_rows(text):
        if len(cells) < 6:
            violations.append(f"line {line_no}: {len(cells)} cells, expected 6")
            continue
        rows_seen += 1
        row_id, _lvl, claim, _gate, status, evidence = cells[:6]
        status_u = status.upper()
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
CATCH_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def check_catches_text(text):
    """Return (alive, rows). The retro-loop is 'alive' if the catches file
    holds >=1 well-formed dated catch row (ISO date + non-empty class).
    Stateless proxy for 'the file exists and grows', honestly limited:
    it proves the loop is being fed, not that the catches are insightful."""
    rows = 0
    for line in text.splitlines():
        cells = _split_row(line)
        if cells is None or len(cells) < 4:
            continue
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
            continue  # separator
        if cells[0].lower().startswith("date"):
            continue  # header
        if CATCH_DATE.search(cells[0]) and cells[1].strip():
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
]

# v2.1 EVO-001: cover the --catches retro-loop checker in the same suite.
CATCH_HDR = "| Date | Classe | Comment raté | Question |\n" \
            "|------|--------|--------------|----------|\n"
CATCH_TESTS = [
    # (name, text, expect_alive: bool)
    ("catches_alive_ok", CATCH_HDR +
     "| 2026-07-11 | doc↔outil | jamais exécuté | l'outil a-t-il été attaqué ? |\n", True),
    ("catches_stale_caught", CATCH_HDR, False),  # header only, no dated catch
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
