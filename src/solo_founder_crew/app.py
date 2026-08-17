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
from solo_founder_crew.adapters.discord_events import LOG_CHANNEL, make_discord_event_sink
from solo_founder_crew.adapters.discord_hitl import DiscordHITL
from solo_founder_crew.config import RuntimeConfig, load_runtime_config
from solo_founder_crew.events import (
    ERROR,
    RUN_FINISHED,
    RUN_STARTED,
    CrewEvent,
    LoggingHITL,
)
from solo_founder_crew.runs_registry import RunRecord, RunsRegistry

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


PUBLISH_CHANNEL = "published"  # logical channel approved artifacts go to


def build_tools(*, publisher=None, pr_tool=None) -> ToolRegistry:
    """Registry of publish tools.

    ``publisher`` is the real ``async (text) -> str`` action for
    ``publisher_tool`` (e.g. post to Discord); ``pr_tool`` is the engineering
    role's equivalent. Either omitted falls back to a stub, so the daemon and
    the test suite run with no side effects and no credentials.
    """
    tools = ToolRegistry()
    tools.register(
        "publisher_tool",
        publisher or _stub_tool,
        escalates="final_approval_before_publish",
    )
    tools.register("pr_tool", pr_tool or _stub_tool, escalates="merge_to_main")
    return tools


def make_pr_tool(config: RuntimeConfig, *, sink=None):
    """The engineering role's ``pr_tool``, chosen by configuration.

    Unset ``SFC_PR_REPO`` → ``None``, and ``build_tools`` falls back to the
    stub. That keeps the daemon runnable out of the box: wiring a live coding
    agent to a real repository has to be opted into deliberately, never
    inherited by someone who just cloned the repo and started it.

    With a repo configured, the engineering role gets
    ``ImplementedPRTool``: the approved proposal is implemented by a coding
    agent in a throwaway worktree and lands as a draft PR containing a real
    diff (M2 Phase 3). ``merge_to_main`` is unaffected and stays the founder's.
    """
    if not config.dev_flow_enabled:
        return None

    from solo_founder_crew.adapters.github_pr import make_implemented_pr_tool

    return make_implemented_pr_tool(
        implementer=make_implementer(config),
        repo=config.pr_repo,
        base_branch=config.pr_base_branch,
        sink=sink,
    )


def make_implementer(config: RuntimeConfig):
    """The coding agent, configured once and shared by both flows that use it.

    ``pr_tool`` writes new work on a fresh branch; ``/fix`` continues an
    existing one. Same agent, same worktree isolation, same timeout, same
    decision rights — what differs is where the branch starts and which tier
    the run gets, since a bounded CI fix does not need what an open-ended
    implementation does.
    """
    from pathlib import Path

    from solo_founder_crew.adapters.implementer import ClaudeCodeImplementer

    return ClaudeCodeImplementer(
        repo_path=Path(config.pr_repo_path).expanduser(),
        worktree_root=Path(config.worktree_root).expanduser(),
        base_branch=config.pr_base_branch,
        timeout_seconds=config.implement_timeout_seconds,
        model=config.implement_model,
        effort=config.implement_effort,
        fix_model=config.fix_model,
        fix_effort=config.fix_effort,
    )


def make_ci_fix(config: RuntimeConfig, *, sink=None):
    """The ``/fix`` flow, or ``None`` when the Dev Flow is off.

    Gated on the same config as ``pr_tool``: without a repository to point at,
    there is no red CI for the crew to be sent at.
    """
    if not config.dev_flow_enabled:
        return None

    from solo_founder_crew.adapters.ci_fix import make_ci_fix_flow

    return make_ci_fix_flow(
        implementer=make_implementer(config), repo=config.pr_repo, sink=sink
    )


