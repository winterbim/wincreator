# WinCreator

Your agent says "done, tested." Can you prove it — six months from now,
to someone who wasn't in the conversation? Most agent sessions can't: the
same context that wrote the code also graded it, the constraints from
message one are long gone by message forty, and a failing check gets
re-attacked at the same level, forever.

**WinCreator turns any non-trivial engineering task into a hierarchy of
verification-gated loops with an auditable Proof Ledger, Builder/Skeptic
role separation, and a re-emitted loop state panel that survives long
sessions.**

[![ledger-check](https://github.com/winterbim/wincreator/actions/workflows/ledger.yml/badge.svg)](https://github.com/winterbim/wincreator/actions/workflows/ledger.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Works with](https://img.shields.io/badge/works%20with-Claude%20Code%20%7C%20Codex%20%7C%20Cursor-6e56cf)](#installation)
[![Sponsor](https://img.shields.io/badge/sponsor-buymeacoffee-orange)](https://buymeacoffee.com/wintfernanh)

## 30-second demo

The mechanical gate is `scripts/ledger_check.py` — stdlib-only, no
dependencies. It parses a `PROOF_LEDGER.md` table and refuses to exit 0 if
any claim is unproven. Below is a real run, not a mockup.

Save this exact table as `PROOF_LEDGER_dirty.md` — one unproven claim, one
rubber-stamped one:

```markdown
| ID | Level | Claim | Gate (what proves it) | Status | Evidence |
|----|-------|-------|------------------------|--------|----------|
| P1 | Meso  | /export endpoint returns 200 for all active cases | Run full dataset, inspect status codes | EVIDENCED | run 2026-07-10: pytest -k export -> 14 passed |
| P2 | Micro | parser rejects malformed input | unit test on truncated file | CLAIMED | |
| P3 | Micro | CSV export matches DB row count | diff row counts after export | EVIDENCED | ok |
```

```
$ python3 skill/Skill_WinCreator/scripts/ledger_check.py PROOF_LEDGER_dirty.md
LEDGER NOT CLEAN — 2 violation(s):
  ✗ line 4 [P2]: CLAIMED with no evidence — loop may not report done. Claim: parser rejects malformed input
  ✗ line 5 [P3]: status EVIDENCED but Evidence cell is empty or too vague ('ok')
exit=1
```

Fix the two claims — real evidence, not "ok":

```markdown
| ID | Level | Claim | Gate (what proves it) | Status | Evidence |
|----|-------|-------|------------------------|--------|----------|
| P1 | Meso  | /export endpoint returns 200 for all active cases | Run full dataset, inspect status codes | EVIDENCED | run 2026-07-10: pytest -k export -> 14 passed |
| P2 | Micro | parser rejects malformed input | unit test on truncated file | EVIDENCED | pytest -k truncated_input -> 1 passed, AssertionError raised as expected |
| P3 | Micro | CSV export matches DB row count | diff row counts after export | EVIDENCED | export.csv rows=482, SELECT COUNT(*) FROM cases=482, match |
```

```
$ python3 skill/Skill_WinCreator/scripts/ledger_check.py PROOF_LEDGER_clean.md
LEDGER CLEAN — 3 row(s) verified in PROOF_LEDGER_clean.md
exit=0
```

That is the entire mechanism. No LLM call, no network, no config. A
single stdlib-only Python script
([`ledger_check.py`](skill/Skill_WinCreator/scripts/ledger_check.py), 91
lines) stands between "the agent said it's done" and a merge.

## The three failure modes

Every agent-assisted engineering session degrades the same three ways,
and knowing them is the key to using this skill well.

1. **Optimism leak** — the same context that wrote the code grades its
   own work, and "it should work" quietly becomes "it works".
   Countermeasure: the Proof Ledger + Builder/Skeptic separation.
   Whoever builds never grades their own gate; the Skeptic receives only
   the claim, the gate, and the raw evidence — never the Builder's
   reasoning, which contaminates judgment.
2. **Context rot** — constraints stated early get lost as the session
   grows; the agent drifts from the original need without noticing.
   Countermeasure: the Loop Panel, a four-line state block re-emitted at
   every gate event (gate announced, gate passed, gate failed, level
   change), so the current truth survives even when session memory
   degrades.
3. **Stuck loops** — a failing check gets re-attacked at the same level
   again and again, when the real defect lives one level up.
   Countermeasure: the Two-Failure Rule — the same gate failing twice
   forbids a third identical attempt and forces a level audit first
   ("would this failure disappear if something one level up were
   different?").

## Real worked example

[`skill/Skill_WinCreator/references/worked-example.md`](skill/Skill_WinCreator/references/worked-example.md)
is a full transcript, not a fiction: a semver comparator with five green
tests and a docstring promising `ValueError` on malformed input — a
promise no test actually checked. The Skeptic pass caught the gap that
"tests pass → done" would have shipped, and a sixth test closed it before
the loop was allowed to report up.

## Installation

**Claude Code**

```
git clone https://github.com/winterbim/wincreator.git
cp -r wincreator/skill/Skill_WinCreator ~/.claude/skills/Skill_WinCreator
```

**npx skills**

```
npx skills add winterbim/wincreator
```

**Manual download**

Download `Skill_WinCreator.skill` from the
[latest release](https://github.com/winterbim/wincreator/releases/latest)
and unzip it into your skills directory.

## This repo eats its own dogfood

[`PROOF_LEDGER.md`](PROOF_LEDGER.md) at the repository root is not a
sample — it is the real ledger for the act of publishing this repository:
every claim made while shipping WinCreator (structure preserved
unmodified, demo output real, no placeholder credentials committed,
attribution consistent) is a row in that file, and
`.github/workflows/ledger.yml` runs `ledger_check.py` against it on every
push. The green badge at the top of this page is that check, live, not a
static image — its
[most recent run](https://github.com/winterbim/wincreator/actions/runs/29097155491)
verified all rows in `PROOF_LEDGER.md` on GitHub's own runner.

## Bootstrap the evolution loop in your own project

The skill itself (doctrine + gate + `SKEPTIC_CATCHES.md`) travels in the
`.skill` package. The *evolution circuit* that lets the skill improve itself
— the `.claude/agents/`, the `CLAUDE.md` wiring, the proposals queue — is
repository scaffolding, so it travels via `git clone`, not the single-file
`.skill`. To run that circuit inside one of your own projects:

```bash
# sources: your clone of this repo, and wherever you installed the skill
WINCREATOR=/path/to/wincreator                 # git clone of this repo
SKILL=~/.claude/skills/Skill_WinCreator        # where you installed the skill

cd /path/to/your/project

# 1. the four evolution agents
mkdir -p .claude/agents
cp "$WINCREATOR"/.claude/agents/wincreator-*.md .claude/agents/

# 2. APPEND the loop section to your CLAUDE.md — never overwrite; your project
#    may already have one (bimwin does), and cat >> preserves it
cat "$WINCREATOR"/templates/CLAUDE.evolution.md >> CLAUDE.md

# 3. create the project-level queue and catches log (only if absent)
[ -f EVOLUTION_QUEUE.md ] || printf '# Evolution Queue\n\n_(empty — awaiting the first retro-analyst pass)_\n' > EVOLUTION_QUEUE.md
[ -f SKEPTIC_CATCHES.md ] || printf '# Skeptic Catches — project log\n\n| Date | Class | Why missed | Question that would have caught it |\n|------|-------|------------|-------------------------------------|\n' > SKEPTIC_CATCHES.md

# 4. the ONLY install smoke test:
python3 "$SKILL"/scripts/ledger_check.py --self-test     # -> self-test: 20/20 passed
```

Every command above was executed in a virgin directory before being
published here (`PROOF_LEDGER-evolution.md`, cycle 4). Two things a fresh
setup must know:

- **`--catches` is STALE at day zero, and that is correct.** A new project
  has no catches yet, so
  `ledger_check.py --catches ./SKEPTIC_CATCHES.md` returns `CATCHES STALE`,
  exit 1 — the expected state, not a broken install. That gate only becomes
  meaningful after real loops feed the log. Use `--self-test` (not
  `--catches`) as the install check.
- **Two `SKEPTIC_CATCHES.md` can exist; the authority is decided.** The one
  in `~/.claude/skills/Skill_WinCreator/` is read-only inherited heritage;
  your project's `./SKEPTIC_CATCHES.md` is the live log the retro-analyst
  writes. A Meso+ loop re-reads **both** at its start. The full rule is in
  `templates/CLAUDE.evolution.md`, which step 2 appends to your `CLAUDE.md`.

## Support this project

WinCreator is free and MIT-licensed. If it saved you from shipping an
unverified "done," consider supporting its development:
[buymeacoffee.com/wintfernanh](https://buymeacoffee.com/wintfernanh) ·
[bimcheck-consulting.com](https://bimcheck-consulting.com)

## License

MIT — see [LICENSE](LICENSE). Copyright Winter Fernandes.

If you use, fork, or build upon this skill, credit Winter Fernandes as
the original creator with a link back to this repository. The MIT
license already requires the copyright notice to be preserved; this line
makes that expectation explicit and visible.

---

Created by **Winter Fernandes** — BIMCheck Consulting
[bimcheck-consulting.com](https://bimcheck-consulting.com)

Attribution required in derivatives — see [NOTICE](NOTICE).
