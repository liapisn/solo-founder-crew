"""Tests for the crew activity log — the #crew-logs stream.

All against `RecordingEventSink`: no Discord, no network. What is pinned is the
*sequence* a founder should see, because the value of this feature is that a
run stops being invisible between "I approved" and "something appeared".

Pins:

1. Events render as one readable line, with detail indented under it.
2. LoggingHITL reports the gate and the decision, and passes the decision back
   untouched — a decorator must not change the contract's behaviour.
3. Feedback typed into "Send back" reaches the log.
4. The PR tool reports implementing → implemented → pr_opened.
5. An escalating diff reports the escalation and no pr_opened.
6. A failed implementation reports an error, not a success.
7. A sink that raises cannot break a run.
"""
from __future__ import annotations

import pytest

from solo_founder_crew.adapters.github_pr import FakeGitHubAPI, ImplementedPRTool
from solo_founder_crew.adapters.implementer import FakeImplementer
from solo_founder_crew.events import (
    AWAITING_REVIEW,
    DECISION,
    ERROR,
    ESCALATION,
    IMPLEMENTED,
    IMPLEMENTING,
    PR_OPENED,
    CrewEvent,
    LoggingHITL,
    NullEventSink,
    RecordingEventSink,
)


# ─── rendering ──────────────────────────────────────────────────────────────


def test_event_renders_as_one_line_with_optional_detail():
    bare = CrewEvent(kind=IMPLEMENTING, role="engineering", summary="implementing X")
    assert bare.render() == "🛠️ **engineering** · implementing X"

    full = CrewEvent(
        kind=PR_OPENED,
        role="engineering",
        summary="opened a draft PR",
        thread_id="run-42",
        detail="https://github.com/liapisn/passly/pull/9",
    )
    line, detail = full.render().split("\n")
    assert "**engineering**" in line and "`run-42`" in line
    assert detail == "https://github.com/liapisn/passly/pull/9"


def test_unknown_kind_still_renders():
    assert CrewEvent(kind="something_new", role="r", summary="s").render().startswith("•")


# ─── the HITL decorator ─────────────────────────────────────────────────────


class _Request:
    role_name = "engineering"
    thread_id = "run-7"
    turn = 2


class _Decision:
    def __init__(self, action="approve", feedback=None):
        self.action, self.feedback = action, feedback


class _StubHITL:
    """Minimal HITLContract double, plus an attribute to prove pass-through."""

    channel_map = {"engineering": "123"}

    def __init__(self, decision):
        self._decision = decision

    async def review(self, request):
        return self._decision


async def test_logging_hitl_reports_the_gate_and_the_decision():
    sink = RecordingEventSink()
    decision = _Decision("approve")
    hitl = LoggingHITL(inner=_StubHITL(decision), sink=sink)

    returned = await hitl.review(_Request())

    assert returned is decision, "the decorator must not alter the decision"
    assert sink.kinds == [AWAITING_REVIEW, DECISION]
    gate, chosen = sink.events
    assert gate.thread_id == "run-7" and "turn 2" in gate.summary
    assert "approve" in chosen.summary


async def test_send_back_feedback_reaches_the_log():
    sink = RecordingEventSink()
    hitl = LoggingHITL(
        inner=_StubHITL(_Decision("reject", "single name field; skip if empty")),
        sink=sink,
    )
    await hitl.review(_Request())

    (chosen,) = sink.of_kind(DECISION)
    assert "reject" in chosen.summary
    assert "single name field" in chosen.detail


def test_logging_hitl_passes_other_attributes_through():
    hitl = LoggingHITL(inner=_StubHITL(_Decision()), sink=RecordingEventSink())
    assert hitl.channel_map == {"engineering": "123"}


# ─── the PR tool's stream ───────────────────────────────────────────────────


def _tool(impl, sink, api=None):
    return ImplementedPRTool(
        implementer=impl, repo="liapisn/passly", api=api or FakeGitHubAPI(), sink=sink
    )


