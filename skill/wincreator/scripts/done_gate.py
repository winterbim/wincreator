#!/usr/bin/env python3
"""Done Gate - refuse "done" while the Proof Ledger still holds unproven claims.

A skill is advice: an agent can read WinCreator and still announce "done" over
a ledger full of CLAIMED rows. This script turns the final rule of the protocol
into a mechanism that runs outside the agent's judgment.

Three entry points, one decision:

  done_gate.py                 check the ledgers of the current project
  done_gate.py --hook          agent stop-hook mode (JSON on stdin, JSON on stdout)
  done_gate.py --summary FILE  also append a Markdown summary (CI job summaries)

The decision is exactly `ledger_check.py`'s: CLAIMED, DISPROVEN and INSUFFICIENT
rows block, and so does any row whose evidence does not carry what its status
requires. PENDING, BLOCKED and WAIVED never block; they are reported so that
waiting or waived work stays visible.

Hook mode blocks at most once per stop attempt, and once per session for a given
set of open claims. When the host reports that the agent is already continuing
because of a stop hook, the gate lets it stop: the agent has been shown the open
claims and must either prove them or tell the user plainly that they are
unproven. The same open claims are not raised again on every later turn of that
session; a new or changed unproven claim is. A gate that could never be passed,
or that nagged on every turn, would only teach people to uninstall it.

Stdlib only. Fail-open by design in hook mode: a missing ledger, an unreadable
payload or an internal error never traps an agent session.
"""
import argparse
import glob
import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger_check  # noqa: E402

VERSION = ledger_check.VERSION
ROOT_PATTERNS = ("PROOF_LEDGER.md", "PROOF_LEDGER-*.md")
QUICK_LEDGER = os.path.join(".wincreator", "PROOF_LEDGER.md")
WAITING_STATUSES = ("PENDING", "BLOCKED", "WAIVED")
MAX_REASON_LINES = 12


def discover_ledgers(root):
    """Ledgers a project is expected to keep, in a stable order.

    WINCREATOR_LEDGER (os.pathsep-separated) replaces discovery entirely, so a
    project with an unusual layout can still be gated.
    """
    explicit = os.environ.get("WINCREATOR_LEDGER", "").strip()
    if explicit:
        return [
            path if os.path.isabs(path) else os.path.join(root, path)
            for path in (part.strip() for part in explicit.split(os.pathsep))
            if path
        ]
    found = []
    for pattern in ROOT_PATTERNS:
        found.extend(sorted(glob.glob(os.path.join(root, pattern))))
    quick = os.path.join(root, QUICK_LEDGER)
    if os.path.isfile(quick):
        found.append(quick)
    unique, seen = [], set()
    for path in found:
        real = os.path.realpath(path)
        if real not in seen:
            seen.add(real)
            unique.append(path)
    return unique


def _status_counts(text):
    counts = {}
    for _line, cells, orphan in ledger_check.parse_ledger_rows(text):
        if orphan or len(cells) < 6:
            continue
        status = ledger_check._strip_emphasis(cells[4]).upper()
        counts[status] = counts.get(status, 0) + 1
    return counts


def evaluate(paths, root, strict_attestation=False):
    """Return one result per ledger: path, rows, violations, status counts."""
    results = []
    for path in paths:
        label = os.path.relpath(path, root) if _inside(path, root) else path
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        except OSError as error:
            results.append({"path": label, "rows": 0, "counts": {},
                            "violations": [f"cannot read ledger: {error}"]})
            continue
        violations, rows = ledger_check.check_text(
            text, label=label, strict_attestation=strict_attestation)
        results.append({"path": label, "rows": rows, "violations": violations,
                        "counts": _status_counts(text)})
    return results


def _inside(path, root):
    try:
        return not os.path.relpath(path, root).startswith("..")
    except ValueError:  # different Windows drives
        return False


def is_blocked(results):
    return any(result["violations"] for result in results)


def render_text(results):
    if not results:
        return "DONE GATE: no Proof Ledger found - nothing to gate."
    lines = []
    for result in results:
        counts = ", ".join(f"{count} {status}" for status, count in sorted(result["counts"].items()))
        if result["violations"]:
            lines.append(f"[BLOCKED] {result['path']} - {len(result['violations'])} blocking problem(s)"
                         f" [{counts or 'no rows'}]")
            lines.extend(f"    {violation}" for violation in result["violations"])
        else:
            lines.append(f"[ok] {result['path']} - {result['rows']} row(s) [{counts or 'no rows'}]")
    waiting = sum(result["counts"].get(status, 0) for result in results for status in WAITING_STATUSES)
    if is_blocked(results):
        lines.append("DONE GATE: BLOCKED - unproven claims remain; this work may not be reported as done.")
    else:
        note = f" ({waiting} waiting/waived row(s) stay visible above)" if waiting else ""
        lines.append(f"DONE GATE: OPEN - no unproven claim blocks completion{note}.")
    return "\n".join(lines)


