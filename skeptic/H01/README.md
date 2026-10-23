# Skeptic dossier — H01

Blind review input. It contains no Builder reasoning, no Builder identity and no
Builder conclusion: only the claim, the gate, the captured evidence and the raw
streams.

- Claim: the G00 audit re-derives the repository baseline and every reference gate it executes passes
- Gate: `python3 -m harness audit --out .harness-artifacts/g00-audit-final.json --quiet`
- Level / tier: Meso / standard
- Capture: CAPTURED_PASS exit=0 (13542 ms)
- Commit at capture: `2f4eb4a72b32ab6afca4085a6f810a2accb914cc`
- Working tree at capture: dirty=False — the only modified path was
  `PROOF_LEDGER-harness.md`, written by the capture itself
- Authoritative attestation (local, gitignored): `.wincreator/attestations/H01/20261023T235243.059351Z-cc6db694-4b7f-4a83-9037-ff655c6b39bc/attestation.json`
- Attestation sha256: `7a94e8f6cad368c5bb8b6670883d6a6a5332aa649f5c1e296fc8bfaa93db1cd9`
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
python3 skill/wincreator/scripts/wincreator.py review H01 \
  --ledger PROOF_LEDGER-harness.md \
  --verdict <evidenced|insufficient|disproven> \
  --reviewer <independent-id> \
  --challenge "<the concrete attack actually performed>" \
  --challenge-packet skeptic/H01/packet.json
```

Alternatively, hand this directory to the `wincreator-skeptic` subagent as its
only input.
