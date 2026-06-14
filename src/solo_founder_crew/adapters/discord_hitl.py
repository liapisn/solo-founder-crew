"""``DiscordHITL`` — the HITL Contract rendered through a Discord channel.

This is the worked *production surface* for Component 5 (Ch.3 §3.8.6). It
lets a solo founder approve, reject, or kill crew actions from a chat
application on their phone — no terminal — so the crew "feels like a
company" the founder supervises.

Design discipline (stated in the thesis and enforced here): **Discord is a
rendering and input surface only, never the source of truth.** All
orchestration state lives in the runtime and its checkpointer; the
``HITLRequest`` is the entire interface between them. This adapter contains
*no* orchestration logic — it turns a ``HITLRequest`` into a message and a
button-tap back into a ``FounderDecision``, and nothing more.

Dependency posture: this module does **not** import ``discord.py`` at
module load, so the package stays importable (and testable) without the
extra dependency. The Discord wiring is isolated behind the
``DiscordTransport`` protocol; a real implementation lazily imports
``discord`` (see ``DiscordPyTransport`` notes). The ``InMemoryTransport``
test double exercises the full pause/resume path with no network.

How the pause/resume of §3.8.4 maps onto Discord
------------------------------------------------
1. The runtime's gate node calls ``interrupt(request.to_interrupt_payload())``;
   LangGraph checkpoints the run.
2. ``Crew.author_flow`` calls ``await hitl.review(request)``.
3. ``DiscordHITL.review`` registers a ``Future`` keyed by ``request_id``,
   then asks the transport to post the request to the mapped channel.
4. ``review`` awaits the future — for seconds or days. Nothing is busy-held;
   the run's state is on disk via the checkpointer.
5. The founder taps a button. The bot's interaction handler builds a
   ``FounderResponse`` and calls ``DiscordHITL.submit_response`` (or, for a
   ``reject`` that ``requires_feedback``, first opens a modal and submits
   once text is entered).
6. ``submit_response`` resolves the future; ``review`` returns the
   ``FounderDecision``; ``author_flow`` resumes the graph with
   ``Command(resume=...)``.

Citable in Ch.3 §3.8.6.
"""
from __future__ import annotations

import asyncio
from typing import Callable, Protocol

from solo_founder_crew.hitl import FounderDecision
from solo_founder_crew.hitl_request import FounderResponse, HITLRequest


# Signature for the optional ``on_posted`` callback the daemon installs
# on ``DiscordHITL`` to record the Discord coordinates of every posted
# gate. Invoked synchronously after the transport returns; called with
# keyword arguments so callers can add fields later without breaking
# existing implementations.
OnPostedCallback = Callable[..., None]


class DiscordTransport(Protocol):
    """The seam between this adapter and Discord proper.

    A concrete transport owns the Discord client, channel objects, and
    interaction components. Keeping it a one-method protocol means the
    adapter's pause/resume logic is testable with an in-memory double and
    the framework never hard-depends on ``discord.py``.
    """

    async def post_request(self, request: HITLRequest, *, channel_id: str) -> str:
        """Render ``request`` into the given Discord channel.

        Returns an opaque message id (useful for editing the message to
        "Approved by founder" once a decision arrives). The concrete
        implementation renders ``request.artifact`` as the body,
        ``request.options`` as buttons, and — for an option whose
        ``requires_feedback`` is true — wires the button to open a modal.
        """
        ...


class UnknownChannel(KeyError):
    """Raised when a request's logical channel has no Discord binding."""


