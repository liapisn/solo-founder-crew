"""``DiscordPyTransport`` — the live Discord wiring for :class:`DiscordHITL`.

This is the concrete ``DiscordTransport`` that renders a ``HITLRequest`` into
a real Discord message (embed + interaction buttons) and turns the founder's
tap back into a ``FounderResponse``. It is kept in its own module, and
``discord`` is imported lazily inside ``__init__``, so importing the package
(or running the test suite) never requires ``discord.py`` to be installed.
Install the optional extra to use it::

    pip install -e ".[discord]"

Wiring (see ``examples/passly_discord.py`` for the full runnable demo)::

    client = discord.Client(intents=discord.Intents.default())
    transport = DiscordPyTransport(client)
    hitl = DiscordHITL(transport, channel_map={"marketing": "<channel id>"})
    transport.bind(hitl.submit_response)   # close the request/response loop

The button callbacks call the bound responder (``hitl.submit_response``),
which resolves the parked ``Future`` inside ``DiscordHITL.review`` — exactly
the pause/resume path described in Ch.3 §3.8.4/§3.8.6. An option whose
``requires_feedback`` is true (the ``reject`` case) opens a modal first and
submits once the founder types guidance.

Persistence note: buttons use stable ``custom_id``s of the form
``hitl:<request_id>:<action>``, so the view *could* be re-registered on
startup (``client.add_view(...)``) to survive a bot restart. The demo keeps
a single in-process view (``timeout=None``); full cross-restart view
re-registration is an extension, not required for the founder gate itself
(the run state survives via the LangGraph checkpointer regardless).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from solo_founder_crew.hitl_request import FounderResponse, HITLRequest

if TYPE_CHECKING:  # pragma: no cover - typing only
    import discord


Responder = Callable[[FounderResponse], None]


class DiscordPyTransport:
    """Live Discord transport for :class:`DiscordHITL`.

    Holds the ``discord.Client`` and a ``responder`` callback
    (``hitl.submit_response``). Constructed before the ``DiscordHITL`` it
    serves (the adapter takes the transport), so the responder is supplied
    afterwards via :meth:`bind`.
    """

    def __init__(self, client: "discord.Client") -> None:
        # Lazy import: keeps discord.py out of the core import path / tests.
        import discord  # noqa: F401  (validate the optional dep is present)

        self._discord = discord
        self._client = client
        self._responder: Responder | None = None
        # Per-run state, keyed by HITLRequest.thread_id:
        self._threads: dict[str, "discord.Thread"] = {}  # revision threads
        self._notify: dict[str, str] = {}  # who to @mention on the gate

    def bind(self, responder: Responder) -> None:
        """Supply the callback that resolves a parked gate (hitl.submit_response)."""
        self._responder = responder

    def set_notify(self, thread_id: str, mention: str) -> None:
        """Record who to @mention when this run's gate is posted (e.g. the
        founder who started it). Keyed by the run's thread_id."""
        self._notify[thread_id] = mention

    async def post_request(self, request: HITLRequest, *, channel_id: str) -> str:
        if self._responder is None:
            raise RuntimeError(
                "DiscordPyTransport.bind(responder) must be called before "
                "posting (pass hitl.submit_response)."
            )
        channel = self._client.get_channel(int(channel_id))
        if channel is None:
            channel = await self._client.fetch_channel(int(channel_id))
        embed = self._build_embed(request)
        view = _DecisionView(self._discord, request, self._responder)
        mention = self._notify.get(request.thread_id)

        # Turn 1 posts to the channel and opens a thread; revision turns
        # (2+) post inside that thread so the channel doesn't fill with
        # successive draft versions.
        if request.turn <= 1:
            message = await channel.send(content=mention, embed=embed, view=view)
            try:
                name = f"{request.role_display_name}: {request.artifact.summary or 'review'}"
                self._threads[request.thread_id] = await message.create_thread(
                    name=name[:90]
                )
            except (self._discord.Forbidden, self._discord.HTTPException):
                pass  # no thread perms — revisions just stay in-channel
            return str(message.id)

        target = self._threads.get(request.thread_id) or channel
        message = await target.send(content=mention, embed=embed, view=view)
        return str(message.id)

    # ── rendering ───────────────────────────────────────────────────────────

    def _build_embed(self, request: "HITLRequest") -> "discord.Embed":
        discord = self._discord
        body = request.artifact.content
        if len(body) > 4000:  # Discord embed description hard limit
            body = body[:3997] + "…"
        embed = discord.Embed(
            title=f"{request.role_display_name} · approval needed",
            description=body,
        )
        if request.escalation_reason:
            embed.add_field(
                name="Why you", value=request.escalation_reason, inline=False
            )
        task = (request.context or {}).get("task_description")
        if task:
            embed.add_field(name="Task", value=str(task)[:1024], inline=False)
        embed.set_footer(
            text=(
                f"{request.venture_id} · #{request.channel} · "
                f"turn {request.turn} · {request.action}"
            )
        )
        return embed


def _make_button_callback(
    discord_mod,
    request: HITLRequest,
    option,
    responder: Responder,
):
    """Build the async callback for one decision button."""

    async def callback(interaction: "discord.Interaction") -> None:
        if option.requires_feedback:
            await interaction.response.send_modal(
                _FeedbackModal(discord_mod, request, option, responder)
            )
            return
        responder(
            FounderResponse(
                request_id=request.request_id,
                action=option.action,
                responder=str(interaction.user),
            )
        )
        await interaction.response.edit_message(
            content=f"✅ You chose **{option.label}**.", view=None
        )

    return callback


def _DecisionView(discord_mod, request: HITLRequest, responder: Responder):
    """Construct a discord.ui.View with one button per request option.

    Written as a factory (not a module-level subclass) so the module imports
    without discord.py present — the ``discord`` types are only touched when
    a live transport actually builds a view.
    """
    view = discord_mod.ui.View(timeout=None)
    for option in request.options:
        style = {
            "approve": discord_mod.ButtonStyle.success,
            "reject": discord_mod.ButtonStyle.secondary,
            "kill": discord_mod.ButtonStyle.danger,
        }.get(option.action, discord_mod.ButtonStyle.primary)
        button = discord_mod.ui.Button(
            label=option.label,
            style=style,
            custom_id=f"hitl:{request.request_id}:{option.action}",
        )
        button.callback = _make_button_callback(
            discord_mod, request, option, responder
        )
        view.add_item(button)
    return view


def _FeedbackModal(discord_mod, request: HITLRequest, option, responder: Responder):
    """Build a modal that collects feedback for a requires_feedback option."""

    class FeedbackModal(discord_mod.ui.Modal, title="Send back with notes"):
        feedback = discord_mod.ui.TextInput(
            label="What should change?",
            style=discord_mod.TextStyle.paragraph,
            required=False,
            max_length=1000,
        )

        async def on_submit(self, interaction: "discord.Interaction") -> None:
            responder(
                FounderResponse(
                    request_id=request.request_id,
                    action=option.action,
                    feedback=str(self.feedback) or None,
                    responder=str(interaction.user),
                )
            )
            await interaction.response.edit_message(
                content=f"↩️ Sent back: {str(self.feedback) or '(no notes)'}",
                view=None,
            )

    return FeedbackModal()
