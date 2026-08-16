"""Tests for `Crew.resume` — restart-durable Author Flow.

This is the M1.5 follow-up to the daemon's restart-durability claim.
The framework promise is: the run state is preserved across a process
restart by the LangGraph checkpointer; a fresh ``Crew`` instance, given
the same checkpointer + the same ``thread_id``, can pick the run up
exactly where it stopped and drive it to a terminal state.

Tests here exercise the framework-level contract without involving
Discord. They use ``MemorySaver`` to simulate "two processes, one
backing store" — that's enough to prove the resume path, because the
contract that matters is *Crew sees existing state, drives the
interrupt loop, run completes*. The daemon-side hookup (re-spawning
``Crew.resume`` tasks on startup + persistent view re-registration)
is tested empirically by running the live daemon.

The pivotal test is :func:`test_resume_after_cancellation_completes_run`:
it cancels an in-flight ``author_flow`` while paused at the HITL gate
(the exact "process restart" scenario), then constructs a fresh
``Crew`` against the same checkpointer and calls ``resume``. If the
run reaches ``status=shipped``, the framework's restart contract holds.
"""
from __future__ import annotations

import asyncio

import pytest
from langgraph.checkpoint.memory import MemorySaver

from solo_founder_crew import (
    Crew,
    FounderDecision,
    MockLLM,
    Role,
    ScriptedHITL,
    ToolRegistry,
    VentureBrief,
)
from solo_founder_crew.adapters.discord_hitl import DiscordHITL, InMemoryTransport
from solo_founder_crew.hitl_request import FounderResponse


DRAFT_V1 = "Draft v1 — first attempt.\n"
DRAFT_V2 = "Draft v2 — revised.\n"


# ─── helpers ────────────────────────────────────────────────────────────────


class _NeverCompletingHITL:
    """A HITL that never returns from ``review`` — used to leave the
    Author Flow paused indefinitely so the test can cancel it.

    Mirrors the production scenario: the process dies while the founder
    is taking their time. The checkpointed graph state survives;
    everything in-memory (the Future, the Crew, the running task) is
    lost.
    """

    def __init__(self) -> None:
        self.entered = asyncio.Event()

    async def review(self, request):  # noqa: ANN001 - mirror the Protocol
        self.entered.set()
        await asyncio.Future()  # parks forever; cancelled when the task is killed


def _tools() -> ToolRegistry:
    registry = ToolRegistry()

    async def publisher(text: str) -> str:
        return f"shipped:{len(text)}"

    registry.register(
        "publisher_tool", publisher, escalates="final_approval_before_publish"
    )
    return registry


def _build_crew(
    *,
    brief: VentureBrief,
    role: Role,
    hitl,
    checkpointer,
    responses: list[str],
) -> Crew:
    return Crew(
        brief=brief,
        roles=[role],
        llm=MockLLM(responses=responses),
        hitl=hitl,
        tools=_tools(),
        checkpointer=checkpointer,
    )


# ─── (1) The canonical case: cancel at the gate, resume, complete ───────────


