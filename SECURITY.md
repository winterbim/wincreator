# Security policy

## Reporting a vulnerability

Report vulnerabilities privately through
[GitHub security advisories](https://github.com/winterbim/wincreator/security/advisories/new).
Please do not open a public issue for a suspected vulnerability.

Include the affected script and version (`skill/wincreator/VERSION`), the exact
command or input, and the raw result. A minimal reproduction is the most
useful evidence.

## Supported versions

Fixes are made on the default branch and shipped in the next release. Only the
latest release is supported.

## What counts

In scope, for example:

- a way to obtain `EVIDENCED` for a claim without a passing captured gate;
- a way for a Builder to review their own Standard or Regulated capture;
- evidence, review or challenge-packet tampering that `verify` accepts;
- the gate process reading `WINCREATOR_SIGNING_KEY`;
- path escape in capture, adequacy or distillation tooling;
- secrets retained despite a redaction rule that should have matched.

## Known boundaries, not vulnerabilities

These are documented design limits:

- WinCreator is not a sandbox. Gates run as ordinary child processes with the
  caller's permissions.
- HMAC signing is tamper evidence for a key holder, not a public signature.
- Anyone who can rewrite both the ledger and every attestation it references,
  and recompute their digests, can forge a history. Use Git history, CI
  retention and release provenance for that threat.
- The Done Gate stop hook is a forcing function for visibility. It can be
  disabled by the user and passed after one honest report.
