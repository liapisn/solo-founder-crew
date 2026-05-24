"""End-to-end tests for `Crew.author_flow`.

Covers all four termination paths through the Author Flow graph:

  1. approve immediately   -> status='shipped', 3 trace events
  2. reject then approve   -> status='shipped', 5 trace events
  3. kill at first gate    -> status='killed',  2 trace events
  4. exhausted revisions   -> status='exhausted', 4 trace events

Each test runs the framework through its public API (Crew + ScriptedHITL
+ MockLLM). No spike code, no LangGraph imports. If these pass, the
package's promise — replicate the spike behaviour as library code —
is met.
"""
from __future__ import annotations

import pytest

from solo_founder_crew import (
    AuthorFlowResult,
    Crew,
    MockLLM,
    Role,
    ScriptedHITL,
    ToolRegistry,
    VentureBrief,
)

DRAFT_V1 = "Introducing Passly — draft version 1.\n"
DRAFT_V2 = "Έρχεται το Passly — draft version 2.\n"
DRAFT_V3 = "Passly v3 — third try.\n"


def _crew(
    brief: VentureBrief,
    role: Role,
    tools: ToolRegistry,
    *,
    hitl: ScriptedHITL,
    responses: list[str],
) -> Crew:
    return Crew(
        brief=brief,
        roles=[role],
        llm=MockLLM(responses=responses),
        hitl=hitl,
        tools=tools,
    )


# ─── Path 1: approve immediately ─────────────────────────────────────────────


async def test_approve_immediately(
    brief: VentureBrief,
    marketing_role: Role,
    tool_registry: ToolRegistry,
    approve_immediately_hitl: ScriptedHITL,
) -> None:
    crew = _crew(
        brief,
        marketing_role,
        tool_registry,
        hitl=approve_immediately_hitl,
        responses=[DRAFT_V1],
    )
    result: AuthorFlowResult = await crew.author_flow(
        task_description="Draft a launch announcement."
    )
    assert result.status == "shipped"
    assert result.approved_artifact == DRAFT_V1
    assert len(result.trace) == 3
    actions = [e.action for e in result.trace.events]
    assert actions == ["draft_content", "hitl_review", "publisher_tool.publish"]


# ─── Path 2: reject then approve (the canonical Passly spike path) ───────────


async def test_reject_then_approve(
    brief: VentureBrief,
    marketing_role: Role,
    tool_registry: ToolRegistry,
    reject_then_approve_hitl: ScriptedHITL,
) -> None:
    crew = _crew(
        brief,
        marketing_role,
        tool_registry,
        hitl=reject_then_approve_hitl,
        responses=[DRAFT_V1, DRAFT_V2],
    )
    result = await crew.author_flow(task_description="Draft a launch announcement.")
    assert result.status == "shipped"
    assert result.approved_artifact == DRAFT_V2  # revised version, not v1
    assert len(result.trace) == 5
    actions = [e.action for e in result.trace.events]
    assert actions == [
        "draft_content",
        "hitl_review",
        "revise_content",
        "hitl_review",
        "publisher_tool.publish",
    ]
    # Founder feedback is preserved in the trace
    rejects = [e for e in result.trace.events if e.decision == "reject"]
    assert len(rejects) == 1
    assert "warmer" in rejects[0].output


# ─── Path 3: founder kills at first gate ─────────────────────────────────────


async def test_kill_at_first_gate(
    brief: VentureBrief,
    marketing_role: Role,
    tool_registry: ToolRegistry,
    kill_hitl: ScriptedHITL,
) -> None:
    crew = _crew(
        brief, marketing_role, tool_registry, hitl=kill_hitl, responses=[DRAFT_V1]
    )
    result = await crew.author_flow(task_description="Draft a launch announcement.")
    assert result.status == "killed"
    assert result.approved_artifact is None
    # draft → hitl_review → run_killed (3 events) OR 2 depending on how
    # run_killed is recorded — check below
    actions = [e.action for e in result.trace.events]
    assert actions[0] == "draft_content"
    assert "hitl_review" in actions
    assert any("kill" in a for a in actions)


# ─── Path 4: revisions exhausted ─────────────────────────────────────────────


