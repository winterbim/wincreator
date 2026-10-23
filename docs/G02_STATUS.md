# G02 — Optional VEOR governance: PARTIAL / BLOCKED

Status: **PARTIAL implementation, BLOCKED claim.** No G02 claim is evidenced.
Contracts are staged under `contracts/g02/`; they are not registered in the
runtime and no proof exists for them.

## Implemented (code present, tests executed)

| Piece | File |
|---|---|
| Strict pin loader, checkout/Node/entrypoint checks, fail-closed status | `harness/governance.py` |
| Reproducible pin (commit, version, Node floor, sidecar entrypoint) | `tools/veor-pin.json` |
| Pin/checkout CLI, exit 3 while blocked, embedded self-test | `tools/veor_check.py` |
| JSON-lines decision client, malformed-response refusal | `harness.governance.Sidecar` |
| Receipt acceptance only via VEOR's verifier (exit 0 + ok + digest/signature) | `governance.verify_receipt` |
| Deterministic receipt↔capture binding | `governance.bind_result` |
| Status command | `python3 -m harness governance` |
| ADRs | `docs/adr/0001`–`0004` |
| Staged task contracts | `contracts/g02/G02-01..04.json` |
| Negative tests | `tests/test_governance.py` |

## Not implemented (deliberately)

- No VEOR source is vendored, cloned or installed by WinCreator.
- No approval key exists in this repository; key custody is unimplemented
  (ADR 0003).
- No MCP gateway integration, no sandboxed gates, no receipt→second-gate flow.
- No write path from governance to any ledger or proof record (ADR 0002).

## Blocking conditions (named, dated 2026-10-23)

1. **Independent Skeptic review** of H01, H03, H04, H05, H07 is outstanding. The
   earlier automatic verdicts were not converted into approvals.
2. **VEOR provisioning**: no checkout at the pinned commit is configured
   (`VEOR_HOME` absent); `python3 tools/veor_check.py` therefore exits 3.
3. **Approval key custody**: no isolated signer has been provisioned, so no
   governance approval can be claimed.

## Exit criteria for READY

- `python3 tools/veor_check.py` exits 0 against a checkout at the pinned commit,
  with Node >= 22.
- `tests/test_governance.py` green on Linux, macOS and Windows.
- H01/H03/H04/H05/H07 carry independent `EVIDENCED` reviews; G02-01..04 are then
  registered and captured through the runtime, not hand-written.
- Key custody demonstrated outside the Builder's reach.

Until then, `G02-01` stays `BLOCKED` in `PROOF_LEDGER-harness.md` and this file
is the honest status.
