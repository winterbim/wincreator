# State-of-the-art audit — AI coding quality, proof and complexity control

**Snapshot date:** 2026-09-27  
**Scope:** public repositories, public documentation and recent software-engineering research relevant to AI-assisted coding, deterministic verification, maintainability/complexity control, agent governance and cryptographic provenance.

This document is deliberately a **dated search result, not a universal uniqueness claim**.
A public project may exist outside the surveyed set, appear later, or implement an
undocumented capability. The falsifier is simple: identify one project that demonstrably
combines the capability set listed under "WinCreator target combination".

## Research question

Can a coding workflow do all of the following at once without collapsing into a large
agent platform?

1. keep intent explicit across long work;
2. freeze evidence before implementation where practical;
3. separate "command passed" from "claim is proven";
4. keep Builder and reviewer roles distinct;
5. retain replayable historical evidence;
6. stop repeated failed loops and force level escalation;
7. detect unrequested/scope-creep work;
8. measure structural growth rather than trust code-quality prose;
9. resist metric gaming by binding the measurement policy/baseline;
10. strengthen broad test claims beyond coverage;
11. remain useful without an LLM;
12. publish independently verifiable release provenance;
13. stay agent/IDE/language agnostic rather than becoming another coding agent.

## Closest public systems surveyed

### GitHub Spec Kit
Source: https://github.com/github/spec-kit

Strongest observed capability: intent lifecycle. Spec Kit carries specification → plan →
tasks → implementation → convergence, and convergence explicitly detects missing,
partial, contradicting and **unrequested** implementation.

Observed boundary relative to this audit: it is primarily a specification/process harness.
Its convergence is semantic/agent-driven rather than a claim-bound raw-evidence ledger,
and it does not itself provide WinCreator-style captured command attestations,
Builder/Skeptic proof status separation, or structural before/after distillation.

### AgentForge
Source: https://github.com/SwayamDesai/AgentForge

This is the closest coding-agent architecture found in the survey. Its documented flow
includes a pre-implementation failing acceptance test, minimal patching, deterministic
checks, advisory review, container testing, bounded repairs, execution budgets and an
auditable result. It also freezes the authored test digest.

AgentForge is substantially broader than WinCreator: it is an agent runtime/platform with
LangGraph orchestration, databases, retrieval, model routing, sandboxing, approvals,
telemetry and execution infrastructure. That is a strength for autonomous execution, but
a different product boundary.

WinCreator's target distinction is portability and proof protocol: no required model,
database, sandbox, LangGraph runtime or provider; the same protocol can sit around Codex,
Claude Code, Cursor, Copilot, a shell script, BIM tooling, or a human engineer.

### Iterative Planner
Source: https://github.com/NikolasMarkou/iterative-planner

Strong on long-session context preservation, explicit state transitions, independent
verification/adversarial roles and complexity budgets. Its documented budget includes
limits on new files/abstractions and a net-neutral/negative line-count target.

Observed boundary: planning/state discipline is stronger than raw proof capture. The
survey did not find a claim-bound execution attestation + immutable evidence-review chain
equivalent to WinCreator's capture/review/verify path.

### Aider
Source: https://github.com/Aider-AI/aider

Strong coding interface with Git integration, automatic linting/testing and an
architect/editor mode.

Observed boundary: it executes useful checks but is not primarily an epistemic proof
protocol. A green command is not independently classified against an explicit claim in a
retained proof ledger.

### Qlty
Source: https://github.com/qltysh/qlty

Strongest surveyed general static-quality tool: linting, formatting, security,
maintainability, coverage, complexity and duplication across many languages.

Observed boundary: it measures code quality; it does not govern AI-session reasoning,
claim/evidence separation, acceptance-oracle immutability, reviewer independence or
agent loop escalation.

### propcheck-ai
Source: https://github.com/mauricioTechDev/propcheck-ai

Interesting narrow complement: enforces property-based-testing discipline for coding
agents and verifies PBT workflow compliance.

Observed boundary: deliberately specialized to property-based testing rather than a
general engineering proof protocol.

### in-toto / GitHub artifact attestations / Sigstore
Sources:
- https://github.com/in-toto/attestation
- https://github.com/actions/attest
- https://github.com/sigstore/rekor

Strongest provenance layer in the survey. These systems provide authenticated metadata,
SLSA/in-toto provenance, keyless Sigstore signing and transparency-backed verification.

Observed boundary: provenance proves where/how an artifact was produced; it does not by
itself prove that a test meaningfully establishes a software claim. WinCreator therefore
uses provenance **in addition to**, not instead of, semantic proof review.

### Attestly / TRACE / Agentegrity
Sources:
- https://github.com/inertialabsxyz/attestly
- https://github.com/agentrust-io/trace-spec
- https://github.com/Cogensec/agentegrity

