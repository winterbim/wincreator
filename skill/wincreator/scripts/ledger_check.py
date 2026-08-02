#!/usr/bin/env python3
"""ledger_check.py v3 — mechanical gate for the Proof Ledger.

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

v3.0 EVO-006/007/008 (breaking: the status set and the evidence rules change):
  E. three statuses added — DISPROVEN (the gate ran and the claim is FALSE),
     SUPERSEDED (the claim was replaced by a reformulated one), BLOCKED (the
     gate cannot run because of a named external dependency). Before v3 a
     negative result had no representation at all, so failures either
     disappeared or were dressed up as PENDING.
  F. the single generic EXEC_MARKER is replaced by per-status validators:
     EXECUTION (EVIDENCED/DISPROVEN), COMMAND (PENDING), USER_WAIVER (WAIVED),
     SUPERSESSION (SUPERSEDED), BLOCKER (BLOCKED). A bare ISO date, or the bare
     word "http", no longer satisfies "a command was executed": execution now
     needs an exit code, an attestation, a run URL, or a named command (in the
     row's Gate or Evidence) together with a dated/raw result.
  G. --strict-attestation (Regulated tier): every EVIDENCED/DISPROVEN row must
     reference a `wincreator prove` attestation (path + sha256), i.e. machine-
     captured evidence rather than a hand-written sentence.
  H. INSUFFICIENT is a first-class blocking status. It cannot be collapsed
     into the non-blocking PENDING state after an independent review.

Usage:
    python ledger_check.py [PROOF_LEDGER.md]     (default: PROOF_LEDGER.md)
    python ledger_check.py --self-test           (run embedded adversarial suite)
    python ledger_check.py --catches [FILE]      (default: SKEPTIC_CATCHES.md)
    python ledger_check.py --strict-attestation [FILE]

Exit codes: 0 clean/alive | 1 violations/stale | 2 file/table missing or self-test failed
"""
import re
import sys

VERSION = "3.0.0"

# Statuses that may legitimately appear in a ledger.
VALID_STATUSES = {
    "CLAIMED", "EVIDENCED", "PENDING", "WAIVED",
    "DISPROVEN", "INSUFFICIENT", "SUPERSEDED", "BLOCKED",
}
# Statuses that forbid a loop from reporting "done".
BLOCKING_STATUSES = {"CLAIMED", "DISPROVEN", "INSUFFICIENT"}
MIN_EVIDENCE_LEN = 10
EXPECTED_HEADER = ["id", "level", "claim", "gate", "status", "evidence"]

ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
BACKTICKED = re.compile(r"`[^`]+`")
SHELL_PROMPT = re.compile(r"(^|\s)\$ \S")
COMMAND_WORD = re.compile(r"\b(command|commande|cmd|run this|à exécuter)\b\s*[:=]?",
                          re.IGNORECASE)
EXIT_CODE = re.compile(r"\bexit\s*(code)?\s*[=: ]\s*-?\d+|\breturncode\b|\bexit=\d",
                       re.IGNORECASE)
ATTESTATION = re.compile(r"attestation\b[^|]{0,120}?sha256[:= ]\s*[0-9a-f]{16,}",
                         re.IGNORECASE)
RUN_URL = re.compile(r"https?://[^\s|]+/[^\s|]+")
# A fragment of an actual result, as opposed to a promise about one.
RESULT_FRAGMENT = re.compile(
    r"->|→|\b\d+\s*(passed|failed|errors?|ok|rows?|bytes|chars|matches|tests?|files?)\b"
    r"|\b(passed|failed|match(ed|es)?|CLEAN|NOT CLEAN|ALIVE|STALE|HTTP \d{3})\b"
    r"|\b\w+=\S|\b\d+\s*(ms|s)\b", re.IGNORECASE)
USER_VOICE = re.compile(r"\b(user|utilisateur|owner|client|approved by|waived by)\b|[\"“”«»]",
                        re.IGNORECASE)
SUPERSESSION = re.compile(r"\b(supersed\w*|superced\w*|replac\w*|remplac\w*)\b",
                          re.IGNORECASE)
CLAIM_ID = re.compile(r"\b[A-Za-z]{1,4}[-_]?\d+(?:-\d+)?\b")
BLOCKER = re.compile(
    r"\b(blocked (by|on)|blocking dependency|waiting on|depends on|"
    r"bloqu\w+ par|d[ée]pend\w* de|en attente de)\b", re.IGNORECASE)

SPLIT_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")


def has_command(evidence: str) -> bool:
    """The Evidence cell names a concrete command (or path) to execute."""
    return bool(BACKTICKED.search(evidence) or SHELL_PROMPT.search(evidence)
                or COMMAND_WORD.search(evidence))


