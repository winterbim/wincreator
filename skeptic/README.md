# Skeptic dossiers — harness runtime delivery

One directory per claim, regenerated at commit `3167651` so each dossier points
at the capture the ledger currently cites (they were first prepared at
`1941d12`). Each contains the claim, the exact gate, the challenge packet and
the raw captured streams. No verdict is pre-filled and no Builder conclusion is
included; `PROOF_LEDGER-harness.md` keeps all five claims at `PENDING`.

| Claim | Attestation sha256 | Packet digest |
|---|---|---|
| H01 | `8b017366ab8d3473…` | `892548a59b0072c3…` |
| H03 | `b130e7952a02ddfb…` | `8921edf33eecc011…` |
| H04 | `947fba424ba1440d…` | `b82091d338ad5a5e…` |
| H05 | `236a81cfe317c7fd…` | `0a2e18bb6c59ea33…` |
| H07 | `d44eee27e265edab…` | `b787df4f3215d52c…` |

H02 is `SUPERSEDED` by H07 (see the ledger), H06 is `PENDING` for lack of a
pinned VEOR checkout, and G02-01 is `BLOCKED` on this review plus provisioning.
