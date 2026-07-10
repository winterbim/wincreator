# Worked example — a real session, not a fiction

This transcript comes from an actual session where the skill was applied to
a small but treacherous task. Nothing below is invented; the commands were
run and the outputs are quoted verbatim. It is included because the single
most instructive moment — the Skeptic catching a hole the Builder missed —
is exactly what the protocol exists to produce.

## The task

> "Write me a semver version comparator in Python (1.2.10 > 1.2.9, handle
> pre-releases)."

Treacherous because naive lexicographic comparison fails on `1.2.10` vs
`1.2.9`, and semver §11 pre-release ordering has several non-obvious rules.

## Step 1 — Classify and announce the gate

```
[LOOP] level=Micro weight=Construction task="semver comparator"
[GATE] executed test suite covering 1.2.10>1.2.9, equality,
       prerelease<release (§11), prerelease identifier ordering
[LEDGER] 0 rows yet
[NEXT] builder: RED — write the failing tests first
```

## Step 2 — RED (tests before implementation)

Tests written for: numeric-not-lexicographic, equality,
`1.0.0-alpha < 1.0.0`, `alpha < alpha.1 < beta`, and §11.4.3
(numeric identifiers < alphanumeric). Run before any implementation:

```
$ python3 -m pytest test_semver.py -q
ERROR test_semver.py  (No module named semver_cmp)
1 error in 0.09s
```

Failing as expected — RED confirmed.

## Step 3 — GREEN (minimal real implementation)

`semver_cmp.py` implemented: tuple comparison for the core,
identifier-by-identifier comparison for pre-releases per §11. Then:

```
$ python3 -m pytest test_semver.py -v
5 passed in 0.01s
```

## Step 4 — Skeptic pass (this is where it gets interesting)

No subagents were available in that session, so the honest degradation was
used — an explicit adversarial pass on the Builder's own claim:

> **Skeptic pass:** unexercised path found. The docstring promises
> `ValueError` on malformed input ("1.2", "abc") but **no test proves it**.
> The claim "comparator is correct" silently included input validation that
> was never verified. Verdict: INSUFFICIENT.

Note what happened: five green tests, an implementation that looked
complete, and the natural flow — "tests pass → done" — would have shipped
it. The gate stayed open instead.

## Step 5 — Iterate at the same level

A `pytest.raises(ValueError)` test was added for both malformed inputs:

```
$ python3 -m pytest test_semver.py -q
6 passed in 0.01s
```

## Step 6 — Ledger and mechanical gate

```markdown
| ID | Level | Claim | Gate (what proves it) | Status | Evidence |
|----|-------|-------|------------------------|--------|----------|
| P1 | Micro | numeric compare correct incl. 1.2.10>1.2.9 and prerelease §11 | pytest suite executed | EVIDENCED | run: pytest → 6 passed in 0.01s |
| P2 | Micro | malformed input raises ValueError | pytest.raises test executed | EVIDENCED | same run, test_malformed_raises PASSED |
```

```
$ python scripts/ledger_check.py PROOF_LEDGER.md
LEDGER CLEAN — 2 row(s) verified in PROOF_LEDGER.md
exit=0
```

## What to take from this

- The protocol added roughly two minutes of overhead to a ten-minute task.
- In exchange, it caught a real gap that green tests had hidden.
- The Skeptic verdict was not a formality: it changed the shipped code.
- The ledger means that six months later, anyone can see exactly what was
  proven, how, and that nothing was waived.

If the protocol ever feels like ceremony, re-read step 4. That moment is
the product.
