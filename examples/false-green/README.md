# False green — a passing gate that proves nothing

The shortest honest demonstration of what WinCreator is for. No install, no LLM,
no dependency:

```bash
python3 examples/false-green/run_demo.py
```

<!-- demo:false-green:start -->
```text
CLAIM   a refund never exceeds what was paid

$ python3 check_weak.py
2 checks passed   (exit 0)
        green. This is where an agent says "done".

seed the bug the claim is about:  min(requested, paid)  ->  requested
$ python3 check_weak.py            # against the broken code
2 checks passed   (exit 0)
        still green: the fault SURVIVED.

VERDICT INSUFFICIENT
        the gate passed, but it cannot detect the failure it is cited against.

$ python3 check_strong.py          # one added check, same broken code
AssertionError: refund exceeded the amount paid   (exit 1)
        red: the fault is KILLED.

VERDICT ADEQUATE
        now a green run of this gate is evidence for the claim.
```
<!-- demo:false-green:end -->

## What is in this folder

| File | Role |
|---|---|
| [`refund.py`](refund.py) | the code under claim: a refund is capped at the amount paid |
| [`check_weak.py`](check_weak.py) | a plausible gate that is green and never exercises the cap |
| [`check_strong.py`](check_strong.py) | the same gate plus the one case the claim is about |
| [`adequacy.json`](adequacy.json) | the seeded fault: remove the cap |
| [`run_demo.py`](run_demo.py) | runs the shipped Evidence Adequacy Gate on both and prints the result |

## Why it matters

`check_weak.py` is the kind of test an agent writes, runs, and then cites as
proof. It passes. It would also pass if the cap were deleted, so its green
result carries no information about the claim. The adequacy gate makes that
visible mechanically: it copies the project, seeds the declared fault, reruns
the gate, and returns `INSUFFICIENT` when the fault survives.

Run the gate yourself on the weak check:

```bash
cd examples/false-green
python3 ../../skill/wincreator/scripts/adequacy_check.py run \
  --root . --manifest adequacy.json --out /tmp/adequacy-report.json \
  -- python3 check_weak.py
```

It exits non-zero with `ADEQUACY: INSUFFICIENT`. Replace `check_weak.py` with
`check_strong.py` and it exits zero with `ADEQUACY: ADEQUATE`.

## Limits

One seeded fault is narrow evidence, not mutation-testing completeness. The
fault must come from the claim, not from arbitrary syntax. See
[`references/evidence-adequacy.md`](../../skill/wincreator/references/evidence-adequacy.md).
