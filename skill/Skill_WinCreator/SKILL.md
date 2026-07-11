---
name: skill-wincreator
version: 2.4.0
description: >-
  Turns any non-trivial engineering task, in any language, stack, or domain
  (backend, frontend, data, infra, hardware, BIM, ops, anything), into a
  hierarchy of verification-gated loops with an auditable Proof Ledger,
  builder/skeptic role separation, and a re-emitted loop state panel that
  survives long sessions. Use whenever the user asks to plan, build, refactor,
  debug, audit, or ship anything technical, whenever they mention "loop
  engineering", "structure this work", "organise cette boucle", "hiérarchise
  ce travail", or whenever a task has more than one step and truth/reliability
  matters more than speed of ideation. Domain-agnostic by design; never
  assumes a specific tech stack. Prefer this over generic brainstorming skills
  when the goal is convergence on a verified, working result rather than
  divergent idea generation.
---

# WinCreator — Hierarchical Engineering Loops with Proof Gates

## Why this skill exists

Every agent-assisted engineering session degrades the same three ways, and
knowing them is the key to using this skill well:

1. **Optimism leak** — the same context that wrote the code grades its own
   work, and "it should work" quietly becomes "it works".
2. **Context rot** — constraints stated early get lost as the session grows;
   the agent drifts from the original need without noticing.
3. **Stuck loops** — a failing check gets re-attacked at the same level again
   and again, when the real defect lives one level up.

This skill counters each one mechanically, not aspirationally: optimism leak
→ Proof Ledger + Builder/Skeptic separation; context rot → the Loop Panel;
stuck loops → the Two-Failure Rule. Everything else in this file exists to
serve those three defenses.

> **Evidence > Assertion. Truth > Speed. Rigor > Improvisation.**

A brainstorming loop diverges: ideas, no obligation of proof. An
**engineering loop** converges: it only reports up after passing a verifiable
**truth gate** — a test actually run, an output actually inspected, a
measurement actually taken. Nothing unproven propagates upward.

The skill is deliberately domain-agnostic: no language, no framework, no
stack assumed. The rigor is structural; the developer (or Claude) translates
each proof criterion into the concrete gesture of their actual domain.

## When NOT to apply the full hierarchy

This skill exists to avoid two opposite failures: improvisation without
proof, and bureaucracy that slows work without adding reliability. Skip the
level/gate/ledger ceremony entirely for:

- **A trivial single-step change** (rename, typo, config value): just do it,
  with a quick check if a tool allows it.
- **A purely explanatory request** ("how does X work?"): answer normally —
  nothing is built, nothing needs execution proof.
- **Pure exploration** where nothing is decided yet: stay in the lightweight
  Exploration mode below.

The signal for the full machinery: the task builds, fixes, ships, or audits
something whose reliability matters, with multiple steps or multiple
plausible ways to go wrong.

## Composition with other skills

This skill does not replace specialized skills (debugging, testing strategy,
code review). It provides the temporal skeleton — which level, which gate,
when to report up — inside which those skills operate. When a specialized
skill covers the technical execution, use it for the execution; keep this one
for the structure and the no-upward-propagation rule.

## The 4 loop levels

Classify the task before starting. Never work "flat".

| Level | Scope | Guiding question |
|---|---|---|
| **Macro** | Architecture, structural choice, project doctrine | "Is this the right foundation, and can we live with the consequences?" |
| **Meso** | A complete module or feature | "Does this meet the real need, end to end, with no gaps?" |
| **Micro** | One atomic unit of work (function, endpoint, component, query) | "Does this do exactly what it claims, concretely proven?" |
| **Nano** | One targeted adjustment | "Compiles/passes/breaks nothing, verified right now?" |

## Loop weight: rigor proportional to stakes

Before choosing a gate, classify the weight:

- **Exploration** — still comparing options, nothing decided. No heavy gate:
  list real options with their real trade-offs; no frozen decision, no formal
  document.
- **Decision** — ready to commit and build on it. Only here does the full
  Macro gate apply.
- **Construction** — the implementation itself (Meso/Micro/Nano): a gate is
  always required, proportional to real criticality.

If ambiguous, one line: "still exploring, or building on a chosen
direction?" — a sentence, not a form.

## The Loop Panel (defense against context rot)

