# LangGraph spike

Same Passly launch scenario, built as a LangGraph state machine.

## Files

| File | Lines | Purpose |
|---|---:|---|
| [`roles.py`](roles.py) | ~40 | `Role` + `DecisionRights` — mirror of custom spike (LangGraph has no Role abstraction) |
| [`tools.py`](tools.py) | ~35 | `PublisherTool` + `enforce_tool_access()` — same contract as custom |
| [`hitl.py`](hitl.py) | ~25 | `ScriptedHITL` |
| [`graph.py`](graph.py) | ~110 | `StateGraph`: draft → hitl → (revise \| publish \| END) |
| [`llm.py`](llm.py) | ~70 | `MockChatModel` (duck-typed) + `build_llm(real_llm)` |
| [`run.py`](run.py) | ~60 | Entrypoint; argparse, `.env`, builds graph, invokes |

## Run

Default — deterministic mock, no API key:

```bash
cd spikes/langgraph
python run.py
```

Optional `--real-llm` smoke test (unscored, ~$0.02 at claude-haiku-4-5):

```bash
# .env at the repo root must contain ANTHROPIC_API_KEY
python run.py --real-llm
```

## Spike notes (rubric-relevant)

**HITL ergonomics**: Excellent native fit. LangGraph supports `interrupt()` to pause the graph at any node, persist state via a checkpointer, and resume with new input — this is exactly the founder gate pattern. For *spike determinism* we use a regular node reading from the fixture (so all three spikes run the same way), but the scaffolding for `interrupt()` is a comment swap away. Rubric score should reflect both: easy to script *and* a clean path to real interactive HITL.

**Role parameterization**: LangGraph has **no Agent/Role abstraction at all** — nodes are functions over a `State` TypedDict. We define `Role` from scratch (identical to the custom spike). Pro: no framework prejudice forces the wrong shape. Con: zero framework leverage on this concept.

**State/memory across turns**: The `RunState` TypedDict is the memory. Explicit, inspectable, easy to serialize. LangGraph also supports checkpoints for true cross-session memory — out of scope for the spike but a strong point for the thesis runtime.

**Tool access control**: Manual via `enforce_tool_access()` inside the publish node. Same pattern as custom; LangGraph adds nothing on this axis.

**Observability**: The graph topology is a first-class artifact — `app.get_graph().draw_mermaid()` produces a diagram identical to the scenario flow. Per-event trace is captured by appending to `state["trace"]` in each node. Best of the three on this criterion.

**Dev experience**: A bit more ceremony than custom (TypedDict, conditional edges, compile step). Less than CrewAI's hidden control flow. The diagram-as-data property pays off when explaining the runtime in Chapter 3.

**Lock-in & cost**: Depends on `langchain-anthropic` for the LLM binding (or `langchain-core` chat model abstractions); switching vendor is a one-import change. LangGraph itself is BSD-licensed and runs locally.

## Substitution friction (found during the mock adaptation)

Notably *lower* than CrewAI's. Cataloguing what was needed:

1. **Duck-typed LLM contract**: nodes only require `state["llm"].invoke(messages).content`. The mock is a 25-line plain class with one method. No subclassing of langchain `BaseChatModel`, no pydantic gymnastics, no output-format coupling (LangGraph does not parse LLM output — the node decides what to do with `.content`).

2. **Namespace package collision (footgun)**: the spike folder is literally named `langgraph/`. If `spikes/` is inserted at `sys.path[0]` (as the custom and CrewAI spikes do), Python treats `spikes/langgraph/` as a namespace-package fragment that shadows the installed `langgraph`, and `from langgraph.graph import …` inside the spike's own `graph.py` becomes a circular self-import. Fix is to `sys.path.append` (not `insert(0,…)`). Documented inline in `run.py` and `llm.py`. One-time cost; future framework code should avoid naming directories after pip-installable packages.

3. **No call-budget surprises**: the graph executes nodes in topological order, one LLM call per node that calls one. Unlike CrewAI's executor, there is no implicit retry-loop on parse failure. The shared mock's queue is exactly sized.
