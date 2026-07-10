#!/usr/bin/env python3
"""ledger_check.py — mechanical gate for the Proof Ledger.

Parses a PROOF_LEDGER.md markdown table and exits non-zero if the ledger is
not clean. Stdlib only, no dependencies. CI-friendly.

Usage:
    python ledger_check.py [path/to/PROOF_LEDGER.md]   (default: PROOF_LEDGER.md)

Exit codes:
    0  ledger clean (no CLAIMED rows; every EVIDENCED row has evidence;
       PENDING/WAIVED rows have a non-empty Evidence cell)
    1  violations found (printed to stdout)
    2  file missing, unreadable, or no ledger table found
"""
import re
import sys

VALID_STATUSES = {"CLAIMED", "EVIDENCED", "PENDING", "WAIVED"}
MIN_EVIDENCE_LEN = 10  # chars; guards against "ok" / "done" pseudo-evidence


def parse_rows(text):
    """Yield (line_no, cells) for data rows of markdown tables in *text*."""
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        # skip header and separator rows
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
            continue
        if cells and cells[0].lower() in ("id",):
            continue
        yield i, cells


def check(path):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"ERROR: cannot read {path}: {e}")
        return 2

    violations = []
    rows_seen = 0
    for line_no, cells in parse_rows(text):
        if len(cells) < 6:
            violations.append(
                f"line {line_no}: row has {len(cells)} cells, expected 6 "
                "(ID | Level | Claim | Gate | Status | Evidence)"
            )
            continue
        rows_seen += 1
        row_id, _level, claim, _gate, status, evidence = cells[:6]
        status_u = status.upper()
        if status_u not in VALID_STATUSES:
            violations.append(
                f"line {line_no} [{row_id}]: unknown status '{status}' "
                f"(valid: {', '.join(sorted(VALID_STATUSES))})"
            )
            continue
        if status_u == "CLAIMED":
            violations.append(
                f"line {line_no} [{row_id}]: CLAIMED with no evidence — "
                f"loop may not report done. Claim: {claim[:60]}"
            )
        elif len(evidence) < MIN_EVIDENCE_LEN:
            violations.append(
                f"line {line_no} [{row_id}]: status {status_u} but Evidence "
                f"cell is empty or too vague ('{evidence}')"
            )

    if rows_seen == 0 and not violations:
        print(f"ERROR: no ledger rows found in {path} — is the table present?")
        return 2

    if violations:
        print(f"LEDGER NOT CLEAN — {len(violations)} violation(s):")
        for v in violations:
            print(f"  ✗ {v}")
        return 1

    print(f"LEDGER CLEAN — {rows_seen} row(s) verified in {path}")
    return 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "PROOF_LEDGER.md"
    sys.exit(check(target))