class DiscordHITL:
    """A ``HITLContract`` implementation backed by a Discord channel.

    ``channel_map`` binds the *logical* channel names the runtime emits
    (e.g. ``"marketing"``, ``"customer-support"``) to concrete Discord
    channel ids. The runtime names an intent; the adapter owns the binding —
    so the framework stays vendor-neutral.

    This satisfies the *enriched* HITL contract: ``review`` takes a
    ``HITLRequest`` rather than a bare string. See ``runtime.py`` /
    ``crew.py`` for the one-line change that has the gate emit a
    ``HITLRequest`` (the gate already interrupts with a dict; the change is
    to build it via ``HITLRequest(...).to_interrupt_payload()`` and pass the
    rebuilt request to ``hitl.review``).
    """

    def __init__(
        self,
        transport: DiscordTransport,
        channel_map: dict[str, str],
        *,
        default_channel_id: str | None = None,
        on_posted: "OnPostedCallback | None" = None,
    ) -> None:
        self._transport = transport
        self._channel_map = dict(channel_map)
        self._default_channel_id = default_channel_id
        # request_id -> Future[FounderDecision]. The pending gate(s).
        self._pending: dict[str, asyncio.Future[FounderDecision]] = {}
        # Optional hook the daemon installs to record the Discord
        # coordinates (channel_id, message_id) of every posted gate so
        # a restart can edit the stale message before the resumed flow
        # posts a fresh one. The callback is invoked synchronously
        # after ``transport.post_request`` returns. Failures inside the
        # callback are swallowed so they never break a live gate post.
        self._on_posted = on_posted

    # ── HITLContract surface ────────────────────────────────────────────

    async def review(self, request: HITLRequest) -> FounderDecision:
        """Post the request to Discord and await the founder's tap.

        Idempotent on ``request_id``: re-entry returns the existing future,
        so a runtime that retries the gate after a restart re-attaches to a
        still-pending decision rather than double-posting.
        """
        loop = asyncio.get_event_loop()
        existing = self._pending.get(request.request_id)
        if existing is not None and not existing.done():
            return await existing

        future: asyncio.Future[FounderDecision] = loop.create_future()
        self._pending[request.request_id] = future

        channel_id = self._resolve_channel(request.channel)
        try:
            message_id = await self._transport.post_request(
                request, channel_id=channel_id
            )
        except Exception:
            self._pending.pop(request.request_id, None)
            raise
        # Fire the on_posted hook, if installed. Defensive try/except
        # — a buggy callback must never break the live gate.
        if self._on_posted is not None and message_id is not None:
            try:
                self._on_posted(
                    request=request,
                    channel_id=channel_id,
                    message_id=str(message_id),
                )
            except Exception:
                import traceback

                print("⚠ on_posted callback raised (gate post itself succeeded):")
                traceback.print_exc()

        try:
            return await future
        finally:
            self._pending.pop(request.request_id, None)

    # ── Inbound from the bot's interaction handler ──────────────────────

    def submit_response(self, response: FounderResponse) -> None:
        """Resolve the parked gate for ``response.request_id``.

        Called by the bot when the founder taps a button (and, for a
        feedback-requiring option, after the modal is submitted). Unknown or
        already-resolved request ids are ignored — a double-tap is harmless.
        """
        future = self._pending.get(response.request_id)
        if future is None or future.done():
            return
        future.set_result(response.to_decision())

    def pending_request_ids(self) -> tuple[str, ...]:
        """Request ids currently awaiting a founder decision (for status)."""
        return tuple(rid for rid, f in self._pending.items() if not f.done())

    def set_on_posted(self, callback: "OnPostedCallback | None") -> None:
        """Install (or clear) the gate-posted hook after construction.

        Convenient for daemons that build the HITL through a helper
        (e.g. :func:`solo_founder_crew.app.build_crew`) and only have
        the registry to thread into the hook *after* the crew is
        assembled. Pass ``None`` to remove a previously installed hook.
        """
        self._on_posted = callback

    # ── Channel bindings (set at startup, e.g. by auto-create) ───────────

    def register_channel(self, logical: str, channel_id: str) -> None:
        """Bind a logical channel name to a concrete Discord channel id."""
        self._channel_map[logical] = channel_id

    def is_mapped(self, logical: str) -> bool:
        """True if ``logical`` already has an explicit channel binding."""
        return logical in self._channel_map

    def channel_for(self, logical: str) -> str | None:
        """Resolve a logical channel to a concrete id (falls back to default)."""
        return self._channel_map.get(logical) or self._default_channel_id

    # ── internals ───────────────────────────────────────────────────────

    def _resolve_channel(self, logical: str | None) -> str:
        if logical is not None and logical in self._channel_map:
            return self._channel_map[logical]
        if self._default_channel_id is not None:
            return self._default_channel_id
        raise UnknownChannel(
            f"No Discord channel bound for logical channel {logical!r} "
            f"(known: {sorted(self._channel_map)}); pass default_channel_id "
            f"to DiscordHITL to catch-all."
        )


class InMemoryTransport:
    """Test double — records posted requests, never touches the network.

    Lets the full ``review`` / ``submit_response`` pause/resume path be
    exercised in a unit test (and in the demo below) with no Discord client.
    """

    def __init__(self) -> None:
        self.posted: list[tuple[str, HITLRequest]] = []
        self.notify: dict[str, str] = {}

    def set_notify(self, thread_id: str, mention: str) -> None:
        self.notify[thread_id] = mention

    async def post_request(self, request: HITLRequest, *, channel_id: str) -> str:
        self.posted.append((channel_id, request))
        return f"msg-{request.request_id}"


# ── Notes for a real transport (kept as prose, not a hard dependency) ────
#
# A production DiscordPyTransport would, roughly:
#
#   import discord                     # lazy: inside __init__, not at module top
#   class DiscordPyTransport:
#       def __init__(self, client: "discord.Client", hitl: DiscordHITL): ...
#       async def post_request(self, request, *, channel_id):
#           channel = self._client.get_channel(int(channel_id))
#           view = self._build_view(request)        # discord.ui.View of Buttons
#           embed = self._build_embed(request)      # title=role, body=artifact
#           msg = await channel.send(embed=embed, view=view)
#           return str(msg.id)
#
#   Each Button's callback builds a FounderResponse and calls
#   hitl.submit_response(...). A button whose ReviewOption.requires_feedback
#   is true opens a discord.ui.Modal first and submits on modal completion.
#
# The bot needs only the "bot" scope plus message + interaction permissions
# in the mapped channels. Per the design discipline above, the transport
# holds no run state — every datum it needs is on the HITLRequest.


async def _demo() -> None:
    """Tiny end-to-end demo of the pause/resume path with no Discord.

    Run: ``python -m solo_founder_crew.adapters.discord_hitl``
    """
    from solo_founder_crew.hitl_request import Artifact

    transport = InMemoryTransport()
    hitl = DiscordHITL(
        transport,
        channel_map={"marketing": "111", "customer-support": "222"},
    )
    request = HITLRequest(
        request_id="req-demo-1",
        thread_id="run-abc",
        venture_id="passly",
        turn=1,
        role_name="marketing",
        action="final_approval_before_publish",
        escalation_reason="Marketing must escalate before anything is published.",
        artifact=Artifact(
            content="🎟️ Passly is here — loyalty passes in Apple/Google Wallet…",
            summary="Launch announcement draft",
        ),
    )

    # The runtime would `await hitl.review(request)`; we run it concurrently
    # with a simulated founder tapping "approve" a moment later.
    async def founder_taps_later() -> None:
        await asyncio.sleep(0.1)
        hitl.submit_response(FounderResponse(request_id="req-demo-1", action="approve"))

    decision, _ = await asyncio.gather(hitl.review(request), founder_taps_later())
    channel_id, posted = transport.posted[0]
    print(f"posted to channel {channel_id} for role {posted.role_display_name!r}")
    print(f"founder decision: {decision.action}")


if __name__ == "__main__":
    asyncio.run(_demo())
