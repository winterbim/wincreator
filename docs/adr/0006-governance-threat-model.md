# ADR 0006 — What the governed surface protects, and what it does not

Status: accepted (2026-10-24).

## Context

G02 claims a governed execution path, not a security boundary against the user
who runs it. Without a written threat model, two opposite mistakes are easy:
treating a signed receipt as proof of isolation, or treating a known bypass as a
reason to claim nothing. This ADR fixes the protected surface, the vectors that
are actually closed, and the ones that remain open.

## Protected surface

The governed surface is:

- `python3 -m harness run-governed` (and `harness.governed.run`);
- `Executor.run(..., governed=True)` **only** when a capture verifier is
  supplied, which is how the governed path invokes it.

Everything outside that surface — a shell, an editor, an agent invoking the same
gate command directly, an MCP server not wired through the harness — is outside
the claim. The harness cannot see it and does not pretend to.

## Vectors and their status

| Vector | Control | Status |
|---|---|---|
| Gate runs before a decision | decision artifact written and bound into the capture before the kernel runs | closed |
| `DENY` / unapproved `REVIEW` | no attempt is opened, `governance_blocked` journaled | closed |
| Sidecar timeout, malformed answer, dead process | `GOVERNANCE_UNAVAILABLE` journaled, no attempt | closed |
| Modified VEOR checkout with the correct HEAD | clean-tree check plus commit/version/entrypoint; `tools/veor_provision.py` provisions the exact commit | closed for the harness path |
| Retry after a governed run | a stated retry reason and a fresh decision are required | closed at the API |
| Resume / run_ready after a crash | governed tasks are skipped, never re-run ungoverned | closed at the API |
| Receipt replay on another capture | receipt binds `resultDigest` to the attestation, exit code and output hashes | closed |
| Approval replay | VEOR consumes the one-shot approval; a restored challenge is refused | closed (proven against real VEOR) |
| Wrong signature / edited receipt | VEOR's own verifier must exit 0 with digest + signature checks | closed |
| Private key in the verification slot | refused before the sidecar starts (`RECEIPT_KEY_INVALID`) | closed |
| Secret in governance artifacts | only `argsDigest` is stored, never the raw arguments | closed for those artifacts |
| Secret in captured stdout/stderr | kernel redaction flags exist; they are opt-in | **partial** |
| `governed=True` without a verifier | refused (`capture verifier` required) | closed at the API |
| A caller that fabricates a valid-looking decision and a no-op verifier | no privilege boundary inside one Python process | **open** (same-user) |
| MCP gateway | not wired in this repository | **out of scope, no claim** |
| OS isolation | none; gates are plain child processes. `--require-sandbox` refuses instead of pretending | **open, fail-closed switch** |
| Remote attestation / revocation | none | **out of scope, no claim** |

## Decision

1. The harness refuses known bypasses at its own API even when the caller is
   trusted: a governed run needs a verifier, a cited decision and a receipt.
2. Key material is validated before use. A private key in the public-key slot
   is a custody error, not a verification input.
3. Isolation is not simulated. `--require-sandbox` (or
   `WINCREATOR_REQUIRE_SANDBOX=1`) makes a protected run `BLOCKED` with
   `SANDBOX_UNAVAILABLE` until a real backend exists.
4. Claims stay scoped: a receipt proves the key holder decided and ran this args
   digest; it does not prove which checkout produced it, that the gate was
   correct, or that the process was isolated.

## Consequences

- A security review can point at this table and see which rows are enforced by
  tests and which are explicit non-claims.
- Operators who need isolation get a refusal, not a false sense of safety.
- A same-user attacker can still edit the store or call internals. Preventing
  that requires an OS/VM boundary (or a separate privileged service), which is
  a later gate and is not claimed here.
