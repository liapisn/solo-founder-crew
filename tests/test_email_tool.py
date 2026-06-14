"""Tests for the Email tool — M2 Phase 2 ``email_tool``.

Same Protocol-with-fake pattern as ``test_github_pr_tool.py``: the
adapter depends on ``EmailAPI``, the tests inject ``FakeEmailAPI``.
No network, no credentials.

Pins:
1. End-to-end happy path: derives subject from first line, builds
   HTML + plaintext bodies, returns the documented status string.
2. Construction guards (no sender, malformed sender, missing
   recipient).
3. Factory env-var resolution (``SFC_EMAIL_FROM``, ``SFC_EMAIL_TO``,
   ``SFC_EMAIL_SUBJECT_PREFIX``).
4. Subject derivation handles markdown headers, blank leading
   lines, long inputs, and empty artefacts.
5. HTML rendering: paragraphs, embedded line breaks, escaping
   special characters, non-Latin scripts.
6. Integration with ``ToolRegistry`` + role escalation rules.
"""
from __future__ import annotations

import pytest

from solo_founder_crew import (
    DecisionRights,
    Role,
    ToolPermissionError,
    ToolRegistry,
    make_marketing,
)
from solo_founder_crew.adapters.email import (
    EmailTool,
    FakeEmailAPI,
    _derive_subject,
    _to_html,
    make_email_tool,
)


ARTIFACT = """\
Passly is here.

Loyalty passes that live straight in Apple and Google Wallet — no app
downloads, no friction. AI drafts your weekly promo, you ship it in
two clicks.

Greek-first. Pre-launch. Early-access from this week.
"""


# ─── End-to-end against FakeEmailAPI ─────────────────────────────────────────


async def test_send_email_happy_path() -> None:
    api = FakeEmailAPI()
    tool = EmailTool(
        sender="onboarding@resend.dev",
        default_to="founder@passly.gr",
        api=api,
    )

    result = await tool(ARTIFACT)

    assert result == "sent:email-1:founder@passly.gr"
    assert len(api.sent) == 1
    sent = api.sent[0]
    assert sent["from"] == "onboarding@resend.dev"
    assert sent["to"] == "founder@passly.gr"
    assert sent["subject"] == "Passly is here."
    assert "Loyalty passes" in sent["text"]
    assert "<p>Passly is here.</p>" in sent["html"]
    assert "<br>" in sent["html"]  # multi-line paragraph survived


async def test_subject_prefix_is_applied() -> None:
    api = FakeEmailAPI()
    tool = EmailTool(
        sender="hello@passly.gr",
        default_to="founder@passly.gr",
        subject_prefix="[Passly] ",
        api=api,
    )
    await tool(ARTIFACT)
    assert api.sent[0]["subject"] == "[Passly] Passly is here."


async def test_text_body_is_full_artifact() -> None:
    api = FakeEmailAPI()
    tool = EmailTool(
        sender="hello@passly.gr",
        default_to="founder@passly.gr",
        api=api,
    )
    await tool(ARTIFACT)
    # The plaintext body should carry the whole artefact, ending
    # with a newline (we normalise that).
    assert api.sent[0]["text"].startswith("Passly is here.")
    assert api.sent[0]["text"].endswith("\n")


# ─── Construction-time guards ────────────────────────────────────────────────


def test_construction_rejects_empty_sender() -> None:
    with pytest.raises(RuntimeError, match="sender"):
        EmailTool(sender="", default_to="x@y", api=FakeEmailAPI())


def test_construction_rejects_malformed_sender() -> None:
    with pytest.raises(RuntimeError, match="sender"):
        EmailTool(sender="not-an-email", default_to="x@y", api=FakeEmailAPI())


def test_construction_accepts_name_email_form() -> None:
    """The "Name <addr@domain>" form is the conventional sender format."""
    tool = EmailTool(
        sender="Passly <hello@passly.gr>",
        default_to="x@y",
        api=FakeEmailAPI(),
    )
    assert tool.sender == "Passly <hello@passly.gr>"


async def test_call_without_recipient_raises() -> None:
    """Constructing without a default_to is permitted (e.g. factory
    with no env var) but calling without one must surface a clear
    error rather than silently sending nothing."""
    tool = EmailTool(
        sender="hello@passly.gr",
        default_to=None,
        api=FakeEmailAPI(),
    )
    with pytest.raises(RuntimeError, match="recipient"):
        await tool("anything")


# ─── Factory reads env vars ──────────────────────────────────────────────────


def test_make_email_tool_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeEmailAPI()
    monkeypatch.setenv("SFC_EMAIL_FROM", "hello@passly.gr")
    monkeypatch.setenv("SFC_EMAIL_TO", "founder@passly.gr")
    monkeypatch.setenv("SFC_EMAIL_SUBJECT_PREFIX", "[Passly] ")
    tool = make_email_tool(api=api)
    assert tool.sender == "hello@passly.gr"
    assert tool.default_to == "founder@passly.gr"
    assert tool.subject_prefix == "[Passly] "


