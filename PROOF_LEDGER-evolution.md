# Proof Ledger — WinCreator self-improvement cycles (loop-until-dry)

The skill applied to its own improvement. Each cycle: red-team the executable
verifier → capitalize real catches → gated surgery → independent Skeptic →
ship. Loop stops when a red-team audit finds no defect warranting surgery.

## Cycle 1 — v2.1.0 → v2.3.0 (EVO-002, EVO-003)

| ID | Level | Claim | Gate (what proves it) | Status | Evidence |
|----|-------|-------|------------------------|--------|----------|
| C1-1 | Meso | red-team of v2.1.0 found 3 real reproduced defects (not nits) | independent adversarial audit executing attack files | EVIDENCED | run 2026-07-11: BUG1 PENDING-no-command `LEDGER CLEAN` exit 0; BUG2 WAIVED-no-date exit 0; BUG3 `--catches` foreign table `CATCHES ALIVE` exit 0 — all spec-invalid yet passing |
| C1-2 | Micro | EVO-002 enforces PENDING command + WAIVED date symmetrically | the 3 attack files now fail; spec-valid controls stay clean | EVIDENCED | run 2026-07-11: b1/b2 -> exit 1 with `PENDING but no command marker` / `WAIVED but no date`; ctrl_valid PENDING+WAIVED -> exit 0 |
| C1-3 | Micro | EVO-003 schema-gates `--catches` | foreign table STALE, real catches ALIVE; header-flip differential | EVIDENCED | run 2026-07-11: `--catches` foreign `| Date | Event |` -> STALE exit 1; renaming col1 Event->Classe -> ALIVE exit 0 (Skeptic differential); real SKEPTIC_CATCHES.md -> ALIVE 6, exit 0 |
| C1-4 | Micro | the self-test caught a regression in the patch before ship | first GREEN run failed 2 cases; fixed; re-ran | EVIDENCED | run 2026-07-11: initial `self-test: 12/14` (FAIL pending_with_command) — `_clean` stripped trailing backtick; fixed via `_strip_emphasis` on status only; re-run `self-test: 14/14 passed` exit 0 |
| C1-5 | Meso | no CI regression, no over-rejection, no new doc↔tool gap | independent Skeptic re-executed everything | EVIDENCED | run 2026-07-11: Skeptic PASS 5/5 — PROOF_LEDGER.md 18 rows CLEAN exit 0, install ledger I12 PENDING still accepted, proof-ledger.md now documents all enforced rules, version 2.3.0 |

## Cycle 2 — v2.3.0 → v2.4.0 (EVO-004)

| ID | Level | Claim | Gate (what proves it) | Status | Evidence |
|----|-------|-------|------------------------|--------|----------|
| C2-1 | Micro | red-team of v2.3.0 found a real HIGH false negative (orphan CLAIMED after blank line) | reproduced independently before acting | EVIDENCED | run 2026-07-11: `c1_orphan.md` (CLAIMED after blank line) -> `LEDGER CLEAN` exit 0; identical row w/o blank line -> exit 1 |
| C2-2 | Micro | EVO-004 flags orphan ledger-like rows without breaking fix B | orphan caught; foreign tables still ignored | EVIDENCED | run 2026-07-11: orphan -> exit 1 "ledger-like row OUTSIDE any ledger table"; `foreign_6col_not_orphan` self-test clean; README-like 2-col table -> ledger row CLEAN exit 0 |
| C2-3 | Micro | no regression on the pre-existing ledgers | re-run the other ledgers + catches + self-test (this file excluded to avoid a self-referential claim) | EVIDENCED | run 2026-07-11: PROOF_LEDGER.md CLEAN 18 rows exit 0; PROOF_LEDGER-v2-install.md exit 0; --catches SKEPTIC_CATCHES.md ALIVE exit 0; --self-test 16/16 exit 0 |
| C2-4 | Meso | change independently verified | Skeptic re-executes from scratch, incl. pre-fix/fix differential | EVIDENCED | run 2026-07-11: independent Skeptic verdict PASS 5/5 — pre-fix HEAD reproduced the orphan CLEAN exit 0, v2.4 flags it exit 1; status-vs-column differential proves the check keys on the status; 16/16; version 2.4.0; also caught a self-referential over-claim in this ledger's own C2-3 (now fixed) |