For any Meso+ task, maintain a compact state block and **re-emit it at every
gate event** (gate announced, gate passed, gate failed, level change). Like a
cockpit instrument panel or a surgical checklist, its value is repetition:
the current truth survives even when session memory degrades or context gets
compacted.

```
[LOOP] level=Meso weight=Construction task="FM export module"
[GATE] full-dataset run + diff vs 3 reference cases
[LEDGER] 2 EVIDENCED / 1 PENDING / 0 CLAIMED / 1 WAIVED
[NEXT] builder: implement error path for missing lots
```

Four lines, never more (a fifth `[AUDIT]` line appears only after a
Two-Failure level audit — see below). WAIVED count is mandatory: waived
debt that leaves the panel becomes invisible debt. If you notice the panel contradicting what you were
about to do, the panel wins — that contradiction IS the context rot being
caught.

### Loop gates

**Macro (Decision mode)** — output: a short written decision, constraints,
owned negative consequences, rollback criterion.
- [ ] Real alternatives listed, not one option disguised as a choice
- [ ] Negative consequences explicitly written, not only benefits
- [ ] Consistent with constraints already in place, or justified exception
- [ ] A concrete future checkpoint to revisit the decision

**Meso** — output: the feature integrated, tested end to end, no gap.
- [ ] Nominal path AND at least one error path actually executed
- [ ] No simulated data presented as final result
- [ ] Result matches the need re-read AFTER implementation, not only before
- [ ] Honest account of done vs. remaining
- **Ledger required** at this level and above.

**Micro** — PLAN (one sentence: what this unit must guarantee) → RED (write
the check that must currently fail) → GREEN (minimal real implementation, no
simulation) → VERIFY (execute the proof, quote the raw result) → REFACTOR
(clean up, then re-verify).
- [ ] Proof executed in this session, not assumed
- [ ] Proof output inspected in detail, not just "it worked"
- [ ] At least one edge case explicitly considered

**Nano** — one targeted change; never silent, always one immediate real
check (compile, lint, quick run).

## The Proof Ledger (Meso+ tasks)

A plain markdown table (default `PROOF_LEDGER.md`) where every claim carries
exactly one status:

| Status | Meaning |
|---|---|
| `CLAIMED` | Asserted, no evidence yet. Must not survive to the end of a loop. |
| `EVIDENCED` | Linked to a proof actually executed and inspected (command + raw result reference). |
| `PENDING` | Proof defined but not executable in this context. Honest waiting state. |
| `WAIVED` | The user explicitly accepted proceeding without proof. Recorded debt, never silent. |

`scripts/ledger_check.py` (stdlib-only) exits non-zero if any CLAIMED rows
remain or any EVIDENCED row lacks evidence. Run it as the final mechanical
gate of every Meso loop, and in CI if the project has one. Full spec:
`references/proof-ledger.md`.

## Builder/Skeptic separation (defense against optimism leak)

Whoever builds never grades their own gate — borrowed from segregation of
duties in financial auditing and independent verification in aviation.

- **Builder** — plans, implements. May add ledger rows only as `CLAIMED`.
- **Skeptic** — verifies. Receives ONLY the claim, the gate definition, and
  the raw evidence — never the Builder's reasoning, which contaminates
  judgment. Its job is to find why the claim is NOT proven. It alone writes
  ledger statuses.
- **Scout** (Exploration only) — surveys options without converging.

**With subagents** (Claude Code, Cowork): spawn the Skeptic as a real
subagent using the role prompt in `references/agents.md`.
**Without subagents** (plain chat): honest degradation — an explicit,
labeled "Skeptic pass:" attacking your own claim before writing any status;
prefer `PENDING` over a self-graded `EVIDENCED` whenever the proof was not
directly observed. **A Skeptic pass that names no concrete attack is void**:
"nothing to report" is not a verdict, it is the optimism leak wearing a
Skeptic costume. If no attack can be named, write the strongest reason the
evidence might not generalize — there is always one. A fresh conversation given only claim + gate + evidence
is a practical approximation of true separation available to every user.

## The Two-Failure Rule (defense against stuck loops)

If the same gate fails **twice**, a third identical attempt is forbidden.
Stop and run a level audit before touching the code again:

