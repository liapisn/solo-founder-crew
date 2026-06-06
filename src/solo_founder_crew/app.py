"""The live crew daemon — M1 of the "company in Discord" roadmap.

Runs the crew as a long-lived local process: the agents are *online*, you
start a flow from Discord with a slash command, and you approve / reject /
kill it with buttons. Runs are durable across restarts via a SQLite
checkpointer. Built local-first; portable to a VM by changing config only
(see ``docs/running-the-crew.md``).

Run:
    pip install -e ".[runtime]"
    python -m solo_founder_crew.app

Layering
--------
- The *pure* core (``build_tools``, ``publish_tool_for``, ``build_crew``,
  ``PlaceholderLLM``) has no Discord dependency and is unit-tested with an
  ``InMemoryTransport`` + ``MemorySaver``.
- The *Discord* layer (``run`` and the slash commands) lazily imports
  ``discord`` and is exercised live, not in the test suite.

Scope (M1): on-demand flows + founder approval, durable. NOT scheduling
(M3), inbound events (M4), or new flow types (M5).
"""
from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from solo_founder_crew import (
    Crew,
    CrewGenerator,
    LLMResponse,
    RealLLM,
    Role,
    ToolRegistry,
    VentureBrief,
    load_dotenv,
)
from solo_founder_crew.adapters.discord_hitl import DiscordHITL
from solo_founder_crew.config import RuntimeConfig, load_runtime_config

# ─── LLM for the daemon ────────────────────────────────────────────────────────


@dataclass
class PlaceholderLLM:
    """Offline stand-in satisfying ``LLMClient`` — returns a deterministic
    placeholder so the daemon runs end-to-end without an API key. Set
    ``SFC_MODEL=real`` (+ ``ANTHROPIC_API_KEY``) for live drafting."""

    model: str = "placeholder"
    calls: list[dict] = field(default_factory=list)

    def complete(self, system: str, user: str) -> LLMResponse:
        idx = len(self.calls)
        self.calls.append({"call_index": idx, "system": system, "user": user})
        return LLMResponse(
            text=(
                "[placeholder draft — the crew is wired and the founder gate "
                "works. Set SFC_MODEL=real (+ ANTHROPIC_API_KEY) for live "
                "drafting.]"
            ),
            call_index=idx,
        )


# ─── Pure core (no Discord) ─────────────────────────────────────────────────────


async def _stub_tool(arg: str) -> str:
    return f"stub-published:{len(arg)}chars"


def build_tools() -> ToolRegistry:
    """Registry with stub publish tools (real integrations are M2)."""
    tools = ToolRegistry()
    tools.register("publisher_tool", _stub_tool, escalates="final_approval_before_publish")
    tools.register("pr_tool", _stub_tool, escalates="merge_to_main")
    return tools


def publish_tool_for(role: Role) -> str:
    """The publish tool a role ships through (its sole allowlisted tool)."""
    return role.tools[0] if role.tools else "publisher_tool"


def channels_for(roles) -> list[str]:
    """Logical channel names a crew needs — kebab-cased role names, de-duped,
    in roster order. These are the channels the daemon ensures/creates."""
    seen: set[str] = set()
    out: list[str] = []
    for r in roles:
        logical = r.name.replace("_", "-")
        if logical not in seen:
            seen.add(logical)
            out.append(logical)
    return out


def consult_prompt(brief_dict: dict, question: str) -> str:
    """User prompt for an advisory 'consult' — the founder asking a role
    (e.g. the product role as PM) about next moves / upcoming features.

    Advisory, not Author Flow: the role answers as a counterpart, it does
    not draft a publishable artifact and there is no founder gate.
    """
    return "\n".join(
        [
            "VENTURE BRIEF (context):",
            json.dumps(brief_dict, ensure_ascii=False, indent=2),
            "",
            f"THE FOUNDER ASKS: {question}",
            "",
            "Reply as this role advising the founder. Be concise and concrete — "
            "name next moves and upcoming features where relevant, and flag any "
            "decision that would need the founder's sign-off. This is advice in "
            "conversation, not publishable copy; do not produce a final artifact.",
        ]
    )


async def consult(llm, role: Role, brief, question: str) -> str:
    """Run a one-shot advisory turn for ``role`` and return its reply text."""
    resp = await asyncio.to_thread(
        llm.complete, role.system_prompt, consult_prompt(brief.as_dict(), question)
    )
    return resp.text


