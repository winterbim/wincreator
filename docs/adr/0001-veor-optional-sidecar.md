# ADR 0001 — VEOR is an optional, pinned sidecar

Status: accepted (2026-10-23) — implementation PARTIAL, see `docs/G02_STATUS.md`.

## Context

VEOR provides deterministic ALLOW/REVIEW/DENY policy, Ed25519 grants and
one-shot approvals, signed execution receipts, an MCP gateway and OS sandbox
backends, all in Node.js (audited in `docs/VEOR_GUARDIAN_AUDIT.md`; 67/67 tests
on commit `87a6fb3`). WinCreator is Python, standard library only, and its
central promise is that it adds no dependency to the proof path.

Reimplementing VEOR in Python would create a second authority with its own
bugs, and would require shipping Ed25519 that the Python standard library does
not provide.

## Decision

- WinCreator consumes VEOR as an **optional sidecar**: a pinned checkout
  (`tools/veor-pin.json`) invoked over JSON-lines, or its offline receipt
  verifier CLI.
- The core package (`skill/wincreator`) and the runtime remain stdlib-only. No
  npm dependency is added, nothing is vendored, nothing is cloned implicitly.
- Every prerequisite failure (pin, checkout commit, package version, entrypoint,
  Node floor) yields **BLOCKED**, never a default allow.
- The pin is a commit SHA because VEOR is not published on npm (registry
  returned E404 on 2026-10-23) and `0.4.0-dev.6` is a developer preview.

## Consequences

- Governance is unavailable out of the box by design; that is visible
  (`python3 tools/veor_check.py` exits 3) instead of silently degraded.
- A user who wants governance provides `VEOR_HOME` with a checkout at the pinned
  commit and Node >= 22.
- Upgrading VEOR is a deliberate pin change plus a re-run of its test suite; it
  is not an `npm update`.
- The proof path never depends on VEOR: a missing sidecar cannot invalidate an
  attestation.
