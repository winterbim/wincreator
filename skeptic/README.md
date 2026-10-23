# Skeptic dossiers — harness runtime delivery

Seven directories, one per claim under review, regenerated at commit `2f4eb4a`
so each dossier points at the capture the ledger currently cites (they were
first prepared at `1941d12`). Each contains the claim, the exact gate, the
challenge packet and the raw captured streams. No verdict is pre-filled and no
Builder conclusion is included; `PROOF_LEDGER-harness.md` keeps all seven claims
at `PENDING`.

| Claim | Attestation sha256 | Packet digest |
|---|---|---|
| H01 | `7a94e8f6cad368c5…` | `cd23a9cf7174c6ed…` |
| H03 | `652440b4681f4ca8…` | `4d62a59a22a7ffe5…` |
| H04 | `aa3ead4771a85d0e…` | `15c106c7427ce6ad…` |
| H05 | `84ec43de92bf6a0e…` | `592963a55cf7af66…` |
| H07 | `c3a404ebc052b166…` | `a45cfc5ae5847bb0…` |
| G02-05 | `b45159dc263961ad…` | `844dd718a5ef5ee9…` |
| G02-06 | `18974ed3d9a9a7b2…` | `5d89864da6ea265d…` |

H02 is `SUPERSEDED` by H07 (see the ledger), H06 is `PENDING` because its gate
is not reproducible from this repository without an external checkout, and
G02-01 is `BLOCKED` on this review. An independent reviewer must still write
every verdict.