def make_discord_publisher(client, guild_id: int):
    """A real ``publisher_tool``: post an approved artifact to #published.

    M2's first real outbound action — when the founder taps Approve, the
    Author Flow's publish step runs this, so the artifact actually appears in
    Discord (vs the old stub). External channels (email, PR, sheets) are M2
    follow-ups behind the same ToolRegistry seam.
    """

    async def publish(text: str) -> str:
        import discord

        guild = client.get_guild(guild_id)
        channel = (
            discord.utils.get(guild.text_channels, name=PUBLISH_CHANNEL)
            if guild
            else None
        )
        if channel is None:
            return f"publish-skipped: no #{PUBLISH_CHANNEL} channel"
        embed = discord.Embed(title="📣 Published", description=text[:4000])
        msg = await channel.send(embed=embed)
        return f"published to #{channel.name} (message {msg.id})"

    return publish


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
    publisher=None,
    pr_tool=None,
    sink=None,
) -> tuple[Crew, DiscordHITL]:
    """Assemble the venture's crew + the Discord HITL surface.

    ``transport`` is a ``DiscordTransport`` (live ``DiscordPyTransport`` in
    production, ``InMemoryTransport`` in tests). ``llm`` / ``checkpointer`` /
    ``publisher`` are injectable for tests; production builds them from
    ``config`` (publisher = post-to-Discord).
    """
    brief = VentureBrief.from_file(config.brief_path)
    roles = CrewGenerator(brief=brief).generate().roles
    tools = build_tools(
        publisher=publisher,
        pr_tool=pr_tool if pr_tool is not None else make_pr_tool(config),
    )
    if llm is None:
        llm = RealLLM() if config.use_real_llm else PlaceholderLLM()
    hitl = DiscordHITL(
        transport,
        channel_map=config.channel_map,
        default_channel_id=config.default_channel_id,
    )
    # Report gates and decisions to the activity log without touching the
    # contract itself — LoggingHITL is a decorator over any HITL surface.
    gated = LoggingHITL(inner=hitl, sink=sink) if sink is not None else hitl
    crew = Crew(
        brief=brief,
        roles=roles,
        llm=llm,
        hitl=gated,
        tools=tools,
        checkpointer=checkpointer,
    )
    return crew, hitl


# ─── Checkpointer (durable across restarts) ─────────────────────────────────────


async def _mark_stale_gate(client, *, channel_id: str, message_id: str) -> None:
    """Edit a pre-restart HITL gate message to mark it stale + strip
    its dead buttons.

    Fetches the Discord message identified by ``(channel_id,
    message_id)`` and rewrites its content to point the founder at
    the freshly-posted gate, while clearing its components (so the
    "Approve / Send back / Kill" buttons disappear). Best-effort —
    any failure (message deleted, channel gone, missing permissions)
    is logged and swallowed so a startup hiccup never blocks the
    rest of the respawn.
    """
    try:
        channel = client.get_channel(int(channel_id))
        if channel is None:
            channel = await client.fetch_channel(int(channel_id))
        msg = await channel.fetch_message(int(message_id))
        await msg.edit(
            content="🔄 Run resumed — see the latest gate above.",
            embed=None,
            view=None,
        )
    except Exception as e:
        print(
            f"  · could not mark stale gate "
            f"(channel={channel_id}, message={message_id}): {e}"
        )


async def drive_resume(
    *,
    crew,
    registry,
    runs: dict,
    record,
    announce,
    sink=None,
) -> str:
    """Drive one run from its checkpointed state to a terminal status.

    Shared by the two callers that need it, because they need exactly the
    same thing: the startup respawn (a run whose driver task died with the
    process) and ``/retry`` (a run whose driver died on an exception). The
    difference between those cases lives in the checkpoint, not here —
    ``Crew.resume`` re-posts a gate if the run is parked at one, and
    re-runs the failed node if it stopped on an exception.

    Returns a one-line, founder-readable outcome. Never raises: both
    callers are fire-and-forget tasks where an escaping exception is
    either a silent log line or a dead ``on_ready``.
    """
    try:
        chosen = crew.role(record.role)
        result = await crew.resume(
            thread_id=record.thread_id,
            role=chosen,
            publish_tool=publish_tool_for(chosen),
        )
        runs.setdefault(record.thread_id, {})["status"] = result.status
        registry.set_status(record.thread_id, result.status)
        if sink is not None:
            await sink.emit(
                CrewEvent(
                    kind=RUN_FINISHED,
                    role=record.role,
                    thread_id=record.thread_id,
                    summary=f"run resumed and finished — **{result.status}**",
                    detail=str((result.final_state or {}).get("publish_result", "") or ""),
                )
            )
        await announce(
            record.logical_channel,
            result.status,
            record.revisions,
            record.thread_id,
        )
        return f"Run {record.thread_id} finished: {result.status}."
    except KeyError:
        # The checkpointer no longer has state for this thread — the
        # registry is stale. Drop the record so /status stops showing a
        # phantom run.
        print(
            f"↻ Dropping stale registry entry {record.thread_id}: "
            f"no matching checkpoint state."
        )
        runs.pop(record.thread_id, None)
        registry.remove(record.thread_id)
        return (
            f"Run {record.thread_id} has no saved state left — dropped it. "
            f"Start again with `/draft`."
        )
    except Exception as e:  # don't crash the daemon
        import traceback

        print(f"✗ resume ({record.role}) failed for thread {record.thread_id}:")
        traceback.print_exc()
        runs.setdefault(record.thread_id, {})["status"] = f"error: {e}"
        registry.set_status(record.thread_id, f"error: {e}")
        if sink is not None:
            await sink.emit(
                CrewEvent(
                    kind=ERROR,
                    role=record.role,
                    thread_id=record.thread_id,
                    summary="resume failed",
                    detail=f"```\n{type(e).__name__}: {e}\n```",
                )
            )
        await announce(
            record.logical_channel,
            f"error: {e}",
            record.revisions,
            record.thread_id,
        )
        return f"Resume failed: {type(e).__name__}: {e}"


