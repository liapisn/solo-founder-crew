# solo-founder-crew

[![CI](https://github.com/liapisn/solo-founder-crew/actions/workflows/ci.yml/badge.svg)](https://github.com/liapisn/solo-founder-crew/actions/workflows/ci.yml)

Multi-agent operating model for solo-founder digital startups. Companion code for the MBA διπλωματική *AI-Native Management and Orchestration* (University of the Aegean / NTUA, Liapis 2026).

This repository hosts the **framework** developed in Chapter 3. The case-study application in Chapter 4 (Passly) consumes this framework as a dependency from its own repo.

## Components

The framework has five components (per the thesis scope):

1. **Venture Brief Schema** — structured input describing a venture's domain, product, customer, constraints. Lives in [`src/solo_founder_crew/schemas/`](src/solo_founder_crew/schemas/) as JSON Schema (single source of truth for prose + code).
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
| 2 | LangGraph runtime + `Crew.author_flow()` API; Passly end-to-end via framework code (see [`examples/passly_launch.py`](examples/passly_launch.py)) | ✅ done |
| 3 | Role Library (5 roles) + rule-driven Crew Generator with audit log (see [`examples/crew_generator_demo.py`](examples/crew_generator_demo.py)) | ✅ done |
| 4 | Production HITL via LangGraph `interrupt()` + checkpointer; `InteractiveHITL` for stdin demos (see [`examples/passly_interactive.py`](examples/passly_interactive.py)) | ✅ done |
| 5 | pytest suite (covering primitives, role library, all four author-flow termination paths) + thesis-side note | ✅ done |
| 6 | HITL surface layer: typed `HITLRequest` envelope ([`schemas/hitl_request.schema.json`](src/solo_founder_crew/schemas/hitl_request.schema.json), [`hitl_request.py`](src/solo_founder_crew/hitl_request.py)); the runtime gate now emits a `HITLRequest` and `HITLContract.review` takes it; `DiscordHITL` surface adapter ([`adapters/discord_hitl.py`](src/solo_founder_crew/adapters/discord_hitl.py)) lets the founder approve/reject/kill from a chat channel. | ✅ done |

**67 tests pass** (`.venv/bin/python -m pytest`). Phases 1–6 complete; the
framework instantiates, runs end-to-end, and renders the founder gate to a
remote surface. Companion thesis section: Ch.3 §3.7 (Orchestration Runtime)
and §3.8 (HITL Contract, incl. the Discord surface).

## Quickstart

```bash
cd solo-founder-crew
.venv/bin/python examples/passly_launch.py            # mock, deterministic, free
.venv/bin/python examples/passly_launch.py --real-llm # claude-haiku-4-5, ~$0.02
```

Shape of the public API as of Phase 2:

```python
from solo_founder_crew import (
    Crew, Role, DecisionRights, VentureBrief,
    ScriptedHITL, ToolRegistry, MockLLM,
)

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

tools = ToolRegistry()
tools.register("publisher_tool", my_publisher_fn,
               escalates="final_approval_before_publish")

crew = Crew(
    brief=brief, roles=[marketing],
    llm=MockLLM(responses=["draft v1...", "draft v2..."]),
    hitl=ScriptedHITL.from_file("scenarios/fixtures/founder_responses.json"),
    tools=tools,
)

result = await crew.author_flow(
    task_description="Draft a launch announcement for this venture."
)
print(result.status, result.approved_artifact)
result.trace.write("out/trace.json")
```

The Author Flow graph topology is also a first-class artifact —
[`docs/author_flow.mermaid`](docs/author_flow.mermaid) is generated
from the same `build_author_graph(...)` the runtime calls. Same
diagram as the [scenario specification](scenarios/passly_launch.md).

## Layout

```
src/solo_founder_crew/schemas/  JSON Schema definitions (Venture Brief, Role, HITL Contract)
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
