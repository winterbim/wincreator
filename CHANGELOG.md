# Changelog

All notable changes to WinCreator are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Repository releases and the skill version are the same number from v3.0.0
on: the frontmatter of `skill/wincreator/SKILL.md`,
`skill/wincreator/CHANGELOG.md`, this file, the git tag and the release
asset all say the same thing. Releases 2.0.0–2.5.0 existed only in the
skill's own changelog; they are listed there and are not restated here.

## [3.0.0] — 2026-08-02

Proof capture. WinCreator stops trusting the agent's account of a gate and
starts executing it: `wincreator prove` runs the command, captures the raw
output, hashes it, binds it to the commit and writes the ledger row itself.
Answers the external audit of 2026-08-02 point by point.

### Added
- `skill/wincreator/scripts/wincreator.py` — `prove` (capture: exit code,
  stdout/stderr sha256, artifact hashes, git commit/branch/dirty/remote,
  environment, canonical digest, optional HMAC-SHA256 signature) and
  `verify` (re-hash everything, cross-check the ledger). A failing gate is
  written `DISPROVEN`; `EVIDENCED` for a non-zero exit code is unreachable.
- `skill/wincreator/scripts/package_check.py` — validates the Agent Skills
  packaging in CI.
- `skill/wincreator/agents/openai.yaml` and
  `skill/wincreator/references/attestation.md`.
- Statuses `DISPROVEN`, `SUPERSEDED`, `BLOCKED`; `--strict-attestation`.
- `PROOF_LEDGER-v3-proof-capture.md` — the ledger of this release, with
  rows written by `wincreator prove` rather than by hand.

### Changed
- Skill package renamed `skill/Skill_WinCreator/` → `skill/wincreator/`
  (`name: wincreator`), matching the Agent Skills name/directory rule.
  Update any local install: `~/.claude/skills/wincreator`.
- Per-status evidence rules replace the single shared marker; a bare date
  or a bare URL no longer passes as an execution trace.
- CI (`.github/workflows/ledger.yml`) now compiles the scripts, runs all
  three self-tests and the package check *before* grading any ledger, then
  checks every ledger in the repo plus `--catches`.
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
