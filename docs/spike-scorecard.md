# Spike Scorecard

Scoring follows the rubric defined in [`spike-charter.md`](spike-charter.md).
Scores are 1–5 per criterion; weighted total = Σ(score × weight). Max
raw score = 75. Each cell is justified in the notes below the table —
no number stands alone.

## Summary

| Criterion | Weight | Custom | CrewAI | LangGraph |
|---|---:|---:|---:|---:|
| HITL ergonomics | 3 | 5 | 2 | 5 |
| Role parameterization | 3 | 5 | 2 | 4 |
| State/memory across turns | 2 | 4 | 3 | 5 |
| Tool access control | 2 | 5 | 2 | 4 |
| Observability / debuggability | 2 | 4 | 2 | 5 |
| Dev experience (solo dev) | 2 | 4 | 2 | 4 |
| Lock-in & cost | 1 | 5 | 2 | 4 |
| **Weighted total** (/75) | — | **69** | **32** | **67** |
| LOC (.py only, all files) | — | 365 | 385 | 428 |
| Mock-substitution overhead (LOC) | — | ~50 | ~115 | ~80 |
| Substitution friction items | — | 0 | 4 | 1 |
| Total LLM calls per `--real-llm` run | — | 2 | 2 | 2 |

**Custom and LangGraph are within rounding noise of each other (69 vs 67
out of 75). CrewAI is a clear third.** The ADR resolves the tie on
non-rubric criteria (production roadmap, thesis defensibility); see
[`adr/0001-framework-choice.md`](adr/0001-framework-choice.md).

## Per-criterion evidence

### HITL ergonomics (weight 3)

| Candidate | Score | Evidence |
|---|---:|---|
| Custom | 5 | Single `await hitl.review(draft)` call inside the runtime loop. Trivial to insert anywhere. Trivial to swap `ScriptedHITL` for a real founder UI. No framework hooks. |
| CrewAI | 2 | `Task(human_input=True)` calls `input()` on stdin — unusable for deterministic spike runs. We **bypassed CrewAI's HITL entirely** and ran each `Task` as its own one-task `Crew.kickoff()`, doing the gate in between. Works, but every workaround is rubric cost. |
| LangGraph | 5 | Native `interrupt()` pauses the graph at any node, persists state via a checkpointer, resumes with founder input. For spike determinism we used a regular node, but the path to real interactive HITL is documented and a comment swap away. Best of all worlds. |

### Role parameterization (weight 3)

| Candidate | Score | Evidence |
|---|---:|---|
| Custom | 5 | `Role` + `DecisionRights` are frozen dataclasses. `must_escalate` is enforced declaratively in `tools.enforce_tool_access()`. The Role object the prose chapter will describe is exactly the same object the code uses. Zero impedance. |
| CrewAI | 2 | CrewAI's `Agent(role=, goal=, backstory=, tools=)` carries name/goal/system-prompt cleanly. There is **no declarative slot for `decision_rights` or `must_escalate`**. We kept them in a sidecar `RoleMeta` dataclass **and** pasted them into the backstory text so the LLM sees them; enforcement is manual in `run.py`. Framework concept and thesis vocabulary do not align. |
| LangGraph | 4 | LangGraph has **no Agent/Role abstraction at all** — nodes are functions over a `State` TypedDict. We define `Role` from scratch (identical to the custom spike). Pro: no framework prejudice forces the wrong shape. Con: zero framework leverage on this concept. Same outcome as custom; one point lower because no native concept to lean on. |

### State / memory across turns (weight 2)

| Candidate | Score | Evidence |
|---|---:|---|
| Custom | 4 | The runtime threads `prior` and `feedback` through `_perform_draft()` explicitly. No hidden memory store. Easy to inspect, easy to serialise. |
| CrewAI | 3 | Memory threaded manually via `context=` on the revision `Task`. CrewAI's built-in memory subsystem exists but we deliberately did not use it (spike parity). Built-in support exists; using it would have added more framework lock-in. |
| LangGraph | 5 | `RunState` TypedDict **is** the memory. Explicit, inspectable, easy to serialise. LangGraph adds first-class checkpointing for true cross-session memory — out of scope for the spike but a strong point for the framework's production roadmap. |

### Tool access control (weight 2)

| Candidate | Score | Evidence |
|---|---:|---|
| Custom | 5 | Single `enforce_tool_access(role, tool_name, escalation_satisfied)` function reads the role's tool allowlist and `must_escalate` set. Trivial to extend to per-tool policies. |
| CrewAI | 2 | Tools are owned by the `Agent`. There is no "may hold but not invoke until escalated" policy. We work around this by **attaching `publisher_tool` to the agent only after founder approval** (`agent.tools = [publisher]`). It works, but it's runtime mutation of agent state — fragile and undeclarative. |
| LangGraph | 4 | Same `enforce_tool_access()` pattern as custom, called inside the publish node. Framework adds nothing on this axis. One point lower because no native concept to lean on. |

### Observability / debuggability (weight 2)