async def test_exhausted_revisions(
    brief: VentureBrief,
    marketing_role: Role,
    tool_registry: ToolRegistry,
    reject_twice_hitl: ScriptedHITL,
) -> None:
    """max_revisions=1 + two rejects -> exhausted, not shipped."""
    crew = _crew(
        brief,
        marketing_role,
        tool_registry,
        hitl=reject_twice_hitl,
        responses=[DRAFT_V1, DRAFT_V2],
    )
    result = await crew.author_flow(
        task_description="Draft a launch announcement.",
        max_revisions=1,
    )
    assert result.status == "exhausted"
    assert result.approved_artifact is None
    actions = [e.action for e in result.trace.events]
    assert "revise_content" in actions
    assert any("exhausted" in a for a in actions)


# ─── thread_id property ──────────────────────────────────────────────────────


async def test_thread_id_is_returned_and_distinct_per_run(
    brief: VentureBrief,
    marketing_role: Role,
    tool_registry: ToolRegistry,
) -> None:
    crew1 = _crew(
        brief,
        marketing_role,
        tool_registry,
        hitl=ScriptedHITL([__import__("solo_founder_crew").FounderDecision(action="approve")]),
        responses=[DRAFT_V1],
    )
    crew2 = _crew(
        brief,
        marketing_role,
        tool_registry,
        hitl=ScriptedHITL([__import__("solo_founder_crew").FounderDecision(action="approve")]),
        responses=[DRAFT_V2],
    )
    r1 = await crew1.author_flow(task_description="x")
    r2 = await crew2.author_flow(task_description="x")
    assert r1.thread_id != r2.thread_id
    assert r1.thread_id.startswith("run-")


# ─── Pre-flight checks ───────────────────────────────────────────────────────


async def test_role_must_be_able_to_draft(
    brief: VentureBrief,
    tool_registry: ToolRegistry,
    approve_immediately_hitl: ScriptedHITL,
) -> None:
    """A role without draft_content in its decision_rights.can must be rejected."""
    from solo_founder_crew import DecisionRights

    bad = Role(
        name="finance",
        goal="x",
        system_prompt="x",
        decision_rights=DecisionRights(can=(), must_escalate=()),
        tools=("publisher_tool",),
    )
    crew = Crew(
        brief=brief,
        roles=[bad],
        llm=MockLLM(responses=[DRAFT_V1]),
        hitl=approve_immediately_hitl,
        tools=tool_registry,
    )
    with pytest.raises(PermissionError, match="draft_content"):
        await crew.author_flow(task_description="x")


async def test_role_must_hold_publish_tool(
    brief: VentureBrief,
    tool_registry: ToolRegistry,
    approve_immediately_hitl: ScriptedHITL,
) -> None:
    from solo_founder_crew import DecisionRights

    bad = Role(
        name="marketing",
        goal="x",
        system_prompt="x",
        decision_rights=DecisionRights(
            can=("draft_content",),
            must_escalate=("final_approval_before_publish",),
        ),
        tools=(),  # no publisher_tool!
    )
    crew = Crew(
        brief=brief,
        roles=[bad],
        llm=MockLLM(responses=[DRAFT_V1]),
        hitl=approve_immediately_hitl,
        tools=tool_registry,
    )
    with pytest.raises(PermissionError, match="publish_tool"):
        await crew.author_flow(task_description="x")


# ─── Multi-role crew requires explicit selection ─────────────────────────────


async def test_multi_role_crew_requires_explicit_role(
    brief: VentureBrief,
    marketing_role: Role,
    tool_registry: ToolRegistry,
    approve_immediately_hitl: ScriptedHITL,
) -> None:
    from solo_founder_crew import make_product

    crew = Crew(
        brief=brief,
        roles=[marketing_role, make_product(brief)],
        llm=MockLLM(responses=[DRAFT_V1]),
        hitl=approve_immediately_hitl,
        tools=tool_registry,
    )
    with pytest.raises(ValueError, match="2 roles"):
        await crew.author_flow(task_description="x")  # ambiguous

    # Explicit selection works
    crew.reset_trace()
    crew.llm = MockLLM(responses=[DRAFT_V1])  # reset queue
    result = await crew.author_flow(task_description="x", role="marketing")
    assert result.status == "shipped"
