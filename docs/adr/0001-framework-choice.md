# ADR 0001 — Orchestration framework choice for the solo-founder-crew

- **Status**: Accepted
- **Date**: 2026-05-23
- **Deciders**: Nikos Liapis (thesis author). Supervisor review pending under [`00_Admin/Supervisor_Sync_Agenda.docx`](../../../Diplomatic/00_Admin/Supervisor_Sync_Agenda.docx).
- **Part of**: Thesis Part 7 — framework spike. Closes the spike opened by [`spike-charter.md`](../spike-charter.md).

## Context

The thesis proposes a five-component framework for solo-founder digital
ventures (Venture Brief Schema, Role Library, Crew Generator,
Orchestration Runtime, HITL Contract). Component 4 — the Orchestration
Runtime — needs an underlying substrate that handles:

- Sequencing of role actions
- Memory of prior turns
- Per-role tool-access enforcement
- A first-class human-in-the-loop pause/resume mechanism (the
  founder's approval gate)
- Observable structured traces for evaluation (Ch.5) and for the
  founder operating the system

Three candidates were considered: **CrewAI**, **LangGraph**, and a
**custom asyncio implementation** built from scratch. All three were
implemented end-to-end against the same Passly launch scenario
([`scenarios/passly_launch.md`](../../scenarios/passly_launch.md)) and
scored against the rubric in
[`spike-charter.md`](../spike-charter.md) §"Rubric". Full evidence:
[`spike-scorecard.md`](../spike-scorecard.md).

## Decision

**Adopt LangGraph as the Orchestration Runtime substrate.** The
framework's own abstractions (`Role`, `DecisionRights`, `HITLContract`,
`ToolRegistry`) will be implemented as a layer over LangGraph's
`StateGraph`, nodes, conditional edges, and `interrupt()` primitives.

## Rationale

### Rubric outcome

| Candidate | Weighted score / 75 |
|---|---:|
| Custom | 69 |
| **LangGraph** | **67** |
| CrewAI | 32 |

Custom and LangGraph are within rounding noise. **CrewAI is decisively
third** — it scored 2/5 on five of seven criteria and surfaced four
distinct substitution-friction items during the mock-LLM adaptation
(see scorecard §"Mock-substitution friction"). It does not fit the
solo-founder operational model: heavy dependency footprint,
non-declarative call budget, no native concept for `decision_rights`,
and an LLM substitution path that requires subclassing a ~25-argument
base class and matching an output-format regex. Eliminated.

### Tie-breaker: LangGraph over Custom

The rubric does not directly score production-readiness or
thesis-defensibility, both of which break the tie cleanly toward
LangGraph:

1. **HITL pause/resume is built-in.** LangGraph's `interrupt()`
   primitive — paired with its checkpointer — is exactly the founder
   gate the HITL Contract describes. The custom spike has a clean
   `await hitl.review()` shape, but building pause/resume across
   process restarts (which a founder running this on a laptop will
   need) is non-trivial work the thesis would have to either deliver
   or defer.

2. **Cross-session memory is built-in.** LangGraph's checkpointer
   serialises the `RunState` to a backing store (SQLite, Postgres,
   memory). The custom spike threads state explicitly — fine for a
   single run, but the solo-founder use case is fundamentally
   stateful across days and sessions. Building a checkpointing layer
   on top of the custom runtime would duplicate LangGraph's existing
   contract.

3. **The graph topology is data.** `app.get_graph().draw_mermaid()`
   produces a diagram the Ch.3 prose can paste in directly. The same
   diagram is what the founder sees if they want to understand what
   the crew is doing. The custom spike has no equivalent — we would
   have to either write a static diagram or build a topology renderer
   ourselves.

4. **Thesis defensibility (DSR).** The Design Science Research
   methodology (Hevner 2004; Peffers 2007) does not penalise building
   on existing artifacts; it asks the candidate to demonstrate that
   the proposed framework is *constructible*. Constructing the
   framework on top of LangGraph is more credible — and easier to
   defend in the viva — than presenting a from-scratch runtime whose
   primitives ad-hoc resemble LangGraph's. The thesis contribution is
   the **framework abstractions** (Role Library, HITL Contract,
   Crew Generator), not the orchestration substrate.