1. **Is this the right level?** Most stuck Micro loops are misclassified
   Meso problems (the function can't be fixed because the interface around
   it is wrong) — and stuck Meso loops are often Macro problems (the feature
   can't work because the architecture forbids it). Ask: "would this failure
   disappear if something one level up were different?"
2. **Is the gate itself right?** Sometimes the gate tests the wrong thing.
   Redefining a gate is legitimate ONLY if done openly, before the next
   attempt, with the reason stated — never retroactively to make a failure
   look like a pass.
3. Then either escalate to the parent level with what was learned, or retry
   once with a genuinely different approach — stated as such.
4. Record the audit in one panel line so it is checkable later:
   `[AUDIT] 2 fails at Micro → cause was Meso interface; escalating`.

Two failures is data. Six failures is a session wasted on the wrong level.

## The no-upward-propagation rule (the heart of the system)

**A loop transmits to its parent only what it has proven, never what it
hopes.**

Refuse actively:
- Declaring a Meso "done" because the Micros "seem" to work
- Over-architecting at Macro to avoid hard Meso work
- Iterating past the Two-Failure Rule without a level audit
- Imposing a full Decision gate during Exploration
- Writing `EVIDENCED` from the Builder role, or without a raw evidence
  reference

## When proof cannot be executed directly

**If the proof was not actually observed, it does not exist — no matter how
solid the reasoning seems.**

- Execution tool available: use it for real, quote the raw output.
- No tool, or code runs on the developer's machine: give the exact command,
  ask for the pasted raw result, mark the row `PENDING` — never "passed" by
  deduction. If the developer proceeds anyway, record `WAIVED` with their
  explicit words: visible debt, never a silent pass.

A skill that claims to enforce proof but lets the AI hallucinate an
unobserved verification is worse than no skill: it manufactures false
confidence.

## The Retro Loop (the skill improves itself)

Every Skeptic `INSUFFICIENT` verdict is paid-for knowledge. Do not let it
evaporate when the session ends:

1. Keep a `SKEPTIC_CATCHES.md` next to the ledger: one line per catch —
   *what class of gap it was, why the Builder missed it, what question would
   have caught it earlier*.
   Example: `2026-07-11 | promised-but-untested behavior | docstring said
   ValueError, no test proved it | ask: "does every promise in the interface
   have an executed check?"`
2. At the start of any Meso+ loop, re-read the catches file (if present) and
   fold recurring patterns into the gate definition — the gate of loop N+1
   inherits the failures of loop N.
3. Periodically (or when the user asks for it), fold stable patterns back
   into this skill itself: a recurring catch class becomes a checklist line
   in `references/gate-checklist-generique.md`. That is the recursive
   improvement path — mechanical, evidence-driven, never aspirational.

The skill's own tooling obeys the same law: `python scripts/ledger_check.py
--self-test` runs the embedded adversarial suite that once broke v1 of the
script. Run it before trusting the mechanical gate — a verifier that was
never itself attacked is an unverified claim. `--catches` closes the loop
one turn further: it fails if `SKEPTIC_CATCHES.md` holds no well-formed
catch, making the retro-loop itself machine-checkable — no catches, no
evolution, and now the gate can say so.

## Protocol summary

1. Classify: level + weight, stated in one line.
2. Announce the truth gate before starting. Open the Loop Panel (Meso+).
3. Build (Builder role). Ledger rows enter as CLAIMED.
4. Verify (Skeptic role — subagent if available, labeled adversarial pass
   otherwise). Skeptic writes the status.
5. Report the raw proof result, never an optimistic summary. Re-emit the
   Panel.
6. Gate failed once → iterate. Failed twice → Two-Failure level audit.
7. Gate passed → report up explicitly with what was proven.
8. Proof not executable → PENDING, never assumed.
9. End of Meso loop: `python scripts/ledger_check.py` as the final
   mechanical gate (`--self-test` first if the script is newly installed).
10. Skeptic catch occurred → one line in `SKEPTIC_CATCHES.md` before
    closing the loop. The next loop's gate inherits it.

References — read when the situation calls for them:
- `references/worked-example.md` — a complete real session transcript,
  including a Skeptic catch that changed the outcome. Read this first if the
  protocol feels abstract.
- `references/proof-ledger.md` — ledger format, states, template, limits
- `references/agents.md` — Builder/Skeptic/Scout role prompts, delegation
  protocol with and without subagents
- `references/gate-checklist-generique.md` — domain-adaptable proof checklist
- `references/loop-ticket-template.md` — iteration traceability template
