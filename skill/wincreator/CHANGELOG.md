# Changelog — wincreator

Version line of the skill itself (distinct from the repository release line
in the root `CHANGELOG.md`). Semver: patch = clarification, minor = new
rule/defense, major = protocol change.

## [3.0.0] — 2026-08-02

Major: the skill stops asking an agent to *describe* its proof and starts
capturing it. Answers the external audit of 2026-08-02, whose central point
was that a hand-written Evidence cell is a narrative, not an audit trail.
The protocol change (four statuses → seven) is covered by that audit's
explicit waiver of the status invariant.

### Added
- **`scripts/wincreator.py prove <ID> -- <command>`** — runs the gate and
  writes the row from what happened: exit code, duration, sha256 of stdout /
  stderr / `--file` artifacts, git commit + branch + dirty flag + remote,
  platform, Python, hostname, CI marker, and a canonical sha256 digest of
  the whole payload, optionally HMAC-SHA256 signed via
  `WINCREATOR_SIGNING_KEY`. Exit code 0 → `EVIDENCED`, anything else →
  `DISPROVEN`; there is no flag to override the verdict.
- **`scripts/wincreator.py verify`** — re-hashes every attestation, log and
  artifact, and cross-checks the ledger: a tampered log, a forged field, a
  status hand-edited away from the captured verdict, or a rewritten captured
  sentence all fail. Appending notes after the captured sentence is allowed.
- **Three statuses**: `DISPROVEN` (the gate ran, the claim is false —
  blocking, like `CLAIMED`), `SUPERSEDED` (replaced by a named successor
  row), `BLOCKED` (a *named*, dated external dependency).
- **`scripts/package_check.py`** — gates the Agent Skills packaging itself
  (name lowercase-hyphenated and equal to the directory, description
  present, SKILL.md budget, no dangling reference, `agents/openai.yaml`
  complete). It is what caught `name: skill-wincreator` in a directory named
  `Skill_WinCreator`.
- **`agents/openai.yaml`** for OpenAI/Codex runtimes, and
  `references/attestation.md` documenting the attestation schema, signing,
  and what `verify` cannot catch.
- **Three tiers** (Lite / Standard / Regulated) so ceremony scales with
  stakes, plus a narrowed trigger description — the previous one fired on
  essentially any multi-step technical task.
- `ledger_check.py --strict-attestation`: every EVIDENCED/DISPROVEN row must
  cite a captured attestation (the Regulated tier).

### Changed
- **Per-status evidence rules instead of one shared marker.** The old
  `EXEC_MARKER` let a bare ISO date satisfy a `PENDING` row that was
  supposed to carry a command. Now: EVIDENCED/DISPROVEN need an execution
  trace (exit code, attestation digest, run URL, or a named command *with* a
  dated/raw result); PENDING needs a concrete command; WAIVED needs a date
  *and* the user's voice; SUPERSEDED a successor; BLOCKED a named blocker.
  `2026-08-02 test passed` is no longer accepted as proof of execution.
- Package renamed `Skill_WinCreator/` → `wincreator/` with
  `name: wincreator`, to satisfy the Agent Skills name/directory rule.
- `--self-test` grew from 20 to 36 cases; `wincreator.py` ships 26 of its
  own and `package_check.py` 6.

## [2.5.0] — 2026-07-11

Proposal EVO-005, from self-improvement cycle 3. A Two-Failure escalation:
the v2.4 orphan heuristic failed at the row level in both directions, so the
fix moved up to parser structure. The cycle-3 red-team found that v2.4's
EVO-004 had itself introduced a regression.

### Fixed
- **False positive (HIGH), regression from EVO-004**: a legitimate foreign
  table with a column named "Status" (roadmap/kanban/CI table) made a valid
  ledger FAIL — its rows were flagged as orphans, breaking the documented
  fix-B promise ("a ledger can live in a file containing other tables"). The
  parser now tracks table boundaries (header+separator): rows under a
  non-ledger header are ignored and never trigger the orphan check.
- **False negative**: a 5-cell orphan (a CLAIMED row whose empty Evidence
  column was omitted) escaped the audit. Orphan detection now needs only the
  status column (>=5 cells).
- **False positive**: a ledger example inside a ``` / ~~~ code fence was
  parsed as live rows — the checker even mis-parsed 3 "rows" out of its own
  spec doc's example block. Fenced blocks are now skipped.
- **`--catches` inconsistency**: a valid 3-column catches table read STALE
  (row check required >=4 cells while the header allowed >=2). Aligned to >=2.

### Known limit (documented, not silently passed)
- Ledger rows must use leading AND trailing pipes. A row missing an edge pipe
  is not recognized (parsing pipe-less lines would mis-read prose containing
  "|"). This is now stated in `references/proof-ledger.md` rather than being a
  silent trap. Deliberately not code-fixed: adding another positional
  heuristic is exactly what EVO-004 showed to be fragile.

### Added
- `--self-test` cases `foreign_status_col_not_orphan`, `orphan_5cell_caught`,
  `fenced_example_ignored`, `catches_3col_alive` (suite now 20 cases).

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
