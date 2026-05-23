# Part 7 Framework Spike — Charter

**Owner:** Nikos Liapis
**Status:** Active
**Decision artifact:** [`docs/adr/0001-framework-choice.md`](adr/0001-framework-choice.md) (to be written at close)
**Thesis context:** Part 7 of the 18-part plan. Locks the framework choice for the Chapter 3 prototype and downstream Chapter 4 Passly case study.

## Question

Which framework provides the best substrate for the solo-founder-crew framework: **CrewAI**, **LangGraph**, or a **custom asyncio-based** implementation?

## Approach

Build the **same scenario** in each candidate, kept to **<300 lines of code per implementation**. Score against a fixed rubric defined *before* coding. The spike is intentionally narrow — it is not the framework, it is just enough to differentiate the candidates.

## Scenario (test bench)

**Passly launch announcement.** A Marketing role drafts a launch announcement for Passly given a Venture Brief. The founder reviews via a Human-in-the-Loop gate (approve / edit / reject). On approve, a stubbed publisher tool "ships" the announcement. A second turn revises if the founder rejected with feedback.

Full spec: [`scenarios/passly_launch.md`](../scenarios/passly_launch.md).

The scenario exercises all five framework components in a single short flow:
- Venture Brief Schema (structured input)
- Role Library (Marketing role with decision rights)
- Crew Generator (single-role crew assembled from the Brief)
- Orchestration Runtime (memory across two turns, tool access)
- HITL Contract (the approval gate)

## Rubric

Score each candidate 1–5 on each criterion. Weighted total decides.

| Criterion | Weight | What "5" looks like |
|---|---:|---|
| HITL ergonomics | 3 | Approval gates are first-class, easy to insert anywhere, easy to test |
| Role parameterization (decision rights, escalation) | 3 | Roles carry typed config; decision rights are declarative not buried in prose |
| State/memory across turns | 2 | Memory model is explicit and inspectable; not coupled to a vendor |
| Tool access control | 2 | Per-role tool allowlists are trivial; no global registry leaks |
| Observability / debuggability | 2 | Traces of which role did what, with what input/output, are easy to capture |
| Dev experience (solo dev) | 2 | Small surface area, low ceremony, runs locally without infra |
| Lock-in & cost (sandbox-friendly) | 1 | No mandatory hosted services; works with any LLM API; no per-seat licensing |

Max raw score = 5 × (3+3+2+2+2+2+1) = 75.

## LLM stance

**The rubric scores framework ergonomics, not LLM output quality.** None
of the seven criteria depend on what the model returns. Accordingly:

- **Default scoring runs use a stub LLM** (`spikes/shared/MockLLM`), a
  pre-loaded response queue returning two canned drafts in order. This
  makes runs deterministic, free, and reproducible — properties the
  Ch.5 evaluation chapter benefits from.
- **One optional real-LLM smoke test per candidate** lives behind a
  `--real-llm` flag in each spike's runner. It exists only to verify
  that the framework's runtime LLM integration is real (closes the
  reviewer pushback "you never ran an actual model through it"). Uses
  `claude-haiku-4-5`, one call per run, ~$0.02 per candidate.
  Requires `ANTHROPIC_API_KEY` to be set; otherwise the spike runs the
  mock path.

The smoke test is **not** scored. It is a methodological reassurance.

## Out of scope for the spike

- Production-grade error handling
- Multi-role crews — one role + founder is enough to score
- The actual Role Library catalogue, Crew Generator algorithm, full HITL Contract DSL
- Output-quality comparison between candidates (would require real-LLM
  runs across all three with statistical care — out of scope for a
  framework-selection ADR)

## Exit criteria

- Three working implementations in `spikes/{custom,crewai,langgraph}/`
- Each runs end-to-end against the shared mock with deterministic output
- Each runs the optional `--real-llm` smoke test successfully when an
  API key is present
- Scorecard filled in at `docs/spike-scorecard.md`
- ADR 0001 written and merged