def has_execution(evidence: str, gate: str = "") -> bool:
    """The row carries a trace of an execution that actually happened.

    Deliberately stricter than v2's EXEC_MARKER, which accepted a bare ISO date
    or the bare word "http": writing "2026-08-02 test passed" in a cell proved
    nothing. Still a heuristic, still unable to judge truthfulness (that is the
    Skeptic's job, and `wincreator prove` is the machine-captured alternative)
    — but the row must now show at least one of:

    - an attestation reference with a sha256 (machine-captured evidence);
    - an exit code / returncode;
    - a run/artifact URL with a path;
    - a named command (in Evidence, or in the Gate column that is supposed to
      hold it) TOGETHER with a dated or raw result in Evidence.

    A command with no result, or a result with no command, is not enough.
    """
    if ATTESTATION.search(evidence) or EXIT_CODE.search(evidence):
        return True
    if RUN_URL.search(evidence):
        return True
    named_command = has_command(evidence) or has_command(gate)
    result = bool(ISO_DATE.search(evidence)) or bool(RESULT_FRAGMENT.search(evidence))
    return named_command and result


def has_attestation(evidence: str) -> bool:
    return bool(ATTESTATION.search(evidence))


def has_user_waiver(evidence: str) -> bool:
    """WAIVED: the user's own words, dated. Structural proxy for both."""
    return bool(ISO_DATE.search(evidence)) and bool(USER_VOICE.search(evidence))


def has_supersession(evidence: str) -> bool:
    """SUPERSEDED: says what replaced it, and names the replacing row."""
    return bool(SUPERSESSION.search(evidence)) and bool(CLAIM_ID.search(evidence))


def has_blocker(evidence: str) -> bool:
    """BLOCKED: names the external dependency, and dates the block."""
    return bool(BLOCKER.search(evidence)) and bool(ISO_DATE.search(evidence))


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


def check_text(text, label="ledger", strict_attestation=False):
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
        prefix = f"line {line_no} [{row_id}]"
        if status_u not in VALID_STATUSES:
            violations.append(f"{prefix}: unknown status '{status}' "
                              f"(valid: {', '.join(sorted(VALID_STATUSES))})")
            continue
        if status_u == "CLAIMED":
            violations.append(
                f"{prefix}: CLAIMED — loop may not report done. Claim: {claim[:60]}")
            continue
        if len(evidence) < MIN_EVIDENCE_LEN:
            violations.append(
                f"{prefix}: {status_u} but Evidence empty/vague ('{evidence}')")
            continue
        if status_u in ("EVIDENCED", "DISPROVEN") and not has_execution(evidence, _gate):
            violations.append(
                f"{prefix}: {status_u} but no execution trace (need an exit code, "
                f"an attestation sha256, a run URL, or a named command in "
                f"Gate/Evidence WITH a dated or raw result): '{evidence[:60]}' "
                f"— prose alone is not proof")
        elif (strict_attestation and status_u in ("EVIDENCED", "DISPROVEN")
                and not has_attestation(evidence)):
            violations.append(
                f"{prefix}: {status_u} without a machine-captured attestation "
                f"(--strict-attestation: run `wincreator prove {row_id} -- <cmd>`): "
                f"'{evidence[:60]}'")
        elif status_u == "PENDING" and not has_command(evidence):
            # v2.2 EVO-002: the spec requires PENDING evidence to hold the exact
            # command handed to the developer. v3 checks for a command
            # specifically — a date or a URL no longer satisfies it.
            violations.append(
                f"{prefix}: PENDING but no command in Evidence (spec: hold the "
                f"exact command handed to the dev, in backticks): '{evidence[:60]}'")
        elif status_u == "WAIVED" and not has_user_waiver(evidence):
            # The spec requires WAIVED evidence to quote the user's words AND
            # date them. Structural proxy, honestly limited like the others:
            # it checks both elements are present, not that the quote is
            # faithful — that stays the Skeptic's job.
            violations.append(
                f"{prefix}: WAIVED but Evidence lacks the user's dated words "
                f"(spec: quote the user and date the waiver): '{evidence[:60]}'")
        elif status_u == "SUPERSEDED" and not has_supersession(evidence):
            violations.append(
                f"{prefix}: SUPERSEDED but Evidence does not name the replacing "
                f"claim (spec: 'superseded by <ID>: <reason>'): '{evidence[:60]}'")
        elif status_u == "BLOCKED" and not has_blocker(evidence):
            violations.append(
                f"{prefix}: BLOCKED but Evidence does not name a dated external "
                f"blocker (spec: 'blocked by <dependency>, <date>'): "
                f"'{evidence[:60]}'")
        if status_u == "INSUFFICIENT":
            if not ("verdict=INSUFFICIENT" in evidence
                    and "reviewer=" in evidence
                    and "reviewed_at=" in evidence):
                violations.append(
                    f"{prefix}: INSUFFICIENT without a linked review verdict, "
                    f"reviewer, and timestamp: '{evidence[:60]}'")
            violations.append(
                f"{prefix}: INSUFFICIENT — independent review found the evidence "
                f"insufficient; the loop may not report done. Claim: {claim[:60]}")
        if status_u == "DISPROVEN":
            # A negative result is a first-class, retained record — and it still
            # forbids reporting done. Retire it via SUPERSEDED once the claim is
            # reformulated and re-proven.
            violations.append(
                f"{prefix}: DISPROVEN — the gate ran and the claim is FALSE; the "
                f"loop may not report done. Fix and re-prove, or reformulate and "
                f"mark this row SUPERSEDED. Claim: {claim[:60]}")
    return violations, rows_seen


