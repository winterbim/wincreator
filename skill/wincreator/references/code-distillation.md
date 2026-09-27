# Code distillation gate

This gate answers a narrow question: after an implementation already works, did
a cleanup reduce measured structural cost without hiding a regression?

It does not score "code quality", and it cannot prove that a solution is
globally minimal. Those claims are too broad to verify mechanically.

## Doctrine

Minimum sufficient structure beats minimum line count. A shorter program can be
worse if it becomes denser, more coupled or dependent on opaque machinery.

The distillation pass therefore keeps a vector of facts instead of collapsing
them into one score:

- source-file count;
- nonblank source lines;
- direct dependencies recognized from common manifests;
- exact repeated source fingerprints;
- largest source-file line count.

Source bytes and physical lines are also retained as context, but they do not
decide the verdict by themselves.

An abstraction must pay rent. A dependency must pay rent. A wrapper, adapter,
manager, provider or new layer is justified by behavior, reuse, isolation or a
real boundary — not by the fact that an agent knows the pattern.

## Standard workflow

First make the behavior work and prove the working candidate. Distillation is
not permission to redesign a failing feature.

Capture the working candidate, preferably scoped to the module being changed:

~~~
python3 scripts/distill_check.py snapshot \
  --root . \
  --scope src/export \
  --out .wincreator/distill-before.json
~~~

The command prints the baseline SHA-256. **Freeze that digest before editing
source.** For Standard/Regulated work, bind the baseline file to an ordinary
WinCreator capture (or another independently retained immutable record) before
the simplification starts. A digest stored only inside the mutable baseline JSON
is not authentication.

The helper has an explicit verification command suitable for that pre-change
capture:

~~~
python3 scripts/distill_check.py verify \
  --snapshot .wincreator/distill-before.json \
  --expect-digest <printed-baseline-sha256>
~~~

A baseline captured or re-created after seeing the comparison result is invalid.

Then simplify without changing the intended behavior. Remove avoidable
duplication, speculative abstractions, unused flexibility and dependencies that
do not buy enough value.

Compare the result:

~~~
python3 scripts/distill_check.py compare \
  --before .wincreator/distill-before.json \
  --baseline-digest <previously-frozen-baseline-sha256> \
  --root . \
  --out .wincreator/distill-report.json
~~~

The snapshot embeds the normalized policy and its SHA-256 digest. Compare
reuses that embedded policy and requires the separately retained baseline
digest. This catches a changed baseline only when that external digest was
actually frozen before the cleanup; WinCreator does not pretend an unkeyed hash
stored beside mutable data is an authentication boundary.

Finally rerun the real behavior gate and bind the structural artifacts into the
ordinary WinCreator attestation:

~~~
python3 scripts/wincreator.py prove P-014 \
  --tier standard \
  --builder builder-01 \
  --file .wincreator/distill-before.json \
  --file .wincreator/distill-report.json \
  -- pytest tests/test_export.py -q
~~~

The behavior gate remains authoritative for correctness. The structural report
is evidence about maintainability cost, not a substitute for tests.

## Verdicts

IMPROVED means at least one lower-is-better structural dimension fell and none
rose. It proves only that measured structural cost decreased under the embedded
policy.

UNCHANGED means the tracked vector did not move. It is not a failure and it is
not proof that no simpler design exists.

REVIEW_REQUIRED means a tracked dimension increased, a new dependency appeared,
or the scan produced a warning. Exit status is 1. A model may explain the
trade-off, but its explanation cannot downgrade the deterministic result. The
Skeptic or user must decide whether the regression is justified.

Malformed input, an escaping scope, or a tampered snapshot fails closed with
exit status 2.

## Why new dependencies are monotonic

Replacing one dependency with another can leave the dependency count unchanged.
That is still new authority and new maintenance surface. The report therefore
forces REVIEW_REQUIRED whenever a previously absent direct dependency appears,
even if another dependency was removed at the same time.

## Policy

A JSON policy may override only the documented scan controls:
source_extensions, exclude_dirs, exclude_globs, duplicate_window_lines and
duplicate_min_chars. Unknown policy keys are rejected.

The default scanner recognizes npm package.json dependencies, Python
requirements files and common project.dependencies arrays in pyproject.toml,
plus direct Cargo.toml and go.mod dependencies. When source scope is narrowed,
manifest discovery still walks the scope's ancestor directories up to the
declared root, so a root or package-level manifest is not silently dropped. This is intentionally a small
direct-dependency surface, not a package-manager replacement.

## Skeptic questions

For code-producing Standard or Regulated Meso+ work, the Skeptic should attack
at least these points:

1. Did the final behavior gate run after distillation, not only before it?
2. Did scope selection omit a part of the change that would make the report
   look artificially smaller?
3. Did a new abstraction or dependency appear, and what concrete problem pays
   for it?
4. Did duplication move rather than disappear?
5. If the report is IMPROVED, could readability, error handling or performance
   have regressed despite the structural gain?
6. If the report is UNCHANGED, is there an obvious wrapper, branch or duplicate
   rule that the mechanical vector cannot see?

## Limits

The scanner is deterministic evidence, not an oracle. It does not understand
domain semantics, prove readability, measure runtime performance, or establish
global optimality. Exact duplicated windows are intentionally conservative and
will miss semantic duplication written with different syntax.

This is why the gate is composed with WinCreator instead of replacing its
Builder/Skeptic protocol.

The design borrows one useful boundary from VEOR: deterministic evidence may
force more review, while probabilistic judgment may never silently weaken a
deterministic warning. The snapshot policy digest also follows the same idea as
binding an execution receipt to the policy that governed it.
