# ADR 0002 — One proof authority, receipts bound by digest

Status: accepted (2026-10-23).

## Context

VEOR produces signed execution receipts and its own hash-chained JSONL ledger.
WinCreator produces attestations and a per-task event journal. Adopting both
ledgers would create two truths about the same effect, and a signed receipt can
be mistaken for proof of correctness when it only attests what crossed a
boundary (`verified` is `null` on VEOR's gateway path).

## Decision

- The **only** component that can mark a claim `EVIDENCED` is the WinCreator
  proof kernel and its reviewer. A VEOR decision or receipt is never evidence
  of a claim.
- The **only** event chain for runtime tasks is the SQLite journal. VEOR's
  ledger is used only when the VEOR gateway itself is deployed; it is not
  mirrored or merged here.
- A receipt is bound to a capture by a deterministic digest over
  `{attestation_digest, return_code, stdout_sha256, stderr_sha256}`
  (`harness.governance.bind_result`). The receipt carries the digest; the
  capture does not embed the receipt.
- A receipt is accepted only after VEOR's own offline verifier exits zero with
  `ok=true` and `digest`/`signature` checks true.

## Consequences

- Governance and proof remain orthogonal: "may this run?" and "is this proven?"
  are answered by different artifacts and different roles.
- Losing the VEOR ledger does not weaken a WinCreator proof; losing the capture
  invalidates the binding, as it should.
- A post-effect receipt cannot be bound by the kernel's pre-execution file
  hashing. Proving the receipt requires its own executed gate, never a sentence
  in an Evidence cell.
