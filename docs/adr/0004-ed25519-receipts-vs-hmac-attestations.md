# ADR 0004 — Keep HMAC attestations, add Ed25519 only for governance receipts

Status: accepted (2026-10-23).

## Context

WinCreator attestations are SHA-256 digests optionally signed with
`WINCREATOR_SIGNING_KEY` (HMAC-SHA256). That is tamper evidence **for a key
holder**, not third-party authenticity: a verifier needs the same secret.
VEOR receipts are Ed25519 and verify offline against a public key.

Python's standard library has no Ed25519. Adding `cryptography` would make the
proof path depend on a third-party package, contradicting the project's
distribution model.

## Decision

- Existing attestation semantics are unchanged: SHA-256 digest plus optional
  HMAC. No new signing algorithm is introduced into the kernel.
- Governance receipts use VEOR's Ed25519 signer and verifier, invoked through
  the pinned sidecar.
- The two are linked by digest (`bind_result`), not by re-signing one with the
  other. Cross-language canonical JSON was measured byte-identical on
  2026-10-23, so digests are comparable.
- A future Ed25519 attestation signature is a separate decision and requires an
  explicit dependency or an out-of-process signer; it is not smuggled in now.

## Consequences

- HMAC remains the honest description: tamper evidence, not public
  attestation.
- Third-party verifiability of a **capture** is not claimed in this delivery;
  third-party verifiability of a **governance receipt** is, when the receipt
  public key is trusted.
- Verification tooling must keep both mechanisms distinct in output, so a valid
  receipt cannot be read as a valid capture signature.
