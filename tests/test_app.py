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
    role_display,
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


async def test_build_tools_uses_provided_publisher(brief) -> None:
    seen = {}

    async def pub(text: str) -> str:
        seen["text"] = text
        return "ok-published"

    tools = build_tools(publisher=pub)
    role = make_marketing(brief)  # holds publisher_tool, escalates publish
    out = await tools.invoke(
        role, "publisher_tool", "the approved copy", escalation_satisfied=True
    )
    assert out == "ok-published"
    assert seen["text"] == "the approved copy"


def test_publish_tool_for_picks_the_roles_tool(brief) -> None:
    assert publish_tool_for(make_marketing(brief)) == "publisher_tool"
    assert publish_tool_for(make_engineering(brief)) == "pr_tool"


def test_channels_for_is_kebab_cased_and_deduped(brief) -> None:
    chans = channels_for(
        [make_marketing(brief), make_customer_support(brief), make_marketing(brief)]
    )
    assert chans == ["marketing", "customer-support"]  # snake→kebab, no dupes


def test_role_display_titlecases_kebab() -> None:
    assert role_display("customer-support") == "Customer Support"
    assert role_display("engineering") == "Engineering"


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


async def test_author_flow_with_async_sqlite_checkpointer(tmp_path) -> None:
    """Run the full gate loop against a real AsyncSqliteSaver — the durable
    path the daemon uses. Catches sync-vs-async checkpointer access bugs
    (the previous _pending_interrupt used sync get_state, which blows up on
    AsyncSqliteSaver)."""
    pytest.importorskip("langgraph.checkpoint.sqlite.aio")
    transport = InMemoryTransport()
    async with open_checkpointer(f"sqlite:///{tmp_path}/state.db") as cp:
        crew, hitl = build_crew(
            _config(),
            transport=transport,
            llm=MockLLM(responses=["Launch copy."]),
            checkpointer=cp,
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
                thread_id="run-sqlite",
            ),
            tap_approve(),
        )
        assert result.status == "shipped"


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
        # Exercise the path that actually runs during a flow (aget_tuple →
        # setup) — this is where a langgraph-checkpoint-sqlite / aiosqlite
        # version mismatch (Connection.is_alive) blew up. Opening alone
        # wasn't enough to catch it.
        assert await cp.aget_tuple({"configurable": {"thread_id": "t"}}) is None
    assert db.exists()


# ─── drive_resume: the shared path behind /retry and startup respawn ─────────
#
# A run that dies after the founder approved used to be unrecoverable: the
# daemon logged `error: …` and the approved artefact was never published.
# `drive_resume` is what brings it back, so the states it can end in are
# worth pinning even though the slash command around it is not testable
# without a gateway.


class _StubCrew:
    """Minimal stand-in for ``Crew``: one role, a scripted ``resume``."""

    def __init__(self, role, outcome) -> None:
        self._role = role
        self._outcome = outcome  # an object to return, or an exception to raise
        self.resumed: list[str] = []

    def role(self, name: str):  # noqa: ANN201 - mirrors Crew.role
        return self._role

    async def resume(self, *, thread_id: str, role, publish_tool: str):  # noqa: ANN001
        self.resumed.append(thread_id)
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


class _Result:
    def __init__(self, status: str, publish_result: str = "") -> None:
        self.status = status
        self.final_state = {"publish_result": publish_result}


def _record(**overrides):  # noqa: ANN201
    from solo_founder_crew.runs_registry import RunRecord

    base = dict(
        thread_id="run-1",
        role="marketing",
        task="Draft a teaser",
        revisions=3,
        logical_channel="marketing",
        status="error: publish exploded",
    )
    base.update(overrides)
    return RunRecord(**base)


def _registry_with(tmp_path, record):  # noqa: ANN201
    from solo_founder_crew.runs_registry import RunsRegistry

    registry = RunsRegistry(tmp_path / "runs.json")
    registry.put(record)
    return registry


async def test_drive_resume_completes_a_failed_run(tmp_path, brief) -> None:
    """The happy retry: the run reaches a terminal status, and every
    surface the founder can look at is updated to say so."""
    from solo_founder_crew.app import drive_resume
    from solo_founder_crew.events import RecordingEventSink

    record = _record()
    registry = _registry_with(tmp_path, record)
    runs: dict = {}
    announced: list[tuple] = []
    sink = RecordingEventSink()

    async def announce(*args) -> None:
        announced.append(args)

    outcome = await drive_resume(
        crew=_StubCrew(make_marketing(brief), _Result("shipped", "published to #x")),
        registry=registry,
        runs=runs,
        record=record,
        announce=announce,
        sink=sink,
    )

    assert "shipped" in outcome
    assert registry.get("run-1").status == "shipped"
    assert runs["run-1"]["status"] == "shipped"
    # The announcement carries the thread id, which is what lets the role
    # channel print a usable `/retry run:…` when things go the other way.
    assert announced == [("marketing", "shipped", 3, "run-1")]
    assert sink.kinds == ["run_finished"]


