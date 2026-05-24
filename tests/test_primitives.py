"""Unit tests for the framework primitives.

Covers: Role, DecisionRights, ToolRegistry, ScriptedHITL, VentureBrief,
RunTrace, MockLLM, load_dotenv. One test per claim worth defending in
Ch.3 prose.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from solo_founder_crew import (
    DecisionRights,
    FounderDecision,
    MockLLM,
    QueueExhausted,
    Role,
    RunTrace,
    ScriptedHITL,
    ToolPermissionError,
    ToolRegistry,
    TraceEvent,
    VentureBrief,
    load_dotenv,
)


# ─── Role + DecisionRights ───────────────────────────────────────────────────


def test_role_is_immutable(marketing_role: Role) -> None:
    """Roles are frozen so a Crew Generator can share instances safely."""
    with pytest.raises((AttributeError, Exception)):
        marketing_role.name = "other"  # type: ignore[misc]


def test_decision_rights_may_perform() -> None:
    rights = DecisionRights(
        can=("draft_content", "revise_content"),
        must_escalate=("final_approval",),
    )
    assert rights.may_perform("draft_content")
    assert rights.may_perform("revise_content")
    assert not rights.may_perform("publish")
    assert not rights.may_perform("final_approval")  # must escalate, not 'can'


def test_role_delegates_may_perform_to_rights(marketing_role: Role) -> None:
    assert marketing_role.may_perform("draft_content")
    assert not marketing_role.may_perform("publish")


# ─── ToolRegistry — the three failure modes ──────────────────────────────────


async def test_registry_blocks_unknown_tool(
    marketing_role: Role, tool_registry: ToolRegistry
) -> None:
    with pytest.raises(KeyError, match="unknown"):
        await tool_registry.invoke(marketing_role, "unknown", "x")


async def test_registry_blocks_role_without_allowlist(
    tool_registry: ToolRegistry,
) -> None:
    finance = Role(
        name="finance",
        goal="x",
        system_prompt="x",
        decision_rights=DecisionRights(can=(), must_escalate=()),
        tools=(),
    )
    with pytest.raises(ToolPermissionError, match="not allowed"):
        await tool_registry.invoke(finance, "publisher_tool", "x")


async def test_registry_blocks_missing_escalation(
    marketing_role: Role, tool_registry: ToolRegistry
) -> None:
    """Tool is in allowlist but escalation flag not set → blocked."""
    with pytest.raises(ToolPermissionError, match="escalation"):
        await tool_registry.invoke(marketing_role, "publisher_tool", "x")


async def test_registry_admits_escalated_call(
    marketing_role: Role, tool_registry: ToolRegistry
) -> None:
    result = await tool_registry.invoke(
        marketing_role, "publisher_tool", "draft", escalation_satisfied=True
    )
    assert result.startswith("shipped:")


async def test_registry_blocks_when_role_does_not_declare_escalation(
    tool_registry: ToolRegistry,
) -> None:
    """A role can have publisher_tool in its allowlist but lack the
    escalation action in must_escalate — registry must still refuse."""
    weird = Role(
        name="weird",
        goal="x",
        system_prompt="x",
        decision_rights=DecisionRights(can=("publish",), must_escalate=()),
        tools=("publisher_tool",),
    )
    with pytest.raises(ToolPermissionError, match="must_escalate"):
        await tool_registry.invoke(
            weird, "publisher_tool", "x", escalation_satisfied=True
        )


# ─── ScriptedHITL ────────────────────────────────────────────────────────────


async def test_scripted_hitl_returns_in_turn_order() -> None:
    hitl = ScriptedHITL(
        [
            FounderDecision(action="reject", feedback="more colour"),
            FounderDecision(action="approve"),
        ]
    )
    d1 = await hitl.review("draft1", turn=1)
    d2 = await hitl.review("draft2", turn=2)
    assert (d1.action, d1.feedback) == ("reject", "more colour")
    assert d2.action == "approve"


async def test_scripted_hitl_raises_when_exhausted() -> None:
    hitl = ScriptedHITL([FounderDecision(action="approve")])
    await hitl.review("draft", turn=1)
    with pytest.raises(RuntimeError, match="exhausted"):
        await hitl.review("draft", turn=2)


def test_scripted_hitl_from_file_roundtrips(tmp_path: Path) -> None:
    fixture = tmp_path / "responses.json"
    fixture.write_text(
        json.dumps(
            {
                "turns": [
                    {"turn": 1, "action": "reject", "feedback": "x"},
                    {"turn": 2, "action": "approve"},
                ]
            }
        )
    )
    hitl = ScriptedHITL.from_file(fixture)
    assert len(hitl._by_turn) == 2  # noqa: SLF001 - internal but stable


# ─── VentureBrief ────────────────────────────────────────────────────────────


def test_brief_validates_against_schema(brief: VentureBrief) -> None:
    """Loading the canonical Passly brief succeeds — i.e. the fixture
    and schema agree."""
    assert brief.venture_id == "passly"
    assert brief.name == "Passly"


def test_brief_dot_access_for_nested_fields(brief: VentureBrief) -> None:
    assert brief.domain.industry == "marketing-tech"
    assert "GR" in brief.domain.geography
    assert brief.voice.tone.startswith("Warm")


def test_brief_rejects_invalid_data() -> None:
    """A brief missing a required key fails schema validation."""
    with pytest.raises(jsonschema.ValidationError):
        VentureBrief({"venture_id": "x"})  # missing every other required field


def test_brief_validated_false_skips_schema() -> None:
    """Tests/fixtures can bypass validation when constructing partial briefs."""
    b = VentureBrief({"venture_id": "x", "name": "X"}, validated=False)
    assert b.venture_id == "x"


# ─── RunTrace ────────────────────────────────────────────────────────────────


def test_trace_records_and_writes(tmp_path: Path) -> None:
    trace = RunTrace(scenario="test_scenario")
    trace.record("marketing", "draft", input="brief", output="DRAFT")
    trace.record(
        "founder", "hitl_review", input="DRAFT", output="needs work", decision="reject"
    )
    out = tmp_path / "trace.json"
    trace.write(out)
    data = json.loads(out.read_text())
    assert data["scenario"] == "test_scenario"
    assert len(data["events"]) == 2
    assert data["events"][1]["decision"] == "reject"


def test_trace_clips_long_outputs() -> None:
    trace = RunTrace()
    long = "x" * 1000
    trace.record("r", "a", output=long)
    assert len(trace.events[0].output) <= 400


def test_trace_event_has_timestamp() -> None:
    e = TraceEvent(role="r", action="a")
    assert e.timestamp.endswith("+00:00")  # ISO with UTC offset


# ─── MockLLM ─────────────────────────────────────────────────────────────────


def test_mock_llm_returns_responses_in_order() -> None:
    llm = MockLLM(responses=["a", "b", "c"])
    assert llm.complete("sys", "u").text == "a"
    assert llm.complete("sys", "u").text == "b"
    assert llm.complete("sys", "u").text == "c"


def test_mock_llm_raises_when_exhausted() -> None:
    llm = MockLLM(responses=["only"])
    llm.complete("sys", "u")
    with pytest.raises(QueueExhausted, match="exhausted"):
        llm.complete("sys", "u")


def test_mock_llm_records_calls() -> None:
    llm = MockLLM(responses=["a", "b"])
    llm.complete("sys-1", "user-1")
    llm.complete("sys-2", "user-2")
    assert len(llm.calls) == 2
    assert llm.calls[0]["system"] == "sys-1"
    assert llm.calls[1]["user"] == "user-2"


# ─── load_dotenv ─────────────────────────────────────────────────────────────


def test_load_dotenv_reads_key_value_pairs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEMO_VAR", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text('# comment\nDEMO_VAR=hello\nWITH_QUOTES="quoted value"\n')
    assert load_dotenv(env_file)
    import os

    assert os.environ["DEMO_VAR"] == "hello"
    assert os.environ["WITH_QUOTES"] == "quoted value"


def test_load_dotenv_preserves_non_empty_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PRESERVED", "real")
    env_file = tmp_path / ".env"
    env_file.write_text("PRESERVED=overridden\n")
    load_dotenv(env_file)
    import os

    assert os.environ["PRESERVED"] == "real"


def test_load_dotenv_replaces_existing_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bug we fixed in fix(env) commit d8d8566 — existing-empty
    must be treated as unset, otherwise --real-llm silently broke
    in shells with ANTHROPIC_API_KEY pre-declared as empty."""
    monkeypatch.setenv("EMPTY_BEFORE", "")
    env_file = tmp_path / ".env"
    env_file.write_text("EMPTY_BEFORE=now-set\n")
    load_dotenv(env_file)
    import os

    assert os.environ["EMPTY_BEFORE"] == "now-set"


def test_load_dotenv_missing_file_is_noop(tmp_path: Path) -> None:
    assert load_dotenv(tmp_path / "absent.env") is False
