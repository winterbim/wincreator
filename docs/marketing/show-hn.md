# Show HN draft — do not post without approval

**Title (plain, no superlatives):**

> Show HN: WinCreator – a proof protocol so agents can't confuse "the command passed" with "the claim is true"

**Post body:**

I built a small protocol for agent-assisted work where "my tests pass" is a
different statement from "the thing I promised is done".

The mechanism: a claim you write in one sentence, a gate command that is
actually executed, raw capture of stdout/stderr/exit/timing, and a status
written by a reviewer that is not the builder. A green exit becomes
`CAPTURED_PASS` — it only becomes `EVIDENCED` after a separate review that is
allowed to answer `INSUFFICIENT`.

Why not just run tests: a green suite does not cover the claim it is cited
against. The failure this targets is the last step — the agent (or the human)
promoting a passing run into "done".

The repo is a Claude/Codex-style skill (SKILL.md + stdlib Python, no
dependencies, ~4.5k lines including its own gates). It runs in three tiers:
Lite (one command, zero setup), Standard (review on every consequential
claim), Regulated (attestations, distinct builder/reviewer identities).

It also carries its own epistemics in public. The first ON/OFF ablation
(Claude Code + Haiku 5.5, 66 runs, 11 held-out cases) found no measurable
benefit — both arms passed everything, at 1.57× cost for the tool-on arm —
and it is published as measured, with the analysis code, in
`bench/results/`. The scope that is not yet proven: long sessions, large
repos, weaker models. That is what the next ablation round targets, and the
result will be published either way.

Install: `npx skills add winterbim/wincreator`

Repo: https://github.com/winterbim/wincreator

Ask HN: what would it take for you to trust an agent's "done" claim?

---

*Posting notes (internal): post Tue–Thu morning US time; reply to every
skeptical comment with evidence, never with the README; if someone asks for
the benefit data, link issue #20 and the bench results directory directly.*
