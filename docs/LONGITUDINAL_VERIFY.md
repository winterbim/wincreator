# Longitudinal verification semantics

A claim can legitimately move through several proof attempts over time, for example:

```text
CAPTURED_PASS -> INSUFFICIENT -> CAPTURED_FAIL / DISPROVEN -> fix -> CAPTURED_PASS -> EVIDENCED
```

`wincreator.py verify --ledger ...` treats that as one evolving proof history:

- every historical attestation is still digest/signature/artifact checked;
- every historical review is still checked against the capture it reviewed;
- claim identity (ID, level, text, gate, row digest) must remain unchanged across the history;
- only the newest valid proof chain for a claim defines the ledger's current status and evidence;
- if that newest chain is `PENDING`, `DISPROVEN`, `INSUFFICIENT`, or `BLOCKED`, verification still fails;
- tampering with an older capture still fails verification even after a newer claim becomes `EVIDENCED`.

This preserves negative attempts as audit evidence without requiring the current ledger row to pretend that an earlier state is still current.
