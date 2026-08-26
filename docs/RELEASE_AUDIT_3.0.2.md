# v3.0.2 release audit

This release was driven by an external-style packaged-skill trial rather than a source-only review.

The trial exercised a realistic proof lifecycle on one claim: a green but incomplete gate was reviewed `INSUFFICIENT`; a stronger gate exposed the defect and became `DISPROVEN`; after the pseudo-project was fixed, the same claim was re-captured and reviewed `EVIDENCED`.

The trial exposed a verifier defect: historical states were being compared to the current ledger row. v3.0.2 fixes that semantic error while keeping every historical capture/review integrity-checked. Regression tests cover the complete lifecycle, historical tampering, and the case where a newer unreviewed capture supersedes older evidence.

Release remains gated by the repository's full CI matrix, official skill validation, deterministic package checks, release attestation, and protected `ci-success` check before tagging/publishing.
