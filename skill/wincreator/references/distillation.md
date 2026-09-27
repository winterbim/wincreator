# Distillation gate

The distillation gate measures structural cost. It does **not** measure correctness,
design taste, security, or business value, and it never upgrades a claim to
EVIDENCED.

Its purpose is narrower: make avoidable code growth visible before an agent can
rationalize it away.

## Principle

A working implementation is only the first candidate.

When simplification matters, capture a structural snapshot before the change,
make the change, capture the result, then compare the two verified snapshots.

The output is a vector rather than a weighted score. WinCreator deliberately
does not invent a universal "code quality = 92/100" number.

Current signals:

- source file count;
- source bytes;
- non-blank source lines;
- largest source file by non-blank lines;
- files at or above 400 non-blank lines;
- repeated exact non-blank lines of at least 24 characters;
- recognized runtime dependency count;
- dependency-manifest count;
- manifests whose dependency structure requires human inspection.

The signals are intentionally mechanical. They are evidence for review, not a
substitute for architectural judgment.

## Commands

Capture the baseline:

```bash
python3 scripts/distill.py snapshot . --out .wincreator/distill-before.json
```

Capture the candidate:

```bash
python3 scripts/distill.py snapshot . --out .wincreator/distill-after.json
```

Compare a refactor:

```bash
python3 scripts/distill.py compare \
  .wincreator/distill-before.json \
  .wincreator/distill-after.json \
  --mode refactor \
  --out .wincreator/distill-report.json
```

Modes:

| Mode | Meaning |
|---|---|
| `audit` | report deltas; structural growth alone does not fail |
| `feature` | report deltas; new known runtime dependencies force REVIEW |
| `refactor` | any increase in guarded structural-cost signals forces REVIEW |

A `REVIEW` exit is not a rejection. It means the change grew structural cost
and the Skeptic must decide whether that growth is justified by the claim.

A `PASS` is even narrower: the configured structural rule did not detect a
regression. It says nothing about semantic correctness.

## Binding it to proof

For a consequential simplification claim, bind the report into the ordinary
WinCreator attestation rather than creating a parallel proof system:

```bash
python3 scripts/wincreator.py prove P-42 \
  --tier standard \
  --builder builder-01 \
  --file .wincreator/distill-report.json \
  -- pytest -q
```

The correctness gate remains the real test. The distillation report is an
attested input to the claim.

The Skeptic should reject claims such as "simpler", "leaner", or "same behavior
with less code" when the report is missing, unverifiable, or contradicted by the
functional gate.

## Rules

1. **Correctness outranks compactness.** Never delete a test, validation path,
   security control, error path, or required observability merely to improve the
   vector.
2. **No universal score.** Keep the raw dimensions visible.
3. **No dependency without review.** Known runtime dependency growth in feature
   mode requests REVIEW; unknown manifest formats are surfaced rather than
   guessed.
4. **No "optimal" claim.** The gate can show that candidate B is structurally
   smaller than candidate A under named signals. It cannot prove global
   optimality.
5. **Advisory can only tighten.** A clean distillation report cannot turn failed
   tests into success or turn insufficient evidence into EVIDENCED.
6. **Refactors pay rent.** If a refactor increases files, lines, large-file
   pressure, duplication, or dependency surface, it needs an explicit reason.
7. **Abstractions must compress.** New layers are justified by real reuse,
   isolation, policy, or change reduction—not by aesthetic preference.
8. **Do not add a Distiller agent.** This is deterministic evidence consumed by
   the existing Builder/Skeptic protocol.

## Limits

The duplicate-line signal is exact-text and language-agnostic; it is not clone
detection. Dependency extraction is exact for `package.json` runtime
`dependencies` and common `requirements*.txt` files. Other recognized
manifests are marked for human inspection instead of parsed heuristically.

Generated/vendor/build directories are excluded by default. Add project-specific
`--exclude` patterns when required and keep those exclusions stable between the
before and after snapshots.

The snapshot digest detects accidental or deliberate editing of the JSON after
capture. It is not a signature. If the artifact must survive an audit boundary,
bind it with `wincreator prove --file` so the existing attestation policy
covers it.
