"""Passly launch with a *live* Discord HITL gate (Ch.3 §3.8.6).

The founder approves / sends back / kills the draft from a Discord channel —
on their phone, no terminal. Same Author Flow as ``passly_launch.py``; only
the HITL surface changes.

Prerequisites
-------------
1. Install the optional extra:    pip install -e ".[discord]"
2. Create a bot and get its token (see docs/discord-setup.md).
3. Put these in ``.env`` (repo root):
       DISCORD_BOT_TOKEN=...           # from the Developer Portal
       DISCORD_MARKETING_CHANNEL_ID=...# right-click a channel → Copy Channel ID
       ANTHROPIC_API_KEY=...           # only if you pass --real-llm
4. Invite the bot to your server with the "bot" scope and permission to
   Send Messages in that channel.

Run
---
    .venv/bin/python examples/passly_discord.py            # mock LLM (free)
    .venv/bin/python examples/passly_discord.py --real-llm # Anthropic Haiku

The bot connects, posts the draft to the marketing channel with
[Approve] [Send back] [Kill run] buttons, waits for your tap (minutes or
days — the run is checkpointed), then publishes / revises / aborts and
prints the result before disconnecting.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from solo_founder_crew import (
    Crew,
    MockLLM,
    RealLLM,
    ToolRegistry,
    VentureBrief,
    load_dotenv,
    make_marketing,
)
from solo_founder_crew.adapters.discord_hitl import DiscordHITL
from solo_founder_crew.adapters.discord_transport import DiscordPyTransport

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIEF_PATH = REPO_ROOT / "scenarios" / "fixtures" / "passly_brief.json"
OUT_DIR = REPO_ROOT / "examples" / "out"

DRAFT_RESPONSES = [
    "Introducing Passly — digital wallet passes and AI marketing for Greek SMBs.\n\n"
    "Loyalty offers live in Apple/Google Wallet. AI drafts campaigns, "
    "owner ships in two clicks. Pre-launch, early-access available.\n",
    "Έρχεται το Passly — οι πελάτες σου, ένα tap μακριά.\n\n"
    "Passes loyalty στο Apple/Google Wallet· το AI γράφει την καμπάνια, "
    "εσύ τη στέλνεις σε 2 κλικ. Pre-launch — ζητάμε early-access.\n",
]


async def main(real_llm: bool) -> None:
    load_dotenv(REPO_ROOT / ".env")

    import discord  # local import: only needed for this live example

    token = os.environ.get("DISCORD_BOT_TOKEN")
    channel_id = os.environ.get("DISCORD_MARKETING_CHANNEL_ID")
    if not token or not channel_id:
        raise SystemExit(
            "Set DISCORD_BOT_TOKEN and DISCORD_MARKETING_CHANNEL_ID in .env "
            "(see docs/discord-setup.md)."
        )

    brief = VentureBrief.from_file(BRIEF_PATH)
    role = make_marketing(brief)

    tools = ToolRegistry()

    async def publisher(text: str) -> str:
        return f"shipped:{len(text)}chars"

    tools.register(
        "publisher_tool", publisher, escalates="final_approval_before_publish"
    )

    llm = RealLLM() if real_llm else MockLLM(responses=DRAFT_RESPONSES)

    client = discord.Client(intents=discord.Intents.default())
    transport = DiscordPyTransport(client)
    hitl = DiscordHITL(transport, channel_map={"marketing": channel_id})
    transport.bind(hitl.submit_response)

    crew = Crew(brief=brief, roles=[role], llm=llm, hitl=hitl, tools=tools)

    @client.event
    async def on_ready() -> None:  # noqa: ANN202
        print(f"Bot connected as {client.user}. Posting the gate…")
        try:
            result = await crew.author_flow(
                task_description=(
                    "Draft a launch announcement for this venture. Match the "
                    "voice. Respect every constraint. Keep under 150 words."
                ),
                max_revisions=2,
            )
            print(
                f"\n── result ──\nstatus    = {result.status}\n"
                f"thread_id = {result.thread_id}\nevents    = {len(result.trace)}"
            )
            OUT_DIR.mkdir(exist_ok=True)
            if result.approved_artifact:
                out = OUT_DIR / "final_announcement_discord.txt"
                out.write_text(result.approved_artifact, encoding="utf-8")
                print(f"approved artifact written to {out}")
            result.trace.write(OUT_DIR / "run_trace_discord.json")
        finally:
            await client.close()

    print("Connecting to Discord… (Ctrl-C to abort)")
    await client.start(token)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Passly with a live Discord HITL gate")
    p.add_argument("--real-llm", action="store_true")
    args = p.parse_args()
    asyncio.run(main(args.real_llm))
