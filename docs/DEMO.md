# Public demo script (~60 seconds)

Use this narrative for a screen recording, LinkedIn video, or live talk.
Keep it factual. Do not invent outputs.

## Setup before recording

```bash
cd examples/minimal
export WC=../../skill/wincreator   # or ~/.claude/skills/wincreator
# Reset ledger row to CLAIMED if replaying
```

Have two terminal panes or a clear scrollback.

## Script

**0:00–0:10 — The problem**

> “Your agent just said: tests pass, we’re done.
> That is an assertion. In serious work — BIM data, production code,
> compliance — an assertion is not a deliverable.”

Show a chat bubble or text: `Tests pass. Done.`

**0:10–0:25 — Claim + prove**

> “WinCreator forces the claim into a ledger, then runs the gate for real.”

Show `PROOF_LEDGER.md` with `CLAIMED`, then run:

```bash
python3 "$WC/scripts/wincreator.py" prove M1 \
  --tier standard --builder demo-builder \
  --ledger PROOF_LEDGER.md \
  -- python3 check_example.py
```

Point at `CAPTURED_PASS` and the fact the row is still not `EVIDENCED`
without review (Standard).

**0:25–0:40 — Independent review**

```bash
python3 "$WC/scripts/wincreator.py" review M1 \
  --verdict evidenced --reviewer demo-skeptic \
  --ledger PROOF_LEDGER.md
```

> “Capture is not proof. A separate review decides whether the capture
> actually supports the claim.”

**0:40–0:55 — Mechanical gate + failure path (optional cut)**

```bash
python3 "$WC/scripts/ledger_check.py" PROOF_LEDGER.md
```

Optional second take: `--fail` on `check_example.py` to show `DISPROVEN`.

**0:55–1:00 — Close**

> “Evidence over assertion. Same standard we already demand of BIM data.”

Show install line:

```bash
npx skills add winterbim/wincreator
```

## Assets to put on screen

- `docs/assets/before-after.svg`
- `docs/assets/flow-prove-review.svg`
- Terminal with real command output only

## What not to do

- Do not skip the ledger file on screen
- Do not pretend Lite auto-approve is Regulated compliance
- Do not claim stars, downloads, or adoption numbers you have not measured
