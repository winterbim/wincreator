# G03 benchmark — real paired smoke, not an effect claim

Status: **executed once on real Codex runs; not a publishable effect estimate.**
One repetition over four infrastructure cases cannot support a claim that
WinCreator improves outcomes. Both arms passed every case, so this run measures
cost and latency, not benefit.

## Design

- Same model, reasoning effort and CLI for both arms: `gpt-6-luna`,
  `high`, `codex-cli 0.163.0`, sandbox `workspace-write`, approval `never`.
- OFF: task without WinCreator. ON: the same task with the skill installed at
  `.agents/skills/wincreator` (tree `d1ed953f…`, VERSION `3.1.0`).
- Four frozen cases, one repetition, both conditions = 8 runs.
- Grader runs outside the workspace, after the agent.
- Cost is token-equivalent at the published standard rates in
  `bench/prices/gpt-6-luna-2026-10-24.json`; it is **not** a billed amount.

Command:

```bash
WINCREATOR_BENCH_MODEL=gpt-6-luna WINCREATOR_BENCH_REASONING_EFFORT=high \
python3 bench/run_ablation.py \
  --output bench-results/g03-codex-luna \
  --repetitions 1 --condition both \
  --price-schedule bench/prices/gpt-6-luna-2026-10-24.json \
  -- python3 /home/wina/wincreator/bench/adapters/codex_exec.py
```

## Results

| Case | OFF | ON | OFF cost | ON cost |
|---|---|---|---|---|
| 001-boundary | pass, 13.8 s | pass, 18.3 s | $0.002567 | $0.003673 |
| 002-escaped-table | pass, 24.5 s | pass, 21.0 s | $0.003537 | $0.003535 |
| 003-stable-unique | pass, 13.5 s | pass, 26.9 s | $0.002356 | $0.005084 |
| 004-config-precedence | pass, 17.4 s | pass, 25.1 s | $0.002855 | $0.005759 |

| Arm | Runs | Passed | Mean duration | Input tokens | Output tokens | Token-equivalent cost |
|---|---|---|---|---|---|---|
| OFF | 4 | 4/4 | 17.3 s | 492,199 | 5,108 | $0.011315 |
| ON | 4 | 4/4 | 22.8 s | 716,539 | 7,488 | $0.018051 |

ON used about 46% more input tokens and 39% more cost in this run, and passed
the same number of cases. That is a cost observation on four smoke cases, not
evidence that the skill is harmful or useless.

## Raw artifacts and reproducibility

- Local (not committed, contains agent logs): `bench-results/g03-codex-luna/`
- Bundle digest: `4afc4a3e956a04d5a952ce5bbc840dffd5b90a2e2487346bae7b7657a09e42a8`
- Manifest digest: `8c3f26f37e0a34fb…`
- Grader isolation: `cwd-only`; the grader is never copied into the workspace,
  but a local process could traverse outside it.

## Limitations (read before quoting any number)

1. **One repetition.** Stochastically meaningless for a benefit claim. The
   README asks for at least three; this is a pipeline smoke, and the primary
   run remains to be scheduled.
2. **Ceiling effect.** All four cases passed in both arms, so the experiment
   cannot separate the conditions.
3. **Provider model identity.** Codex did not emit `server_model`; the requested
   ID is recorded and identity is marked `unavailable`.
4. **Cost is derived.** Cached input is billed at the published cached rate
   ($0.01/M) and the rest at $0.10/M input, $0.50/M output. A subscription
   account has a different marginal cost.
5. **No hidden oracle.** Isolation is `cwd-only`; a publication-grade hidden
   oracle needs a container/VM boundary.
