# Changelog

All notable changes to WinCreator are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The package version lives in `skill/wincreator/VERSION`; official Skill
frontmatter intentionally contains only `name` and `description`. A tag or
release is authoritative only after it exists on GitHub. The v2 development
history remains available in Git and is not restated here.

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
- CI workflow (`.github/workflows/ledger.yml`) that runs the ledger gate
  on every push — the repository verifies its own `PROOF_LEDGER.md`.
- `Skill_WinCreator.skill` release asset for manual installation.

[3.0.0]: https://github.com/winterbim/wincreator/releases/tag/v3.0.0
[1.0.0]: https://github.com/winterbim/wincreator/releases/tag/v1.0.0
