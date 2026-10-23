# ADR 0003 — Approval keys stay outside the Builder

Status: accepted (2026-10-23) — key provisioning PARTIAL.

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

## Consequences

- G02 cannot claim a working approval flow until key custody is provisioned and
  proven; the current status is PARTIAL/BLOCKED.
- Automated CI may verify signatures but must never hold the signing key.
- A stolen key allows approving its own actions until the key is replaced; no
  revocation service exists in VEOR 0.4, so rotation is a pin/key change.
