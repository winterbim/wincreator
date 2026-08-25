# Contributing

This repository practices the doctrine it publishes: no change merges on
the strength of "it works." Two things are required of every pull request.

## 1. The ledger gate must pass

```
python3 skill/wincreator/scripts/ledger_check.py --self-test
python3 skill/wincreator/scripts/wincreator.py --self-test
python3 skill/wincreator/scripts/package_check.py --self-test
python3 -m pytest -q
python3 skill/wincreator/scripts/package_check.py skill/wincreator
python3 skill/wincreator/scripts/ledger_check.py PROOF_LEDGER.md
python3 skill/wincreator/scripts/ledger_check.py PROOF_LEDGER-v3-proof-capture.md
python3 skill/wincreator/scripts/ledger_check.py --catches skill/wincreator/SKEPTIC_CATCHES.md
```

CI runs all of these for every pull request and for pushes to `master`
(`.github/workflows/ci.yml`) — the verifiers prove themselves before they are
allowed to grade anything. If your change adds or modifies a claim about the
skill's behavior, add a row to `PROOF_LEDGER.md` with real evidence. Prefer
capturing it rather than writing it:

```
python3 skill/wincreator/scripts/wincreator.py prove P-XX \
  --tier standard --builder your-id -- <your command>
python3 skill/wincreator/scripts/wincreator.py review P-XX \
  --verdict evidenced --reviewer skeptic-id
```

`CLAIMED`, `DISPROVEN`, and `INSUFFICIENT` rows do not merge. `PENDING` and `BLOCKED` may merge only while the named wait is still true — re-check them before calling the loop done.

## 2. A Skeptic pass in the PR description

Before requesting review, add a section titled `Skeptic pass:` to the PR
description. Re-read only your own claim, the gate that was supposed to
prove it, and the raw evidence — then argue, in your own words, why the
claim might still be false. Name at least one concrete attack (an
unexercised edge case, an environment difference, a weaker neighboring
claim that got proven instead of the real one). If you can't find a hole,
say so explicitly — but look first.

See `skill/wincreator/references/agents.md` for the full Builder /
Skeptic protocol this is drawn from.

## Style

Match the existing tone: no filler, no unearned superlatives, no emoji.
Every claim in prose should be traceable to something that was actually
run or read.
