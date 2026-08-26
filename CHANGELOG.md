# Changelog

All notable changes to WinCreator are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The package version lives in `skill/wincreator/VERSION`; official Skill
frontmatter intentionally contains only `name` and `description`. A tag or
release is authoritative only after it exists on GitHub. The v2 development
history remains available in Git and is not restated here.

## [3.0.2] — 2026-08-26

Production-readiness close-out after an external-style end-to-end trial.

### Added
- `scripts/quick_prove.py`: zero-setup Lite/Standard entry point that creates a
  minimal private ledger and a collision-safe claim ID from one explicit claim
  plus one real gate command.
- Regression coverage for empty pre-created ledgers and for longitudinal proof
  histories containing `INSUFFICIENT`, `DISPROVEN`, and a later successful
  re-proof.

### Fixed
- `verify --ledger` now integrity-checks every historical capture/review while
  comparing the ledger's current status and evidence only with the newest proof
  chain for each claim. Earlier failed or insufficient attempts remain valid
  audit history instead of falsely contradicting a later `EVIDENCED` state.
- A pre-existing empty `.wincreator/PROOF_LEDGER.md` is initialized with the
  required table header instead of producing a malformed zero-setup ledger.

### Changed
- README and the short demo lead with the one-command proof path and make the
  green-command/insufficient-evidence distinction the central demonstration.

## [3.0.1] — 2026-08-25

Close-out after the 2026-08-25 audit: waiting is not a freeze, the live
retro-loop file is CI-gated, and operator surfaces match v3.

### Added
- SKILL.md: re-check `PENDING`/`BLOCKED` at Meso close; re-derive documentary
  claims at read time (EVO-008, catches 2026-08-02 and 2026-08-25).
- CI and `tools/run_release_gate.py` run `--catches` on the live
  `SKEPTIC_CATCHES.md`, not only self-test fixtures.
- `package_check.py` requires a semver `VERSION` file.

### Changed
- Tool `--version` reads `skill/wincreator/VERSION` instead of a hardcoded
  string.
- Surgeon, `CLAUDE.md`, and `CONTRIBUTING.md` aligned on 8 statuses, the
  `VERSION` file, and the 24 000-character SKILL.md budget.
- README no longer freezes a release tag or a version numeral in install copy.

## [3.0.0] — 2026-08-02

Claim-bound capture and independent review. `wincreator prove` executes a
gate and records `CAPTURED_*`; `wincreator review` separately decides whether
the result is `EVIDENCED`, `INSUFFICIENT`, or `DISPROVEN`.

### Added
- `wincreator.py prove/review/verify`: exact claim/gate binding, review
  attestations, signing-key isolation, clean-tree Regulated policy, atomic
  ledger updates, duplicate rejection, collision-safe captures, redaction,
  output limits, private mode, and fail-closed declared evidence files.
- `schemas/attestation-v1.schema.json`, external pytest suite, and safe v2→v3
  migration tool.
- Deterministic `skill.zip` plus byte-identical `wincreator.skill`.
- 12-job Ubuntu/Windows/macOS × Python 3.10–3.13 test matrix and pinned
  official Skill validators.
- `skill/wincreator/agents/openai.yaml` and
  `skill/wincreator/references/attestation.md`.
- Statuses `DISPROVEN`, `SUPERSEDED`, `BLOCKED`; `--strict-attestation`.
- `PROOF_LEDGER-v3-proof-capture.md` — separates locally observed results
  from GitHub publication claims that remain PENDING/BLOCKED until observed.

### Changed
- Skill package renamed `skill/Skill_WinCreator/` → `skill/wincreator/`
  (`name: wincreator`), matching the Agent Skills name/directory rule.
  Update any local install: `~/.claude/skills/wincreator`.
- Per-status evidence rules replace the single shared marker; a bare date
  or a bare URL no longer passes as an execution trace.
- CI moved to `.github/workflows/ci.yml`; `.github/workflows/release.yml`
  binds the tag commit to `GITHUB_SHA` before publishing assets.
- README: the obsolete "91 lines" claim is gone, the demo outputs are real
  v3 runs, installation paths updated, license/attribution wording aligned
  with MIT (attribution is a request, not an added condition).

## [1.0.0] — 2026-07-10

First public release.

### Added
- `Skill_WinCreator` skill (renamed `wincreator` in v3.0.0): hierarchical engineering loops
  (Macro / Meso / Micro / Nano) with proof gates.
- Proof Ledger format and the stdlib-only `ledger_check.py` mechanical
  gate (exits non-zero on any unproven claim).
- Builder / Skeptic role separation (defense against optimism leak) and
  copy-paste role prompts in `references/agents.md`.
- Loop Panel (defense against context rot) and the Two-Failure Rule
  (defense against stuck loops).
- Worked example (`references/worked-example.md`): a real semver-comparator
  session where the Skeptic caught an unverified `ValueError` path.
- Domain-adaptable proof checklist and a loop-ticket template.