async def test_drive_resume_keeps_a_run_that_fails_again(tmp_path, brief) -> None:
    """A retry that fails is reported, not swallowed — and the record
    survives, so the founder can retry once more after fixing the cause."""
    from solo_founder_crew.app import drive_resume
    from solo_founder_crew.events import RecordingEventSink

    record = _record()
    registry = _registry_with(tmp_path, record)
    runs: dict = {}
    announced: list[tuple] = []
    sink = RecordingEventSink()

    async def announce(*args) -> None:
        announced.append(args)

    outcome = await drive_resume(
        crew=_StubCrew(make_marketing(brief), RuntimeError("still broken")),
        registry=registry,
        runs=runs,
        record=record,
        announce=announce,
        sink=sink,
    )

    assert "still broken" in outcome
    assert registry.get("run-1") is not None  # retryable again
    assert registry.get("run-1").status.startswith("error:")
    assert announced[0][1].startswith("error:")
    assert sink.kinds == ["error"]


async def test_drive_resume_drops_a_run_the_checkpointer_forgot(
    tmp_path, brief
) -> None:
    """No saved state means there is nothing to retry — the record is a
    phantom and is removed rather than left in `/status` forever."""
    from solo_founder_crew.app import drive_resume

    record = _record()
    registry = _registry_with(tmp_path, record)
    runs = {"run-1": {"role": "marketing", "task": "x", "status": "error: boom"}}

    async def announce(*args) -> None:
        raise AssertionError("a dropped run has no outcome to announce")

    outcome = await drive_resume(
        crew=_StubCrew(make_marketing(brief), KeyError("run-1")),
        registry=registry,
        runs=runs,
        record=record,
        announce=announce,
        sink=None,
    )

    assert "no saved state" in outcome.lower()
    assert registry.get("run-1") is None
    assert "run-1" not in runs


async def test_retry_publishes_a_run_that_died_after_approval(tmp_path) -> None:
    """The whole reported failure, end to end on the daemon's own path.

    A run is approved, the publish tool blows up, the driver dies. Before
    the fix this was terminal: the founder's approval was consumed and the
    artefact never left the process. Now `/retry`'s ``drive_resume`` picks
    the run up from the checkpoint, re-runs *only* the publish step, and
    the artefact ships without the founder being asked twice.
    """
    from langgraph.checkpoint.memory import MemorySaver

    from solo_founder_crew.app import drive_resume
    from solo_founder_crew.runs_registry import RunRecord, RunsRegistry

    published: list[str] = []
    fail_next = True

    async def flaky_publisher(text: str) -> str:
        nonlocal fail_next
        if fail_next:
            fail_next = False
            raise RuntimeError("discord 503")
        published.append(text)
        return "published to #published"

    transport = InMemoryTransport()
    crew, hitl = build_crew(
        _config(),
        transport=transport,
        llm=MockLLM(responses=["Launch copy for Passly."]),
        checkpointer=MemorySaver(),
        publisher=flaky_publisher,
    )

    async def tap_approve() -> None:
        while not hitl.pending_request_ids():
            await asyncio.sleep(0)
        rid = hitl.pending_request_ids()[0]
        hitl.submit_response(FounderResponse(request_id=rid, action="approve"))

    marketing = crew.role("marketing")
    with pytest.raises(RuntimeError, match="discord 503"):
        await asyncio.gather(
            crew.author_flow(
                task_description="Draft a launch announcement.",
                role=marketing,
                publish_tool=publish_tool_for(marketing),
                thread_id="run-boom",
            ),
            tap_approve(),
        )
    assert published == []  # nothing shipped, and the approval is spent

    registry = RunsRegistry(tmp_path / "runs.json")
    record = RunRecord(
        thread_id="run-boom",
        role="marketing",
        task="Draft a launch announcement.",
        revisions=3,
        logical_channel="marketing",
        status="error: discord 503",
    )
    registry.put(record)

    gates_before = len(transport.posted)

    async def announce(*args) -> None:
        return None

    outcome = await drive_resume(
        crew=crew,
        registry=registry,
        runs={},
        record=record,
        announce=announce,
        sink=None,
    )

    assert "shipped" in outcome
    assert published == ["Launch copy for Passly."]
    assert registry.get("run-boom").status == "shipped"
    # The founder was not asked again: no second gate was posted.
    assert len(transport.posted) == gates_before
