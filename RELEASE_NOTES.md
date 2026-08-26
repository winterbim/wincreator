# WinCreator v3.0.2

Production-readiness release after an external-style end-to-end trial of the packaged skill.

## What changed

- Added the zero-setup `quick_prove.py` path: one explicit claim plus one real command, with no hand-written ledger required for Lite or Standard entry.
- Fixed empty pre-created quick ledgers so setup tooling or `touch .wincreator/PROOF_LEDGER.md` cannot break the first proof.
- Fixed longitudinal verification: `verify --ledger` still integrity-checks every historical capture and review, but only the newest proof chain for each claim is compared with the ledger's current status/evidence.
- Added regressions for the real lifecycle `INSUFFICIENT -> DISPROVEN -> fix -> EVIDENCED`, historical tamper detection, and a newest unreviewed run correctly returning the claim to a non-evidenced state.
- README/demo now center the actual failure mode: a green command can still be insufficient evidence for the claim.

The important semantic guarantee in this release is that failed and insufficient attempts remain immutable audit history without falsely invalidating a later successful re-proof.

Install or update:

```bash
npx skills add winterbim/wincreator
```

Then the default path is:

```bash
python3 ~/.claude/skills/wincreator/scripts/quick_prove.py \
  "parser rejects malformed input" \
  -- python3 check_parser.py
```

See `README.md` for Standard review, Regulated constraints, sensitive-output controls, and the full development/release gates.