def render_markdown(results):
    blocked = is_blocked(results)
    lines = ["## WinCreator Done Gate", ""]
    if not results:
        return "\n".join(lines + ["No Proof Ledger found - nothing to gate.", ""])
    lines.append("**BLOCKED** - unproven claims remain." if blocked
                 else "**OPEN** - no unproven claim blocks completion.")
    lines += ["", "| Ledger | Rows | Statuses | Blocking |", "|---|---|---|---|"]
    for result in results:
        counts = ", ".join(f"{count} {status}" for status, count in sorted(result["counts"].items()))
        lines.append(f"| `{result['path']}` | {result['rows']} | {counts or '-'} |"
                     f" {len(result['violations'])} |")
    for result in results:
        if result["violations"]:
            lines += ["", f"### `{result['path']}`", ""]
            lines.extend(f"- {violation.replace('|', chr(92) + '|')}" for violation in result["violations"])
    return "\n".join(lines) + "\n"


def hook_reason(results):
    problems = [f"{result['path']}: {violation}"
                for result in results for violation in result["violations"]]
    shown = problems[:MAX_REASON_LINES]
    more = len(problems) - len(shown)
    body = "\n".join(f"- {problem}" for problem in shown)
    if more > 0:
        body += f"\n- ... and {more} more (run done_gate.py for the full list)"
    return (
        "WinCreator Done Gate: the Proof Ledger still holds unproven claims, so this "
        "work cannot be reported as done yet.\n"
        f"{body}\n"
        "Before stopping, do one of these for each row - do not edit a status by hand:\n"
        "1. run the real gate through `wincreator.py prove <ID> -- <command>` and have it "
        "reviewed;\n"
        "2. if the user explicitly accepts the gap, record WAIVED with their dated words;\n"
        "3. if the claim was wrong or replaced, fix it or mark it SUPERSEDED by its "
        "successor;\n"
        "4. otherwise tell the user plainly which claims are still unproven and why, "
        "instead of saying the work is done."
    )


def run_hook(stdin_text, default_root):
    """Stop-hook protocol: print a block decision as JSON, or nothing to allow."""
    if os.environ.get("WINCREATOR_DONE_GATE", "").strip().lower() in {"off", "0", "false", "no"}:
        return None
    try:
        payload = json.loads(stdin_text) if stdin_text.strip() else {}
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    if payload.get("stop_hook_active"):
        return None  # already blocked once for this stop; never loop
    # The agent may have changed directory: gate the project root the host
    # declares as well as the directory the stop happened in.
    roots, results, seen = [], [], set()
    for candidate in (os.environ.get("CLAUDE_PROJECT_DIR"), payload.get("cwd")):
        if isinstance(candidate, str) and os.path.isdir(candidate) and candidate not in roots:
            roots.append(candidate)
    for root in roots or [default_root]:
        fresh = [path for path in discover_ledgers(root) if os.path.realpath(path) not in seen]
        seen.update(os.path.realpath(path) for path in fresh)
        results.extend(evaluate(fresh, root))
    if not is_blocked(results):
        return None
    if _already_reported(payload.get("session_id"), (roots or [default_root])[0], results):
        return None
    return {"decision": "block", "reason": hook_reason(results)}


def _already_reported(session_id, root, results):
    """True when this exact set of open claims was already raised in this session.

    State is a tiny marker in the system temp directory. Any failure to read or
    write it means "not reported": the gate then blocks, and `stop_hook_active`
    still guarantees it cannot loop.
    """
    if not isinstance(session_id, str) or not session_id:
        return False
    problems = sorted(f"{result['path']}: {violation}"
                      for result in results for violation in result["violations"])
    state = hashlib.sha256("\n".join([os.path.realpath(root)] + problems).encode("utf-8")).hexdigest()
    marker_dir = os.path.join(tempfile.gettempdir(), "wincreator-done-gate")
    marker = os.path.join(marker_dir, hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:32])
    try:
        with open(marker, encoding="utf-8") as handle:
            if handle.read().strip() == state:
                return True
    except OSError:
        pass
    try:
        os.makedirs(marker_dir, exist_ok=True)
        with open(marker, "w", encoding="utf-8") as handle:
            handle.write(state)
    except OSError:
        pass
    return False


# ------------------------------------------------------------------ self-test
_HEADER = ("| ID | Level | Claim | Gate (what proves it) | Status | Evidence |\n"
           "|----|-------|-------|------------------------|--------|----------|\n")
_CLAIMED = "| P1 | Micro | parser rejects malformed input | `pytest -q` | CLAIMED | |\n"
_EVIDENCED = ("| P1 | Micro | parser rejects malformed input | `pytest -q` | EVIDENCED | "
              "run 2026-01-01: `pytest -q` -> exit=0, 12 passed |\n")
_PENDING = ("| P2 | Micro | export handles empty lots | `pytest tests/test_export.py` | PENDING | "
            "run `pytest tests/test_export.py` on the developer machine and paste the result |\n")


