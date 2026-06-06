"""Offline tests for the live DiscordPyTransport (Ch.3 §3.8.6).

These exercise the discord.py rendering — embed, button view, feedback modal
— without a gateway connection or token. Skipped entirely unless the optional
``discord`` extra is installed (``pip install -e ".[discord]"``).
"""
from __future__ import annotations

import pytest

discord = pytest.importorskip("discord")

from solo_founder_crew.adapters.discord_transport import (  # noqa: E402
    DiscordPyTransport,
    _DecisionView,
    _FeedbackModal,
)
from solo_founder_crew.hitl_request import Artifact, HITLRequest  # noqa: E402


def _request(**overrides) -> HITLRequest:
    base = dict(
        request_id="r1",
        thread_id="run-1",
        venture_id="passly",
        turn=1,
        role_name="marketing",
        action="final_approval_before_publish",
        escalation_reason="must escalate before publish",
        artifact=Artifact(content="Launch copy…", summary="draft"),
        context={"task_description": "Draft a launch announcement."},
    )
    base.update(overrides)
    return HITLRequest(**base)


def _transport() -> DiscordPyTransport:
    client = discord.Client(intents=discord.Intents.default())
    return DiscordPyTransport(client)


def test_embed_carries_role_task_and_footer() -> None:
    embed = _transport()._build_embed(_request())
    assert embed.title.startswith("Marketing")
    assert "Launch copy" in (embed.description or "")
    assert "turn 1" in (embed.footer.text or "")
    field_names = [f.name for f in embed.fields]
    assert "Why you" in field_names
    assert "Task" in field_names


def test_embed_truncates_overlong_body() -> None:
    embed = _transport()._build_embed(_request(artifact=Artifact(content="x" * 5000)))
    assert len(embed.description) <= 4000
    assert embed.description.endswith("…")


def test_view_has_one_button_per_option_with_stable_custom_ids() -> None:
    view = _DecisionView(discord, _request(), lambda r: None)
    assert [c.label for c in view.children] == ["Approve", "Send back", "Kill run"]
    assert [c.style.name for c in view.children] == ["success", "secondary", "danger"]
    assert [c.custom_id for c in view.children] == [
        "hitl:r1:approve",
        "hitl:r1:reject",
        "hitl:r1:kill",
    ]


def test_feedback_modal_builds_for_reject_option() -> None:
    req = _request()
    modal = _FeedbackModal(discord, req, req.option_for("reject"), lambda r: None)
    assert modal.title == "Send back with notes"


def test_post_without_bind_raises() -> None:
    import asyncio

    async def go() -> None:
        with pytest.raises(RuntimeError, match="bind"):
            await _transport().post_request(_request(), channel_id="123")

    asyncio.run(go())