def build_crew(
    config: RuntimeConfig,
    *,
    transport,
    llm=None,
    checkpointer=None,
) -> tuple[Crew, DiscordHITL]:
    """Assemble the venture's crew + the Discord HITL surface.

    ``transport`` is a ``DiscordTransport`` (live ``DiscordPyTransport`` in
    production, ``InMemoryTransport`` in tests). ``llm`` / ``checkpointer``
    are injectable for tests; production builds them from ``config``.
    """
    brief = VentureBrief.from_file(config.brief_path)
    roles = CrewGenerator(brief=brief).generate().roles
    tools = build_tools()
    if llm is None:
        llm = RealLLM() if config.use_real_llm else PlaceholderLLM()
    hitl = DiscordHITL(
        transport,
        channel_map=config.channel_map,
        default_channel_id=config.default_channel_id,
    )
    crew = Crew(
        brief=brief,
        roles=roles,
        llm=llm,
        hitl=hitl,
        tools=tools,
        checkpointer=checkpointer,
    )
    return crew, hitl


# ─── Checkpointer (durable across restarts) ─────────────────────────────────────


@contextlib.asynccontextmanager
async def open_checkpointer(url: str):
    """Yield a checkpointer for the daemon's lifetime.

    ``sqlite:///path`` → durable ``AsyncSqliteSaver`` (survives restarts).
    ``memory`` (or sqlite unavailable) → in-process ``MemorySaver``.
    """
    if url.startswith("sqlite:///"):
        try:
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        except ImportError:
            print("⚠ langgraph-checkpoint-sqlite not installed — using in-memory "
                  "state (not durable). Install the [runtime] extra for durability.")
        else:
            db_path = url[len("sqlite:///"):]
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            async with AsyncSqliteSaver.from_conn_string(db_path) as saver:
                yield saver
            return
    from langgraph.checkpoint.memory import MemorySaver

    yield MemorySaver()


# ─── Discord layer (lazy import) ────────────────────────────────────────────────


async def ensure_channels(client, config: RuntimeConfig, crew, hitl) -> None:
    """Make sure each role has a Discord channel, creating missing ones.

    Logical channel names are the kebab-cased role names (#marketing,
    #engineering, …). Explicit ``crew.toml`` bindings win and are never
    overwritten. Auto-created channels go under a "<venture> crew" category.
    Requires the bot's **Manage Channels** permission to create; if missing,
    warns and falls back to whatever bindings exist.
    """
    import discord

    guild = client.get_guild(config.guild_id)
    if guild is None:
        print(f"⚠ bot is not a member of guild {config.guild_id} — skipping channel setup.")
        return

    category = None
    created: list[str] = []
    for logical in channels_for(crew.roles):
        if hitl.is_mapped(logical):
            continue  # explicit crew.toml binding wins
        existing = discord.utils.get(guild.text_channels, name=logical)
        if existing is None and config.auto_create_channels:
            try:
                if category is None:
                    cat_name = f"{crew.brief.name} crew"
                    category = discord.utils.get(
                        guild.categories, name=cat_name
                    ) or await guild.create_category(cat_name)
                existing = await guild.create_text_channel(logical, category=category)
                created.append(logical)
            except discord.Forbidden:
                print(
                    "⚠ missing 'Manage Channels' permission — can't auto-create\n"
                    "  channels. Re-invite the bot with Manage Channels, or map\n"
                    "  channels in crew.toml. See docs/running-the-crew.md."
                )
                return
        if existing is not None:
            hitl.register_channel(logical, str(existing.id))
        elif not config.auto_create_channels:
            print(f"⚠ no #{logical} channel and auto-create is off — map it in crew.toml.")
    if created:
        print(f"  created channels: {', '.join('#' + c for c in created)}")


