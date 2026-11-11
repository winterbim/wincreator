# WinCreator frontier benchmark

This directory is the public, reproducible benchmark program for measuring whether WinCreator changes coding outcomes — not a leaderboard built from feature counts.

## The primary experiment

Run the **same agent/model/runtime** twice on the same frozen case:

- **OFF** — normal coding task, WinCreator absent;
- **ON** — same task and budget, with the current WinCreator skill installed in the workspace.

Use at least 3 repetitions for stochastic agents. Preserve every raw result. Do not compare different models or budgets and call the difference a WinCreator effect.

The runner records:

- hidden/held-out grader pass/fail;
- agent exit/timing and output digests;
- source file count, nonblank lines, bytes and largest file;
- task, seed and grader digests;
- the exact condition and repetition.

It deliberately does **not** produce a universal code-quality score.

## Validate cases first

Every benchmark seed must be RED before an agent sees it:

~~~bash
python3 bench/validate_cases.py
~~~

A case whose seed already passes its grader is rejected.

## Run an agent

The agent command receives these environment variables:

- `WINCREATOR_BENCH_WORKSPACE`
- `WINCREATOR_BENCH_PROMPT`
- `WINCREATOR_BENCH_CONDITION` (`off` or `on`)
- `WINCREATOR_BENCH_CASE`

It may also use command placeholders `{workspace}`, `{prompt}`, and `{condition}`.

Example adapter shape:

~~~bash
python3 bench/run_ablation.py \
  --output bench-results/codex-gpt56 \
  --repetitions 3 \
  --condition both \
  -- my-agent-wrapper --workspace {workspace} --prompt-file {prompt}
~~~

The ON workspace contains `.agents/skills/wincreator`; the OFF workspace does not.
Every ON result also records the pre-run tree digest and VERSION of that exact
copied Skill, so treatment identity is not inferred from the surrounding checkout.

## Codex CLI adapter

For a real paired run with Codex CLI, authenticate Codex first, then pin the
same model and reasoning effort for both arms:

~~~bash
export WINCREATOR_BENCH_MODEL="<exact-model-id>"
export WINCREATOR_BENCH_REASONING_EFFORT="high"

python3 bench/run_ablation.py \
  --output bench-results/codex \
  --repetitions 3 \
  --condition both \
  -- python3 bench/adapters/codex_exec.py
~~~

The adapter uses Codex non-interactively with an ephemeral session, JSONL
events, closed stdin, explicit `workspace-write` sandboxing and approval policy
`never`. It does **not** use the dangerous sandbox/approval bypass. User config
and exec-policy rules are ignored by default to reduce uncontrolled treatment
differences; pass `--keep-user-config` only when that configuration is itself
part of the declared benchmark environment.

The adapter writes normalized provider metrics outside the workspace. When
Codex emits a terminal `turn.completed` event, token usage is retained in the
run result. The requested model ID is recorded. Unless the JSONL event also
contains a provider-reported `server_model`, model identity is marked
`unavailable` rather than pretending the requested alias independently proves
what the provider served.

Codex CLI has had non-TTY stdin regressions in automation environments. The
adapter supplies `DEVNULL` explicitly, so a positional prompt cannot hang while
waiting for inherited stdin.

## Claude Code adapter

~~~bash
export WINCREATOR_BENCH_MODEL="<exact-model-id-or-alias>"
python3 bench/run_ablation.py --output bench-results/claude --repetitions 3 \
  --condition both --jobs 8 -- python3 "$PWD/bench/adapters/claude_code.py"
python3 bench/analyze.py bench-results/claude/bundle.json
~~~

Pass the adapter by absolute path: the agent command runs inside each workspace.
The adapter never bypasses permissions, records the provider-reported model,
whether the ON arm actually opened or executed the skill, and any tool input
naming a path outside the workspace. `--jobs` runs independent workspaces in
parallel; `--case` restricts the run.

## Published results

| Date | Agent / model | Cases | OFF pass | ON pass | Finding |
|---|---|---|---|---|---|
| 2026-11-11 | Claude Code / Claude Haiku 5.5 | 005–015, 3 reps | 33/33 | 33/33 | [ceiling: no measurable effect, ON costs 57% more](results/2026-11-11-claude-code-haiku-5-5/README.md) |

A result is added here whatever it shows.

## Oracle isolation

The grader is executed by the harness **after** the agent and is never copied into the workspace. That is held-out-by-runner isolation, not a security boundary: a local agent process could still traverse outside its working directory.

Therefore results must record the isolation level. A publication-grade hidden-oracle run should use a container, bubblewrap, VM, remote grader, or equivalent boundary that prevents the Builder from reading the oracle. Never call the default local mode “secret” or “hidden” without that stronger boundary.

## Current cases

The initial corpus targets small failure classes that coding agents commonly mishandle:

1. boundary/type contract;
2. escaped delimiter parsing;
3. stable uniqueness with unhashable values;
4. typed configuration precedence.

Cases 005–015 add false-green traps with a required completion report: weak
visible tests (005–009), requirements that cannot be verified in the workspace
(010–011), a green suite on the wrong module (012), a buried spec amendment
(013), a flaky gate (014) and a mock that hides the bug (015).
`tests/test_bench_cases.py` proves each grader accepts a reference solution and
rejects the shortcut it targets. Claude Haiku 5.5 solves all of them in both
arms, so they are now known to be **too easy to discriminate**.

Cases 001–004 are infrastructure smoke cases, not enough for a frontier claim. The planned corpus also includes real-repository bug fixes, green-test behavior drift, dependency substitution, stale/fabricated evidence, scope omission, cross-platform failures, flaky checks and provenance mismatch.

## Comparison corpus

`frontier-corpus.json` pins public comparison projects to exact revisions. README claims are discovery evidence only; release-grade comparisons must cite source locations or reproducible commands at those revisions.

The permitted frontier claim remains deliberately narrow:

> No public equivalent identified in the frozen comparison corpus matches WinCreator's declared verification contract on the published benchmark at the pinned revisions.

That sentence is **not earned yet**. It becomes publishable only after the requirements in issue #11 are satisfied.
