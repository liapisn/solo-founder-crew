"""Shared fixtures for the framework test suite."""
from __future__ import annotations

from pathlib import Path

import pytest

from solo_founder_crew import (
    DecisionRights,
    FounderDecision,
    Role,
    ScriptedHITL,
    ToolRegistry,
    VentureBrief,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PASSLY_BRIEF = REPO_ROOT / "scenarios" / "fixtures" / "passly_brief.json"


@pytest.fixture
def brief() -> VentureBrief:
    """The canonical Passly Venture Brief."""
    return VentureBrief.from_file(PASSLY_BRIEF)


@pytest.fixture
def marketing_role() -> Role:
    """A minimal Marketing role for tests that don't need the full library version."""
    return Role(
        name="marketing",
        goal="Draft customer-facing announcements.",
        system_prompt="You are Marketing.",
        decision_rights=DecisionRights(
            can=("draft_content", "revise_content"),
            must_escalate=("final_approval_before_publish",),
        ),
        tools=("publisher_tool",),
    )


@pytest.fixture
def tool_registry() -> ToolRegistry:
    """A registry with a stub publisher_tool that escalates."""
    registry = ToolRegistry()

    async def publisher(text: str) -> str:
        return f"shipped:{len(text)}"

    registry.register(
        "publisher_tool", publisher, escalates="final_approval_before_publish"
    )
    return registry


@pytest.fixture
def approve_immediately_hitl() -> ScriptedHITL:
    return ScriptedHITL([FounderDecision(action="approve")])


@pytest.fixture
def reject_then_approve_hitl() -> ScriptedHITL:
    return ScriptedHITL(
        [
            FounderDecision(action="reject", feedback="warmer tone please"),
            FounderDecision(action="approve"),
        ]
    )


@pytest.fixture
def kill_hitl() -> ScriptedHITL:
    return ScriptedHITL([FounderDecision(action="kill")])


@pytest.fixture
def reject_twice_hitl() -> ScriptedHITL:
    """Two rejects in a row — exhausts max_revisions=1."""
    return ScriptedHITL(
        [
            FounderDecision(action="reject", feedback="more"),
            FounderDecision(action="reject", feedback="still no"),
        ]
    )
