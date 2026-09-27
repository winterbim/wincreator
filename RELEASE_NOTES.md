# WinCreator v3.1.0

This release turns WinCreator from a proof-capture discipline into a stronger **anti-false-success engineering layer** for AI-assisted development.

## What changed

- **Distillation Gate** — a working implementation is only a candidate. WinCreator can capture structural cost before cleanup, bind the scan policy and externally frozen baseline digest, detect dependency/scope regressions, then require the real behavior gate again after simplification.
- **Minimum sufficient structure, not minimum LOC** — structural evidence tracks source surface, nonblank lines, dependency changes, duplicate fingerprints and large-file pressure without collapsing them into a fake universal quality score.
- **Stronger adversarial review** — Standard/Regulated review now requires a concrete challenge against the claim/evidence rather than accepting an empty "looks good" Skeptic pass; historical review evidence remains part of the verification story.
- **RED lock and negative-space proof** — consequential new behavior can freeze the acceptance oracle before implementation, and reviewers are explicitly directed toward mutation/property/differential/fuzz techniques when they fit the claim.
- **Intent convergence** — final review compares the actual diff, new dependencies and interfaces with the original request so unrequested architecture cannot hide inside a green test suite.
- **Fail-closed dependency evidence** — fragile heuristic manifest parsing was replaced by content fingerprints where reliable semantic parsing would create false-clean results.
- **Public build provenance** — release packages publish GitHub/Sigstore provenance suitable for independent verification.
- **Self-ablation dogfood** — ChatGPT was used as the subject of a reproducible experiment. The initial implementation passed its visible tests but failed adversarial cases; a later fully-green suite still allowed a controlled mutation to survive; after strengthening the oracle and distilling the implementation, the final candidate preserved behavior while reducing structural size. The experiment itself then exposed a bad benchmark fixture in CI, which was fixed without changing the code under test.
- **Cross-platform proof** — the self-ablation and normal repository gates are exercised across Ubuntu, macOS and Windows on Python 3.10–3.13.

## What this release does not claim

WinCreator does **not** claim that fewer lines are automatically better, that a structural PASS proves semantic correctness, or that v3.1.0 is globally optimal. The release makes narrower, auditable claims and records the limits beside the evidence.

The ongoing frontier benchmark is tracked in issue #11: competing public systems are pinned to exact revisions and compared on claim integrity, reviewer independence, mutation adequacy, provenance, scope integrity, portability and operational cost before any "frontier" claim is published.

## Install or update

```bash
npx skills add winterbim/wincreator
```

The lightweight path remains:

```bash
python3 ~/.claude/skills/wincreator/scripts/quick_prove.py \
  "parser rejects malformed input" \
  -- python3 check_parser.py
```

For consequential code-producing work, use the Standard/Regulated protocol in `SKILL.md`, including independent review and the Distillation Gate where applicable.