These projects are strong evidence that signed, portable agent-run attestations are
becoming a serious category. Attestly signs agent work and supports independent
verification; TRACE specifies portable runtime evidence; Agentegrity combines local
evaluation with signed attestation chains.

Observed boundary: their center of gravity is agent execution/integrity/governance, not
minimal software implementation plus behavior-preserving structural distillation.

### Delimit
Source: https://github.com/delimit-ai/delimit-action

A strong specialized merge gate: detects API/schema breaking changes and emits signed,
replayable Sigstore attestations.

Observed boundary: narrower domain (API compatibility) rather than a general
claim/evidence/minimality workflow.

### Cognitive Deadlift / similar workflow skills
Source: https://github.com/alinafe82/cognitive-deadlift

Strong ideas around complexity budgets, diff interrogation, assumptions and resisting
autopilot.

Observed boundary: repository rules and review artifacts are validated, but the project
itself states that it does not judge whether a model behaved well. WinCreator's target is
to bind claims to actually captured gates and then independently review that binding.

## WinCreator target combination

The target is **not** "more agents". It is the smallest portable layer that composes the
strong ideas above:

| Capability | WinCreator target |
|---|---|
| Intent persistence | Loop Panel + claim/gate ledger |
| Pre-implementation oracle | RED-lock: failed acceptance capture + attested test file |
| Raw execution evidence | captured stdout/stderr/exit/timing/environment/Git/files |
| Claim vs execution separation | CAPTURED_* is distinct from EVIDENCED/INSUFFICIENT/DISPROVEN |
| Independent review | Builder/Skeptic identity separation |
| Historical evidence | immutable capture/review history + longitudinal verification |
| Stuck-loop control | Two-Failure Rule with level escalation |
| Scope economy | final required/supporting/unrequested diff review |
| Anti-bloat | policy-bound Structural Distillation Gate |
| Metric-gaming resistance | externally frozen baseline digest + embedded scan-policy digest |
| Dependency safety | parsed narrow formats; unknown manifest change fails closed to review |
| Strong-test guidance | mutation/property/metamorphic/differential/fuzz when claim scope requires it |
| LLM independence | capture/verify/distillation remain deterministic/offline |
| Release provenance | GitHub/Sigstore artifact attestations in release workflow |
| Portability | skill/protocol wraps existing agents instead of replacing them |

## Current survey conclusion

**No single surveyed public repository was observed to combine the complete target
combination above.**

That sentence is intentionally narrower than "nothing in the world does this". The
closest system by end-to-end coding lifecycle is AgentForge; the strongest intent layer
is Spec Kit; the strongest general static-quality layer is Qlty; the strongest provenance
family is in-toto/Sigstore; specialized projects such as propcheck-ai are stronger on
individual verification techniques.

The architectural opportunity for WinCreator is therefore the **composition boundary**:
make those concerns cooperate without turning WinCreator into a large autonomous-agent
runtime.

## What this research changed in the implementation

The audit produced concrete changes instead of marketing copy:

1. **RED lock** was added after finding AgentForge's frozen acceptance-test digest model.
   WinCreator reuses its existing file-attestation/history verification instead of adding
   a second test-lock subsystem.
2. **Intent convergence** was added after studying Spec Kit's explicit
   `unrequested` finding class.
3. **Negative-space verification** guidance now rejects raw coverage as sufficient for
   broad claims and points to mutation/property/differential/fuzz evidence.
4. **Public Sigstore-backed release provenance** was added via GitHub
   `actions/attest`, while keeping semantic proof separate from supply-chain
   provenance.
5. **Manifest parser scope was reduced**, not expanded, after adversarial review found
   repeated grammar edge cases. Unknown complex manifests are content-fingerprinted and
   a change forces review. This removed a fragile parser class instead of accumulating
   syntax patches.

## Research support for the problem statement

Recent work supports treating maintainability as a first-class AI-coding problem:

- Zhu, Tsantalis & Rigby, *AI-Generated Smells: An Analysis of Code and Architecture in
  LLM and Agent-Driven Development* (2026):
  https://arxiv.org/abs/2605.02741
- Sun, Ståhl, Sandahl & Kessler, *Quality assurance of LLM-generated code: Addressing
  non-functional quality characteristics* (Journal of Systems and Software, 2026):
  https://doi.org/10.1016/j.jss.2026.112885
- Moradi Dakhel et al., *Effective Test Generation Using Pre-trained Large Language
  Models and Mutation Testing* (2023):
  https://arxiv.org/abs/2308.16557

The common implication is important: functional correctness alone does not establish
maintainability, and coverage alone is not a strong defect-detection oracle.

## Falsification and maintenance rule

This document becomes stale by design. Re-run the survey before making a public
"unique", "first", or "best" claim.

A competing project falsifies the current differentiation claim if it can demonstrate,
in one coherent public system, the full target combination above with executable
evidence—not only prompt instructions or marketing prose.

When that happens, update this document and improve WinCreator or narrow the claim.
