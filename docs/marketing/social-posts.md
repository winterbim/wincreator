# Channel drafts — do not post without approval

All drafts must satisfy the honest-claims rules in
[`../marketing-plan.md`](../marketing-plan.md): the null result is disclosed,
no unproven benefit is implied, every post carries the install command.

## r/ClaudeAI

**Title:** I got tired of Claude Code telling me "done" when the tests were only adjacent to the claim — so I built a proof protocol for it

**Body:**

WinCreator forces the separation between "the command passed" and "the claim
is true". You write the claim in one sentence, it runs the real gate, captures
stdout/exit/timing into a tamper-evident attestation, and the status in the
ledger is written by a reviewer that isn't the builder — the reviewer is
allowed (and expected) to answer INSUFFICIENT when the green gate doesn't
actually cover the claim.

The published ablation so far found no measurable benefit against Haiku 5.5
on short tasks (both arms 33/33, +57% cost when ON) — that's in the repo, not
hidden. The bet is on long sessions and bigger repos, and that round is in
progress.

Zero-setup path:

```
npx skills add winterbim/wincreator
python3 "$WC/scripts/quick_prove.py" "parser rejects malformed input" -- python3 check_parser.py
```

Repo: https://github.com/winterbim/wincreator

## r/LocalLLaMA

**Title:** A stdlib-only proof ledger for local agent loops (the tool that measures whether your 70B actually finished the job)

**Body:**

Built for the case where the local model re-attacks the same failing check
five times and starts narrating success. WinCreator captures the actual gate
execution (exit, output, timing, git context) into a signed attestation, and
separates CAPTURED_PASS (the command worked) from EVIDENCED (the evidence
proves the claim). Two out of three local workflows I set it up against were
marking CLAIMED rows as done before this.

Works with any harness that can run a shell command — no API dependency, pure
Python stdlib. First published ablation (with a frontier model, admittedly)
was null at short task sizes and is published as measured; long-session cases
are the open target.

`npx skills add winterbim/wincreator` — https://github.com/winterbim/wincreator

## X / Twitter thread (5 posts)

1/ Your agent ran the tests green. Your agent said "done". Nobody checked
that the tests cover the claim. That gap is where most agent work quietly
fails — and it's the exact gap WinCreator closes.
https://github.com/winterbim/wincreator

2/ The mechanism is 4 steps: write the claim → run the real gate → capture
raw output into a signed attestation → let a separate reviewer decide
EVIDENCED or INSUFFICIENT. The reviewer can be an agent, but not the builder.

3/ It ships as a skill (~4.5k lines including its own self-tests), pure
stdlib, no dependencies. Three tiers: Lite is literally one command,
Standard adds the reviewer, Regulated adds attestations + identities.

4/ Full transparency: first ablation (66 runs, Claude Code + Haiku 5.5)
showed no measurable gain on short tasks — published as measured, 1.57×
overhead when ON. Weaker models, long sessions and big repos are the
unproven zone. Next round targets exactly that.

5/ If you've ever found a PR where the test proves a weaker claim than the
one in the commit message — that's the bug this is built for.
Install: npx skills add winterbim/wincreator

## LinkedIn (short form)

**Text:**

Most "agent finished the task" claims in the industry are unverified
narrations. WinCreator applies a CI mindset to agent claims: the claim is
bound to an executed command, the evidence is captured machine-readably, and
the pass/fail-on-the-claim decision belongs to a reviewer who didn't build
the thing. The first published benchmark result is honestly null — which is
exactly the standard of evidence the tool enforces, applied to itself.
MIT, stdlib-only: https://github.com/winterbim/wincreator
