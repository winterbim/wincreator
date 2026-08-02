# WinCreator

Your agent says "done, tested." Can you prove it — six months from now,
to someone who wasn't in the conversation? Most agent sessions can't: the
same context that wrote the code also graded it, the constraints from
message one are long gone by message forty, and a failing check gets
re-attacked at the same level, forever.

**WinCreator turns any non-trivial engineering task into a hierarchy of
verification-gated loops with an auditable Proof Ledger, Builder/Skeptic
role separation, and a re-emitted loop state panel that survives long
sessions — and since v3.0.0 it does not ask the agent to *describe* its
proof: `wincreator prove` runs the gate, captures the raw output, hashes
it, binds it to the commit, and writes the ledger row itself.**

[![ledger-check](https://github.com/winterbim/wincreator/actions/workflows/ledger.yml/badge.svg)](https://github.com/winterbim/wincreator/actions/workflows/ledger.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Works with](https://img.shields.io/badge/works%20with-Claude%20Code%20%7C%20Codex%20%7C%20Cursor-6e56cf)](#installation)
[![Sponsor](https://img.shields.io/badge/sponsor-buymeacoffee-orange)](https://buymeacoffee.com/wintfernanh)

## 30-second demo

Two stdlib-only scripts, no dependency, no LLM call, no network:
[`ledger_check.py`](skill/wincreator/scripts/ledger_check.py) refuses to
exit 0 while a claim is unproven, and
[`wincreator.py`](skill/wincreator/scripts/wincreator.py) captures the
proof so nobody has to be trusted to write it. Every output below is a
real run, pasted verbatim except for sha256 digests shortened to fit.

**1. The gate rejects narrated proof.** Save this as
`PROOF_LEDGER_dirty.md` — an unproven claim, a rubber stamp, and a row
that merely *sounds* like evidence:

```markdown
| ID | Level | Claim | Gate (what proves it) | Status | Evidence |
|----|-------|-------|------------------------|--------|----------|
| P1 | Meso  | /export endpoint returns 200 for all active cases | `pytest -k export` on the full dataset | EVIDENCED | run 2026-07-10: `pytest -k export` -> 14 passed |
| P2 | Micro | parser rejects malformed input | unit test on truncated file | CLAIMED | |
| P3 | Micro | CSV export matches DB row count | diff row counts after export | EVIDENCED | ok |
| P4 | Micro | the nightly job finished under 5 min | time the run | EVIDENCED | 2026-08-02 test passed |
```

```
$ python3 skill/wincreator/scripts/ledger_check.py PROOF_LEDGER_dirty.md
LEDGER NOT CLEAN — 3 violation(s):
  ✗ line 4 [P2]: CLAIMED — loop may not report done. Claim: parser rejects malformed input
  ✗ line 5 [P3]: EVIDENCED but Evidence empty/vague ('ok')
  ✗ line 6 [P4]: EVIDENCED but no execution trace (need an exit code, an attestation sha256, a run URL, or a named command in Gate/Evidence WITH a dated or raw result): '2026-08-02 test passed' — prose alone is not proof
exit=1
```

**2. The proof is captured, not typed.** `wincreator prove` runs the gate
and writes the row from what actually happened:

```
$ python3 skill/wincreator/scripts/wincreator.py prove P2 -- python3 check_parser.py
parser accepted a truncated file: no error raised

[DISPROVEN] P2: CLAIMED -> DISPROVEN in PROOF_LEDGER.md
[ATTESTATION] .wincreator/attestations/P2/20260802T084356Z/attestation.json sha256=6f5fac1239…
[GATE FAILED] exit=1 — the claim is recorded DISPROVEN, not EVIDENCED. A failed gate cannot be written as a proof.
exit=1
```

The row it wrote, and what the gate then says about it:

```markdown
| P2 | Micro | parser rejects malformed input | `python3 check_parser.py` | DISPROVEN | wincreator prove 2026-08-02T08:43:56Z: `python3 check_parser.py` -> exit=1 (8 ms); stdout tail: parser accepted a truncated file: no error raised; commit 0ba6a514e1f3+dirty; attestation .wincreator/attestations/P2/20260802T084356Z/attestation.json sha256=6f5fac1239… |
```

```
$ python3 skill/wincreator/scripts/ledger_check.py PROOF_LEDGER.md
LEDGER NOT CLEAN — 1 violation(s):
  ✗ line 3 [P2]: DISPROVEN — the gate ran and the claim is FALSE; the loop may not report done. Fix and re-prove, or reformulate and mark this row SUPERSEDED. Claim: parser rejects malformed input
exit=1
```

Fix the parser, re-run the same command, and the status flips — because
the exit code flipped, not because anyone said so:

```
$ python3 skill/wincreator/scripts/wincreator.py prove P2 -- python3 check_parser.py
truncated file rejected: ValueError raised as expected

[EVIDENCED] P2: DISPROVEN -> EVIDENCED in PROOF_LEDGER.md
[ATTESTATION] .wincreator/attestations/P2/20260802T084402Z/attestation.json sha256=080f934c78…
$ python3 skill/wincreator/scripts/ledger_check.py PROOF_LEDGER.md
LEDGER CLEAN — 1 row(s) verified in PROOF_LEDGER.md
exit=0
```

**3. Editing the story afterwards is detectable.** Rewrite the captured
sentence by hand and `verify` re-derives it from the attestation:

```
$ python3 skill/wincreator/scripts/wincreator.py verify --ledger PROOF_LEDGER.md
  [OK  ] .wincreator/attestations/P2/20260802T084402Z/attestation.json
  [OK  ] .wincreator/attestations/P2/20260802T084356Z/attestation.json
  [LEDGER] 1 attestation reference(s) in PROOF_LEDGER.md
         ✗ PROOF_LEDGER.md: row P2 evidence text was rewritten after capture (the captured sentence is machine-owned; append your notes after it instead of editing it)
VERIFY FAILED — 1 problem(s)
exit=1
```

That is the entire mechanism. Stdlib only, and it stands between "the
agent said it's done" and a merge.

## What an attestation contains

Each `prove` run writes `stdout.log`, `stderr.log` and an
`attestation.json` under `.wincreator/attestations/<claim>/<timestamp>/`:
the exact argv, the exit code, the duration, UTC start/end, the sha256 of
stdout and stderr, the sha256 of every `--file` artifact, the git commit /
branch / dirty flag / remote, the platform, Python version and hostname,
and a canonical sha256 digest of all of it. Set `WINCREATOR_SIGNING_KEY`
and the digest is also HMAC-SHA256 signed. `wincreator.py verify`
re-computes every hash, so a tampered log, a forged verdict, a laundered
status or a rewritten evidence sentence all surface as failures.

This is a local, self-verifying audit trail — not a transparency log:
someone who controls the repository can delete an attestation and re-run
the gate. The intended hardening path is CI-side retention plus signed
attestations in the in-toto/SLSA family; that is not implemented yet.

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

[`skill/wincreator/references/worked-example.md`](skill/wincreator/references/worked-example.md)
is a full transcript, not a fiction: a semver comparator with five green
tests and a docstring promising `ValueError` on malformed input — a
promise no test actually checked. The Skeptic pass caught the gap that
"tests pass → done" would have shipped, and a sixth test closed it before
the loop was allowed to report up.

## Installation

**Claude Code**

```
git clone https://github.com/winterbim/wincreator.git
cp -r wincreator/skill/wincreator ~/.claude/skills/wincreator
```

**Codex / OpenAI agents, Cursor, and any Agent Skills runtime**

The package follows the open Agent Skills layout (`SKILL.md` +
`agents/openai.yaml` + `scripts/` + `references/`), so copying
`skill/wincreator/` into your runtime's skills directory is the whole
install. Check it yourself:

```
$ python3 skill/wincreator/scripts/package_check.py skill/wincreator
PACKAGE VALID — skill/wincreator matches the Agent Skills conventions
```

**npx skills**

```
npx skills add winterbim/wincreator
```

**Manual download**

Download `wincreator.skill` from the
[latest release](https://github.com/winterbim/wincreator/releases/latest)
and unzip it into your skills directory. Each release ships a
`wincreator.skill.sha256` beside it; the same asset and checksum are
rebuilt in CI by `./tools/build_package.sh`, so you can check what you
downloaded instead of trusting it.

> Installing from an older release? The package directory was renamed
> `Skill_WinCreator` → `wincreator` in v3.0.0 to satisfy the Agent Skills
> rule that the skill name matches its directory. Remove the old
> `~/.claude/skills/Skill_WinCreator` after installing.

## This repo eats its own dogfood

[`PROOF_LEDGER.md`](PROOF_LEDGER.md) at the repository root is not a
sample — it is the real ledger for the act of publishing this repository:
every claim made while shipping WinCreator (structure preserved
unmodified, demo output real, no placeholder credentials committed,
attribution consistent) is a row in that file, and
`.github/workflows/ledger.yml` runs it against every ledger in the repo on
every push — after making the verifier prove itself first
(`--self-test` for all three scripts, `py_compile`, package validation),
because a verifier that was never attacked is an unverified claim. The
v3 work itself is captured in
[`PROOF_LEDGER-v3-proof-capture.md`](PROOF_LEDGER-v3-proof-capture.md),
whose rows were written by `wincreator prove`, not by hand. The green
badge at the top of this page is that workflow, live, not a static image.

## How much ceremony? Three tiers

The full hierarchy is not always the right answer, and applying it to a
typo is how a governance skill becomes the problem it was built to solve.
Pick a tier and say which one you picked:

| Tier | Use when | What you run |
|---|---|---|
| **Lite** (default) | one claim, one gate, checkable now | announce the gate, execute it, quote the raw result — no ledger file |
| **Standard** | multi-step work whose failure is expensive or silent | Loop Panel + `PROOF_LEDGER.md` + Skeptic pass + `ledger_check.py` |
| **Regulated** | audited, contractual or safety-relevant work | Standard + `wincreator prove` on every claim, `--strict-attestation`, retained artifacts, human sign-off |

## Bootstrap the evolution loop in your own project

The skill itself (doctrine + gate + `SKEPTIC_CATCHES.md`) travels in the
`.skill` package. The *evolution circuit* that lets the skill improve itself
— the `.claude/agents/`, the `CLAUDE.md` wiring, the proposals queue — is
repository scaffolding, so it travels via `git clone`, not the single-file
`.skill`. To run that circuit inside one of your own projects:

```bash
# sources: your clone of this repo, and wherever you installed the skill
WINCREATOR=/path/to/wincreator                 # git clone of this repo
SKILL=~/.claude/skills/wincreator              # where you installed the skill

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
python3 "$SKILL"/scripts/ledger_check.py --self-test     # -> self-test: 36/36 passed
python3 "$SKILL"/scripts/wincreator.py --self-test       # -> self-test: 26/26 passed
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
  in `~/.claude/skills/wincreator/` is read-only inherited heritage;
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

The MIT license is the whole legal obligation: keep the copyright notice
and the license text in substantial copies. Beyond that, a credit to
Winter Fernandes with a link back to this repository is a **request, not
a condition** — appreciated, never enforced. See [NOTICE](NOTICE).

---

Created by **Winter Fernandes** — BIMCheck Consulting
[bimcheck-consulting.com](https://bimcheck-consulting.com)

Attribution appreciated in derivatives — see [NOTICE](NOTICE).
