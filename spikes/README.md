# Spikes

Three minimal implementations of the [Passly launch scenario](../scenarios/passly_launch.md), one per candidate framework. Each is throwaway code: it exists to score the candidate against the [rubric](../docs/spike-charter.md#rubric), not to become the framework.

Hard rules per implementation:
- < 300 LOC (excluding shared schema and fixtures)
- Loads the same Venture Brief fixture
- Uses the same LLM (claude-haiku-4-5)
- Produces `final_announcement.txt` and `run_trace.json`
- HITL responses come from `scenarios/fixtures/founder_responses.json` — no interactive prompt

## Order

Recommended order to implement, easiest framing first:

1. **custom** — sets the baseline. Tells us what we'd build if we built it ourselves.
2. **crewai** — high-level, opinionated. Tells us what we get if we accept its abstractions.
3. **langgraph** — graph-based, lower-level than CrewAI. Tells us the middle path.

After all three: fill in [`../docs/spike-scorecard.md`](../docs/spike-scorecard.md) and write [`../docs/adr/0001-framework-choice.md`](../docs/adr/0001-framework-choice.md).
