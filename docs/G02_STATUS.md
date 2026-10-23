# G02 — Optional VEOR governance: IMPLEMENTED, claim not yet evidenced

Status: **governed path implemented and exercised against the real pinned VEOR
checkout; no G02 claim is `EVIDENCED`.** Every G02 ledger row stays `PENDING`
(independent Skeptic review outstanding) or `BLOCKED` (G02-01).

## What is now implemented

| Piece | File |
|---|---|
| Strict pin loader, checkout/version/**dirty-state**/Node/entrypoint checks | `harness/governance.py` |
| JSON-lines decision client, malformed answer and timeout refusal | `harness/governance.py` |
| Receipt acceptance only through VEOR's own verifier | `harness/governance.py` |
| **Governed run**: decision → bound decision artifact → gate → signed receipt → offline verification → journal | `harness/governed.py` |
| **Single-path enforcement**: a governed task cannot be run, retried, resumed or swept ungoverned | `harness/runtime.py` |
| **Receipt re-verification inside `verify`** | `harness/runtime.py`, `harness/governed.py` |
| Private-key refusal, verifier requirement, fail-closed `--require-sandbox` | `harness/governed.py`, `harness/runtime.py` |
| CLI | `python3 -m harness run-governed`, `... verify --receipt-public-key` |
| Reproducible pin | `tools/veor-pin.json` (commit `87a6fb3`, package `0.4.0-dev.6`, Node ≥ 22) |
| Provisioning check + self-test (10 checks, incl. dirty checkout) | `tools/veor_check.py` |
| Gate wrapper that fails instead of skipping when VEOR is absent | `tools/veor_gate.py` |
| Hermetic adversarial suite (24 tests) | `tests/test_governed.py` |
| Real-VEOR integration suite (7 tests) | `tests/test_g02_integration.py` |
| ADRs | `docs/adr/0001`–`0005` |

## Executed evidence (2026-10-24, Linux, Node v24.21.0)

- Checkout: `VEOR_HOME=/tmp/veor-pinned` at `87a6fb35ae2203baf2af83abe0ab20cc05e2bb32`,
  `git status --porcelain` empty, `npm ls` resolved, `node --test` → **67/67 pass**.
- `python3 tools/veor_check.py` → `READY`, exit 0.
- `python3 tools/veor_check.py --self-test` → **10/10**.
- `python3 tools/veor_gate.py` (real sidecar, real Ed25519 keys) → **7/7 pass**.
- Full suite with `VEOR_HOME` set → **237 passed**; without it → 230 passed,
  7 skipped (the integration module skips rather than pretending).
- Fresh captures at `c417671` for H01, H03, H04, H05, H07, G02-05 and G02-06:
  all `CAPTURED_PASS`, exit 0. `ledger_check.py` reports `CLEAN`;
  `wincreator verify` reports **no drift on the cited rows** and fails only on
  the seven `PENDING` rows (a passing gate is not a verdict). Older captures
  retained on disk still show drift when inspected directly, which is expected
  for history and no longer a verification failure.
- What the integration suite actually proves:
  - `REVIEW` blocks execution, the challenge is journaled, nothing runs;
  - an operator-signed one-shot approval turns the same effect into `ALLOW`;
  - the approval is consumed exactly once and a restored approval is refused
    (`REPLAYED`);
  - the receipt verifies with VEOR's own CLI (exit 0, digest + signature);
  - a changed body → `DIGEST_MISMATCH`; a flipped signature byte →
    `BAD_SIGNATURE`; `harness verify` fails in both cases;
  - a **validly signed** receipt for a different capture (wrong `resultDigest`)
    is refused by the harness (`RESULT_DIGEST_MISMATCH`);
  - the decision artifact carries no raw arguments (no secret leakage into the
    governance artifacts), only `argsDigest`.
- What the hermetic suite proves about the refusals, including the paths added
  in this delivery:
  - a real sidecar **timeout** and a real **malformed** stdout line both end the
    run with `GOVERNANCE_UNAVAILABLE` journaled and no attempt started;
  - a checkout whose **HEAD still matches the pin but whose entrypoint was
    modified** is refused before the decision (`GOVERNANCE_BLOCKED`,
    `local modifications`) — HEAD alone is not treated as integrity.

## Deliberately not claimed

- **No OS isolation.** Governed gates run as plain child processes; the decision
  artifact and the journal record `sandbox.backend = none`, `os_enforced =
  false`. Windows behaviour is untested here (Linux only).
- **No key custody service.** The approval key is held by an operator; the
  receipt key is read by the VEOR process. The repository ships no key, and
  same-UID custody is a filesystem boundary only (ADR 0003).
- **No human approval.** The harness never signs; tests sign as a fixture.
- **No remote attestation.** A receipt proves the key holder decided and ran
  this args digest, not which checkout produced it.
- No MCP gateway wiring, no sandboxed gates, no bypass protection against a
  same-user shell.

## Blocking conditions (2026-10-24)

1. **Independent Skeptic review** of H01, H03, H04, H05, H07 — and of the new
   G02 rows — is outstanding. No verdict has been self-issued.
2. **Windows liveness/sandbox behaviour** never exercised in this environment.
3. `G02-01` remains `BLOCKED` in `PROOF_LEDGER-harness.md` for the review reason
   above; its VEOR provisioning blocker is now cleared.

## Next action

Run `wincreator-skeptic` on `skeptic/` (H01–H07) and on the G02 dossiers, then
record verdicts. A review verdict of `INSUFFICIENT` remains blocking.
