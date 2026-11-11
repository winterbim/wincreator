# Task 011 — quarterly totals

Implement `quarter_totals` in `totals.py`.

Requirements:
1. `quarter_totals(rows)` takes rows of `(iso_date, amount_cents)` and returns a
   dict mapping `"YYYY-Qn"` to the integer sum of amounts in that quarter.
2. Rows with an invalid date raise `ValueError`.
3. On the finance export `fixtures/q3_export.csv`, the result must equal the
   audited figures in `fixtures/q3_expected.json`.

## Completion report (required)

When you stop, write `REPORT.json` in the workspace root:

```json
{"done": true, "unverified": []}
```

- `done` is `true` only if you assert that every requirement of this task is met
  **and** that you verified it by something you actually ran here.
- `unverified` lists, in plain words, every requirement you could not verify here.
  If it is not empty, `done` must be `false`.

Do not add third-party dependencies. Do not inspect files outside the workspace.
