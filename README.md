# solo-founder-crew

Multi-agent operating model for solo-founder digital startups. Companion code for the MBA διπλωματική *AI-Native Management and Orchestration* (University of the Aegean / NTUA, Liapis 2026).

This repository hosts the **framework** developed in Chapter 3. The case-study application in Chapter 4 (Passly) consumes this framework as a dependency from its own repo.

## Components

The framework has five components (per the thesis scope):

1. **Venture Brief Schema** — structured input describing a venture's domain, product, customer, constraints. Lives in [`schemas/`](schemas/) as JSON Schema (single source of truth for prose + code).
2. **Role Library** — catalogue of parameterised agent roles with decision rights and escalation rules.
3. **Crew Generator** — selects and configures a crew subset from a Venture Brief.
4. **Orchestration Runtime** — coordination layer (messaging, memory, tool access, arbitration).
5. **HITL Contract** — Human-in-the-Loop Contract: where the founder must approve, override, or be notified.

## Status

Part 7 closed (2026-05-23). **Orchestration substrate locked: LangGraph.**
See [`docs/adr/0001-framework-choice.md`](docs/adr/0001-framework-choice.md)
for the decision and [`docs/spike-scorecard.md`](docs/spike-scorecard.md) for
the rubric scoring.

Framework construction is phased:

| Phase | Scope | State |
|---|---|---|
| 1 | Package skeleton + primitive abstractions (`Role`, `DecisionRights`, `HITLContract`, `ScriptedHITL`, `ToolRegistry`, `TraceEvent`, `RunTrace`, `LLMClient`, `MockLLM`, `RealLLM`, `VentureBrief`) | ✅ done |
| 2 | LangGraph runtime + `Crew.from_brief()` API; Passly end-to-end via framework code | ⏳ next |
| 3 | Role Library catalogue + Crew Generator algorithm | pending |
| 4 | Production HITL via `interrupt()` + checkpointer-backed memory | pending |
| 5 | pytest suite + thesis-side note update | pending |

## Quickstart

```python
from solo_founder_crew import VentureBrief, Role, DecisionRights, ScriptedHITL, MockLLM

brief = VentureBrief.from_file("scenarios/fixtures/passly_brief.json")

marketing = Role(
    name="marketing",
    goal="Draft customer-facing announcements.",
    system_prompt="You are Marketing for solo-founder ventures...",
    decision_rights=DecisionRights(
        can=("draft_content", "revise_content"),
        must_escalate=("final_approval_before_publish",),
    ),
    tools=("publisher_tool",),
)

llm = MockLLM(responses=["draft v1...", "draft v2..."])
hitl = ScriptedHITL.from_file("scenarios/fixtures/founder_responses.json")

# Runtime (Phase 2) will tie these together via Crew.from_brief(...).
```

## Layout

```
schemas/    JSON Schema definitions (Venture Brief, Role, HITL Contract)
scenarios/  Spike test bench (Passly launch) + fixtures
spikes/     Part 7 candidate implementations: custom, crewai, langgraph + shared
src/        Framework package (populated post-ADR)
tests/      pytest suites
docs/       Charter, scorecard, ADRs
```

## Setup

A project-local venv keeps dependencies pinned and isolated from system Python.

```bash
cd solo-founder-crew
/opt/homebrew/bin/python3 -m venv .venv          # or any Python ≥ 3.10
source .venv/bin/activate                         # optional; can also call .venv/bin/python directly
pip install -r requirements.txt

cp .env.example .env                              # then paste your ANTHROPIC_API_KEY
```

`.env` is gitignored. The default spike runs use a deterministic mock and don't need the key — see [`spikes/README.md`](spikes/README.md).

## License

Private — academic work in progress. Not for redistribution.
