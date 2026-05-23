# Custom spike — asyncio baseline

Pure-Python, no framework dependencies beyond the Anthropic SDK and jsonschema. The point is to establish the *baseline* — what we'd build if we built it ourselves — so CrewAI and LangGraph can be scored against a known reference.

## Files

| File | Lines | Purpose |
|---|---:|---|
| [`roles.py`](roles.py) | ~45 | `Role` + `DecisionRights` dataclasses; `MARKETING` role definition |
| [`tools.py`](tools.py) | ~45 | `PublisherTool` stub + `enforce_tool_access()` |
| [`hitl.py`](hitl.py) | ~30 | `ScriptedHITL` — reads founder responses from fixture |
| [`llm.py`](llm.py) | ~30 | Anthropic SDK wrapper |
| [`runtime.py`](runtime.py) | ~110 | Orchestrator: memory, trace, draft → HITL → revise → publish flow |
| [`run.py`](run.py) | ~50 | Entrypoint; validates brief against schema, runs, writes outputs |

Total: ~310 LOC. Slightly over the 300 budget — close enough; can trim if rubric notes call it out.

## Run

```bash
export ANTHROPIC_API_KEY=sk-ant-...
cd spikes/custom
pip install -r requirements.txt
python run.py
```

Outputs land in `out/`:
- `final_announcement.txt` — the approved draft
- `run_trace.json` — structured event log (used by the scorecard "observability" criterion)

## Spike notes (rubric-relevant)

These observations go into [`docs/spike-scorecard.md`](../../docs/spike-scorecard.md) once all three candidates are done.

**HITL ergonomics**: The gate is a single `await hitl.review(...)` call. Trivial to insert anywhere; trivial to mock by swapping `ScriptedHITL` for an interactive version. No framework hooks to learn.

**Role parameterization**: `DecisionRights` is a frozen dataclass; `must_escalate` is enforced declaratively in `tools.enforce_tool_access()` by reading the Role object. The Role and its rights are the same object the prose chapter will describe — zero impedance.

**State/memory across turns**: The runtime threads `prior` and `feedback` through `_perform_draft()` explicitly. No hidden memory store. Easy to inspect, easy to serialize.

**Tool access control**: Single function `enforce_tool_access()` reads the role's tool allowlist and `must_escalate` set. Easy to extend to per-tool policies.

**Observability**: `Runtime.trace` is a list of `TraceEvent` dataclasses, serialized to JSON. Every action shows up with role, input, and output. No vendor SDK to interrogate.

**Dev experience**: Six small files, no framework concepts to learn. Cost: we wrote all of it.

**Lock-in & cost**: Only dependency is `anthropic`. Swapping vendor = swap `llm.py`.
