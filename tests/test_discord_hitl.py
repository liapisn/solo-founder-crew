"""Tests for the DiscordHITL surface adapter (Ch.3 §3.8.6).

Covers the adapter's contract-satisfying behaviour with the InMemoryTransport
double — channel routing, the Future-based pause/resume, idempotent re-entry —
and one end-to-end run driving Crew.author_flow, proving the enriched HITL
contract path works through a real graph.
"""
from __future__ import annotations

import asyncio

import pytest

from solo_founder_crew import (
    Artifact,
    Crew,
    FounderResponse,
    HITLRequest,
    MockLLM,
    Role,
    ToolRegistry,
    VentureBrief,
)
from solo_founder_crew.adapters.discord_hitl import (
    DiscordHITL,
    InMemoryTransport,
    UnknownChannel,
)


def _request(**overrides) -> HITLRequest:
    base = dict(
        request_id="req-1",
        thread_id="run-1",
        venture_id="passly",
        turn=1,
        role_name="marketing",
        action="final_approval_before_publish",
        artifact=Artifact(content="draft body", summary="a draft"),
    )
    base.update(overrides)
    return HITLRequest(**base)


# ─── Channel resolution ────────────────────────────────────────────────────────


async def test_posts_to_mapped_channel() -> None:
    transport = InMemoryTransport()
    hitl = DiscordHITL(transport, channel_map={"marketing": "CHAN_MKT"})
    task = asyncio.ensure_future(hitl.review(_request()))
    await asyncio.sleep(0)  # let review() post before we assert
    assert transport.posted[0][0] == "CHAN_MKT"
    hitl.submit_response(FounderResponse(request_id="req-1", action="approve"))
    await task


def test_inmemory_transport_set_notify_stores() -> None:
    t = InMemoryTransport()
    t.set_notify("run-1", "<@42>")
    assert t.notify["run-1"] == "<@42>"


def test_register_channel_and_is_mapped() -> None:
    hitl = DiscordHITL(InMemoryTransport(), channel_map={})
    assert hitl.is_mapped("marketing") is False
    hitl.register_channel("marketing", "123")
    assert hitl.is_mapped("marketing") is True


def test_channel_for_resolves_mapped_then_default() -> None:
    h = DiscordHITL(
        InMemoryTransport(), channel_map={"marketing": "M"}, default_channel_id="D"
    )
    assert h.channel_for("marketing") == "M"
    assert h.channel_for("unmapped") == "D"  # falls back to default
    assert DiscordHITL(InMemoryTransport(), channel_map={}).channel_for("x") is None


async def test_unknown_channel_without_default_raises() -> None:
    hitl = DiscordHITL(InMemoryTransport(), channel_map={})
    with pytest.raises(UnknownChannel):
        await hitl.review(_request(channel="nowhere"))


async def test_default_channel_catches_all() -> None:
    transport = InMemoryTransport()
    hitl = DiscordHITL(transport, channel_map={}, default_channel_id="FALLBACK")
    task = asyncio.ensure_future(hitl.review(_request(channel="unmapped")))
    await asyncio.sleep(0)
    assert transport.posted[0][0] == "FALLBACK"
    hitl.submit_response(FounderResponse(request_id="req-1", action="kill"))
    await task


# ─── Pause / resume via Future ──────────────────────────────────────────────────


async def test_review_blocks_until_response_then_returns_decision() -> None:
    hitl = DiscordHITL(InMemoryTransport(), channel_map={"marketing": "C"})
    task = asyncio.ensure_future(hitl.review(_request()))
    await asyncio.sleep(0)
    assert not task.done()  # parked, awaiting the founder
    assert hitl.pending_request_ids() == ("req-1",)

    hitl.submit_response(
        FounderResponse(request_id="req-1", action="reject", feedback="warmer")
    )
    decision = await task
    assert decision.action == "reject"
    assert decision.feedback == "warmer"
    assert hitl.pending_request_ids() == ()  # cleared after resolution


async def test_unknown_or_double_response_is_ignored() -> None:
    hitl = DiscordHITL(InMemoryTransport(), channel_map={"marketing": "C"})
    # response for a request that was never raised: harmless no-op
    hitl.submit_response(FounderResponse(request_id="ghost", action="approve"))

    task = asyncio.ensure_future(hitl.review(_request()))
    await asyncio.sleep(0)
    hitl.submit_response(FounderResponse(request_id="req-1", action="approve"))
    hitl.submit_response(FounderResponse(request_id="req-1", action="kill"))  # late
    decision = await task
    assert decision.action == "approve"  # first wins, second ignored


