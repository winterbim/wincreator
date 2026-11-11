# Done Gate

The protocol's last rule is "no loop reports done while an unproven claim
remains". Written in a skill, that rule is advice the agent may skip. The Done
Gate runs it outside the agent's judgment, in three places that all make the
same decision.

## The decision

`scripts/done_gate.py` applies `ledger_check.py` to every ledger of the project:

- **blocks:** `CLAIMED`, `DISPROVEN`, `INSUFFICIENT`, and any row whose evidence
  does not carry what its status requires;
- **never blocks, always shown:** `PENDING`, `BLOCKED`, `WAIVED`.

Ledgers are discovered at the project root (`PROOF_LEDGER.md`,
`PROOF_LEDGER-*.md`) and at `.wincreator/PROOF_LEDGER.md`. Set
`WINCREATOR_LEDGER` (paths separated by the OS path separator) to replace
discovery for an unusual layout.

```
python3 scripts/done_gate.py                    # exit 1 while unproven claims remain
python3 scripts/done_gate.py --strict-attestation   # Regulated tier
python3 scripts/done_gate.py --require-ledger   # also fail when no ledger exists
python3 scripts/done_gate.py --self-test
```

## 1. Agent stop hook

Installing WinCreator as a Claude Code plugin registers the hook. To wire it by
hand for a skill-only install, add this to `.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/skills/wincreator/scripts/done_gate.py --hook",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

When the agent tries to end its turn over an open ledger, the hook answers with
a block decision that lists the rows and four honest exits: prove the claim,
record the user's dated waiver, supersede it, or tell the user plainly what is
unproven. Any agent runtime with a stop/finish hook that passes JSON on stdin
and accepts `{"decision": "block", "reason": "..."}` on stdout can use the same
command.

Behavior worth knowing before relying on it:

- **It never loops.** If the runtime reports `stop_hook_active`, the gate lets
  the agent stop.
- **It raises a given set of open claims once per session.** The same open rows
  are not repeated on every later turn; a new or changed unproven claim is
  raised again.
- **It fails open.** No ledger, unreadable input, a missing Python, or an
  internal error never traps a session.
- **Off switch:** `WINCREATOR_DONE_GATE=off`.

## 2. CI gate

```yaml
# .github/workflows/proof-ledger.yml
name: proof-ledger
on: [push, pull_request]
jobs:
  done-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: winterbim/wincreator@master   # or pin a release tag / commit SHA
        with:
          strict-attestation: "false"
          require-ledger: "false"
```

The job fails while unproven claims remain and writes a claims table to the job
summary. Inputs: `ledger`, `root`, `strict-attestation`, `require-ledger`.

## 3. Anywhere else

The plain CLI exit code is the contract: use it from a pre-commit hook, a
Makefile target, or a release script.

## Limits

The Done Gate reads ledgers; it does not create claims. An agent that never
opens a ledger is never gated, so the gate complements the skill, it does not
replace it. It checks the ledger's form and statuses, not attestation
integrity: run `wincreator.py verify --ledger <ledger>` for that. A stop hook
that can be passed after one honest report is a forcing function for
visibility, not a sandbox: it guarantees the user is told, not that the work
is finished.
