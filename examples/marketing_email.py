"""Marketing role end-to-end with the email tool.

Counterpart to ``passly_launch.py`` (Discord publisher) and
``engineering_pr.py`` (GitHub PR). The Marketing role drafts a launch
announcement; founder approves through the HITL gate; the runtime
invokes ``email_tool`` which **sends a real email** via Resend (or a
``FakeEmailAPI`` in the default mock path).

By default the example runs against a ``FakeEmailAPI`` so it is safe
to execute with no credentials and no network. Pass ``--live`` to
actually call Resend:

  - ``ANTHROPIC_API_KEY``  (only if also running ``--real-llm``)
  - ``RESEND_API_KEY``      (sign up at https://resend.com — free tier)
  - ``SFC_EMAIL_FROM``      (sandbox: ``onboarding@resend.dev``;
                              production: ``hello@<your-verified-domain>``)
  - ``SFC_EMAIL_TO``        (sandbox restricts delivery to the
                              account-owner address)
  - optional ``SFC_EMAIL_SUBJECT_PREFIX``

Run:
    cd solo-founder-crew
    python examples/marketing_email.py                  # mock + FakeEmailAPI
    python examples/marketing_email.py --real-llm       # Haiku + FakeEmailAPI
    python examples/marketing_email.py --real-llm --live  # Haiku + real send
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from solo_founder_crew import (
    AnthropicLLM,
    Crew,
    FounderDecision,
    LLMClient,
    MockLLM,
    ScriptedHITL,
    ToolRegistry,
    VentureBrief,
    load_dotenv,
    make_marketing,
)
from solo_founder_crew.adapters.email import (
    EmailTool,
    FakeEmailAPI,
    make_email_tool,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIEF_PATH = REPO_ROOT / "scenarios" / "fixtures" / "passly_brief.json"


# Canned marketing draft for the no-API-key path. Real-LLM path
# produces something richer and venture-voiced.
MOCK_DRAFT = """\
Passly — loyalty that lives in your wallet.

You're a καφέ, a κομμωτήριο, a small shop. Your regulars come back
because they like you, not because they downloaded an app. So why
make them download one?

With Passly, your loyalty cards and offers live straight in Apple
Wallet and Google Wallet. AI drafts your weekly promo. You glance,
tweak, ship — two clicks, done. Greek-first, GDPR-friendly, built
for the way you actually work.

Pre-launch. Early access starting this week.

Passly. Όπως πρέπει.
"""


def build_llm(real: bool) -> LLMClient:
    if real:
        return AnthropicLLM(model="claude-haiku-4-5")
    return MockLLM(responses=[MOCK_DRAFT], model="mock-haiku")


def build_email_tool(live: bool) -> EmailTool:
    if live:
        # Reads SFC_EMAIL_FROM + SFC_EMAIL_TO from env; uses
        # ResendEmailAPI which validates RESEND_API_KEY at construction.
        return make_email_tool()
    # Default: in-memory fake — no creds, no network.
    return EmailTool(
        sender="onboarding@resend.dev",
        default_to="founder@passly.gr",
        subject_prefix="[Passly] ",
        api=FakeEmailAPI(),
    )


async def main(real_llm: bool, live: bool) -> None:
    load_dotenv(REPO_ROOT / ".env")

    brief = VentureBrief.from_file(BRIEF_PATH)
    marketing = make_marketing(brief)

    email_tool = build_email_tool(live)

    tools = ToolRegistry()
    tools.register(
        "email_tool", email_tool, escalates="final_approval_before_publish"
    )

    crew = Crew(
        brief=brief,
        roles=[marketing],
        llm=build_llm(real_llm),
        hitl=ScriptedHITL([FounderDecision(action="approve")]),
        tools=tools,
    )

    print(
        f"\n── Marketing email flow "
        f"(LLM = {'Anthropic Haiku' if real_llm else 'mock-haiku'}, "
        f"backend = {'real Resend' if live else 'FakeEmailAPI'}) ──"
    )

    result = await crew.author_flow(
        task_description=(
            "Draft a launch teaser email for Greek café and salon owners. "
            "Keep it warm, peer-to-peer, under 150 words. End with a "
            "short Greek tagline."
        ),
        role="marketing",
        publish_tool="email_tool",
    )

    print(f"  status: {result.status}  events: {len(result.trace)}")
    print(f"  publish_result: {result.final_state.get('publish_result')}")
    if isinstance(email_tool.api, FakeEmailAPI):
        api = email_tool.api
        if api.sent:
            sent = api.sent[0]
            print(f"  fake-api from: {sent['from']}")
            print(f"  fake-api to:   {sent['to']}")
            print(f"  fake-api subject: {sent['subject']!r}")
            print(f"  fake-api text first line: "
                  f"{sent['text'].splitlines()[0]!r}")
    print(
        "  approved-artifact first line: "
        f"{(result.approved_artifact or '').splitlines()[0]!r}"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Marketing role → email (M2 Phase 2 send-email demo)"
    )
    p.add_argument(
        "--real-llm",
        action="store_true",
        help="Use Anthropic Haiku instead of the canned mock draft. "
        "Requires ANTHROPIC_API_KEY.",
    )
    p.add_argument(
        "--live",
        action="store_true",
        help="Send a real email via Resend (FakeEmailAPI otherwise). "
        "Requires RESEND_API_KEY + SFC_EMAIL_FROM + SFC_EMAIL_TO.",
    )
    args = p.parse_args()
    asyncio.run(main(args.real_llm, args.live))