5. **License + governance.** LangGraph is BSD-3, actively maintained
   by LangChain, runs locally with no mandatory hosted services.
   Acceptable for a sandbox academic deployment and for any future
   Passly production use.

### What we keep from the custom spike

The custom spike's score (69) is high because we tailored every
component to the thesis vocabulary. Those abstractions — `Role`,
`DecisionRights`, `ToolRegistry.invoke()`, the trace event shape —
**carry forward into the framework package**. They become the
solo-founder-crew layer; LangGraph nodes are the carrier underneath.

### What we discard from the spike

- The custom asyncio runtime (replaced by LangGraph's graph executor)
- All three spikes' ad-hoc scenario wiring (the framework's Crew
  Generator will subsume this)
- CrewAI entirely

## Consequences

### Positive

- One framework dependency for the runtime (`langgraph`), well-maintained, BSD-licensed.
- The thesis-side abstractions (Role, HITL Contract) are framework-substrate-agnostic — if LangGraph is ever swapped, those don't change.
- The Ch.3 prose can reference LangGraph's published primitives (interrupt, checkpointer, conditional edges) rather than introducing entirely novel concepts.
- Chapter 4 (Passly application) consumes solo-founder-crew which consumes LangGraph — three layers, each with one responsibility.

### Negative / risks

- **API churn risk.** LangGraph is < 2 years old and at 1.0.1 as of installation. Pin a minor version in `requirements.txt` and re-evaluate before each chapter draft. Track [LangGraph releases](https://github.com/langchain-ai/langgraph/releases) in the thesis tracker.
- **Python version constraint.** LangGraph itself is permissive but its dependency tree (`langchain-anthropic`, etc.) effectively requires Python ≤ 3.13. The project venv is pinned at 3.11.
- **Namespace footgun.** The spike folder being named `langgraph/` collided with the installed package as a namespace-package fragment. Resolved with `sys.path.append`. The framework package will live at `src/solo_founder_crew/` — no collision risk there.
- **LangChain ecosystem coupling for LLM bindings.** `langchain-anthropic` is the natural binding but couples us to the langchain way of constructing chat models. Acceptable given the rubric's "Lock-in & cost" criterion already weighed this at 1 (lowest); the dependency is replaceable in a single file.

### Decision is reversible if

- LangGraph introduces a breaking API change that costs > 1 week to absorb during framework construction.
- The thesis discovers a use case in Ch.3 or Ch.4 that LangGraph genuinely cannot model (none identified in the spike).
- License or governance changes.

In any of those cases, the framework abstractions (`Role`, etc.) survive
the swap; only the substrate underneath changes. That portability is
itself an argument for the chosen design.

## Follow-ups

- [ ] Move `Role`, `DecisionRights`, `HITLContract`, `ToolRegistry`, `TraceEvent` from `spikes/custom/` to `src/solo_founder_crew/` as the package skeleton.
- [ ] Build the `Crew Generator` (Component 3) over LangGraph's `StateGraph` builder.
- [ ] Wire `interrupt()` as the production HITL gate; keep `ScriptedHITL` as the test double.
- [ ] Add a checkpointer-backed memory variant for cross-session runs (Component 4 completeness).
- [ ] Pin `langgraph` to a known-good minor version in `requirements.txt`.
- [ ] Update [`02_Framework/`](../../../Diplomatic/02_Framework/) note in the thesis repo (currently a stub) to point at this ADR.
- [ ] Reference this ADR from the Ch.3 prose draft (`05_Drafts/Ch3_Framework.docx`) when it begins.

## References

- Rubric & scenario: [`spike-charter.md`](../spike-charter.md), [`scenarios/passly_launch.md`](../../scenarios/passly_launch.md)
- Scoring evidence: [`spike-scorecard.md`](../spike-scorecard.md)
- Worked-example outputs: [`spike-evidence/`](../spike-evidence/)
- Spike commits: `2d13a7f` (initial three implementations), `8fab6d4` (charter + mock refactor), `655031a` / `d1c2e77` / `3bf0587` (mock+real adaptations of custom / crewai / langgraph)
- DSR methodology: Hevner et al. (2004); Peffers et al. (2007) — see [`06_References/thesis.bib`](../../../Diplomatic/06_References/thesis.bib)
