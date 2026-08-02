# Captured attestations — what `wincreator prove` writes

A ledger row written by hand is a *story* about a proof. An attestation is
the proof's own record: produced by the process that ran the gate, before
anyone had the chance to describe it.

```
python3 scripts/wincreator.py prove P-014 -- pytest tests/test_export.py -q
python3 scripts/wincreator.py prove P-014 --file dist/report.ifc -- ./export.sh
python3 scripts/wincreator.py verify --ledger PROOF_LEDGER.md
python3 scripts/wincreator.py --self-test
```

## Layout

```
.wincreator/attestations/<CLAIM_ID>/<UTC timestamp>/
├── stdout.log          raw, untouched
├── stderr.log          raw, untouched
└── attestation.json    everything below, plus the digest of itself
```

## `attestation.json`

```json
{
  "schema": "wincreator.attestation/v1",
  "payload": {
    "claim_id": "P-014",
    "command": ["pytest", "tests/test_export.py", "-q"],
    "command_string": "pytest tests/test_export.py -q",
    "exit_code": 0,
    "verdict": "EVIDENCED",
    "started_at": "2026-08-02T08:44:02Z",
    "ended_at": "2026-08-02T08:44:09Z",
    "duration_ms": 7123,
    "stdout": {"path": "…/stdout.log", "sha256": "…", "bytes": 812, "tail": "14 passed"},
    "stderr": {"path": "…/stderr.log", "sha256": "…", "bytes": 0, "tail": ""},
    "files": [{"path": "dist/report.ifc", "sha256": "…", "bytes": 91233}],
    "git": {"commit": "…", "short": "0ba6a514e1f3", "branch": "main",
            "dirty": false, "remote": "https://github.com/…"},
    "environment": {"cwd": "/repo", "platform": "Linux-6.8…", "python": "3.12.3",
                    "hostname": "runner-7", "user": "ci", "ci": "github-actions"}
  },
  "digest": {"algorithm": "sha256", "canonicalization": "json/sorted-compact",
             "value": "…"},
  "signature": {"algorithm": "hmac-sha256", "value": "…", "key_id": "…"}
}
```

`verdict` is derived from `exit_code`, never chosen: `0` → `EVIDENCED`,
anything else → `DISPROVEN`. There is no flag to override it.

## Signing

Set `WINCREATOR_SIGNING_KEY` (CI secret, local keychain, whatever your
threat model needs) and every attestation carries an HMAC-SHA256 of its
canonical digest. `verify` checks the signature when the same key is
present, and reports the attestation as *unsigned* rather than valid when
it is missing one it should have.

HMAC proves the attestation was produced by someone holding the key; it is
not a public-key signature and not a transparency log. Whoever holds the
key can also forge one.

## What `verify` catches, and what it cannot

Catches: a rewritten `stdout.log`/`stderr.log`, a modified artifact, a
forged field inside `attestation.json`, a missing attestation referenced by
the ledger, a row whose status was hand-edited away from the captured
verdict, and a captured evidence sentence that was rewritten (appending
notes after it is allowed).

Cannot catch: deletion of the whole attestation directory followed by a
fresh run, a gate that tests the wrong thing, or a command that passes for
the wrong reason. The first is a retention problem — keep attestations as
CI artifacts, where the agent under review cannot rewrite them. The other
two are why the Skeptic role still exists.
