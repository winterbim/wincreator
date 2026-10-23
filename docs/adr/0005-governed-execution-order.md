# ADR 0005 — A governed task has one execution path

Status: accepted (2026-10-24).

## Context

Adding governance as an extra check next to the existing runtime creates the
classic bypass: the gate can still be executed through the old path, and the
decision becomes advisory. Two orderings also matter:

- decide **after** execution: the effect already happened, so `DENY` is theatre;
- receipt **before** the capture exists: the receipt cannot bind what ran.

## Decision

1. **Decide first.** VEOR is asked about the proposed effect (tool, contract
   digest, gate command) before the gate starts. `DENY`, `REVIEW` without a
   consumed one-shot approval, an unavailable sidecar, a timeout or a malformed
   answer ends the run with a journaled `governance_blocked` event. Nothing is
   executed, no attempt is opened.
2. **Bind the authorization into the capture.** The decision is written as
   `governance-decision.json` (no raw arguments, only `argsDigest`) and passed to
   the proof kernel as a hashed input, so the attestation commits to the
   authorization that preceded it.
3. **Sign after the capture.** VEOR signs a receipt binding the decision (tool,
   args digest, policy digest, ALLOW) to a digest of the capture (attestation
   digest, exit code, stdout/stderr hashes).
4. **Verify before trusting.** The receipt counts only after VEOR's own verifier
   exits zero with `ok=true`, digest and signature checks, and after every bound
   field matches both the decision artifact and the re-derived capture binding.
5. **One path.** Once a task has any `governance_*` event, the runtime refuses
   `run`, `retry` (without a fresh decision) and skips it in `resume` /
   `run_ready`. Re-execution requires `run-governed`, which always asks VEOR
   again and journals the new decision.
6. **Authority stays split** (ADR 0002). A verified receipt is journaled as
   `governance_bound`; it never writes a ledger status or a proof verdict.
7. **Optional by construction.** Tasks that never entered the governance path
   are untouched, and the ungoverned path never looks for Node.js.

## Consequences

- A governed retry needs a stated reason, so repeated execution is always
  visible in the journal rather than an implicit property of `resume`.
- `verify` re-runs the receipt verifier; a governed proof whose receipt is
  missing, tampered or bound to another capture fails verification.
- A same-user shell can still run the same commands outside the harness. This
  ADR governs the harness surface only; claiming more would be false.
- Governed gates are not sandboxed (see `docs/HARNESS_RUNTIME.md`), so the
  receipt proves the decision and the capture, not the isolation.