async def test_reentry_while_pending_returns_same_future() -> None:
    transport = InMemoryTransport()
    hitl = DiscordHITL(transport, channel_map={"marketing": "C"})
    req = _request()
    t1 = asyncio.ensure_future(hitl.review(req))
    await asyncio.sleep(0)
    t2 = asyncio.ensure_future(hitl.review(req))  # retry same request_id
    await asyncio.sleep(0)
    # re-entry must not double-post to the channel
    assert len(transport.posted) == 1
    hitl.submit_response(FounderResponse(request_id="req-1", action="approve"))
    d1, d2 = await asyncio.gather(t1, t2)
    assert d1.action == d2.action == "approve"


# ─── End-to-end through Crew.author_flow ────────────────────────────────────────


async def test_discord_hitl_drives_author_flow(
    brief: VentureBrief,
    marketing_role: Role,
    tool_registry: ToolRegistry,
) -> None:
    transport = InMemoryTransport()
    hitl = DiscordHITL(transport, channel_map={"marketing": "CHAN_MKT"})
    crew = Crew(
        brief=brief,
        roles=[marketing_role],
        llm=MockLLM(responses=["Launch copy for Passly."]),
        hitl=hitl,
        tools=tool_registry,
    )

    async def founder_taps_approve() -> None:
        while not hitl.pending_request_ids():
            await asyncio.sleep(0)
        rid = hitl.pending_request_ids()[0]
        hitl.submit_response(FounderResponse(request_id=rid, action="approve"))

    result, _ = await asyncio.gather(
        crew.author_flow(task_description="Draft a launch announcement."),
        founder_taps_approve(),
    )

    assert result.status == "shipped"
    # the gate posted a request carrying the role + the gated action
    channel_id, posted = transport.posted[0]
    assert channel_id == "CHAN_MKT"
    assert posted.role_name == "marketing"
    assert posted.action == "final_approval_before_publish"
    assert posted.venture_id == "passly"


# ─── on_posted callback (M1.6 — stale-gate edit on respawn) ─────────────────


async def test_on_posted_fires_after_gate_posts() -> None:
    """The hook gives the daemon a place to record the message_id of the
    gate it just posted, so a future restart can edit that stale
    message before the resumed flow posts a fresh one."""
    received: list[dict] = []

    def hook(*, request: HITLRequest, channel_id: str, message_id: str) -> None:
        received.append(
            {
                "request_id": request.request_id,
                "thread_id": request.thread_id,
                "channel_id": channel_id,
                "message_id": message_id,
            }
        )

    transport = InMemoryTransport()
    hitl = DiscordHITL(
        transport,
        channel_map={"marketing": "CHAN_MKT"},
        on_posted=hook,
    )

    task = asyncio.ensure_future(hitl.review(_request()))
    while not hitl.pending_request_ids():
        await asyncio.sleep(0)

    assert len(received) == 1
    assert received[0]["request_id"] == "req-1"
    assert received[0]["thread_id"] == "run-1"
    assert received[0]["channel_id"] == "CHAN_MKT"
    # InMemoryTransport.post_request returns f"msg-{request_id}"
    assert received[0]["message_id"] == "msg-req-1"

    hitl.submit_response(FounderResponse(request_id="req-1", action="approve"))
    await task


async def test_on_posted_failure_does_not_break_review() -> None:
    """A buggy ``on_posted`` callback must not break the live gate; the
    review path still resolves normally."""

    def bad_hook(**_: object) -> None:
        raise RuntimeError("simulated buggy callback")

    transport = InMemoryTransport()
    hitl = DiscordHITL(
        transport,
        channel_map={"marketing": "CHAN_MKT"},
        on_posted=bad_hook,
    )

    task = asyncio.ensure_future(hitl.review(_request()))
    while not hitl.pending_request_ids():
        await asyncio.sleep(0)
    hitl.submit_response(FounderResponse(request_id="req-1", action="approve"))
    decision = await task
    assert decision.action == "approve"


async def test_no_on_posted_callback_is_fine() -> None:
    """Adapters constructed without the hook still post and resolve
    normally — backward compatible."""
    transport = InMemoryTransport()
    hitl = DiscordHITL(transport, channel_map={"marketing": "CHAN_MKT"})
    task = asyncio.ensure_future(hitl.review(_request()))
    while not hitl.pending_request_ids():
        await asyncio.sleep(0)
    hitl.submit_response(FounderResponse(request_id="req-1", action="approve"))
    decision = await task
    assert decision.action == "approve"
