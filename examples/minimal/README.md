# Minimal example — copy, run, see the protocol

This folder is a self-contained illustration of WinCreator on a trivial task.
It is not the skill itself. Install the skill first, then use this as a sandbox.

## What you will see

1. A claim enters the ledger as `CLAIMED`
2. `wincreator prove` runs a real command and records a capture
3. `wincreator review` decides whether the capture proves the claim
4. The mechanical gate (`ledger_check.py`) only accepts evidenced work

## Setup

From the repository root (after cloning):

```bash
# Install the skill once (or use the copy already under skill/wincreator)
npx skills add winterbim/wincreator

# Work inside this example
cd examples/minimal
```

The scripts below assume the skill lives at `../../skill/wincreator` relative
to this folder (source tree) or at `~/.claude/skills/wincreator` after install.
Adjust the path if needed.

```bash
export WC=../../skill/wincreator
# or: export WC=~/.claude/skills/wincreator
```

## Step 1 — Ledger with one claim

`PROOF_LEDGER.md` already contains:

```markdown
| ID  | Level | Claim                                      | Gate (what proves it)     | Status  | Evidence |
|-----|-------|--------------------------------------------|---------------------------|---------|----------|
| M1  | Nano  | example script exits 0 and prints OK       | `python3 check_example.py`| CLAIMED |          |
```

## Step 2 — Run the gate through capture

```bash
python3 "$WC/scripts/wincreator.py" prove M1 \
  --tier lite --auto-approve-lite \
  --builder demo-builder \
  --ledger PROOF_LEDGER.md \
  -- python3 check_example.py
```

Expected: capture succeeds (`CAPTURED_PASS` / auto-approved in Lite).

## Step 3 — Standard path (capture then separate review)

Reset the row to `CLAIMED` if you want to replay the Standard flow, then:

```bash
python3 "$WC/scripts/wincreator.py" prove M1 \
  --tier standard \
  --builder demo-builder \
  --ledger PROOF_LEDGER.md \
  -- python3 check_example.py

python3 "$WC/scripts/wincreator.py" review M1 \
  --verdict evidenced \
  --reviewer demo-skeptic \
  --ledger PROOF_LEDGER.md
```

## Step 4 — Mechanical gate

```bash
python3 "$WC/scripts/ledger_check.py" PROOF_LEDGER.md
```

Expected when the claim is evidenced:

```text
LEDGER CLEAN — …
```

## Intentionally broken gate (optional)

To see a `CAPTURED_FAIL` / `DISPROVEN` path:

```bash
python3 "$WC/scripts/wincreator.py" prove M1 \
  --tier standard --builder demo-builder \
  --ledger PROOF_LEDGER.md \
  -- python3 check_example.py --fail
```

## What this is not

- Not a substitute for reading `skill/wincreator/SKILL.md`
- Not a substitute for the full worked transcript in
  `skill/wincreator/references/worked-example.md`
- Not production compliance — Lite auto-approve is for illustration only

## Next

- Full real session with a Skeptic catch:
  [`skill/wincreator/references/worked-example.md`](../../skill/wincreator/references/worked-example.md)
- Protocol reference: [`skill/wincreator/SKILL.md`](../../skill/wincreator/SKILL.md)
