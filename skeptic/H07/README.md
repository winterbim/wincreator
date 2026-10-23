# Skeptic dossier — H07

Blind review input. It contains no Builder reasoning, no Builder identity and no
Builder conclusion: only the claim, the gate, the captured evidence and the raw
streams.

- Claim: the state machine rejects every undeclared transition, contracts are immutable once registered, and the journal detects edits to retained events and deletion of an event that has a successor
- Gate: `python3 -m pytest -q tests/test_harness_contracts.py tests/test_harness_store.py`
- Level / tier: Meso / standard
- Capture: CAPTURED_PASS exit=0 (875 ms)
- Commit at capture: `2f4eb4a72b32ab6afca4085a6f810a2accb914cc`
- Working tree at capture: dirty=True — the only modified path was
  `PROOF_LEDGER-harness.md`, written by the capture itself
- Authoritative attestation (local, gitignored): `.wincreator/attestations/H07/20261023T235259.836657Z-4a57d900-a484-4f69-9991-98d3719e539d/attestation.json`
- Attestation sha256: `c3a404ebc052b1661547bc1840a6bce47cdcbda186bd024e5b044d1a579c6460`
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
python3 skill/wincreator/scripts/wincreator.py review H07 \
  --ledger PROOF_LEDGER-harness.md \
  --verdict <evidenced|insufficient|disproven> \
  --reviewer <independent-id> \
  --challenge "<the concrete attack actually performed>" \
  --challenge-packet skeptic/H07/packet.json
```

Alternatively, hand this directory to the `wincreator-skeptic` subagent as its
only input.
