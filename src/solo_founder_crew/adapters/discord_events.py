"""Discord adapter for the crew activity log.

Posts ``CrewEvent``s as plain messages to one logical channel (``#crew-logs``
by default). Deliberately not embeds and not per-role webhooks: this is a
scrolling operational feed, and it should read like a log rather than compete
visually with the HITL gate, which is the thing that actually wants attention.

Failures here are swallowed. A crew run must never die because a log message
could not be posted.
"""

from __future__ import annotations

from dataclasses import dataclass

from solo_founder_crew.events import CrewEvent

LOG_CHANNEL = "crew-logs"


@dataclass
class DiscordEventSink:
    """Posts to a Discord channel via the same transport the HITL surface uses.

    ``send`` is an ``async (channel_id: str, content: str) -> None`` callable,
    injected rather than importing ``discord`` here — that keeps this module
    importable (and testable) without the runtime extra installed.
    """

    send: object  # async (channel_id, content) -> None
    channel_id: str | None = None
    max_chars: int = 1800  # Discord's limit is 2000; leave room for the prefix

    async def emit(self, event: CrewEvent) -> None:
        if not self.channel_id:
            return
        content = event.render()
        if len(content) > self.max_chars:
            content = content[: self.max_chars - 1] + "…"
        try:
            await self.send(self.channel_id, content)  # type: ignore[operator]
        except Exception as exc:  # noqa: BLE001 — logging must never break a run
            print(f"⚠ crew-log post failed ({type(exc).__name__}: {exc})")


def make_discord_event_sink(client, channel_id: str | None):
    """Build a sink that posts with the bot's own identity.

    ``client`` is a live ``discord.Client``. Returns a ``DiscordEventSink``;
    with no channel bound it is inert, which is the no-log-channel case.
    """

    async def send(cid: str, content: str) -> None:
        channel = client.get_channel(int(cid))
        if channel is None:
            return
        await channel.send(content)

    return DiscordEventSink(send=send, channel_id=channel_id)
