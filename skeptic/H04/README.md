# Skeptic dossier — H04

Blind review input. It contains no Builder reasoning, no Builder identity and no
Builder conclusion: only the claim, the gate, the captured evidence and the raw
streams.

- Claim: a runtime killed mid-gate is recovered by resume with an abandoned attempt, a retry and a clean journal
- Gate: `python3 -m pytest -q tests/test_harness_crash.py`
- Level / tier: Meso / standard
- Capture: CAPTURED_PASS exit=0 (514 ms)
- Commit at capture: `3167651472a639decf49ac17b835b21395e044e9`
- Working tree at capture: dirty=True — the only modified path was
  `PROOF_LEDGER-harness.md`, written by the capture itself
- Authoritative attestation (local, gitignored): `.wincreator/attestations/H04/20261023T232447.023240Z-21e913cf-ae16-4c92-abbf-952437e8a983/attestation.json`
- Attestation sha256: `947fba424ba1440d9971b2fb3a16748a4d2cc05a36598c6b2b818c289fbd0f3c`
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
