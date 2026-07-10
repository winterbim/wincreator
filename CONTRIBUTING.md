# Contributing

This repository practices the doctrine it publishes: no change merges on
the strength of "it works." Two things are required of every pull request.

## 1. The ledger gate must pass

```
python3 skill/Skill_WinCreator/scripts/ledger_check.py PROOF_LEDGER.md
```

CI runs this on every push (`.github/workflows/ledger.yml`). If your change
adds or modifies a claim about the skill's behavior, add a row to
`PROOF_LEDGER.md` with real evidence — a command actually run, an output
actually inspected. `CLAIMED` rows do not merge.

## 2. A Skeptic pass in the PR description

Before requesting review, add a section titled `Skeptic pass:` to the PR
description. Re-read only your own claim, the gate that was supposed to
prove it, and the raw evidence — then argue, in your own words, why the
claim might still be false. Name at least one concrete attack (an
unexercised edge case, an environment difference, a weaker neighboring
claim that got proven instead of the real one). If you can't find a hole,
say so explicitly — but look first.

See `skill/Skill_WinCreator/references/agents.md` for the full Builder /
Skeptic protocol this is drawn from.

## Style

Match the existing tone: no filler, no unearned superlatives, no emoji.
Every claim in prose should be traceable to something that was actually
run or read.
