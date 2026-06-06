"""Tests for the crew daemon's pure core (app.py) — no Discord gateway.

The Discord-facing ``run()`` and slash commands are exercised live, not here.
Everything testable without a gateway connection is covered with an
``InMemoryTransport`` + ``MemorySaver``.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from solo_founder_crew import (
    FounderResponse,
    MockLLM,
    make_customer_support,
    make_engineering,
    make_marketing,
)
from solo_founder_crew.app import (
    PlaceholderLLM,
    build_crew,
    build_tools,
    channels_for,
    consult_prompt,
    open_checkpointer,
    publish_tool_for,
)
from solo_founder_crew.adapters.discord_hitl import InMemoryTransport
from solo_founder_crew.config import RuntimeConfig

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIEF = REPO_ROOT / "scenarios" / "fixtures" / "passly_brief.json"


def _config(**overrides) -> RuntimeConfig:
    base = dict(
        brief_path=BRIEF,
        model="mock",
        checkpointer_url="memory",
        guild_id=None,
        discord_token=None,
        channel_map={"marketing": "CM"},
        default_channel_id="CDEFAULT",
    )
    base.update(overrides)
    return RuntimeConfig(**base)


# ─── tools + publish-tool selection ─────────────────────────────────────────────


def test_build_tools_registers_both_publish_tools() -> None:
    tools = build_tools()
    # both names registered (smoke: they're in the private map)
    assert "publisher_tool" in tools._tools  # noqa: SLF001
    assert "pr_tool" in tools._tools  # noqa: SLF001


def test_publish_tool_for_picks_the_roles_tool(brief) -> None:
    assert publish_tool_for(make_marketing(brief)) == "publisher_tool"
    assert publish_tool_for(make_engineering(brief)) == "pr_tool"


def test_channels_for_is_kebab_cased_and_deduped(brief) -> None:
    chans = channels_for(
        [make_marketing(brief), make_customer_support(brief), make_marketing(brief)]
    )
    assert chans == ["marketing", "customer-support"]  # snake→kebab, no dupes


def test_consult_prompt_carries_brief_and_question() -> None:
    p = consult_prompt({"name": "Passly"}, "what should we build next?")
    assert "what should we build next?" in p
    assert "Passly" in p
    assert "advice" in p.lower() or "advis" in p.lower()


def test_placeholder_llm_is_deterministic_and_offline() -> None:
    llm = PlaceholderLLM()
    r1 = llm.complete("sys", "draft something")
    r2 = llm.complete("sys", "draft again")
    assert "placeholder" in r1.text.lower()
    assert r1.text == r2.text
    assert (r1.call_index, r2.call_index) == (0, 1)


# ─── build_crew ──────────────────────────────────────────────────────────────


def test_build_crew_uses_generated_roster() -> None:
    crew, hitl = build_crew(_config(), transport=InMemoryTransport())
    # pre-launch Passly → marketing, product, engineering
    names = [r.name for r in crew.roles]
    assert names == ["marketing", "product", "engineering"]
    assert isinstance(crew.llm, PlaceholderLLM)  # mock model → placeholder


async def test_build_crew_runs_author_flow_end_to_end() -> None:
    from langgraph.checkpoint.memory import MemorySaver

    transport = InMemoryTransport()
    crew, hitl = build_crew(
        _config(),
        transport=transport,
        llm=MockLLM(responses=["Launch copy for Passly."]),
        checkpointer=MemorySaver(),
    )

    async def tap_approve() -> None:
        while not hitl.pending_request_ids():
            await asyncio.sleep(0)
        rid = hitl.pending_request_ids()[0]
        hitl.submit_response(FounderResponse(request_id=rid, action="approve"))

    marketing = crew.role("marketing")
    result, _ = await asyncio.gather(
        crew.author_flow(
            task_description="Draft a launch announcement.",
            role=marketing,
            publish_tool=publish_tool_for(marketing),
            thread_id="run-1",
        ),
        tap_approve(),
    )
    assert result.status == "shipped"
    channel_id, posted = transport.posted[0]
    assert channel_id == "CM"  # marketing → mapped channel
    assert posted.role_name == "marketing"


# ─── checkpointer ────────────────────────────────────────────────────────────


async def test_open_checkpointer_memory() -> None:
    from langgraph.checkpoint.memory import MemorySaver

    async with open_checkpointer("memory") as cp:
        assert isinstance(cp, MemorySaver)


async def test_open_checkpointer_sqlite(tmp_path) -> None:
    pytest.importorskip("langgraph.checkpoint.sqlite.aio")
    db = tmp_path / "state.db"
    async with open_checkpointer(f"sqlite:///{db}") as cp:
        assert cp is not None
    assert db.exists()
