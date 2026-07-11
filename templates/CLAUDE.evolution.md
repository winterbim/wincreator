
## WinCreator — evolution loop (project-level)

This block is appended to a host project's `CLAUDE.md` to run the WinCreator
self-improvement circuit there. Paths assume the skill is installed at
`~/.claude/skills/Skill_WinCreator/`; adjust if you installed it elsewhere.

- Any non-trivial task follows skill-wincreator (classify, announce the gate, Panel).
- Every claim is verified by the `wincreator-skeptic` subagent (never self-graded).
- On every INSUFFICIENT verdict and at the close of every Meso+ loop: invoke `wincreator-retro-analyst`.
- When `EVOLUTION_QUEUE.md` holds ≥1 proposal with a confirmed pattern, OR every 10 catches, OR on request: invoke `wincreator-skill-surgeon` (one proposal = one Meso loop).
- Never rewrite the skill outside this circuit. The invariants (4 ledger statuses, Builder/Skeptic, no-upward-propagation, Two-Failure) move only with an explicit user waiver.

### Loop files (this project)

- Mechanical gate: `python3 ~/.claude/skills/Skill_WinCreator/scripts/ledger_check.py`
  (run `--self-test` before trusting the gate; expect `20/20 passed`).
- Proposals queue: `./EVOLUTION_QUEUE.md` (project root).
- Live catches (written by the retro-analyst): `./SKEPTIC_CATCHES.md` (project root).

### Which SKEPTIC_CATCHES.md is authoritative (decided, not left ambiguous)

Two files can exist. The rule:

- `~/.claude/skills/Skill_WinCreator/SKEPTIC_CATCHES.md` — **read-only inherited
  heritage** (the skill's seed catches). Never written by this project.
- `./SKEPTIC_CATCHES.md` — **the live project log**. The retro-analyst appends
  here; the surgeon sources confirmed patterns from here.
- At the **start of a Meso+ loop, re-read BOTH**: inherited heritage informs
  the gate, project catches drive local evolution.

### Day-zero note (avoid a false "broken install")

A fresh project has no project catches yet, so
`ledger_check.py --catches ./SKEPTIC_CATCHES.md` returns **STALE, exit 1** —
this is the **expected** state, not a broken install. That gate only becomes
meaningful after the first real loops feed the log. The single install
smoke test is `--self-test` (expect `20/20 passed`, exit 0).