def test_make_email_tool_explicit_args_win(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeEmailAPI()
    monkeypatch.setenv("SFC_EMAIL_FROM", "from-env@passly.gr")
    monkeypatch.setenv("SFC_EMAIL_TO", "to-env@passly.gr")
    tool = make_email_tool(
        sender="explicit@passly.gr",
        default_to="explicit-to@passly.gr",
        api=api,
    )
    assert tool.sender == "explicit@passly.gr"
    assert tool.default_to == "explicit-to@passly.gr"


def test_make_email_tool_missing_sender_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SFC_EMAIL_FROM", raising=False)
    with pytest.raises(RuntimeError, match="SFC_EMAIL_FROM"):
        make_email_tool(api=FakeEmailAPI())


def test_make_email_tool_missing_recipient_is_deferred(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No SFC_EMAIL_TO at construction is permitted (caller might pass
    it later or override per-call); the error surfaces on invocation
    instead."""
    monkeypatch.setenv("SFC_EMAIL_FROM", "hello@passly.gr")
    monkeypatch.delenv("SFC_EMAIL_TO", raising=False)
    tool = make_email_tool(api=FakeEmailAPI())
    assert tool.default_to is None


# ─── Subject derivation ──────────────────────────────────────────────────────


def test_subject_skips_blank_leading_lines() -> None:
    assert _derive_subject("\n\n  Real subject\nMore …") == "Real subject"


def test_subject_strips_markdown_header() -> None:
    assert _derive_subject("# Hello world\nBody …") == "Hello world"


def test_subject_falls_back_when_empty() -> None:
    assert _derive_subject("   \n\t\n") == "Message from the crew"


def test_subject_truncates_long_input() -> None:
    long = "x" * 200
    out = _derive_subject(long, max_len=80)
    assert len(out) == 80


# ─── HTML rendering ──────────────────────────────────────────────────────────


def test_html_wraps_paragraphs() -> None:
    html = _to_html("Para one.\n\nPara two.")
    assert "<p>Para one.</p>" in html
    assert "<p>Para two.</p>" in html


def test_html_preserves_line_breaks_within_paragraph() -> None:
    html = _to_html("Line one.\nLine two.")
    # Single paragraph with embedded <br>
    assert html == "<p>Line one.<br>Line two.</p>"


def test_html_escapes_special_characters() -> None:
    html = _to_html("5 < 10 & a > b")
    assert "&lt;" in html and "&gt;" in html and "&amp;" in html
    # And does NOT contain raw < or > inside the paragraph text
    assert "5 < 10" not in html
    assert "a > b" not in html


def test_html_handles_greek_and_other_non_latin() -> None:
    html = _to_html("Έρχεται το Passly — passes που δουλεύουν.")
    # Greek characters survive verbatim (no HTML encoding needed for them)
    assert "Έρχεται" in html
    assert "<p>" in html


def test_html_drops_empty_paragraphs() -> None:
    html = _to_html("Real text.\n\n   \n\nMore.")
    # Three blank-separated blocks but only two have content
    assert html.count("<p>") == 2


# ─── Integration with ToolRegistry + role escalation ────────────────────────


async def test_email_tool_registers_and_enforces_escalation(brief) -> None:
    """The email tool plugs into ToolRegistry the same way pr_tool does;
    only escalation-satisfied invocations succeed."""
    api = FakeEmailAPI()
    email_tool = EmailTool(
        sender="hello@passly.gr",
        default_to="founder@passly.gr",
        api=api,
    )

    registry = ToolRegistry()
    registry.register(
        "email_tool", email_tool, escalates="final_approval_before_publish"
    )

    # Use the canonical Marketing role; it holds the email_tool in
    # its allowlist after this PR's roles_library update.
    marketing = make_marketing(brief)
    assert "email_tool" in marketing.tools

    # No escalation evidence — refused.
    with pytest.raises(ToolPermissionError, match="escalation"):
        await registry.invoke(marketing, "email_tool", ARTIFACT)

    # With escalation evidence, the email goes out.
    result = await registry.invoke(
        marketing, "email_tool", ARTIFACT, escalation_satisfied=True
    )
    assert result.startswith("sent:")
    assert len(api.sent) == 1


async def test_email_tool_refuses_roles_without_email_in_allowlist(brief) -> None:
    api = FakeEmailAPI()
    email_tool = EmailTool(
        sender="hello@passly.gr",
        default_to="founder@passly.gr",
        api=api,
    )
    registry = ToolRegistry()
    registry.register(
        "email_tool", email_tool, escalates="final_approval_before_publish"
    )

    # A role that escalates the right action but doesn't hold email_tool
    no_email = Role(
        name="finance",
        goal="x",
        system_prompt="x",
        decision_rights=DecisionRights(
            can=("draft_content",),
            must_escalate=("final_approval_before_publish",),
        ),
        tools=("publisher_tool",),  # no email_tool
    )
    with pytest.raises(ToolPermissionError, match="not allowed"):
        await registry.invoke(
            no_email, "email_tool", ARTIFACT, escalation_satisfied=True
        )
