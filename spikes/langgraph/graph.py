"""LangGraph state machine for the Passly launch scenario.

Rubric evidence:
- Nodes (draft, hitl, revise, publish) make the flow visible as data — strong
  for observability and for the thesis (the diagram is the same as
  scenarios/passly_launch.md).
- HITL is implemented two ways: as a regular node that consults the scripted
  fixture (for deterministic spike runs), with comments showing where
  LangGraph's native `interrupt()` would slot in for real interactive use.
- State is a TypedDict — explicit, inspectable, serializable. Better fit for
  memory-across-turns than CrewAI's implicit memory.
- Tool gating is still manual (enforce_tool_access in the publish node).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from hitl import FounderDecision, ScriptedHITL
from roles import MARKETING, Role
from tools import PublisherTool, enforce_tool_access

# LLM construction now lives in llm.py (build_llm). The graph only
# requires state["llm"] to expose `.invoke(messages).content`.
MAX_REVISIONS = 1


class RunState(TypedDict, total=False):
    brief: dict
    role: Role
    draft: str
    feedback: str | None
    turn: int
    decision: dict
    approved: str | None
    publish_result: dict
    trace: list[dict]
    # injected at compile time
    llm: Any
    hitl: ScriptedHITL
    publisher: PublisherTool


def _append(state: RunState, event: dict) -> list[dict]:
    return [*state.get("trace", []), event]


def _draft_prompt(brief: dict, prior: str | None, feedback: str | None) -> str:
    parts = [
        "VENTURE BRIEF (authoritative):",
        json.dumps(brief, ensure_ascii=False, indent=2),
        "",
        "TASK: Draft a launch announcement. Match the voice. Respect every "
        "constraint. Keep under 150 words.",
    ]
    if prior is not None:
        parts += ["", "PRIOR DRAFT:", prior, "", f"FOUNDER FEEDBACK: {feedback or ''}",
                  "Produce a revised draft addressing the feedback."]
    return "\n".join(parts)


def draft_node(state: RunState) -> dict:
    role: Role = state["role"]
    if not role.may_perform("draft_content"):
        raise PermissionError(f"{role.name} cannot draft_content")
    prompt = _draft_prompt(state["brief"], prior=None, feedback=None)
    text = state["llm"].invoke(
        [("system", role.system_prompt), ("user", prompt)]
    ).content.strip()
    return {
        "draft": text,
        "turn": 1,
        "trace": _append(state, {"role": role.name, "action": "draft_content", "output_preview": text[:120]}),
    }


def hitl_node(state: RunState) -> dict:
    """Scripted gate. In a real deployment, swap for `interrupt()` —
    LangGraph would pause here and resume with the founder's input."""
    decision: FounderDecision = state["hitl"].review(turn=state["turn"])
    payload = {"action": decision.action, "feedback": decision.feedback}
    return {
        "decision": payload,
        "trace": _append(state, {
            "role": "founder", "action": "hitl_review",
            "turn": state["turn"], "decision": payload,
            "draft_preview": state["draft"][:120],
        }),
    }


def revise_node(state: RunState) -> dict:
    role: Role = state["role"]
    if not role.may_perform("revise_content"):
        raise PermissionError(f"{role.name} cannot revise_content")
    prompt = _draft_prompt(state["brief"], prior=state["draft"], feedback=state["decision"].get("feedback"))
    text = state["llm"].invoke(
        [("system", role.system_prompt), ("user", prompt)]
    ).content.strip()
    return {
        "draft": text,
        "turn": state["turn"] + 1,
        "trace": _append(state, {"role": role.name, "action": "revise_content", "output_preview": text[:120]}),
    }


def publish_node(state: RunState) -> dict:
    role: Role = state["role"]
    publisher: PublisherTool = state["publisher"]
    enforce_tool_access(role, publisher.name, escalation_satisfied=True)
    result = publisher.publish(state["draft"])
    return {
        "approved": state["draft"],
        "publish_result": result,
        "trace": _append(state, {
            "role": role.name, "action": "publisher_tool.publish",
            "input": {"chars": len(state["draft"])}, "output": result,
        }),
    }


def route_after_hitl(state: RunState) -> str:
    action = state["decision"]["action"]
    if action == "approve":
        return "publish"
    if action == "kill":
        return END
    if action == "reject" and state["turn"] <= MAX_REVISIONS:
        return "revise"
    return END  # revision budget exhausted


def build_graph():
    g: StateGraph = StateGraph(RunState)
    g.add_node("draft", draft_node)
    g.add_node("hitl", hitl_node)
    g.add_node("revise", revise_node)
    g.add_node("publish", publish_node)

    g.add_edge(START, "draft")
    g.add_edge("draft", "hitl")
    g.add_conditional_edges("hitl", route_after_hitl,
                            {"publish": "publish", "revise": "revise", END: END})
    g.add_edge("revise", "hitl")
    g.add_edge("publish", END)
    return g.compile()
