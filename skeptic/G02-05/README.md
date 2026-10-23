# Skeptic dossier — G02-05

Blind review input. It contains no Builder reasoning, no Builder identity and no
Builder conclusion: only the claim, the gate, the captured evidence and the raw
streams.

- Claim: a governed run executes only under a verified ALLOW and a bound receipt
- Gate: `python3 -m pytest -q tests/test_governed.py`
- Level / tier: Meso / standard
- Capture: CAPTURED_PASS exit=0 (2381 ms)
- Commit at capture: `c4176711a8fc8562d814b55dc8fa8c8ba87d24bb`
- Working tree at capture: dirty=True — the only modified path was
  `PROOF_LEDGER-harness.md`, written by the capture itself
- Authoritative attestation (local, gitignored): `.wincreator/attestations/G02-05/20261023T235810.350719Z-a2a31698-bb47-47aa-ba2e-eacfd99d95c5/attestation.json`
- Attestation sha256: `6cf2561b6a4ec8e272ff3b6fec8a8bbf040ca7eff013a99e2d8441b4dd5ba9f1`
- Review schema expected: `wincreator.review/v3`

## Files

| File | Content |
|---|---|
| `packet.json` | blind-safe challenge packet, bound to the attestation digest |
| `stdout.log` | raw captured stdout (bounded by the kernel) |
| `stderr.log` | raw captured stderr (bounded by the kernel) |

## Questions to answer

1. Does the captured gate exercise the claim itself, or only a neighbouring
   property?
2. Name one concrete counterexample or evidence gap the gate would not catch.
3. Is any part of the claim true only because of a fixture, and if so is that
   stated in the claim?

## Recording a verdict

The reviewer writes the verdict; the Builder must not. `INSUFFICIENT` is a
blocking outcome and must not be softened into `PENDING`.

```bash
python3 skill/wincreator/scripts/wincreator.py review G02-05 \
  --ledger PROOF_LEDGER-harness.md \
  --verdict <evidenced|insufficient|disproven> \
  --reviewer <independent-id> \
  --challenge "<the concrete attack actually performed>" \
  --challenge-packet skeptic/G02-05/packet.json
```

Alternatively, hand this directory to the `wincreator-skeptic` subagent as its
only input.