async def run(config: RuntimeConfig) -> None:
    """Connect the bot and serve until interrupted. Requires the [runtime] extra."""
    import discord
    from discord import app_commands

    from solo_founder_crew.adapters.discord_transport import DiscordPyTransport

    config.require_discord()

    client = discord.Client(intents=discord.Intents.default())
    tree = app_commands.CommandTree(client)
    transport = DiscordPyTransport(client)

    async with open_checkpointer(config.checkpointer_url) as checkpointer:
        crew, hitl = build_crew(config, transport=transport, checkpointer=checkpointer)
        transport.bind(hitl.submit_response)
        runs: dict[str, dict] = {}  # thread_id -> {role, task, status}

        role_names = [r.name for r in crew.roles]

        @tree.command(
            name="crew",
            description="Show the current crew and each role's decision rights",
        )
        async def crew_cmd(interaction):  # noqa: ANN001
            lines = [f"**{crew.brief.name}** crew ({len(crew.roles)} roles):"]
            for r in crew.roles:
                dr = r.decision_rights
                lines.append(
                    f"• **{r.name}** — may: {', '.join(dr.can)} · "
                    f"escalates: {', '.join(dr.must_escalate)}"
                )
            await interaction.response.send_message("\n".join(lines), ephemeral=True)

        @tree.command(description="Start an Author Flow for a role; review lands in its channel")
        @app_commands.describe(role="Which role drafts", task="What to draft")
        async def draft(interaction, role: str, task: str):  # noqa: ANN001
            if role not in role_names:
                await interaction.response.send_message(
                    f"Unknown role {role!r}. Crew: {', '.join(role_names)}.",
                    ephemeral=True,
                )
                return
            thread_id = f"run-{interaction.id}"
            runs[thread_id] = {"role": role, "task": task, "status": "running"}
            await interaction.response.send_message(
                f"▶ {role} is drafting — review will appear in the role's channel.",
                ephemeral=True,
            )

            async def _go() -> None:
                chosen = crew.role(role)
                try:
                    result = await crew.author_flow(
                        task_description=task,
                        role=chosen,
                        publish_tool=publish_tool_for(chosen),
                        thread_id=thread_id,
                    )
                    runs[thread_id]["status"] = result.status
                except Exception as e:  # surface, don't crash the daemon
                    runs[thread_id]["status"] = f"error: {e}"

            asyncio.create_task(_go())

        @tree.command(
            name="ask",
            description="Ask a role for advice (default: product/PM); reply posts in its channel",
        )
        @app_commands.describe(
            question="What to ask", role="Which role to ask (default: product)"
        )
        async def ask(interaction, question: str, role: str = "product"):  # noqa: ANN001
            if role not in role_names:
                await interaction.response.send_message(
                    f"Unknown role {role!r}. Crew: {', '.join(role_names)}.",
                    ephemeral=True,
                )
                return
            logical = role.replace("_", "-")
            cid = hitl.channel_for(logical)
            if cid is None:
                await interaction.response.send_message(
                    f"No channel bound for {role}. Enable auto-create or map one "
                    f"in crew.toml.",
                    ephemeral=True,
                )
                return
            await interaction.response.send_message(
                f"Asked **{role}** — reply posting in <#{cid}>.", ephemeral=True
            )
            chosen = crew.role(role)

            async def _go() -> None:
                try:
                    answer = await consult(crew.llm, chosen, crew.brief, question)
                except Exception as e:  # surface, don't crash the daemon
                    answer = f"(error: {e})"
                channel = client.get_channel(int(cid)) or await client.fetch_channel(
                    int(cid)
                )
                embed = discord.Embed(
                    title=f"{chosen.name} · reply",
                    description=answer[:4000],
                )
                embed.add_field(name="You asked", value=question[:1024], inline=False)
                await channel.send(embed=embed)

            asyncio.create_task(_go())

        @tree.command(description="Show in-flight runs and gates awaiting your tap")
        async def status(interaction):  # noqa: ANN001
            if not runs:
                await interaction.response.send_message("No runs yet.", ephemeral=True)
                return
            pending = set(hitl.pending_request_ids())
            lines = ["**Runs:**"]
            for tid, r in runs.items():
                awaiting = any(p.startswith(tid) for p in pending)
                flag = " ⏳ awaiting your tap" if awaiting else ""
                lines.append(f"• {r['role']}: {r['status']} — {r['task'][:60]}{flag}")
            await interaction.response.send_message("\n".join(lines), ephemeral=True)

        @client.event
        async def on_ready():  # noqa: ANN202
            guild = discord.Object(id=config.guild_id)
            try:
                # Commands are registered globally; copy them into the guild so
                # a guild-scoped sync picks them up and they appear instantly.
                tree.copy_global_to(guild=guild)
                synced = await tree.sync(guild=guild)
            except discord.Forbidden:
                print(
                    "⚠ Connected, but could NOT register slash commands — the bot\n"
                    "  is missing the 'applications.commands' scope. Re-invite it\n"
                    "  with BOTH 'bot' AND 'applications.commands' (OAuth2 → URL\n"
                    "  Generator), then restart. See docs/running-the-crew.md."
                )
                return
            await ensure_channels(client, config, crew, hitl)
            print(
                f"Crew online as {client.user} · venture={crew.brief.name} · "
                f"roles={role_names} · {len(synced)} commands on guild "
                f"{config.guild_id}"
            )

        print(f"Connecting to Discord (guild {config.guild_id})… Ctrl-C to stop.")
        try:
            await client.start(config.discord_token)
        except discord.LoginFailure:
            print(
                "✗ Discord login failed — DISCORD_BOT_TOKEN is invalid.\n"
                "  It must be the Bot token (Developer Portal → your app → Bot →\n"
                "  Reset Token): ~70 chars with two dots. NOT the Application ID,\n"
                "  Public Key, Client Secret, or a webhook URL. See "
                "docs/running-the-crew.md."
            )
        finally:
            if not client.is_closed():
                await client.close()


def main() -> None:
    load_dotenv(".env")
    import os

    config = load_runtime_config(os.environ)
    asyncio.run(run(config))


if __name__ == "__main__":
    main()
