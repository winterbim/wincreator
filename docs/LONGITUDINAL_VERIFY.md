# Longitudinal verification semantics

A claim can legitimately move through several proof attempts over time, for example:

```text
CAPTURED_PASS -> INSUFFICIENT -> CAPTURED_FAIL / DISPROVEN -> fix -> CAPTURED_PASS -> EVIDENCED
```

`wincreator.py verify --ledger ...` treats that as one evolving proof history:

- every historical attestation is still digest/signature/artifact checked;
- every historical review is still checked against the capture it reviewed;
- claim identity (ID, level, text, gate, row digest) must remain unchanged across the history;
- only the newest **applied** valid proof chain for a claim defines the ledger's current status and evidence;
- if that newest chain is `PENDING`, `DISPROVEN`, `INSUFFICIENT`, or `BLOCKED`, verification still fails;
- tampering with an older capture still fails verification even after a newer claim becomes `EVIDENCED`.

An applied chain is one that successfully won the atomic ledger state transition. Overlapping captures use a proof-state compare-and-swap; a stale capture is refused and its unapplied run directory is discarded rather than becoming ambiguous history. Verification also rejects a ledger that is manually rolled back to an older valid chain after a newer applied attempt.

This preserves negative attempts as audit evidence without allowing an earlier success to resurrect a claim after newer evidence changed its state.