def self_test():
    cases = []

    def case(name, ok):
        cases.append((name, bool(ok)))

    saved = {key: os.environ.pop(key, None)
             for key in ("WINCREATOR_LEDGER", "WINCREATOR_DONE_GATE", "CLAUDE_PROJECT_DIR")}
    try:
        with tempfile.TemporaryDirectory() as root:
            payload = json.dumps({"cwd": root, "stop_hook_active": False})
            case("no_ledger_allows_stop", run_hook(payload, root) is None)

            ledger = os.path.join(root, "PROOF_LEDGER.md")
            with open(ledger, "w", encoding="utf-8") as handle:
                handle.write(_HEADER + _CLAIMED)
            decision = run_hook(payload, root)
            case("claimed_row_blocks_stop", decision and decision["decision"] == "block"
                 and "P1" in decision["reason"])
            case("second_stop_is_never_looped",
                 run_hook(json.dumps({"cwd": root, "stop_hook_active": True}), root) is None)
            case("garbage_payload_falls_back_to_default_root",
                 (run_hook("not json", root) or {}).get("decision") == "block")
            session = json.dumps({"cwd": root, "session_id": f"self-test-{os.getpid()}-{id(cases)}"})
            first, second = run_hook(session, root), run_hook(session, root)
            case("same_open_claims_raised_once_per_session", first and second is None)
            with open(ledger, "a", encoding="utf-8") as handle:
                handle.write(_CLAIMED.replace("P1", "P9"))
            case("new_unproven_claim_blocks_again", run_hook(session, root) is not None)
            with open(ledger, "w", encoding="utf-8") as handle:
                handle.write(_HEADER + _CLAIMED)
            os.environ["WINCREATOR_DONE_GATE"] = "off"
            case("explicit_off_switch_allows_stop", run_hook(payload, root) is None)
            del os.environ["WINCREATOR_DONE_GATE"]
            subdir = os.path.join(root, "src")
            os.makedirs(subdir)
            os.environ["CLAUDE_PROJECT_DIR"] = root
            case("project_root_is_gated_when_agent_stops_in_a_subdirectory",
                 run_hook(json.dumps({"cwd": subdir}), subdir) is not None)
            del os.environ["CLAUDE_PROJECT_DIR"]
            os.rmdir(subdir)

            with open(ledger, "w", encoding="utf-8") as handle:
                handle.write(_HEADER + _EVIDENCED + _PENDING)
            results = evaluate(discover_ledgers(root), root)
            case("evidenced_and_pending_do_not_block", not is_blocked(results))
            case("waiting_rows_stay_visible", "1 PENDING" in render_text(results))

            quick_dir = os.path.join(root, ".wincreator")
            os.makedirs(quick_dir)
            with open(os.path.join(quick_dir, "PROOF_LEDGER.md"), "w", encoding="utf-8") as handle:
                handle.write(_HEADER + _CLAIMED)
            results = evaluate(discover_ledgers(root), root)
            case("quick_ledger_is_discovered_and_blocks",
                 len(results) == 2 and is_blocked(results))
            case("markdown_summary_names_blocked", "**BLOCKED**" in render_markdown(results))

            os.environ["WINCREATOR_LEDGER"] = "PROOF_LEDGER.md"
            case("explicit_ledger_replaces_discovery",
                 not is_blocked(evaluate(discover_ledgers(root), root)))
            os.environ["WINCREATOR_LEDGER"] = "missing.md"
            case("missing_explicit_ledger_blocks_cli",
                 is_blocked(evaluate(discover_ledgers(root), root)))
            del os.environ["WINCREATOR_LEDGER"]
    finally:
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value

    for name, ok in cases:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    passed = sum(1 for _name, ok in cases if ok)
    print(f"self-test: {passed}/{len(cases)} passed")
    return 0 if passed == len(cases) else 1


def build_parser():
    parser = argparse.ArgumentParser(
        prog="wincreator-done-gate",
        description="Refuse 'done' while the Proof Ledger still holds unproven claims.",
    )
    parser.add_argument("ledgers", nargs="*", help="ledger files (default: discover in --root)")
    parser.add_argument("--root", default=".", help="project root used for discovery")
    parser.add_argument("--hook", action="store_true",
                        help="agent stop-hook mode: read the hook JSON on stdin")
    parser.add_argument("--strict-attestation", action="store_true",
                        help="require machine-captured attestations (Regulated tier)")
    parser.add_argument("--require-ledger", action="store_true",
                        help="fail when no ledger is found instead of passing")
    parser.add_argument("--summary", metavar="FILE",
                        help="append a Markdown summary to FILE (e.g. $GITHUB_STEP_SUMMARY)")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:  # a claim may hold characters the console encoding cannot print
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    if args.self_test:
        return self_test()
    if args.hook:
        try:
            decision = run_hook(sys.stdin.read(), os.getcwd())
        except Exception as error:  # fail open: never trap a session on our own bug
            print(f"wincreator done gate skipped: {error}", file=sys.stderr)
            return 0
        if decision:
            print(json.dumps(decision))
        return 0
    root = os.path.abspath(args.root)
    paths = [os.path.abspath(path) for path in args.ledgers] or discover_ledgers(root)
    results = evaluate(paths, root, strict_attestation=args.strict_attestation)
    print(render_text(results))
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as handle:
            handle.write(render_markdown(results))
    if not results:
        return 1 if args.require_ledger else 0
    return 1 if is_blocked(results) else 0


if __name__ == "__main__":
    sys.exit(main())
