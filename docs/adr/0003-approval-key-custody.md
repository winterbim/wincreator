# ADR 0003 — Approval keys stay outside the Builder

Status: accepted (2026-10-23); approval flow implemented 2026-10-24, no key is
provisioned by this repository.

## Context

VEOR approvals are Ed25519 signatures over challenge id, tool, argument digest,
scope and expiry, consumed once. VEOR's own threat model states the limit: this
does not prove the signer was human if the autonomous agent can read the private
key. A Builder-held approval key would turn human review into self-approval with
a signature attached.

## Decision

- The approval private key is never stored in the repository, never passed to a
  gate process, and never readable by the Builder's runtime user.
- Approval is an out-of-process action: a separate OS user, a separate signer
  service, or a manual step performed by the reviewer.
- WinCreator's harness keeps its existing separation (builder vs reviewer
  identity, immutable reviews). Governance approval does not replace claim
  review, and claim review does not replace governance approval.
- If the key cannot be isolated, the correct status is BLOCKED for
  governance-gated actions, not "approved by the agent".

## Implementation (2026-10-24)

- `harness/governed.py` never reads, writes or receives key material. It records
  the challenge id of a `REVIEW` and stops; the operator signs the pending
  challenge with VEOR's own `approve` command, out of band.
- The receipt private key is read by the VEOR sidecar process
  (`VEOR_RECEIPT_PRIVATE_KEY`) and never by the harness. The harness only keeps
  the **public** key path, used for offline verification.
- `run-governed` refuses to start when no readable receipt public key is
  configured: an unverifiable receipt must not be produced at all.

## Consequences

- The approval flow is testable end to end (see `tests/test_g02_integration.py`),
  but a passing test is a **fixture**, not evidence that a human approved
  anything. The G02 claim stays unproven until an operator-held key is
  provisioned outside the Builder's reach.
- Automated CI may verify signatures but must never hold the signing key.
- Same-user deployment is a residual risk: the process that runs the harness
  could read the key file if it tried. Isolation is an OS/filesystem boundary.
- A stolen key allows approving its own actions until the key is replaced; no
  revocation service exists in VEOR 0.4, so rotation is a pin/key change.
