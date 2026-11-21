# Marketing plan — wincreator

Distribution plan for the skill. Written for the repository as it is, not as a
pitch would like it to be. Every number below was read or run in this
repository; the plan is updated when they move.

## Non-negotiable rules

These rules exist because this project's product is honesty about evidence.
Marketing that violates them destroys the product.

1. Never claim a benefit that no published run supports. Until a positive
   ablation exists, the honest line is: "the mechanism separates execution
   from justification; its measured overhead is 1.57×; its benefit on weak
   models and long sessions is not yet proven."
2. The null result ([`bench/README.md`](../bench/README.md), issue #20) is a
   credibility asset, not a liability. Publish it in the launch thread.
3. Every public post contains the one-line install command
   (`npx skills add winterbim/wincreator`) so the post maps to a
   countable install on skills.sh.
4. No launch post is published unreviewed. The drafts live in
   `docs/marketing/`; a human or the user-approved channel account posts it.

## Measured starting point (as of 2026-11)

| Fact | Value | Source |
|---|---|---|
| skills.sh installs | 3 | skills.sh/winterbim/wincreator |
| GitHub stars / forks | 3 / 0 | GitHub API |
| ON vs OFF result (Haiku 5.5, 66 runs) | 33/33 vs 33/33, overhead 1.57× | issue #20, `bench/results/` |
| Release gate (this checkout) | PASS, 100 tests | `tools/run_release_gate.py` |

## Sequencing

### Phase 0 — assets (no launch before this)

- **The false-DONE demo, first screen.** The single most effective asset is a
  short recording (or frame-by-frame SVG, like `docs/assets/before-after.svg`)
  of an agent reporting DONE with green tests while the review records
  INSUFFICIENT. PR #19 builds this; the README should show it above the fold
  when it exists.
- **One sentence with one number.** Candidates: "66-run published ablation",
  "runs on 3 operating systems in CI", "provenance-signed releases". Pick per
  channel; never combine into a superlative.
- **A ledger badge.** A badge that fails visibly when a ledger row is
  CLAIMED/INVALID communicates the product in 15 pixels. `ledger_check.py`
  already returns the bits needed.

### Phase 1 — make installs countable and cheap

skills.sh ranks by real install counts. Every channel touch should end in
`npx skills add winterbim/wincreator`. Track installs weekly (the marketer
agent records the number in its round output; the launch-digest workflow
rebuilds the packet per release).

### Phase 2 — the positive ablation, then launch

The release-blocking evidence is an ON/OFF run where the control arm fails:
weaker models, longer sessions, repository-sized tasks. The harness for this
already exists (`bench/run_ablation.py`, the `analyze.py` Wilson-interval
pipeline, the #20 disclosure format). Run it with the same rigour, publish it
either way — a documented positive result supersedes the documented null, and
both belong in the launch post.

Then launch: Show HN (draft in [`docs/marketing/show-hn.md`](marketing/show-hn.md)),
r/ClaudeAI, r/LocalLLaMA, X and LinkedIn (drafts in
[`docs/marketing/social-posts.md`](marketing/social-posts.md)), in the same week so
the skills.sh trend window sees the installs together.

### Phase 3 — plugging into harnesses

The GitHub Action (Done Gate, PR #19) is the architectural fix for reach: an
Action comments on PRs in projects that never heard of this repo, drawing
visitors here. Numeric follow-on targets, in order: the Action on the GitHub
Marketplace, a pytest plugin entry point, a second worked example in a
non-code domain (issue #3), a French README (issue #1).

## Metrics loop

Collected once per marketing round and rendered into the launch packet by
`tools/launch_digest.py`:

- skills.sh install count (weekly);
- stars, forks, open issues;
- inbound referrers from the launch threads;
- one qualitative artefact: the best independently-written post or issue that
  round.

A round that moves none of these for two consecutive rounds is a signal to
change the asset, not to post more.

## Automation surfaces already in place

- `tools/launch_digest.py` — rebuilds the launch packet from repo facts.
- `.github/workflows/launch-digest.yml` — rebuilds the packet on every
  published release and on demand; result is an artifact, nothing is posted
  externally.
- `.claude/agents/wincreator-marketer.md` — the agent that runs the rounds:
  metrics first, then per-channel actions, never unapproved external posts.
