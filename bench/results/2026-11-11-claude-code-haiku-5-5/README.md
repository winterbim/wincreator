# Result: Claude Code + Claude Haiku 5.5, WinCreator ON vs OFF (2026-11-11)

**No measurable effect on outcome. The ON arm cost 57% more.**

| Arm | Held-out grader pass | False "done" reports | Mean cost | Mean time |
|---|---|---|---|---|
| OFF | 33/33 | 0 | $0.011 | 41 s |
| ON (WinCreator 3.1.0) | 33/33 | 0 | $0.017 | 37 s |

Full tables: [`REPORT.md`](REPORT.md). Raw data: [`bundle.json`](bundle.json)
(digest `90683bf048adf54a55a975e5957ede331eef5fb7c86517bc69b473c14ec637b1`).

## What was run

- 11 cases (`005`–`015`), 3 repetitions, both arms: 66 runs.
- Agent: Claude Code 2.1.322, `claude -p`, requested model `haiku`, provider-reported
  model `claude-haiku-5-5` in every run. Same command for both arms
  ([`bench/adapters/claude_code.py`](../../adapters/claude_code.py)).
- ON arm: the skill tree copied into the workspace and one sentence in the task
  telling the agent to use it. The Done Gate hook was **not** part of the treatment.
- The cases were committed (`c201811` on the benchmark branch) before the scored runs.

## How to read it

1. **This is a ceiling result, not evidence that the protocol is useless.** Both
   arms solved every case, so the benchmark could not have shown a benefit even
   if one exists. With 33/33 the 95% interval for each arm is 90–100%.
2. **It is evidence about these task sizes.** The cases are single-file or
   three-file tasks that fit in one short session. On them, this model reads the
   contract, tests beyond the visible check, and reports unverifiable
   requirements honestly without being told to. The failure modes WinCreator
   targets did not occur in the control arm.
3. **The cost is real.** The ON arm used 57% more money and 4 more turns per run.
   The treatment was taken up: the agent opened the skill in 30/33 runs and
   executed a WinCreator script in 17/33.
4. **What it does not cover:** long sessions where context degrades, multi-day
   work, large repositories, weaker or older models, other agents, and the
   audit-trail value of a ledger for a human reviewer. None of these were measured.

## Threats to validity

- The completion report required of both arms (`REPORT.json`) asks the agent to
  separate "verified" from "unverified". That instruction is itself a small
  honesty intervention and was present in the control arm.
- Isolation is cwd-only. One run named a path outside its workspace; it wrote a
  scratch script under `/tmp` and did not read the grader.
- The child sessions ran inside a managed Claude Code environment with its own
  system instructions and plugins, identical for both arms.
- One unscored pilot repetition on cases `005`–`011` preceded the commit that
  froze the cases. Cases `012`–`015` were written after that pilot (to be harder)
  and before any run on them.
- Three repetitions on one model is a small sample of one configuration.

## Reproduce

```bash
export WINCREATOR_BENCH_MODEL=haiku
python3 bench/run_ablation.py --output bench-results/haiku --repetitions 3 \
  --condition both --jobs 8 \
  --case 005-csv-roundtrip --case 006-retry-contract --case 007-pagination \
  --case 008-split-amount --case 009-slugify --case 010-unreachable-service \
  --case 011-missing-oracle --case 012-wrong-target --case 013-buried-amendment \
  --case 014-flaky-gate --case 015-mocked-away \
  -- python3 "$PWD/bench/adapters/claude_code.py"
python3 bench/analyze.py bench-results/haiku/bundle.json
```
