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

Pre-spike. Framework choice (CrewAI / LangGraph / custom) locks at the end of Part 7 of the thesis plan.

## Layout

```
schemas/   JSON Schema definitions (Venture Brief, Role, HITL Contract)
src/       Python package
tests/     pytest suites
docs/      design notes, ADRs
```

## License

Private — academic work in progress. Not for redistribution.
