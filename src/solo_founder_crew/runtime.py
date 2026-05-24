"""Component 4 — Orchestration Runtime over LangGraph.

This module implements **Author Flow** — the framework's canonical
solo-founder content pattern:

    draft → founder review → (revise → review){0,N} → publish

It is *one* flow built on the framework's primitives. Additional flows
(decision-deliberation, triage) arrive in Phase 3 and share the same
state and trace shape.

Design notes worth citing in Ch.3 §"Orchestration Runtime":

- **State carries data; services live in closures.** `AuthorFlowState`
  is a TypedDict containing only JSON-serialisable values (brief, role,
  draft, turn, decision). The `LLMClient`, `HITLContract`, and
  `ToolRegistry` are captured by node factories. This separation makes
  the Phase 4 checkpointer trivially correct — there is no live object
  in the state to serialise.

- **DecisionRights enforced inside the nodes.** Each LLM-calling node
  (`draft_node`, `revise_node`) checks `role.may_perform(action)`
  before issuing the call. PermissionError surfaces from the runtime,
  not from the LLM client.

- **Conditional edges encode the HITL semantics.** Approve → publish;
  reject + budget remaining → revise; otherwise END. The router is the
  framework's machine-readable version of the prose HITL spec.

- **The trace is appended by every node**, including the founder
  review node — same trace shape as the spikes (`role`, `action`,
  `input`, `output`, `decision`, `timestamp`).
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from solo_founder_crew.brief import VentureBrief
from solo_founder_crew.hitl import FounderDecision, HITLContract
from solo_founder_crew.llm import LLMClient
from solo_founder_crew.role import Role
from solo_founder_crew.tools import ToolRegistry
from solo_founder_crew.trace import RunTrace

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph.state import CompiledStateGraph


# Default action names. Custom values can be passed to `build_author_graph`.
DRAFT_ACTION = "draft_content"
REVISE_ACTION = "revise_content"
ESCALATION_ACTION = "final_approval_before_publish"


class AuthorFlowState(TypedDict, total=False):
    """Serialisable state for an Author Flow run.

    Services (`LLMClient`, `HITLContract`, `ToolRegistry`) are NOT in
    state — see module docstring. The state alone is enough to
    checkpoint/resume in Phase 4.
    """

    # Inputs (set once at start)
    brief: dict[str, Any]
    role: dict[str, Any]
    task_description: str
    max_revisions: int
    publish_tool: str

    # Mutates during the run
    draft: str
    turn: int
    decision: dict[str, Any]
    approved_artifact: str | None
    publish_result: Any
    status: str  # "shipped" | "killed" | "exhausted"


# ─── Prompt assembly ─────────────────────────────────────────────────────────


def _build_author_prompt(
    brief: dict[str, Any],
    task_description: str,
    *,
    prior_draft: str | None = None,
    founder_feedback: str | None = None,
) -> str:
    """Compose the user prompt for a draft or revise step.

    Kept here (not in the Role) so the Role stays declarative. The
    Crew/runtime owns *how* the brief enters the conversation; the
    Role owns *who* the conversation is with.
    """
    sections = [
        "VENTURE BRIEF (authoritative — match its voice and respect every constraint):",
        json.dumps(brief, ensure_ascii=False, indent=2),
        "",
        f"TASK: {task_description}",
    ]
    if prior_draft is not None:
        sections += [
            "",
            "PRIOR DRAFT (founder rejected — do not repeat its mistakes):",
            prior_draft,
            "",
            f"FOUNDER FEEDBACK: {founder_feedback or '(no specific guidance)'}",
            "",
            "Produce a revised draft that addresses the feedback.",
        ]
    return "\n".join(sections)


# ─── Node factories ──────────────────────────────────────────────────────────
#
# Each factory closes over the runtime services and returns an async node
# function. The closure pattern is what keeps services out of the
# serialisable state — see module docstring.


def _make_draft_node(
    llm: LLMClient,
    role: Role,
    trace: RunTrace,
):
    async def draft_node(state: AuthorFlowState) -> dict[str, Any]:
        if not role.may_perform(DRAFT_ACTION):
            raise PermissionError(
                f"Role {role.name!r} cannot perform {DRAFT_ACTION!r}"
            )
        prompt = _build_author_prompt(state["brief"], state["task_description"])
        resp = await asyncio.to_thread(llm.complete, role.system_prompt, prompt)
        trace.record(
            role=role.name,
            action=DRAFT_ACTION,
            input=state["task_description"],
            output=resp.text,
        )
        return {"draft": resp.text, "turn": 1}

    return draft_node


def _make_hitl_node():
    """HITL gate as a LangGraph interrupt point.

    The node calls ``interrupt(payload)``, which pauses the graph and
    checkpoints state. The runner outside the graph
    (``Crew.author_flow``) fetches a ``FounderDecision`` via the
    configured ``HITLContract`` and resumes with ``Command(resume=…)``.

    On resume, the node body runs *again* from the top — that's how
    LangGraph delivers the resumed value. So the node MUST be
    idempotent up to the ``interrupt()`` call. We keep it
    side-effect-free: trace recording for the founder review happens
    in the runner, not here.
    """

    async def hitl_node(state: AuthorFlowState) -> dict[str, Any]:
        decision_payload = interrupt(
            {
                "artifact": state["draft"],
                "turn": state["turn"],
            }
        )
        # decision_payload is the dict the runner passed to Command(resume=...)
        return {"decision": decision_payload}

    return hitl_node


def _make_revise_node(
    llm: LLMClient,
    role: Role,
    trace: RunTrace,
):
    async def revise_node(state: AuthorFlowState) -> dict[str, Any]:
        if not role.may_perform(REVISE_ACTION):
            raise PermissionError(
                f"Role {role.name!r} cannot perform {REVISE_ACTION!r}"
            )
        prompt = _build_author_prompt(
            state["brief"],
            state["task_description"],
            prior_draft=state["draft"],
            founder_feedback=state["decision"].get("feedback"),
        )
        resp = await asyncio.to_thread(llm.complete, role.system_prompt, prompt)
        trace.record(
            role=role.name,
            action=REVISE_ACTION,
            input=state["decision"].get("feedback") or "",
            output=resp.text,
        )
        return {"draft": resp.text, "turn": state["turn"] + 1}

    return revise_node


def _make_publish_node(
    tools: ToolRegistry,
    role: Role,
    trace: RunTrace,
):
    async def publish_node(state: AuthorFlowState) -> dict[str, Any]:
        approved = state["draft"]
        result = await tools.invoke(
            role,
            state["publish_tool"],
            approved,
            escalation_satisfied=True,  # we got here only after `approve`
        )
        trace.record(
            role=role.name,
            action=f"{state['publish_tool']}.publish",
            input=f"{len(approved)} chars",
            output=str(result),
        )
        return {
            "approved_artifact": approved,
            "publish_result": result,
            "status": "shipped",
        }

    return publish_node


def _make_kill_node(trace: RunTrace):
    async def kill_node(_: AuthorFlowState) -> dict[str, Any]:
        trace.record(role="founder", action="run_killed")
        return {"status": "killed", "approved_artifact": None}

    return kill_node


def _make_exhausted_node(trace: RunTrace):
    async def exhausted_node(_: AuthorFlowState) -> dict[str, Any]:
        trace.record(role="founder", action="revision_budget_exhausted")
        return {"status": "exhausted", "approved_artifact": None}

    return exhausted_node


# ─── Router ──────────────────────────────────────────────────────────────────


def _route_after_hitl(state: AuthorFlowState) -> str:
    action = state["decision"]["action"]
    if action == "approve":
        return "publish"
    if action == "kill":
        return "kill"
    if action == "reject":
        if state["turn"] <= state["max_revisions"]:
            return "revise"
        return "exhausted"
    raise ValueError(
        f"Unknown founder decision action: {action!r} "
        f"(expected one of: approve, reject, kill)"
    )


# ─── Public graph builder ────────────────────────────────────────────────────


@dataclass
class AuthorFlowGraph:
    """A compiled Author Flow graph plus its trace.

    The trace is the same object the nodes append to during the run,
    so it accumulates events in execution order without the caller
    having to pull anything out of the final state.
    """

    compiled: "CompiledStateGraph"
    trace: RunTrace


def build_author_graph(
    *,
    role: Role,
    llm: LLMClient,
    tools: ToolRegistry,
    trace: RunTrace | None = None,
    checkpointer: "BaseCheckpointSaver | None" = None,
) -> AuthorFlowGraph:
    """Compose the Author Flow StateGraph and compile it with a checkpointer.

    The HITL gate is implemented as a LangGraph ``interrupt()`` (see
    ``_make_hitl_node``). The caller drives the interrupt loop via
    ``Crew.author_flow``; this function only knows how to build the
    graph.

    ``checkpointer`` defaults to in-process ``MemorySaver`` — enough
    for tests and same-process interactive runs. Pass a SqliteSaver
    or any other ``BaseCheckpointSaver`` for cross-process resume.
    """
    if trace is None:
        trace = RunTrace()
    if checkpointer is None:
        checkpointer = MemorySaver()

    g: StateGraph = StateGraph(AuthorFlowState)
    g.add_node("draft", _make_draft_node(llm, role, trace))
    g.add_node("hitl", _make_hitl_node())
    g.add_node("revise", _make_revise_node(llm, role, trace))
    g.add_node("publish", _make_publish_node(tools, role, trace))
    g.add_node("kill", _make_kill_node(trace))
    g.add_node("exhausted", _make_exhausted_node(trace))

    g.add_edge(START, "draft")
    g.add_edge("draft", "hitl")
    g.add_conditional_edges(
        "hitl",
        _route_after_hitl,
        {
            "publish": "publish",
            "revise": "revise",
            "kill": "kill",
            "exhausted": "exhausted",
        },
    )
    g.add_edge("revise", "hitl")
    g.add_edge("publish", END)
    g.add_edge("kill", END)
    g.add_edge("exhausted", END)

    return AuthorFlowGraph(compiled=g.compile(checkpointer=checkpointer), trace=trace)
