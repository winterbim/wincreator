# Skeptic dossier — H04

Blind review input. It contains no Builder reasoning, no Builder identity and no
Builder conclusion: only the claim, the gate, the captured evidence and the raw
streams.

- Claim: a runtime killed mid-gate is recovered by resume with an abandoned attempt, a retry and a clean journal
- Gate: `python3 -m pytest -q tests/test_harness_crash.py`
- Level / tier: Meso / standard
- Capture: CAPTURED_PASS exit=0 (531 ms)
- Commit at capture: `1941d12958b287d093bfb55816cd1626458ac6e1`
- Working tree at capture: dirty=True — the only modified path was
  `PROOF_LEDGER-harness.md`, written by the capture itself
- Authoritative attestation (local, gitignored): `.wincreator/attestations/H04/20261023T215446.555345Z-459da777-f98f-47f3-bbf6-e83592cc0c8a/attestation.json`
- Attestation sha256: `4d18638226d8b95b32adc98e53f388bc90968d6c2f01bd4a70b78dafbf20c8e1`
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
python3 skill/wincreator/scripts/wincreator.py review H04 \
  --ledger PROOF_LEDGER-harness.md \
  --verdict <evidenced|insufficient|disproven> \
  --reviewer <independent-id> \
  --challenge "<the concrete attack actually performed>" \
  --challenge-packet skeptic/H04/packet.json
```

Alternatively, hand this directory to the `wincreator-skeptic` subagent as its
only input.
