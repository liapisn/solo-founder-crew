# CrewAI spike

Same Passly launch scenario as [`../custom/`](../custom/), built on CrewAI's `Agent` / `Task` / `Crew` abstractions.

## Files

| File | Lines | Purpose |
|---|---:|---|
| [`roles.py`](roles.py) | ~50 | `RoleMeta` sidecar + `build_marketing_agent()` (CrewAI `Agent`) |
| [`tools.py`](tools.py) | ~30 | `PublisherTool` as a CrewAI `BaseTool` |
| [`hitl.py`](hitl.py) | ~25 | `ScriptedHITL` — reads fixture, identical contract to custom spike |
| [`run.py`](run.py) | ~115 | Entrypoint; drives CrewAI one Task at a time so HITL gates fit between kickoffs |

## Run

```bash
export ANTHROPIC_API_KEY=sk-ant-...
cd spikes/crewai
pip install -r requirements.txt
python run.py
```

## Spike notes (rubric-relevant)

**HITL ergonomics**: CrewAI's `Task(human_input=True)` calls `input()` on stdin — fine for interactive use but blocks scripted/deterministic runs. To get the same gate as the custom spike we **bypass CrewAI's HITL** and run each `Task` as its own one-task `Crew.kickoff()`, doing the gate in between. This is friction worth noting in the scorecard.

**Role parameterization**: CrewAI's `Agent(role=, goal=, backstory=, tools=)` carries name/goal/system-prompt cleanly. But there is **no declarative slot for `decision_rights` or `must_escalate`** — we keep them in a sidecar `RoleMeta` dataclass and *also* paste them into the backstory text so the LLM sees them. Enforcement is manual (in `run.py`). The framework's own concept and the thesis vocabulary do not align 1:1.

**State/memory across turns**: We thread the prior draft and feedback manually into the revision `Task.description`. CrewAI has a built-in memory subsystem we deliberately did not use — for spike parity with the other two implementations.

**Tool access control**: CrewAI tools are owned by the `Agent`. There is no "may hold but not invoke until escalated" policy. We work around it by **attaching `publisher_tool` to the agent only after founder approval** (`agent.tools = [publisher]`). It works, but it's runtime mutation of agent state — fragile.

**Observability**: CrewAI emits verbose logs to stdout when `verbose=True`; structured machine-readable traces of agent thoughts/tool calls require either parsing the verbose output or hooking into CrewAI's callback system. We bypass both and capture our own `trace` list per event — identical to the custom spike — so the comparison is fair.

**Dev experience**: Fast to get an Agent + Task running. Friction shows up when the desired flow doesn't match CrewAI's `Crew.kickoff()` opinions — every workaround above is rubric evidence.

**Lock-in & cost**: CrewAI depends on `litellm` (broad model coverage, good for vendor agnosticism) but pins specific Python and pydantic versions and has had API churn between minor releases. Worth a "tracking-cost" note.
