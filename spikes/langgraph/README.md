# LangGraph spike

Same Passly launch scenario, built as a LangGraph state machine.

## Files

| File | Lines | Purpose |
|---|---:|---|
| [`roles.py`](roles.py) | ~40 | `Role` + `DecisionRights` — mirror of custom spike (LangGraph has no Role abstraction) |
| [`tools.py`](tools.py) | ~35 | `PublisherTool` + `enforce_tool_access()` — same contract as custom |
| [`hitl.py`](hitl.py) | ~25 | `ScriptedHITL` |
| [`graph.py`](graph.py) | ~110 | `StateGraph`: draft → hitl → (revise | publish | END) |
| [`run.py`](run.py) | ~45 | Entrypoint; loads fixtures, invokes the compiled graph |

## Run

```bash
export ANTHROPIC_API_KEY=sk-ant-...
cd spikes/langgraph
pip install -r requirements.txt
python run.py
```

## Spike notes (rubric-relevant)

**HITL ergonomics**: Excellent native fit. LangGraph supports `interrupt()` to pause the graph at any node, persist state via a checkpointer, and resume with new input — this is exactly the founder gate pattern. For *spike determinism* we use a regular node reading from the fixture (so all three spikes run the same way), but the scaffolding for `interrupt()` is a comment swap away. Rubric score should reflect both: easy to script *and* a clean path to real interactive HITL.

**Role parameterization**: LangGraph has **no Agent/Role abstraction at all** — nodes are functions over a `State` TypedDict. We define `Role` from scratch (identical to the custom spike). Pro: no framework prejudice forces the wrong shape. Con: zero framework leverage on this concept.

**State/memory across turns**: The `RunState` TypedDict is the memory. Explicit, inspectable, easy to serialize. LangGraph also supports checkpoints for true cross-session memory — out of scope for the spike but a strong point for the thesis runtime.

**Tool access control**: Manual via `enforce_tool_access()` inside the publish node. Same pattern as custom; LangGraph adds nothing on this axis.

**Observability**: The graph topology is a first-class artifact — `app.get_graph().draw_mermaid()` produces a diagram identical to the scenario flow. Per-event trace is captured by appending to `state["trace"]` in each node. Best of the three on this criterion.

**Dev experience**: A bit more ceremony than custom (TypedDict, conditional edges, compile step). Less than CrewAI's hidden control flow. The diagram-as-data property pays off when explaining the runtime in Chapter 3.

**Lock-in & cost**: Depends on `langchain-anthropic` for the LLM binding (or `langchain-core` chat model abstractions); switching vendor is a one-import change. LangGraph itself is BSD-licensed and runs locally.