def check(path, strict_attestation=False):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"ERROR: cannot read {path}: {e}")
        return 2
    violations, rows_seen = check_text(text, strict_attestation=strict_attestation)
    if rows_seen == 0 and not violations:
        print(f"ERROR: no ledger table found in {path} "
              "(header must be: ID | Level | Claim | Gate... | Status | Evidence)")
        return 2
    if violations:
        print(f"LEDGER NOT CLEAN — {len(violations)} violation(s):")
        for v in violations:
            print(f"  ✗ {v}")
        return 1
    mode = " [strict-attestation]" if strict_attestation else ""
    print(f"LEDGER CLEAN{mode} — {rows_seen} row(s) verified in {path}")
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
     "| P1 | Micro | handles `a \\| b` | test executed | EVIDENCED | run 2026-07-11: `pytest` -> 4 passed |\n", False),
    ("foreign_table_ignored",
     "| Option | Avantage |\n|---|---|\n| Rust | rapide |\n\n" + HDR +
     "| P1 | Micro | ok | test | EVIDENCED | run 2026-07-11: `pytest` -> 6 passed |\n", False),
    ("bold_status_ok", HDR +
     "| P1 | Micro | ok | test | **EVIDENCED** | run 2026-07-11: `pytest` -> 6 passed |\n", False),
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
    ("insufficient_review_blocks_done", HDR +
     "| P4 | Micro | perf ok | bench | INSUFFICIENT | attestation.json exit=0; "
     "review review.json verdict=INSUFFICIENT reviewer=skeptic reviewed_at=2026-08-02T12:00:00Z "
     "sha256=0123456789abcdef |\n", True),
    ("insufficient_without_review_metadata_caught", HDR +
     "| P4 | Micro | perf ok | bench | INSUFFICIENT | more proof would be useful here |\n", True),
    ("waived_no_date_caught", HDR +
     "| P5 | Micro | perf | bench | WAIVED | user said just skip it for now, no need to bother |\n", True),
    ("waived_with_date_ok", HDR +
     "| P6 | Micro | perf | bench | WAIVED | user 2026-07-11: \"ship without the benchmark\" |\n", False),
    # v2.4 EVO-002... EVO-004: an orphan ledger row detached by a blank line
    # must NOT silently read CLEAN.
    ("orphan_ledger_row_caught", HDR +
     "| P1 | Micro | ok | test | EVIDENCED | run 2026-07-11: `pytest` -> passed |\n\n"
     "| P2 | Micro | orphan | test | CLAIMED | |\n", True),
    ("foreign_6col_not_orphan",
     "| A | B | C | D | E | F |\n|--|--|--|--|--|--|\n| 1 | 2 | 3 | 4 | 5 | 6 |\n\n" + HDR +
     "| P1 | Micro | ok | test | EVIDENCED | run 2026-07-11: `pytest` -> passed |\n", False),
    # v2.5 EVO-005: parser-level fixes after the v2.4 orphan heuristic proved
    # both too aggressive (foreign 'Status' column) and too lax (5-cell / fenced).
    ("foreign_status_col_not_orphan",
     "| Task | Owner | Priority | Due | Status | Notes |\n"
     "|------|-------|----------|-----|--------|-------|\n"
     "| Rewrite | wina | high | Q3 | PENDING | later |\n\n" + HDR +
     "| P1 | Micro | ok | test | EVIDENCED | run 2026-07-11: `pytest` -> passed |\n", False),
    ("orphan_5cell_caught", HDR +
     "| P1 | Micro | ok | test | EVIDENCED | run 2026-07-11: `pytest` -> passed |\n\n"
     "| P2 | Micro | broken | test | CLAIMED |\n", True),
    ("fenced_example_ignored",
     "```markdown\n| EX | Micro | demo | test | CLAIMED | |\n```\n\n" + HDR +
     "| P1 | Micro | ok | test | EVIDENCED | run 2026-07-11: `pytest` -> passed |\n", False),
    # v3.0 EVO-006: bare markers no longer read as an executed proof.
    ("bare_date_and_passed_caught", HDR +
     "| P1 | Micro | export works | inspect the export by hand | EVIDENCED | 2026-08-02 test passed |\n", True),
    ("command_without_result_caught", HDR +
     "| P1 | Micro | export works | `make export` | EVIDENCED | I ran the export command as required |\n", True),
    ("gate_command_with_dated_result_ok", HDR +
     "| P1 | Micro | export works | `make export` on the full dataset | EVIDENCED | 2026-08-02: 482 rows exported, 0 diff vs reference |\n", False),
    ("bare_url_word_caught", HDR +
     "| P1 | Micro | export works | run the export | EVIDENCED | see http docs for details |\n", True),
    ("exit_code_ok", HDR +
     "| P1 | Micro | export works | run the export | EVIDENCED | `pytest -q` exit=0, 12 passed |\n", False),
    ("ci_run_url_ok", HDR +
     "| P1 | Micro | CI green | the workflow run | EVIDENCED | https://github.com/o/r/actions/runs/1 conclusion=success |\n", False),
    ("attestation_ok", HDR +
     "| P1 | Micro | export works | run the export | EVIDENCED | attestation .wincreator/attestations/P1/x.json sha256=0123456789abcdef0123 |\n", False),
    # v3.0 EVO-007: negative and non-runnable outcomes are representable.
    ("disproven_blocks", HDR +
     "| P1 | Micro | export never drops rows | full-dataset diff | DISPROVEN | `wincreator prove` 2026-08-02: `diff` -> exit=1, 3 rows missing |\n", True),
    ("disproven_needs_execution", HDR +
     "| P1 | Micro | export never drops rows | full-dataset diff | DISPROVEN | it seemed wrong to me honestly |\n", True),
    ("superseded_ok", HDR +
     "| P1 | Micro | export never drops rows | full-dataset diff | SUPERSEDED | superseded by P7 after the DISPROVEN run of 2026-08-02 |\n", False),
    ("superseded_without_target_caught", HDR +
     "| P1 | Micro | export never drops rows | full-dataset diff | SUPERSEDED | not relevant anymore, dropped it |\n", True),
    ("blocked_ok", HDR +
     "| P1 | Micro | SSO login works | end-to-end login run | BLOCKED | blocked by the IdP sandbox outage since 2026-08-01, ticket OPS-412 |\n", False),
    ("blocked_without_dependency_caught", HDR +
     "| P1 | Micro | SSO login works | end-to-end login run | BLOCKED | cannot do it right now 2026-08-01 |\n", True),
    ("unknown_status_caught", HDR +
     "| P1 | Micro | ok | test | ALMOST | run 2026-07-11: `pytest` -> passed |\n", True),
]

