# CrewAI spike

Same Passly launch scenario as [`../custom/`](../custom/), built on CrewAI's `Agent` / `Task` / `Crew` abstractions.

## Files

| File | Lines | Purpose |
|---|---:|---|
| [`roles.py`](roles.py) | ~50 | `RoleMeta` sidecar + `build_marketing_agent(llm)` (CrewAI `Agent`) |
| [`tools.py`](tools.py) | ~30 | `PublisherTool` as a CrewAI `BaseTool` |
| [`hitl.py`](hitl.py) | ~25 | `ScriptedHITL` — reads fixture, identical contract to custom spike |
| [`llm.py`](llm.py) | ~65 | `MockCrewLLM(crewai.LLM)` (default) + `build_llm(real_llm)` |
| [`run.py`](run.py) | ~125 | Entrypoint; argparse, drives CrewAI one Task at a time |

## Run

Default — deterministic mock, no API key, no anthropic install needed beyond what's already in the project venv:

```bash
cd spikes/crewai
python run.py
```

Optional `--real-llm` smoke test (unscored, ~$0.02 at claude-haiku-4-5):

```bash
# .env at the repo root must contain ANTHROPIC_API_KEY
python run.py --real-llm
```

## Spike notes (rubric-relevant)

**HITL ergonomics**: CrewAI's `Task(human_input=True)` calls `input()` on stdin — fine for interactive use but blocks scripted/deterministic runs. To get the same gate as the custom spike we **bypass CrewAI's HITL** and run each `Task` as its own one-task `Crew.kickoff()`, doing the gate in between. This is friction worth noting in the scorecard.

**Role parameterization**: CrewAI's `Agent(role=, goal=, backstory=, tools=)` carries name/goal/system-prompt cleanly. But there is **no declarative slot for `decision_rights` or `must_escalate`** — we keep them in a sidecar `RoleMeta` dataclass and *also* paste them into the backstory text so the LLM sees them. Enforcement is manual (in `run.py`). The framework's own concept and the thesis vocabulary do not align 1:1.

**State/memory across turns**: We thread the prior draft and feedback manually into the revision `Task.description`. CrewAI has a built-in memory subsystem we deliberately did not use — for spike parity with the other two implementations.

**Tool access control**: CrewAI tools are owned by the `Agent`. There is no "may hold but not invoke until escalated" policy. We work around it by **attaching `publisher_tool` to the agent only after founder approval** (`agent.tools = [publisher]`). It works, but it's runtime mutation of agent state — fragile.

**Observability**: CrewAI emits verbose logs to stdout when `verbose=True`; structured machine-readable traces of agent thoughts/tool calls require either parsing the verbose output or hooking into CrewAI's callback system. We bypass both and capture our own `trace` list per event — identical to the custom spike — so the comparison is fair.

**Dev experience**: Fast to get an Agent + Task running. Friction shows up when the desired flow doesn't match CrewAI's `Crew.kickoff()` opinions — every workaround above is rubric evidence.

**Lock-in & cost**: CrewAI depends on `litellm` (broad model coverage, good for vendor agnosticism) but pins specific Python and pydantic versions and has had API churn between minor releases. Worth a "tracking-cost" note.

## Substitution friction (found during the mock adaptation)

These show up as concrete cost items when you do *not* want CrewAI to call the model itself.

1. **Subclassing `crewai.LLM` to inject a stub**: the parent constructor takes ~25 kwargs (timeout, temperature, top_p, n, stop, max_tokens, presence_penalty, frequency_penalty, logit_bias, response_format, seed, logprobs, top_logprobs, base_url, api_base, api_version, api_key, callbacks, reasoning_effort, stream, …) and `super().__init__(model=...)` insists on a litellm-recognised provider string even when `.call()` will be fully overridden. Concretely: had to pass `model="anthropic/claude-haiku-4-5"` as a *sentinel*, not a real route, to keep litellm's init quiet.

2. **Python version pin**: latest CrewAI requires Python `<=3.13`. The project's Homebrew default is 3.14, so the venv had to be rebuilt on 3.11. Documented in the repo-root README.

3. **Output format coupling**: CrewAI's agent executor parses LLM output for `"Thought: …\nFinal Answer: …"`. Plain responses get rejected and CrewAI re-prompts, blowing the call budget. The mock adapter has to wrap its canned text in that scaffold — i.e. the framework couples the LLM contract to its own parser. Not a blocker, but it leaks into the LLM substitution layer.

4. **Call budget is not declarative**: even with `max_iter=1` on the Agent, the executor can make multiple LLM calls per Task while parsing/retrying. The shared mock's `QueueExhausted` exception caught this on the first run. For the custom and (anticipated) LangGraph spikes, calls per Task are explicit.
