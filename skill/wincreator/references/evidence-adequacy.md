# Evidence adequacy

A green gate proves that the command passed. It does **not** prove the gate is capable of detecting the fault class named by the claim.

For consequential Standard/Regulated code work, WinCreator can run a deterministic mutation adequacy check before accepting the final evidence.

## Manifest

Declare a small set of controlled, claim-relevant mutations:

```json
{
  "schema": "wincreator.adequacy-manifest/v1",
  "mutations": [
    {
      "id": "reject-boundary-regression",
      "path": "src/access.py",
      "find": "age >= 18",
      "replace": "age > 18"
    }
  ]
}
```

Each literal mutation is applied in an isolated temporary copy of the project. The real project is not edited.

## Run

```bash
python3 scripts/adequacy_check.py run \
  --root . \
  --manifest .wincreator/adequacy.json \
  --out .wincreator/adequacy-report.json \
  -- python3 -m pytest -q
```

The baseline gate must pass first.

For each declared mutation:

- **KILLED** — the gate failed after the seeded fault;
- **KILLED_TIMEOUT** — the seeded fault caused the gate to exceed the declared timeout;
- **SURVIVED** — the gate still passed;
- **INVALID** — the mutation could not be applied exactly as declared.

The report verdict is:

- **ADEQUATE** — every required mutation was killed;
- **INSUFFICIENT** — at least one required mutation survived;
- **ERROR** — the baseline was not green or a declared mutation was invalid.

An optional mutation may use `"required": false`; its survival is recorded but does not block the verdict.

## What this proves

An ADEQUATE result is narrow evidence that the declared gate can detect the declared seeded faults. It is **not** mutation-testing completeness, formal correctness, or proof that every possible bug is covered.

Choose mutations from the claim and observed failure modes, not from arbitrary syntax. A trivial mutation that any test kills adds little evidence.

Bind both the manifest and report to the final WinCreator capture with `--file`, then rerun the unmutated behavior gate. The mutation report supplements the real functional proof; it never replaces it.

## Integrity and limits

The report is canonicalized and SHA-256 bound and can be checked with:

```bash
python3 scripts/adequacy_check.py verify \
  --report .wincreator/adequacy-report.json
```

Mutation paths are confined to the copied project root. The tool uses a temporary filesystem copy, not an OS security sandbox. Tests may still invoke network services or external paths if the declared gate itself does so.

The mechanism is intentionally language-agnostic and stdlib-only. Projects that already use mature mutation frameworks such as Stryker, mutmut, PIT, cargo-mutants, or equivalent should keep them; WinCreator can bind their reports as evidence instead of duplicating their engines.
