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

Part 7 spike in progress. Framework choice (CrewAI / LangGraph / custom) locks once the three candidate implementations under [`spikes/`](spikes/) are scored against the rubric in [`docs/spike-charter.md`](docs/spike-charter.md).

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
