# Attestation and review records

Use capture for a mechanical result, then review for an epistemic verdict:

```bash
python3 scripts/wincreator.py prove P-014 \
  --tier standard --builder builder-01 \
  --file dist/report.ifc \
  -- pytest tests/test_export.py -q

python3 scripts/wincreator.py review P-014 \
  --verdict evidenced --reviewer skeptic-01

python3 scripts/wincreator.py verify --ledger PROOF_LEDGER.md
```

## Capture states

- `CAPTURED_PASS`: the process exited zero; Standard/Regulated remains
  `PENDING` until review.
- `CAPTURED_FAIL`: the process exited non-zero and the ledger becomes
  `DISPROVEN`; review can never turn it into `EVIDENCED`.
- `CAPTURE_ERROR`: the process could not be executed or timed out.

Review verdicts are `EVIDENCED`, `INSUFFICIENT`, or `DISPROVEN`. A review
records the capture digest, reviewer, timestamp, verdict, and a separate
canonical digest. Regulated mode rejects a reviewer whose identifier equals
the Builder identifier. `INSUFFICIENT` is written to the ledger as a distinct,
blocking status; it is never collapsed into the non-blocking `PENDING` state.
CI and tool-driven reviews must pass `--automatic`, which records
`automatic: true`; that marker is not a substitute for authenticated human
approval in the surrounding PR or compliance process.

## Canonical capture schema

`schemas/attestation-v1.schema.json` is authoritative. The top-level fields
are exactly:

```json
{
  "schema": "wincreator.attestation/v1",
  "payload": {
    "tool_version": "3.0.0",
    "claim": {
      "id": "P-014",
      "level": "Micro",
      "text": "export preserves every row",
      "gate": "pytest tests/test_export.py -q",
      "row_sha256": "...",
      "ledger_sha256_before": "...",
      "status_before": "CLAIMED"
    },
    "ledger": "PROOF_LEDGER.md",
    "builder": "builder-01",
    "command": ["pytest", "tests/test_export.py", "-q"],
    "command_string": "pytest tests/test_export.py -q",
    "capture": {
      "status": "CAPTURED_PASS",
      "exit_code": 0,
      "error": null
    },
    "started_at": "2026-08-02T10:00:00.000000Z",
    "finished_at": "2026-08-02T10:00:01.000000Z",
    "duration_ms": 1000,
    "stdout": {
      "path": ".wincreator/attestations/P-014/.../stdout.log",
      "sha256": "...",
      "original_bytes": 812,
      "stored_bytes": 812,
      "truncated": false,
      "body_stored": true,
      "tail": "14 passed"
    },
    "stderr": {
      "path": ".wincreator/attestations/P-014/.../stderr.log",
      "sha256": "...",
      "original_bytes": 0,
      "stored_bytes": 0,
      "truncated": false,
      "body_stored": true,
      "tail": ""
    },
    "files": [],
    "git": {
      "available": true,
      "commit": "...",
      "tree": "...",
      "branch": "main",
      "dirty": false,
      "remote": "https://github.com/winterbim/wincreator",
      "submodules": "",
      "untracked_digest": "..."
    },
    "environment": {
      "platform": "Linux-...",
      "python": "3.13.5",
      "hostname": "runner-7",
      "cwd": "/repo",
      "ci": "true",
      "user": "runner"
    },
    "policy": {
      "tier": "regulated",
      "dirty_override": false,
      "private": false,
      "redaction_literals": 0,
      "redaction_regexes": 0,
      "max_output_bytes": 1048576,
      "no_output_body": false
    }
  },
  "digest": {
    "algorithm": "sha256",
    "canonicalization": "json/sorted-compact/utf-8",
    "value": "..."
  },
  "signature": {
    "algorithm": "hmac-sha256",
    "key_id": "...",
    "value": "..."
  }
}
```

There is one name for each field: `finished_at`, `algorithm`, `hostname`,
`cwd`, `ci`, `user`, `tree`, and `canonicalization`. Do not use the obsolete
aliases `ended_at`, `alg`, or `node`.

## Git and file policy

Git context includes the commit, tree, branch, dirty state, remote, recursive
submodule status, and a digest of untracked paths/content. Regulated capture
fails closed unless Git inspection succeeds and the complete Git context is
unchanged before and after the command runs.

A path declared with `--file` is mandatory: if it is missing, capture stops
before the gate. Use `--optional-file` only when absence is allowed and must
be recorded.

Run directories use microseconds plus a UUID and are created exclusively, so
concurrent captures for one claim do not collide.

Stored stdout/stderr paths, the ledger name, and the review capture reference
are relative so an exported attestation bundle remains verifiable after it is
moved or downloaded. Retain the `attestations/` tree, ledger, and every declared
file at its recorded relative path inside the bundle.

## Output and privacy policy

Apply literal/regex redaction before persistence. Hash the retained bytes, not
the pre-redaction secret. Record both original and retained byte counts and
whether truncation occurred. `--no-output-body` writes empty log bodies while
retaining size metadata. `--private` writes under a private attestation root
and marks the policy; do not commit those records.

stdout, stderr, paths, hostname, username, working directory and evidence
files may contain sensitive data. Inspect the record before publishing it.

## Signing limits

The child gate environment never contains `WINCREATOR_SIGNING_KEY`. Signing
occurs only after the process exits. HMAC proves possession of a shared key and
makes later changes detectable to another key holder. It is not public,
independent proof: a repository owner who also holds the key can regenerate
history. Retained GitHub Actions artifacts reduce this risk but do not remove
it. Sigstore/Rekor, in-toto and full SLSA are intentionally future work.
