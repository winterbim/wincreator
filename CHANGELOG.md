# Changelog

All notable changes to WinCreator are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-07-10

First public release.

### Added
- `Skill_WinCreator` skill: hierarchical engineering loops
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

[1.0.0]: https://github.com/winterbim/wincreator/releases/tag/v1.0.0