# v3.0: --strict-attestation is a separate suite (same texts, harsher mode).
STRICT_TESTS = [
    # (name, text, expect_violations: bool)
    ("strict_rejects_handwritten_evidence", HDR +
     "| P1 | Micro | ok | test | EVIDENCED | `pytest -q` exit=0, 12 passed |\n", True),
    ("strict_accepts_attestation", HDR +
     "| P1 | Micro | ok | test | EVIDENCED | attestation .wincreator/attestations/P1/x.json sha256=0123456789abcdef0123 |\n", False),
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
    for name, text, expect_bad in STRICT_TESTS:
        violations, _ = check_text(text, strict_attestation=True)
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
    total = len(SELF_TESTS) + len(STRICT_TESTS) + len(CATCH_TESTS)
    print(f"self-test: {total-failed}/{total} passed")
    return 2 if failed else 0


def main(argv):
    args = list(argv)
    if args and args[0] in {"--help", "-h"}:
        print(__doc__.strip())
        return 0
    if args and args[0] == "--self-test":
        return self_test()
    if args and args[0] == "--version":
        print(f"ledger_check.py {VERSION}")
        return 0
    if args and args[0] == "--catches":
        return check_catches(args[1] if len(args) > 1 else "SKEPTIC_CATCHES.md")
    strict = "--strict-attestation" in args
    if strict:
        args.remove("--strict-attestation")
    return check(args[0] if args else "PROOF_LEDGER.md", strict_attestation=strict)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