async def test_resume_after_cancellation_completes_run(
    brief: VentureBrief, marketing_role: Role
) -> None:
    """Author Flow is paused at the HITL gate, the running task is
    cancelled (simulating ``Ctrl-C`` / process death), a fresh Crew is
    built against the same checkpointer + a real HITL, and ``resume``
    completes the run.
    """
    checkpointer = MemorySaver()
    thread_id = "run-resume-001"

    # First "process": start the flow, park at the gate, get cancelled.
    parking_hitl = _NeverCompletingHITL()
    crew_alpha = _build_crew(
        brief=brief,
        role=marketing_role,
        hitl=parking_hitl,
        checkpointer=checkpointer,
        responses=[DRAFT_V1],
    )

    task = asyncio.create_task(
        crew_alpha.author_flow(
            task_description="Draft a launch teaser.", thread_id=thread_id
        )
    )
    # Wait until the gate has been hit (Crew has called ``review``).
    await asyncio.wait_for(parking_hitl.entered.wait(), timeout=2.0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Second "process": new Crew, same checkpointer, decision is approve.
    crew_beta = _build_crew(
        brief=brief,
        role=marketing_role,
        hitl=ScriptedHITL([FounderDecision(action="approve")]),
        checkpointer=checkpointer,
        responses=[],  # the resumed graph won't call the LLM again
    )
    result = await crew_beta.resume(thread_id, role="marketing")

    assert result.status == "shipped"
    assert result.thread_id == thread_id
    assert result.approved_artifact == DRAFT_V1


# ─── (2) Multi-turn resume: paused → reject → paused → approve ──────────────


async def test_resume_supports_multiple_revision_turns(
    brief: VentureBrief, marketing_role: Role
) -> None:
    """Resume at turn 1, reject (→ revise → pause at turn 2), then
    approve. The interrupt loop inside ``resume`` should handle the
    second pause without help."""
    checkpointer = MemorySaver()
    thread_id = "run-resume-002"

    parking_hitl = _NeverCompletingHITL()
    crew_alpha = _build_crew(
        brief=brief,
        role=marketing_role,
        hitl=parking_hitl,
        checkpointer=checkpointer,
        responses=[DRAFT_V1, DRAFT_V2],
    )

    task = asyncio.create_task(
        crew_alpha.author_flow(
            task_description="Draft.", thread_id=thread_id, max_revisions=1
        )
    )
    await asyncio.wait_for(parking_hitl.entered.wait(), timeout=2.0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    crew_beta = _build_crew(
        brief=brief,
        role=marketing_role,
        hitl=ScriptedHITL(
            [
                FounderDecision(action="reject", feedback="warmer please"),
                FounderDecision(action="approve"),
            ]
        ),
        checkpointer=checkpointer,
        responses=[DRAFT_V2],  # only the revise call hits the LLM
    )
    result = await crew_beta.resume(thread_id, role="marketing")

    assert result.status == "shipped"
    assert result.approved_artifact == DRAFT_V2  # the revised draft
    # Two HITL events visible in the trace: the reject + the approve.
    decisions = [e.decision for e in result.trace.events if e.decision]
    assert decisions == ["reject", "approve"]


# ─── (3) Idempotent on terminal state ───────────────────────────────────────


async def test_resume_on_terminal_thread_returns_state_no_side_effects(
    brief: VentureBrief,
    marketing_role: Role,
) -> None:
    """Calling ``resume`` on a thread that has already shipped must
    return the saved terminal state without touching the LLM, the
    HITL, or the publisher. Safe to call idempotently — useful when
    the daemon's registry says a run is "running" but the checkpointer
    knows it actually completed."""
    checkpointer = MemorySaver()
    thread_id = "run-resume-003"

    # First, run a flow to completion so the checkpointer holds a
    # terminal state.
    crew = _build_crew(
        brief=brief,
        role=marketing_role,
        hitl=ScriptedHITL([FounderDecision(action="approve")]),
        checkpointer=checkpointer,
        responses=[DRAFT_V1],
    )
    first = await crew.author_flow(
        task_description="x", thread_id=thread_id
    )
    assert first.status == "shipped"

    # Now resume — with a HITL that would error if called, and an
    # exhausted LLM queue. The resume must not invoke either.
    class _ExplodingHITL:
        async def review(self, request):  # noqa: ANN001
            raise AssertionError("resume on terminal state must not call HITL")

    crew_again = _build_crew(
        brief=brief,
        role=marketing_role,
        hitl=_ExplodingHITL(),
        checkpointer=checkpointer,
        responses=[],
    )
    second = await crew_again.resume(thread_id, role="marketing")
    assert second.status == "shipped"
    assert second.approved_artifact == DRAFT_V1


# ─── (3b) A node that raised is retried, not abandoned ──────────────────────


class _FlakyPublisher:
    """A publish tool that fails the first ``fail_times`` calls.

    Stands in for the real ways the publish step dies mid-run: Discord
    5xx, a GitHub timeout, the coding agent crashing. ``calls`` counts
    every attempt so a test can prove the artefact was published once
    and only once.
    """

    def __init__(self, fail_times: int = 1) -> None:
        self.fail_times = fail_times
        self.calls = 0

    async def __call__(self, text: str) -> str:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("publish exploded")
        return f"shipped:{len(text)}"


def _crew_with_publisher(
    *, brief: VentureBrief, role: Role, publisher, checkpointer, hitl, responses
) -> Crew:
    registry = ToolRegistry()
    registry.register(
        "publisher_tool", publisher, escalates="final_approval_before_publish"
    )
    return Crew(
        brief=brief,
        roles=[role],
        llm=MockLLM(responses=responses),
        hitl=hitl,
        tools=registry,
        checkpointer=checkpointer,
    )


async def test_resume_retries_a_node_that_raised(
    brief: VentureBrief, marketing_role: Role
) -> None:
    """The founder approved, publishing blew up, the run died.

    Regression: ``resume`` used to read the checkpointed state instead of
    re-invoking, so the queued ``publish`` node never re-ran. The run came
    back ``status="unknown"``, nothing was published, and the approval the
    founder had already given was spent for nothing. Now the failed node
    is retried and the run reaches its real terminal state.
    """
    checkpointer = MemorySaver()
    thread_id = "run-resume-004"
    publisher = _FlakyPublisher(fail_times=1)

    crew_alpha = _crew_with_publisher(
        brief=brief,
        role=marketing_role,
        publisher=publisher,
        checkpointer=checkpointer,
        hitl=ScriptedHITL([FounderDecision(action="approve")]),
        responses=[DRAFT_V1],
    )
    with pytest.raises(RuntimeError, match="publish exploded"):
        await crew_alpha.author_flow(task_description="x", thread_id=thread_id)
    assert publisher.calls == 1

    # The retry: same checkpointer, and a HITL that would fail the test if
    # consulted — the founder is not asked to approve the same draft twice.
    class _ExplodingHITL:
        async def review(self, request):  # noqa: ANN001
            raise AssertionError("a retry must not re-ask the founder")

    crew_beta = _crew_with_publisher(
        brief=brief,
        role=marketing_role,
        publisher=publisher,
        checkpointer=checkpointer,
        hitl=_ExplodingHITL(),
        responses=[],  # nor re-draft: the LLM queue is empty
    )
    result = await crew_beta.resume(thread_id, role="marketing")

    assert result.status == "shipped"
    assert result.approved_artifact == DRAFT_V1
    assert publisher.calls == 2  # the failed attempt, then the one that stuck


async def test_resume_of_a_still_broken_run_raises(
    brief: VentureBrief, marketing_role: Role
) -> None:
    """If the retry fails too, the error surfaces.

    A second failure must be as loud as the first — the daemon reports it
    and the founder decides whether to retry again. Silently returning a
    non-terminal state is what made the original bug invisible.
    """
    checkpointer = MemorySaver()
    thread_id = "run-resume-005"
    publisher = _FlakyPublisher(fail_times=99)

    crew = _crew_with_publisher(
        brief=brief,
        role=marketing_role,
        publisher=publisher,
        checkpointer=checkpointer,
        hitl=ScriptedHITL([FounderDecision(action="approve")]),
        responses=[DRAFT_V1],
    )
    with pytest.raises(RuntimeError, match="publish exploded"):
        await crew.author_flow(task_description="x", thread_id=thread_id)

    with pytest.raises(RuntimeError, match="publish exploded"):
        await crew.resume(thread_id, role="marketing")
    assert publisher.calls == 2


async def test_resume_at_a_gate_does_not_re_invoke(
    brief: VentureBrief, marketing_role: Role
) -> None:
    """The retry path must not disturb the normal one.

    A run paused at a gate has pending work too (the ``hitl`` node), so
    the check has to distinguish "awaiting the founder" from "stopped on
    an exception". If it did not, resuming a parked run would re-post the
    gate before the founder had answered the first one.
    """
    checkpointer = MemorySaver()
    thread_id = "run-resume-006"
    publisher = _FlakyPublisher(fail_times=0)

    parking_hitl = _NeverCompletingHITL()
    crew_alpha = _crew_with_publisher(
        brief=brief,
        role=marketing_role,
        publisher=publisher,
        checkpointer=checkpointer,
        hitl=parking_hitl,
        responses=[DRAFT_V1],
    )
    task = asyncio.create_task(
        crew_alpha.author_flow(task_description="x", thread_id=thread_id)
    )
    await asyncio.wait_for(parking_hitl.entered.wait(), timeout=2.0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    crew_beta = _crew_with_publisher(
        brief=brief,
        role=marketing_role,
        publisher=publisher,
        checkpointer=checkpointer,
        hitl=ScriptedHITL([FounderDecision(action="approve")]),
        responses=[],  # an empty queue: re-drafting would raise here
    )
    result = await crew_beta.resume(thread_id, role="marketing")
    assert result.status == "shipped"
    assert result.approved_artifact == DRAFT_V1  # the original draft, not a new one


# ─── (4) Unknown thread_id ──────────────────────────────────────────────────


async def test_resume_on_unknown_thread_raises_key_error(
    brief: VentureBrief, marketing_role: Role
) -> None:
    """If the caller asks to resume a thread the checkpointer has never
    seen, ``KeyError`` surfaces — the daemon's startup hook can catch
    it and drop the stale run from its registry."""
    crew = _build_crew(
        brief=brief,
        role=marketing_role,
        hitl=ScriptedHITL([FounderDecision(action="approve")]),
        checkpointer=MemorySaver(),
        responses=[DRAFT_V1],
    )
    with pytest.raises(KeyError, match="no-such-thread"):
        await crew.resume("no-such-thread", role="marketing")


# ─── (5) Misconfigured Crew ─────────────────────────────────────────────────


async def test_resume_without_checkpointer_raises(
    brief: VentureBrief, marketing_role: Role
) -> None:
    crew = Crew(
        brief=brief,
        roles=[marketing_role],
        llm=MockLLM(responses=[]),
        hitl=ScriptedHITL([]),
        tools=_tools(),
        checkpointer=None,  # ← the misconfiguration under test
    )
    with pytest.raises(RuntimeError, match="checkpointer"):
        await crew.resume("any", role="marketing")


# ─── (6) End-to-end through the DiscordHITL contract ────────────────────────
#
# This is the test that proves the *daemon's actual path* works. It uses
# DiscordHITL + InMemoryTransport — the same contract the live daemon
# uses with DiscordPyTransport — and goes through the full
# "post-restart click resolves the resumed run" sequence.


async def test_resume_through_discord_hitl_inmemory_end_to_end(
    brief: VentureBrief, marketing_role: Role
) -> None:
    """End-to-end: paused crew is cancelled, new crew + fresh DiscordHITL
    resumes, the test injects a founder response via the new transport,
    the resumed run completes."""
    checkpointer = MemorySaver()
    thread_id = "run-discord-001"

    # First process: real DiscordHITL with InMemoryTransport. The
    # transport posts to a fake channel; the founder never clicks; we
    # cancel the task to simulate process death.
    transport_a = InMemoryTransport()
    hitl_a = DiscordHITL(transport_a, channel_map={"marketing": "channel-1"})

    crew_alpha = _build_crew(
        brief=brief,
        role=marketing_role,
        hitl=hitl_a,
        checkpointer=checkpointer,
        responses=[DRAFT_V1],
    )

    task = asyncio.create_task(
        crew_alpha.author_flow(
            task_description="Draft a launch teaser.", thread_id=thread_id
        )
    )
    # Wait for the transport to have received the gate post. The
    # InMemoryTransport records (channel_id, HITLRequest) tuples in
    # ``posted``; the first element appearing means ``review`` has
    # been called and is now parked.
    for _ in range(40):
        if transport_a.posted:
            break
        await asyncio.sleep(0.02)
    assert transport_a.posted, "gate never posted on first process"
    request_id_alpha = transport_a.posted[0][1].request_id
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Second process: fresh DiscordHITL + transport, same checkpointer.
    transport_b = InMemoryTransport()
    hitl_b = DiscordHITL(transport_b, channel_map={"marketing": "channel-1"})

    crew_beta = _build_crew(
        brief=brief,
        role=marketing_role,
        hitl=hitl_b,
        checkpointer=checkpointer,
        responses=[],
    )

    # Kick off resume; it parks on hitl_b.review until we submit.
    resume_task = asyncio.create_task(
        crew_beta.resume(thread_id, role="marketing")
    )

    # Wait for the new transport to have received the (re-posted) gate.
    # The resumed Crew reconstructs the HITLRequest from the same
    # checkpointed payload, so the request_id matches the alpha run's.
    for _ in range(40):
        if transport_b.posted:
            break
        await asyncio.sleep(0.02)
    assert transport_b.posted, "resumed Crew did not re-post the gate"
    request_id_beta = transport_b.posted[0][1].request_id
    assert request_id_beta == request_id_alpha  # same request, same id

    # The "founder" approves — exactly the path a real button click
    # would take: callback → hitl.submit_response(FounderResponse(...)).
    hitl_b.submit_response(
        FounderResponse(
            request_id=request_id_beta, action="approve", responder="test-founder"
        )
    )
    result = await asyncio.wait_for(resume_task, timeout=2.0)

    assert result.status == "shipped"
    assert result.approved_artifact == DRAFT_V1