| Candidate | Score | Evidence |
|---|---:|---|
| Custom | 4 | `Runtime.trace` is a list of `TraceEvent` dataclasses, serialised to JSON. Every action shows up with role, input, output, timestamp. No vendor SDK to interrogate. |
| CrewAI | 2 | Verbose logs to stdout when `verbose=True`; structured traces require callback hooks or log parsing. We bypassed both and built our own `trace` list. **Critical finding**: CrewAI's call budget per Task is **not declarative** — `max_iter=1` does not bound LLM calls. The shared mock's `QueueExhausted` exception caught the executor retrying on parse failures. You cannot reason about cost without instrumenting. |
| LangGraph | 5 | The graph topology is a first-class artifact. `app.get_graph().draw_mermaid()` produces a diagram identical to [`scenarios/passly_launch.md`](../scenarios/passly_launch.md). Per-event trace via `state["trace"]` append in each node. One LLM call per draft/revise node, no implicit retries. Best of the three. |

### Dev experience (weight 2)

| Candidate | Score | Evidence |
|---|---:|---|
| Custom | 4 | Six small files, no framework concepts to learn. Total ~150 LOC of runtime + ~50 LOC of scenario wiring. The cost is **we wrote all of it** — but every line is in service of the thesis vocabulary. |
| CrewAI | 2 | Fast to get a single Agent + Task running, slow to make it do anything outside `Crew.kickoff()`'s opinions. The mock adaptation surfaced four substitution-friction items (see commit `d1c2e77`). Pulls ~150 transitive dependencies; pins Python ≤ 3.13 (required a venv rebuild). |
| LangGraph | 4 | More ceremony than custom (TypedDict, conditional edges, compile step). Less than CrewAI. The diagram-as-data property is the single biggest dev-experience win — you can show the topology to a stakeholder. One namespace footgun documented (folder name collides with the pip package; use `sys.path.append`). |

### Lock-in & cost (weight 1)

| Candidate | Score | Evidence |
|---|---:|---|
| Custom | 5 | Only direct dependency is `anthropic`. Vendor swap = swap `llm.py`. No version pins beyond `python >= 3.10`. |
| CrewAI | 2 | Depends on `litellm` (broad coverage, good) + ~150 transitive deps including `langchain`, `chromadb`, `pydantic-settings`, etc. Pins Python ≤ 3.13. Has had API churn between minor releases. Heavy. |
| LangGraph | 4 | BSD-licensed, runs locally. `langchain-anthropic` is the standard binding; vendor swap is a one-import change. Lighter dep tree than CrewAI. |

## Mock-substitution friction (the unscored-but-illuminating cost)

How hard was it to swap in a deterministic stub LLM? This isn't a rubric
criterion but it surfaces the framework's coupling to its LLM contract,
which is rubric evidence under "Lock-in & cost" and "Dev experience".

### Custom — **0 items**

The LLM is a one-method Protocol we own (`LLM.complete(system, user) -> str`). The mock implementation is trivial.

### CrewAI — **4 items**

1. **25-arg base class**: `crewai.LLM.__init__` takes ~25 kwargs we don't use; subclass still requires a litellm-recognised provider string at init (we passed `"anthropic/claude-haiku-4-5"` as a sentinel).
2. **Python version pin**: latest CrewAI requires Python ≤ 3.13. Project Homebrew default is 3.14, so the venv had to be rebuilt on 3.11.
3. **Output format coupling**: CrewAI's agent executor parses LLM output for `"Thought: …\nFinal Answer: …"`. Plain responses get rejected and re-prompted, blowing the call budget. The mock must wrap its canned text in that scaffold.
4. **Non-declarative call budget**: even with `max_iter=1` on the Agent, the executor can make multiple LLM calls per Task while parsing/retrying. Caught by the mock's `QueueExhausted`.

### LangGraph — **1 item**

1. **Namespace footgun**: spike folder is named `langgraph/`. With `spikes/` at `sys.path[0]`, Python treats `spikes/langgraph/` as a namespace-package fragment that shadows the installed `langgraph`, causing `from langgraph.graph import …` inside the spike's own `graph.py` to recurse. Fix is `sys.path.append`, documented inline. One-time cost; future framework code should avoid naming directories after pip-installable packages.

The duck-typed LLM contract was the biggest single win for LangGraph — a 25-line plain class with one `invoke()` method satisfies the contract. No subclassing, no pydantic, no parser format.

## Qualitative — real-LLM voice differences

Same model (`claude-haiku-4-5`), same brief, same scripted founder
feedback. Three different outputs preserved at
[`spike-evidence/`](spike-evidence/):

| Candidate | Register | Tagline | Word count |
|---|---|---|---:|
| Custom | Warm English with Greek tagline | "Passly—τα passes που δουλεύουν." | ~140 |
| CrewAI | Punchy English, agent-personality voice | "Απλά και δυνατά." | ~130 |
| LangGraph | Fully Greek, tightest copy | "Passly. Για τους δικούς μας." | ~75 |

The variance is *framework-induced* — same model, same prompts, three
voices. Worth a paragraph in Ch.5 on how each candidate's default
scaffolding around the LLM call shapes register independent of
explicit prompting.

## Decision

See [`adr/0001-framework-choice.md`](adr/0001-framework-choice.md).