async def _respawn_pending_runs(
    *,
    registry,
    crew,
    runs: dict,
    announce,
    client=None,
    sink=None,
) -> None:
    """On startup, re-spawn driver tasks for runs that were in flight
    when the previous process died.

    Every record in the registry is first mirrored into the in-memory
    ``runs`` dict, not only the pending ones: ``/status`` is where the
    founder reads a failed run's id, and ``/retry`` is unusable without
    it. A restart used to erase that from view entirely.

    Then, for each *pending* record:

    1. Its ``runs`` entry is marked "running" again.
    2. If the record carries a ``latest_gate_*`` pair (post-M1.6
       registries do), edit the stale Discord message to say
       "🔄 Run resumed — see the latest gate above" and strip its
       buttons. The old buttons can no longer be served by this
       process, so this prevents the founder from clicking them
       and getting Discord's generic "interaction failed".
    3. Spawn an ``asyncio`` task that hands the record to
       ``drive_resume``, which calls ``crew.resume(thread_id, role)``.
       That call re-builds the same graph, reads the paused state from
       the checkpointer, and posts a *fresh* HITL gate message (with
       the live buttons). The fresh gate gets a new Future, and the
       click on its button resolves it normally.
    4. On terminal status (or ``KeyError`` if the checkpointer no
       longer knows about the thread), update both the in-memory
       dict and the persistent registry, then announce the outcome
       in the role's channel.

    Only ``running`` records are pending, so a run that died on an
    exception is *not* picked up here — restarting the daemon must not
    silently re-attempt an outbound action. That retry is the founder's
    call, via ``/retry``, and goes through the same ``drive_resume``.

    The respawn is best-effort: a single bad record must not block
    the daemon from coming online for the rest of the crew.
    """
    for rec in registry.all():
        runs.setdefault(
            rec.thread_id,
            {"role": rec.role, "task": rec.task, "status": rec.status},
        )
    pending = registry.pending()
    if not pending:
        return
    print(
        f"↻ Re-spawning {len(pending)} pending run(s) from registry: "
        + ", ".join(f"{r.thread_id}({r.role})" for r in pending)
    )
    for record in pending:
        # Best-effort: mark the pre-restart gate stale BEFORE we
        # spawn the resume task, so the founder doesn't race the
        # new gate with the old one's dead buttons.
        if (
            client is not None
            and record.latest_gate_channel_id
            and record.latest_gate_message_id
        ):
            await _mark_stale_gate(
                client,
                channel_id=record.latest_gate_channel_id,
                message_id=record.latest_gate_message_id,
            )
        runs[record.thread_id] = {
            "role": record.role,
            "task": record.task,
            "status": "running",
        }

        async def _resume(rec=record) -> None:
            await drive_resume(
                crew=crew,
                registry=registry,
                runs=runs,
                record=rec,
                announce=announce,
                sink=sink,
            )

        asyncio.create_task(_resume())


