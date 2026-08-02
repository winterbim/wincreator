# WinCreator

WinCreator structures consequential engineering work as proof-gated loops.
It keeps claims in a Markdown ledger, captures the command that tested each
claim, and separates a mechanical command result from an independent review.

[![ci — default branch](https://github.com/winterbim/wincreator/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/winterbim/wincreator/actions/workflows/ci.yml?query=branch%3Amaster)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

The CI badge reports the default branch only. It is not evidence that an open
pull request is green; use that PR's checks for the PR state.

## What changed in v3

Earlier versions could validate a sentence about a proof. v3 captures the
process that ran the gate and binds it to the exact claim:

- exactly one installable Skill: `skill/wincreator/SKILL.md`;
- official frontmatter containing only `name` and `description`;
- current `agents/openai.yaml` interface metadata;
- `CAPTURED_PASS`, `CAPTURED_FAIL`, and `CAPTURE_ERROR` separated from
  `EVIDENCED`, `INSUFFICIENT`, and `DISPROVEN` review verdicts;
- claim ID, level, text, gate, row digest, and pre-capture ledger digest in
  every attestation;
- atomic, locked ledger writes and duplicate-ID rejection;
- mandatory `--file`, explicit `--optional-file`, collision-safe run IDs;
- clean-tree enforcement for Regulated captures;
- output redaction, size limits, body suppression, and private captures;
- deterministic `skill.zip` and byte-identical `wincreator.skill` packages;
- Linux, Windows, and macOS CI across Python 3.10–3.13.

The version is stored in `skill/wincreator/VERSION`, not in SKILL.md
frontmatter.

## Capture and review

Given a ledger row:

```markdown
| ID | Level | Claim | Gate (what proves it) | Status | Evidence |
|----|-------|-------|------------------------|--------|----------|
| P2 | Micro | parser rejects malformed input | `python3 check_parser.py` | CLAIMED | |
```

Capture the gate:

```bash
python3 skill/wincreator/scripts/wincreator.py prove P2 \
  --tier standard \
  --builder builder-01 \
  -- python3 check_parser.py
```

An exit code of zero produces `CAPTURED_PASS` but leaves the ledger row
`PENDING` until review. A non-zero exit produces `CAPTURED_FAIL` and records
`DISPROVEN`; the CLI returns the gate's non-zero code.

Review the capture:

```bash
python3 skill/wincreator/scripts/wincreator.py review P2 \
  --verdict evidenced \
  --reviewer skeptic-01
```

Verify capture logs, attested files, review linkage, ledger status, and the
unchanged claim/gate fields:

```bash
python3 skill/wincreator/scripts/wincreator.py verify \
  --ledger PROOF_LEDGER.md
```

Lite work may opt into `--tier lite --auto-approve-lite`. Standard and
Regulated work require a real review. In Regulated mode the working tree must
be clean and the reviewer must differ from the Builder. Standard captures
outside Git should pass source inputs with `--file`; otherwise the CLI warns
that no source snapshot is claim-bound.

## Sensitive data

stdout, stderr, file paths, the working directory, hostname, username, and
attested files may contain sensitive data. Apply controls before capture:

```bash
python3 skill/wincreator/scripts/wincreator.py prove P2 \
  --redact "$TOKEN" \
  --redact-regex 'password=[^ ]+' \
  --max-output-bytes 1048576 \
  --no-output-body \
  --private \
  -- python3 check_parser.py
```

Redaction happens before logs are written and hashes cover the retained,
redacted bytes. Attestations record original and retained byte counts. The
gate never inherits `WINCREATOR_SIGNING_KEY`; HMAC signing happens after it
exits.

HMAC makes modifications detectable to someone holding the key. It is not a
public signature or an independent transparency log, and a repository owner
who also holds the key can rewrite history. Sigstore, Rekor, in-toto and full
SLSA remain future work.

## Package validation

The internal policy checker deliberately makes only this claim:

```bash
python3 skill/wincreator/scripts/package_check.py skill/wincreator
# WINCREATOR PACKAGE POLICY: PASS
```

Official validation is separate:

```bash
python3 /path/to/openai-skills/skills/.system/skill-creator/scripts/quick_validate.py \
  skill/wincreator
npx --yes skills-ref@0.1.5 validate skill/wincreator
```

Build twice and compare the deterministic package:

```bash
./tools/build_package.sh dist/build-1
./tools/build_package.sh dist/build-2
sha256sum dist/build-1/skill.zip dist/build-2/skill.zip
```

Each output directory contains:

```text
skill.zip
skill.zip.sha256
wincreator.skill
wincreator.skill.sha256
```

`skill.zip` and `wincreator.skill` are byte-identical aliases. Their only
Skill entry is `wincreator/SKILL.md`, and the archive must remain below 25 MiB.

## Installation

These commands use only the v3 path and name. The GitHub release command is
appropriate after `v3.0.0` is actually published; until then, do not treat
`releases/latest` as proof of v3 availability.

### Git / Claude Code

```bash
git clone https://github.com/winterbim/wincreator.git
mkdir -p ~/.claude/skills
cp -r wincreator/skill/wincreator ~/.claude/skills/wincreator
python3 ~/.claude/skills/wincreator/scripts/ledger_check.py --self-test
python3 ~/.claude/skills/wincreator/scripts/wincreator.py --self-test
```

### npx skills

```bash
npx skills add winterbim/wincreator
```

After installation, confirm that exactly one discovered SKILL.md has
`name: wincreator` and that `VERSION` contains `3.0.0`.

### ChatGPT / manual package

Build or download `skill.zip`, then upload that file. It contains a single
root directory, `wincreator/`, and a single `SKILL.md`. The release asset is
not considered official until the v3 tag and GitHub release exist and its
checksum matches `skill.zip.sha256`.

### Safe migration from v1/v2

The migration tool backs up known old installations, removes only those known
directories, installs v3, runs the validators, and prints the active version:

```bash
python3 tools/migrate_v2_to_v3.py
```

The explicit manual equivalent is:

```bash
rm -rf ~/.claude/skills/Skill_WinCreator
rm -rf ~/.claude/skills/skill-wincreator
cp -r skill/wincreator ~/.claude/skills/wincreator
```

Prefer the migration tool when an old installation may contain user files.

## Development gates

```bash
python3 -m compileall -q skill/wincreator/scripts tools tests
python3 skill/wincreator/scripts/ledger_check.py --self-test
python3 skill/wincreator/scripts/wincreator.py --self-test
python3 skill/wincreator/scripts/package_check.py --self-test
python3 -m pytest -q
python3 skill/wincreator/scripts/package_check.py skill/wincreator
./tools/build_package.sh
```

CI runs these gates on Ubuntu, Windows, and macOS with Python 3.10, 3.11,
3.12, and 3.13, uploads a package from every matrix job, and runs the pinned
OpenAI Skill Creator validator plus the pinned Agent Skills reference
validator in a separate job.

## Publication status

The authoritative publication state is GitHub, not this paragraph:

- default branch: <https://github.com/winterbim/wincreator>;
- open PR checks: <https://github.com/winterbim/wincreator/pulls>;
- latest release: <https://github.com/winterbim/wincreator/releases/latest>.

Do not infer a v3 tag, release, assets, `latest` state, or successful public
installation from the source tree alone. Those claims are evidenced only
after the corresponding GitHub operations and clean-clone checks complete.

## License

MIT — see [LICENSE](LICENSE). Copyright Winter Fernandes.
