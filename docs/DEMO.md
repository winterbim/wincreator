# Public demo script (~60 seconds)

The demo should make one idea obvious: **green is not the same thing as proven**.
Use real output only.

## Setup

```bash
cd examples/minimal
export WC=../../skill/wincreator   # or ~/.claude/skills/wincreator
rm -rf .wincreator
```

## Script

**0:00–0:08 — The familiar failure**

Show this sentence full-screen:

> “Tests passed. The feature is done.”

Say:

> “Agents collapse two different questions: did a command pass, and did that command actually prove the claim?”

**0:08–0:22 — One command, no setup**

Run:

```bash
python3 "$WC/scripts/quick_prove.py" \
  "the example output satisfies its contract" \
  -- python3 check_example.py
```

Point at the explicit claim, gate, capture status, attestation and generated ledger path.

Say:

> “Lite is deliberately cheap. I state the claim, WinCreator creates the evidence trail, and the gate actually runs.”

**0:22–0:38 — Raise the stakes**

Run the same shape in Standard:

```bash
python3 "$WC/scripts/quick_prove.py" \
  "the example output satisfies its contract" \
  --tier standard \
  -- python3 check_example.py
```

Point at `CAPTURED_PASS` and `PENDING`.

Say:

> “Same green command. Different conclusion. Standard refuses to call the claim evidenced until the capture itself is reviewed.”

**0:38–0:52 — Show the actual product**

Use the generated claim ID from the previous command:

```bash
python3 "$WC/scripts/wincreator.py" review <CLAIM_ID> \
  --ledger .wincreator/PROOF_LEDGER.md \
  --verdict insufficient \
  --reviewer demo-skeptic
```

Say:

> “If the test is too weak for the claim, the honest result is `INSUFFICIENT` — even though the test passed.”

This is the important moment of the demo. Do not make the happy path the climax.

**0:52–1:00 — Close**

Show:

```bash
npx skills add winterbim/wincreator
```

Say:

> “WinCreator does not make tests smarter. It stops agents from saying that a test proved more than it actually proved.”

## Rules for the recording

- Keep the terminal output real.
- Do not hand-edit the quick ledger before the demo.
- Make `INSUFFICIENT` visible; that is the differentiator.
- Do not describe Lite auto-approval as independent review.
- Do not claim adoption, compliance or security guarantees beyond what the repository demonstrates.