def _registry_path(checkpointer_url: str) -> Path:
    """Where the operational runs registry lives.

    Co-locates ``runs.json`` with the SQLite checkpointer database so a
    single ``data/`` directory holds all persistent daemon state. For
    in-memory checkpointers the path is still ``./data/runs.json`` —
    harmless if unused; convenient if the user later switches to a
    durable checkpointer.
    """
    if checkpointer_url.startswith("sqlite:///"):
        db_path = Path(checkpointer_url[len("sqlite:///"):])
        return db_path.parent / "runs.json"
    return Path("./data/runs.json")


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


def role_display(logical: str) -> str:
    """Human-facing label for a logical channel / role (e.g. 'customer-support'
    → 'Customer Support'). Used as the per-role webhook identity."""
    return logical.replace("-", " ").title()


async def ensure_channels(client, config: RuntimeConfig, crew, hitl) -> dict:
    """Ensure each role has a channel and a per-role webhook; return the
    ``{logical -> discord.Webhook}`` map used to post under each role's identity.

    Channels: kebab-cased role names (#marketing, …), created under a
    "<venture> crew" category if missing (needs Manage Channels). Explicit
    ``crew.toml`` bindings win. Webhooks: one per channel, named after the
    role, so the role can post under its own name + avatar (needs Manage
    Webhooks; if absent, role posts fall back to the bot identity).
    """
    import discord

    webhooks: dict[str, discord.Webhook] = {}
    guild = client.get_guild(config.guild_id)
    if guild is None:
        print(f"⚠ bot is not a member of guild {config.guild_id} — skipping channel setup.")
        return webhooks

    category = None
    created: list[str] = []
    webhook_denied = False
    # #published is where approved artifacts land (the publisher tool posts
    # here); #crew-logs carries the activity feed.
    for logical in [*channels_for(crew.roles), PUBLISH_CHANNEL, LOG_CHANNEL]:
        # Resolve the channel: explicit binding → existing by name → create.
        channel = None
        if hitl.is_mapped(logical):
            cid = hitl.channel_for(logical)
            channel = client.get_channel(int(cid)) if cid and cid.isdigit() else None
        if channel is None:
            channel = discord.utils.get(guild.text_channels, name=logical)
        if channel is None and config.auto_create_channels:
            try:
                if category is None:
                    cat_name = f"{crew.brief.name} crew"
                    category = discord.utils.get(
                        guild.categories, name=cat_name
                    ) or await guild.create_category(cat_name)
                channel = await guild.create_text_channel(logical, category=category)
                created.append(logical)
            except discord.Forbidden:
                print(
                    "⚠ missing 'Manage Channels' permission — can't auto-create\n"
                    "  channels. Re-invite with Manage Channels, or map channels\n"
                    "  in crew.toml. See docs/running-the-crew.md."
                )
                return webhooks
        if channel is None:
            if not config.auto_create_channels:
                print(f"⚠ no #{logical} channel and auto-create is off — map it in crew.toml.")
            continue

        hitl.register_channel(logical, str(channel.id))

        # Per-role webhook for distinct identity on role posts.
        name = role_display(logical)
        try:
            hooks = await channel.webhooks()
            hook = discord.utils.get(hooks, name=name)
            if hook is None:
                hook = await channel.create_webhook(name=name)
            webhooks[logical] = hook
        except discord.Forbidden:
            webhook_denied = True

    if created:
        print(f"  created channels: {', '.join('#' + c for c in created)}")
    if webhook_denied:
        print(
            "⚠ missing 'Manage Webhooks' permission — role posts will use the\n"
            "  bot's identity instead of per-role names. Re-invite with Manage\n"
            "  Webhooks for distinct teammate identities."
        )
    return webhooks


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
        publisher = make_discord_publisher(client, config.guild_id)
        # The activity log. Inert until ensure_channels binds #crew-logs on
        # connect, so nothing depends on the channel existing.
        sink = make_discord_event_sink(client, None)
        crew, hitl = build_crew(
            config,
            transport=transport,
            checkpointer=checkpointer,
            publisher=publisher,
            pr_tool=make_pr_tool(config, sink=sink),
            sink=sink,
        )
        transport.bind(hitl.submit_response)
        # The `/fix` flow. Built here rather than inside the command so a
        # misconfigured Dev Flow surfaces at startup, not on first use.
        ci_fix = make_ci_fix(config, sink=sink)
        runs: dict[str, dict] = {}  # thread_id -> {role, task, status}
        role_webhooks: dict = {}  # logical -> discord.Webhook (per-role identity)
        # Operational metadata for restart-durability. Lives next to the
        # checkpointer's SQLite DB so a single ``data/`` directory holds
        # all persistent state for the daemon. See runs_registry.py.
        registry = RunsRegistry(_registry_path(config.checkpointer_url))
        # Diagnostic: surface the registry's resolved path + counts at
        # startup so any "respawn didn't fire" issue can be diagnosed
        # from the daemon's stdout without a debugger.
        print(
            f"📂 Registry: {registry.path.resolve()} "
            f"(all={len(registry.all())}, pending={len(registry.pending())})"
        )
        # Install the on_posted hook: every time a HITL gate is posted
        # to Discord, record the (channel_id, message_id) on the run's
        # registry record. On restart we use those coordinates to edit
        # the stale gate before posting a fresh one — closes the M1.5
        # "old buttons say 'interaction failed'" gap.
        def _record_gate(
            *, request, channel_id: str, message_id: str
        ) -> None:
            registry.set_latest_gate(
                request.thread_id, channel_id=channel_id, message_id=message_id
            )

        hitl.set_on_posted(_record_gate)

        role_names = [r.name for r in crew.roles]

        async def _announce_outcome(
            logical: str, status: str, revisions: int, thread_id: str | None = None
        ) -> None:
            """Post a closing line to the role's channel when a flow ends, so
            the founder isn't left guessing (and the stale gate buttons aren't
            the last word)."""
            cid = hitl.channel_for(logical)
            if cid is None:
                return
            text = {
                "shipped": "✅ Approved & published to #published.",
                "killed": "🛑 Run killed — nothing published.",
                "exhausted": (
                    f"⚠ Sent back {revisions} time(s) — revision budget used up, "
                    f"nothing published. Run `/draft` again (raise `revisions:` for "
                    f"more rounds)."
                ),
            }.get(status, f"Run ended: {status}.")
            if status.startswith("error:"):
                # A crashed run is not a lost one: the draft and any decision
                # you already made are in the checkpoint, and the step that
                # died is still queued. Say so — the previous wording left
                # the founder to assume their approval had evaporated.
                cmd = f"`/retry run:{thread_id}`" if thread_id else "`/retry`"
                text = (
                    f"💥 The run hit an error and stopped:\n"
                    f"```\n{status[7:].strip()[:600]}\n```"
                    f"Nothing was lost — your draft and any decision you made are "
                    f"saved. {cmd} re-runs just the step that failed."
                )
            channel = client.get_channel(int(cid)) or await client.fetch_channel(int(cid))
            await channel.send(text)

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
        @app_commands.describe(
            role="Which role drafts",
            task="What to draft",
            revisions="How many times you can Send back before the run ends (default 3)",
        )
        async def draft(interaction, role: str, task: str, revisions: int = 3):  # noqa: ANN001
            if role not in role_names:
                await interaction.response.send_message(
                    f"Unknown role {role!r}. Crew: {', '.join(role_names)}.",
                    ephemeral=True,
                )
                return
            revisions = max(0, min(revisions, 10))
            thread_id = f"run-{interaction.id}"
            logical = role.replace("_", "-")
            runs[thread_id] = {"role": role, "task": task, "status": "running"}
            registry.put(
                RunRecord(
                    thread_id=thread_id,
                    role=role,
                    task=task,
                    revisions=revisions,
                    logical_channel=logical,
                    status="running",
                )
            )
            # Ping the founder on the review gate so it's easy to find/act on.
            transport.set_notify(thread_id, interaction.user.mention)
            await interaction.response.send_message(
                f"▶ {role} is drafting — review will appear in the role's channel "
                f"(up to {revisions} send-backs).",
                ephemeral=True,
            )

            async def _go() -> None:
                chosen = crew.role(role)
                await sink.emit(
                    CrewEvent(
                        kind=RUN_STARTED,
                        role=role,
                        thread_id=thread_id,
                        summary="started a run",
                        detail=f"> {task}",
                    )
                )
                try:
                    result = await crew.author_flow(
                        task_description=task,
                        role=chosen,
                        publish_tool=publish_tool_for(chosen),
                        max_revisions=revisions,
                        thread_id=thread_id,
                    )
                    runs[thread_id]["status"] = result.status
                    registry.set_status(thread_id, result.status)
                    # The publish tool's own message (PR url, escalation notice,
                    # "changed nothing") is the most useful thing to surface.
                    publish_result = str(
                        (result.final_state or {}).get("publish_result", "") or ""
                    )
                    await sink.emit(
                        CrewEvent(
                            kind=RUN_FINISHED,
                            role=role,
                            thread_id=thread_id,
                            summary=f"run finished — **{result.status}**",
                            detail=publish_result,
                        )
                    )
                    await _announce_outcome(
                        logical, result.status, revisions, thread_id
                    )
                except Exception as e:  # don't crash the daemon, but be loud
                    import traceback

                    print(f"✗ /draft ({role}) failed for thread {thread_id}:")
                    traceback.print_exc()
                    runs[thread_id]["status"] = f"error: {e}"
                    registry.set_status(thread_id, f"error: {e}")
                    await sink.emit(
                        CrewEvent(
                            kind=ERROR,
                            role=role,
                            thread_id=thread_id,
                            summary="run failed",
                            detail=f"```\n{type(e).__name__}: {e}\n```",
                        )
                    )
                    await _announce_outcome(
                        logical, f"error: {e}", revisions, thread_id
                    )

            asyncio.create_task(_go())

        @tree.command(
            name="fix",
            description="Send the engineering role at a red CI run on one of its PRs",
        )
        @app_commands.describe(pr="Pull request number, e.g. 22")
        async def fix(interaction, pr: int):  # noqa: ANN001
            if ci_fix is None:
                await interaction.response.send_message(
                    "The Dev Flow is off — set `SFC_PR_REPO` and "
                    "`SFC_PR_REPO_PATH` to enable `/fix`.",
                    ephemeral=True,
                )
                return
            # Deliberately not a RunRecord: `/fix` is a direct tool call, not a
            # checkpointed Author Flow, so there is no graph state for the
            # restart-respawn path to resume. It still shows up in `/status`.
            thread_id = f"fix-{interaction.id}"
            runs[thread_id] = {
                "role": "engineering",
                "task": f"fix red CI on PR #{pr}",
                "status": "running",
            }
            await interaction.response.send_message(
                f"▶ engineering is reading PR #{pr}'s failing job — progress in "
                f"<#{hitl.channel_for(LOG_CHANNEL)}>."
                if hitl.channel_for(LOG_CHANNEL)
                else f"▶ engineering is reading PR #{pr}'s failing job.",
                ephemeral=True,
            )

            async def _go() -> None:
                await sink.emit(
                    CrewEvent(
                        kind=RUN_STARTED,
                        role="engineering",
                        thread_id=thread_id,
                        summary=f"`/fix {pr}` — sent at a red CI run",
                    )
                )
                try:
                    summary = await ci_fix(pr)
                    runs[thread_id]["status"] = "done"
                    kind = RUN_FINISHED
                except Exception as e:  # don't crash the daemon, but be loud
                    import traceback

                    print(f"✗ /fix failed for PR #{pr}:")
                    traceback.print_exc()
                    runs[thread_id]["status"] = f"error: {e}"
                    summary = f"The fix attempt failed: {type(e).__name__}: {e}"
                    kind = ERROR
                # The outcome goes to the log channel first: an agent run can
                # take the better part of the interaction token's 15-minute
                # life, so the ephemeral follow-up is the copy that may not
                # arrive, not the one the founder has to rely on.
                await sink.emit(
                    CrewEvent(
                        kind=kind,
                        role="engineering",
                        thread_id=thread_id,
                        summary=f"`/fix {pr}` finished",
                        detail=summary,
                    )
                )
                with contextlib.suppress(Exception):
                    await interaction.followup.send(summary, ephemeral=True)

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
            mention = interaction.user.mention

            async def _go() -> None:
                try:
                    answer = await consult(crew.llm, chosen, crew.brief, question)
                except Exception as e:  # don't crash the daemon, but be loud
                    import traceback

                    print(f"✗ /ask ({role}) failed:")
                    traceback.print_exc()
                    answer = f"(error: {e})"
                display = role_display(logical)
                embed = discord.Embed(title=f"{display} · reply", description=answer[:4000])
                embed.add_field(name="You asked", value=question[:1024], inline=False)
                # @mention the asker so they're pinged to read it.
                hook = role_webhooks.get(logical)
                if hook is not None:
                    # Post under the role's own name (per-role identity).
                    await hook.send(content=mention, embed=embed, username=display)
                else:
                    channel = client.get_channel(int(cid)) or await client.fetch_channel(
                        int(cid)
                    )
                    await channel.send(content=mention, embed=embed)

            asyncio.create_task(_go())

        @tree.command(
            name="retry",
            description="Re-run the step a failed run died on (nothing is re-drafted)",
        )
        @app_commands.describe(run="Run id, as shown by /status")
        async def retry(interaction, run: str):  # noqa: ANN001
            record = registry.get(run)
            if record is None:
                known = [r.thread_id for r in registry.all() if not r.is_pending]
                await interaction.response.send_message(
                    f"No run {run!r} in the registry."
                    + (f" Known: {', '.join(known[-5:])}." if known else ""),
                    ephemeral=True,
                )
                return
            if record.status in ("shipped", "killed", "exhausted"):
                await interaction.response.send_message(
                    f"Run {run} already ended: **{record.status}**. Nothing to "
                    f"retry — start a new one with `/draft`.",
                    ephemeral=True,
                )
                return
            await interaction.response.send_message(
                f"↻ Retrying {run} ({record.role}) — the founder decisions it "
                f"already has are not asked again.",
                ephemeral=True,
            )

            async def _go() -> None:
                await sink.emit(
                    CrewEvent(
                        kind=RUN_STARTED,
                        role=record.role,
                        thread_id=run,
                        summary="`/retry` — re-running the step that failed",
                    )
                )
                outcome = await drive_resume(
                    crew=crew,
                    registry=registry,
                    runs=runs,
                    record=record,
                    announce=_announce_outcome,
                    sink=sink,
                )
                with contextlib.suppress(Exception):
                    await interaction.followup.send(outcome, ephemeral=True)

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
                # A failed run is retryable, so it has to show the id that
                # `/retry` wants. Healthy runs stay uncluttered.
                if str(r.get("status", "")).startswith("error:"):
                    flag += f" · `/retry run:{tid}`"
                lines.append(
                    f"• {r['role']}: {r['status']} — {r.get('task', '')[:60]}{flag}"
                )
            await interaction.response.send_message("\n".join(lines), ephemeral=True)

        @client.event
        async def on_ready():  # noqa: ANN202
            # Wrap the whole handler so any failure surfaces as a
            # visible traceback in stdout rather than disappearing
            # into discord.py's silent event-handler error path. This
            # is debug-grade defence; cheap to keep on permanently.
            try:
                print("· on_ready: syncing slash commands…")
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
                print(f"· on_ready: synced {len(synced)} commands; ensuring channels…")
                role_webhooks.update(await ensure_channels(client, config, crew, hitl))
                sink.channel_id = hitl.channel_for(LOG_CHANNEL)
                if sink.channel_id:
                    print(f"· activity log → #{LOG_CHANNEL}")
                else:
                    print(f"⚠ no #{LOG_CHANNEL} channel bound — activity log is off.")
                print(
                    f"Crew online as {client.user} · venture={crew.brief.name} · "
                    f"roles={role_names} · {len(synced)} commands on guild "
                    f"{config.guild_id}"
                )
                # Restart-durability: re-spawn drivers for runs that were
                # still in flight when the previous process died. Each
                # resume task posts a fresh HITL gate in the role's
                # channel (the old message's buttons are stale and will
                # show "interaction failed" if clicked — that's a known
                # gap; see M1.5 follow-up note in docs/roadmap.md).
                print(
                    f"· on_ready: checking for pending runs to respawn "
                    f"(registry has {len(registry.pending())} pending)…"
                )
                await _respawn_pending_runs(
                    registry=registry,
                    crew=crew,
                    runs=runs,
                    announce=_announce_outcome,
                    client=client,
                    sink=sink,
                )
                print("· on_ready: startup complete.")
            except Exception:  # don't crash the daemon's event loop silently
                import traceback

                print("✗ on_ready raised — daemon may still be online but startup "
                      "did NOT complete cleanly:")
                traceback.print_exc()

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
