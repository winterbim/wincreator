# Changelog — skill-wincreator

Version line of the skill itself (distinct from the repository release line
in the root `CHANGELOG.md`). Semver: patch = clarification, minor = new
rule/defense, major = protocol change.

## [2.4.0] — 2026-07-11

Proposal EVO-004, from self-improvement cycle 2 (a red-team audit of v2.3.0).

### Fixed
- Orphan ledger row → false negative (HIGH). A row detached from its table
  by a blank line (or a header typo) was silently skipped, so a `CLAIMED`
  row below a blank line read `LEDGER CLEAN`, exit 0 — a real ledger a user
  might write when grouping rows visually. Now a row that carries a valid
  ledger status in column 5 but sits outside any recognized table is flagged.
  The blank-line-ends-table rule (which isolates foreign tables — fix B) is
  preserved; foreign tables never carry a ledger status in column 5, proven
  by the `foreign_6col_not_orphan` self-test.

### Added
- `--self-test` cases `orphan_ledger_row_caught`, `foreign_6col_not_orphan`
  (suite now 16 cases).

Source catch (SKEPTIC_CATCHES.md, 2026-07-11): "ligne ledger orpheline après
ligne vide, silencieusement ignorée".

## [2.3.0] — 2026-07-11

Proposal EVO-003, produced by the evolution circuit applied to v2.1.0 (a
red-team audit of the verifier itself).

### Fixed
- `--catches` is now schema-gated like the ledger parser: only rows under a
  real catches header (`Date | Class(e)…`) are counted. A foreign table with
  an ISO date in column 0 no longer reads as `CATCHES ALIVE`. This is the v2
  fix B hardening finally carried to the newer surface — the exact recurring
  "a verifier shipped without being verified" meta-class (lineage of EVO-001).
- `_strip_emphasis` now also handles `~~strike~~`, and is applied only to the
  Status token (not every cell), so Evidence ending in a backtick-wrapped
  command keeps its execution marker. (This corrected a regression the
  `--self-test` caught during the v2.2 work — the gate defended itself.)

### Added
- `--self-test` case `catches_foreign_table_stale`.

## [2.2.0] — 2026-07-11

Proposal EVO-002, from the same red-team audit. Two HIGH false-negatives.

### Fixed
- The spec's per-status evidence rules are now enforced symmetrically. v1/v2
  enforced the "must contain" rule only for EVIDENCED; a vague **PENDING**
  (no command) or **WAIVED** (no date) passed as `LEDGER CLEAN`, exit 0, on a
  ledger the spec's own Status-semantics section defines as invalid. PENDING
  now requires a command marker, WAIVED requires an ISO date.

### Added
- `--self-test` cases `pending_no_command_caught`,
  `pending_with_command_still_ok`, `waived_no_date_caught`,
  `waived_with_date_ok` (suite now 14 cases). Guards against over-rejection:
  the spec's own valid PENDING/WAIVED examples stay CLEAN.

Source catches (SKEPTIC_CATCHES.md, 2026-07-11): "enforcement asymétrique
spec↔outil (PENDING)" and "(WAIVED)".

## [2.1.0] — 2026-07-11

Produced by the auto-evolution circuit itself (proposal EVO-001 in
`EVOLUTION_QUEUE.md`, Skill-Surgeon under full gate), proving the loop runs
end to end rather than being merely installed.

### Added
- `scripts/ledger_check.py --catches [FILE]`: makes the retro-loop
  machine-checkable. Exits non-zero if `SKEPTIC_CATCHES.md` holds no
  well-formed dated catch (retro-loop not being fed). Stateless proxy for
  "the file exists and grows", honestly limited: it proves the loop is fed,
  not that the catches are insightful.
- Two new `--self-test` cases (`catches_alive_ok`, `catches_stale_caught`) —
  the suite now runs 9/9, covering the new feature.

Source catches (generalized meta-class "a verifier shipped without being
verified", 3 occurrences 2026-07-11): see EVO-001.

## [2.0.0] — 2026-07-11

Self-improvement pass: the skill was applied to itself (Meso/Construction,
gates announced, Builder/Skeptic, final mechanical gate exit=0). Every change
below was born from a real adversarial test whose raw output is cited in
`HANDOFF-wincreator-v2.md`.

### Fixed (scripts/ledger_check.py — the only executable artifact)
- Escaped pipes `\|` inside cells no longer break cell splitting. v1 choked
  on the very escaping `references/proof-ledger.md` requires — a doc↔tool
  contradiction.
- Only tables whose header matches the ledger schema are parsed; a foreign
  markdown table in the same file (e.g. a README) no longer false-positives.
- Markdown emphasis around a status (`**EVIDENCED**`) is tolerated.
- EVIDENCED rows now require an execution marker (command, ISO date, path,
  output fragment, exit code) — prose alone ("ça marche bien") is rejected.
  Honestly limited: it does not judge truthfulness, only rejects bare prose.

### Added
- `--self-test`: an embedded adversarial suite (7 cases) that replays the
  bugs which broke v1. The verifier now carries its own proof.
- Doctrine: **Retro Loop** (`SKEPTIC_CATCHES.md` capitalises every catch and
  feeds the next loop's gate), **named-attack rule** (a Skeptic pass with no
  named attack is void), **WAIVED** count mandatory in the Loop Panel,
  `[AUDIT]` trace line after a Two-Failure audit, and protocol steps 9–10
  (self-test on install; catch → one line before closing the loop).

[2.0.0]: https://github.com/winterbim/wincreator
