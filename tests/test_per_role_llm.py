"""Tests for per-role LLM routing on `Crew`.

The framework's `LLMClient` Protocol is substrate-neutral. The `Crew`
exposes that as a per-role routing map (`Crew.role_llms`); when no
override is set for a role, the crew default (`Crew.llm`) is used.

These tests pin three behaviours:

1. **Fallback.** A role with no entry in `role_llms` uses `crew.llm`.
2. **Override.** A role with an entry in `role_llms` uses that mapping.
3. **Independent traces.** Different LLMs called from different roles
   appear in their own call logs, not the crew default's log.

Notes on technique. We exploit the fact that `MockLLM` records every
call it serves in `MockLLM.calls`, so we can verify *which* LLM was
invoked for a given role by inspecting call counts on each LLM
instance. The recorded `system` prompt also lets us cross-check —
each role's system prompt is brief-bound and distinctive.
"""
from __future__ import annotations

import pytest

from solo_founder_crew import (
    Crew,
    DecisionRights,
    FounderDecision,
    MockLLM,
    Role,
    ScriptedHITL,
    ToolRegistry,
    VentureBrief,
    make_engineering,
    make_marketing,
)

PRESS = "Press release draft.\n"
SPEC = "Engineering spec draft.\n"


def _approve_now() -> ScriptedHITL:
    return ScriptedHITL([FounderDecision(action="approve")])


def _eng_tool_registry() -> ToolRegistry:
    """The engineering role uses `pr_tool`, not `publisher_tool`. The
    registry is wired with both so a single fixture can serve both roles."""
    registry = ToolRegistry()

    async def publisher(text: str) -> str:
        return f"published:{len(text)}"

    async def pr(text: str) -> str:
        return f"pr_opened:{len(text)}"

    registry.register(
        "publisher_tool", publisher, escalates="final_approval_before_publish"
    )
    registry.register("pr_tool", pr, escalates="merge_to_main")
    return registry


# ─── Fallback: no override → crew.llm is used ────────────────────────────────


async def test_crew_default_llm_used_when_no_override(
    brief: VentureBrief,
    marketing_role: Role,
    tool_registry: ToolRegistry,
) -> None:
    default_llm = MockLLM(responses=[PRESS])
    crew = Crew(
        brief=brief,
        roles=[marketing_role],
        llm=default_llm,
        hitl=_approve_now(),
        tools=tool_registry,
        # role_llms left empty — fallback to default
    )
    result = await crew.author_flow(task_description="x")
    assert result.status == "shipped"
    assert len(default_llm.calls) == 1
    assert default_llm.calls[0]["output"] == PRESS


# ─── Override: role_llms[name] wins ──────────────────────────────────────────


async def test_role_specific_llm_overrides_default(
    brief: VentureBrief,
    marketing_role: Role,
    tool_registry: ToolRegistry,
) -> None:
    default_llm = MockLLM(responses=["default-output"])  # should NOT be called
    role_llm = MockLLM(responses=[PRESS])

    crew = Crew(
        brief=brief,
        roles=[marketing_role],
        llm=default_llm,
        hitl=_approve_now(),
        tools=tool_registry,
        role_llms={"marketing": role_llm},
    )
    result = await crew.author_flow(task_description="x")

    assert result.status == "shipped"
    assert result.approved_artifact == PRESS  # came from role_llm, not default
    assert len(role_llm.calls) == 1
    assert len(default_llm.calls) == 0


# ─── Inert override: unknown role name is silently ignored ───────────────────


async def test_unknown_role_name_in_role_llms_is_inert(
    brief: VentureBrief,
    marketing_role: Role,
    tool_registry: ToolRegistry,
) -> None:
    """``role_llms`` keyed by a name not in ``crew.roles`` should not raise.

    This matters for the Crew Generator scenario: the same routing map can
    be reused across crews with different compositions; absent roles are
    simply unaffected.
    """
    default_llm = MockLLM(responses=[PRESS])
    ghost_llm = MockLLM(responses=["never-called"])

    crew = Crew(
        brief=brief,
        roles=[marketing_role],
        llm=default_llm,
        hitl=_approve_now(),
        tools=tool_registry,
        role_llms={"finance": ghost_llm},  # finance not in roles
    )
    result = await crew.author_flow(task_description="x")
    assert result.status == "shipped"
    assert len(default_llm.calls) == 1
    assert len(ghost_llm.calls) == 0


# ─── Multi-role crew: each role's LLM serves only its own actions ────────────


async def test_different_llms_for_different_roles_in_same_crew(
    brief: VentureBrief,
    marketing_role: Role,
) -> None:
    """In a multi-role crew, each role's flow uses its mapped LLM, even
    when both flows run from the same Crew instance."""
    tools = _eng_tool_registry()
    engineering_role = make_engineering(brief)

    marketing_llm = MockLLM(responses=[PRESS])
    engineering_llm = MockLLM(responses=[SPEC])

    crew = Crew(
        brief=brief,
        roles=[marketing_role, engineering_role],
        llm=marketing_llm,  # also serves as default
        hitl=_approve_now(),
        tools=tools,
        role_llms={"engineering": engineering_llm},
    )

    # Run 1: marketing flow → uses default (= marketing_llm).
    r1 = await crew.author_flow(task_description="x", role="marketing")
    assert r1.status == "shipped"
    assert r1.approved_artifact == PRESS

    # Reset trace & HITL queue between runs.
    crew.reset_trace()
    crew.hitl = _approve_now()

    # Run 2: engineering flow → uses role-specific LLM.
    r2 = await crew.author_flow(
        task_description="y", role="engineering", publish_tool="pr_tool"
    )
    assert r2.status == "shipped"
    assert r2.approved_artifact == SPEC

    # Each LLM saw exactly the calls intended for its role — no crosstalk.
    assert len(marketing_llm.calls) == 1
    assert len(engineering_llm.calls) == 1
    assert marketing_llm.calls[0]["output"] == PRESS
    assert engineering_llm.calls[0]["output"] == SPEC

    # Each role's system prompt is brief-bound and distinctive — the
    # adapter cannot have swapped them.
    assert "Marketing" in marketing_llm.calls[0]["system"]
    assert "Engineering" in engineering_llm.calls[0]["system"]


# ─── _llm_for() unit-level: direct API check ─────────────────────────────────


def test_llm_for_returns_override_or_default(
    brief: VentureBrief,
    marketing_role: Role,
    tool_registry: ToolRegistry,
) -> None:
    default_llm = MockLLM(responses=[])
    override_llm = MockLLM(responses=[])

    crew = Crew(
        brief=brief,
        roles=[marketing_role],
        llm=default_llm,
        hitl=_approve_now(),
        tools=tool_registry,
        role_llms={"marketing": override_llm},
    )

    assert crew._llm_for(marketing_role) is override_llm  # noqa: SLF001
    bogus = Role(
        name="ghost",
        goal="x",
        system_prompt="x",
        decision_rights=DecisionRights(can=(), must_escalate=()),
        tools=(),
    )
    assert crew._llm_for(bogus) is default_llm  # noqa: SLF001


# ─── AnthropicLLM is the preferred name; RealLLM is its alias ────────────────


def test_anthropic_llm_and_real_llm_are_the_same_class() -> None:
    """The Phase-1 examples and the spike runners import RealLLM. The
    public-API renaming to AnthropicLLM keeps the old name as an alias
    so nothing breaks."""
    from solo_founder_crew import AnthropicLLM, RealLLM

    assert AnthropicLLM is RealLLM
