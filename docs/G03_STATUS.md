# G03 — Hardening, reproducibility, review inputs and benchmark: PARTIAL

Status: **five G03 workstreams implemented and exercised; none turns a claim
into `EVIDENCED`.** The G02 rows stay `PENDING`/`BLOCKED`, and no independent
Skeptic verdict was produced.

## What changed

| Workstream | Delivery | Gate |
|---|---|---|
| Verify drift | Only captures cited by a current ledger row are re-hashed against today's tree. Historical captures keep their document/signature integrity checks but are not failed for legitimate code drift. `verify --ledger` no longer rescans the whole attest dir. | `tests/test_wincreator_verify.py` |
| Reproducible VEOR provisioning | `tools/veor_provision.py` clones the pin's repository (or an operator mirror), checks out the exact commit, refuses dirty/wrong-version/non-empty destinations, installs the lockfile and can require VEOR's pinned test count. | `tools/veor_provision.py --self-test`, `tests/test_veor_provision.py` |
| Hardening | Private key material in the verification slot is refused (`RECEIPT_KEY_INVALID`); `Executor.run(governed=True)` without a receipt verifier is refused; `--require-sandbox` fails closed (`SANDBOX_UNAVAILABLE`); threat model written down. | `tests/test_governed.py`, ADR 0006 |
| Seven Skeptic dossiers | G02-05 and G02-06 dossiers added next to H01/H03/H04/H05/H07. No verdict, no Builder conclusion. | `skeptic/`, packets verified |
| ON/OFF benchmark | Explicit, sourced token-price schedule; cost recorded per run; real paired Codex smoke executed. | `bench/run_ablation.py`, `docs/BENCH_G03.md` |

## Executed evidence (2026-10-24, Linux, Node v24.21.0)

- `tools/veor_provision.py --self-test` → **5/5**.
- Full provisioning from the pinned mirror → commit
  `87a6fb35ae2203baf2af83abe0ab20cc05e2bb32`, version `0.4.0-dev.6`,
  `npm ci` succeeded, `node --test` → **67/67**, exit 0.
- `wincreator verify --ledger PROOF_LEDGER-harness.md` → **29 captures**
  integrity-checked; **no drift failures**; exit 1 only for the **7 PENDING**
  rows (a green gate is not a verdict).
- Full suite with `VEOR_HOME` set → **237 passed**; without it → **230 passed,
  7 skipped**.
- Real ON/OFF benchmark: 8 Codex runs, OFF 4/4 and ON 4/4, with duration,
  tokens and token-equivalent cost recorded in `docs/BENCH_G03.md`.

## Gate status

| Gate | Status | Why |
|---|---|---|
| G03-01 verify drift | **PASS** | current evidence still fails on drift; history preserved |
| G03-02 exact-commit provisioning | **PASS** | real pinned commit provisioned, installed and tested |
| G03-03 bypass/key/sandbox controls | **PASS** (implemented controls) | tests cover private key, missing verifier, sandbox refusal |
| G03-04 seven review dossiers | **PASS** (inputs ready) | seven blind packets; no verdict issued |
| G03-05 ON/OFF benchmark | **PARTIAL** | real 1-repetition smoke; the 3-repetition primary run is not executed |
| OS isolation | **BLOCKED** | no sandbox backend; `--require-sandbox` refuses |
| MCP gateway | **OUT OF SCOPE** | not wired into this repository; no protection claimed |

## Problems remaining

1. **No independent review.** H01, H03, H04, H05, H07, G02-05, G02-06 remain
   `PENDING`; G02-01 remains `BLOCKED`. This is the only reason `verify` fails.
2. **No OS isolation.** A same-user shell can run the same gate directly. A
   Python caller can fabricate a decision and a no-op verifier. ADR 0006 states
   both as open.
3. **MCP is not a governed surface** here: there is no MCP wiring to protect.
4. **Benchmark is a smoke.** One repetition, four cases, ceiling effect; no
   outcome benefit can be claimed. Cost is token-equivalent, not billed.
5. **Secret redaction for captured output is opt-in**, not enforced.
6. **Windows governed path with real VEOR** was not exercised locally; CI covers
   the non-VEOR runtime on Windows.

## Next action

Run an independent `wincreator-skeptic` over the seven dossiers, then record
verdicts. Schedule the 3-repetition benchmark before quoting any ON/OFF effect,
and treat `INSUFFICIENT` as blocking.