async def test_a_successful_change_reports_implementing_then_pr_opened():
    sink = RecordingEventSink()
    impl = FakeImplementer(files=("api/app/main.py",), num_turns=6, cost_usd=0.21)
    url = await _tool(impl, sink)("Add a health detail endpoint")

    assert sink.kinds == [IMPLEMENTING, IMPLEMENTED, PR_OPENED]
    started, done, opened = sink.events
    assert "Add a health detail endpoint" in started.summary
    assert "1 file(s) changed" in done.summary
    assert "6 turns" in done.detail and "$0.2100" in done.detail
    assert opened.detail == url


async def test_an_escalating_diff_reports_escalation_and_no_pr():
    sink = RecordingEventSink()
    impl = FakeImplementer(files=("api/requirements.txt",))
    await _tool(impl, sink)("Add a caching layer")

    assert PR_OPENED not in sink.kinds
    (esc,) = sink.of_kind(ESCALATION)
    assert "dependency_change" in esc.summary
    assert "no PR opened until you say so" in esc.detail


async def test_a_failed_implementation_reports_an_error():
    sink = RecordingEventSink()
    impl = FakeImplementer(error="FileNotFoundError: data/worktrees/sfc-tree-x")
    await _tool(impl, sink)("Something")

    assert sink.kinds == [IMPLEMENTING, ERROR]
    assert "FileNotFoundError" in sink.of_kind(ERROR)[0].detail
    assert IMPLEMENTED not in sink.kinds


async def test_an_empty_diff_reports_it_and_opens_no_pr():
    sink = RecordingEventSink()
    await _tool(FakeImplementer(files=()), sink)("Do nothing")

    assert PR_OPENED not in sink.kinds
    assert "changed nothing" in sink.of_kind(IMPLEMENTED)[0].summary


# ─── robustness ─────────────────────────────────────────────────────────────


async def test_no_sink_is_a_supported_configuration():
    """The daemon runs with no #crew-logs channel bound."""
    api = FakeGitHubAPI()
    tool = ImplementedPRTool(
        implementer=FakeImplementer(), repo="liapisn/passly", api=api, sink=None
    )
    assert (await tool("Add a thing")).startswith("https://github.com/")


async def test_null_sink_accepts_everything():
    await NullEventSink().emit(CrewEvent(kind=ERROR, role="r", summary="s"))


async def test_a_broken_discord_sink_cannot_break_a_run(capsys):
    """A log post that fails must not take the pull request with it."""
    from solo_founder_crew.adapters.discord_events import DiscordEventSink

    async def exploding(cid, content):
        raise RuntimeError("discord is down")

    sink = DiscordEventSink(send=exploding, channel_id="123")
    api = FakeGitHubAPI()
    url = await _tool(FakeImplementer(), sink, api)("Add a thing")

    assert url.startswith("https://github.com/")
    assert "crew-log post failed" in capsys.readouterr().out


async def test_discord_sink_is_inert_without_a_channel():
    from solo_founder_crew.adapters.discord_events import DiscordEventSink

    sent = []

    async def record(cid, content):
        sent.append((cid, content))

    await DiscordEventSink(send=record, channel_id=None).emit(
        CrewEvent(kind=ERROR, role="r", summary="s")
    )
    assert sent == []


async def test_long_messages_are_truncated_for_discord():
    from solo_founder_crew.adapters.discord_events import DiscordEventSink

    sent = []

    async def record(cid, content):
        sent.append(content)

    sink = DiscordEventSink(send=record, channel_id="1", max_chars=80)
    await sink.emit(CrewEvent(kind=ERROR, role="r", summary="x" * 500))

    assert len(sent[0]) == 80 and sent[0].endswith("…")


@pytest.mark.parametrize(
    "kind", [AWAITING_REVIEW, DECISION, IMPLEMENTING, IMPLEMENTED, PR_OPENED, ERROR]
)
def test_every_kind_has_an_icon(kind):
    from solo_founder_crew.events import ICONS

    assert kind in ICONS
