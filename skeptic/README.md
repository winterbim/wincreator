# Skeptic dossiers — harness runtime delivery

One directory per claim, prepared at commit `1941d12` for blind review.
Each contains the claim, the exact gate, the challenge packet and the raw
captured streams. No verdict is pre-filled and no Builder conclusion is
included; `PROOF_LEDGER-harness.md` keeps all five claims at `PENDING`.

| Claim | Attestation sha256 | Packet digest |
|---|---|---|
| H01 | `94ca95bb44526998…` | `704236eb94d563c5…` |
| H03 | `8dbbc6b3f4953880…` | `283c8bbc337bff35…` |
| H04 | `4d18638226d8b95b…` | `15b500e7c748c031…` |
| H05 | `ecfce0b9dde9fe3a…` | `b9450dfc8451aafd…` |
| H07 | `9b61cf04c06a84d8…` | `51401d82da5e50e7…` |

H02 is `SUPERSEDED` by H07 (see the ledger), H06 is `PENDING` for lack of a
pinned VEOR checkout, and G02-01 is `BLOCKED` on this review plus provisioning.
