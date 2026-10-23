# Skeptic dossier — H04

Blind review input. It contains no Builder reasoning, no Builder identity and no
Builder conclusion: only the claim, the gate, the captured evidence and the raw
streams.

- Claim: a runtime killed mid-gate is recovered by resume with an abandoned attempt, a retry and a clean journal
- Gate: `python3 -m pytest -q tests/test_harness_crash.py`
- Level / tier: Meso / standard
- Capture: CAPTURED_PASS exit=0 (522 ms)
- Commit at capture: `2f4eb4a72b32ab6afca4085a6f810a2accb914cc`
- Working tree at capture: dirty=True — the only modified path was
  `PROOF_LEDGER-harness.md`, written by the capture itself
- Authoritative attestation (local, gitignored): `.wincreator/attestations/H04/20261023T235259.213956Z-2ea3ac79-8327-4f05-9b4a-ce0b5ff6350c/attestation.json`
- Attestation sha256: `aa3ead4771a85d0ea6d65a6bdfc523dbac088641ba9db64f5f4736a4be77b284`
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
