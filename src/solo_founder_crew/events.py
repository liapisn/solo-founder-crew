"""Crew activity events — the operational log of what the crew is doing.

The HITL gate tells the founder when a *decision* is needed. It says nothing
about everything either side of that: which run started, that a draft is
waiting, what the founder decided, that a coding agent is working, what it
cost, whether a pull request opened. Until now that history lived only in the
daemon's stdout and the LangGraph checkpointer — which is why a live run could
fail with a bare ``FileNotFoundError`` and look, from Discord, like nothing
happened at all.

``CrewEventSink`` is the seam for that stream. Same Protocol-with-fake recipe
as ``HITLContract``, ``LLMClient``, ``GitHubAPI`` and ``Implementer``: a real
adapter posts to Discord, ``RecordingEventSink`` keeps events in memory for
tests, and ``NullEventSink`` is the default so nothing is required to run.

Worth citing in Ch.4: these events *are* the case-study measurements — gate
latency, revision counts, approve/reject ratios, escalation frequency, cost
per change — captured while the venture is built rather than reconstructed
afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

# ─── Event kinds ────────────────────────────────────────────────────────────
# Deliberately a small, closed vocabulary: a log nobody can read at a glance
# is a log nobody reads.

RUN_STARTED = "run_started"
AWAITING_REVIEW = "awaiting_review"
DECISION = "decision"
IMPLEMENTING = "implementing"
IMPLEMENTED = "implemented"
PR_OPENED = "pr_opened"
ESCALATION = "escalation"
RUN_FINISHED = "run_finished"
ERROR = "error"

#: Rendered prefix per kind. Keeps the Discord surface readable without
#: teaching every call site how to format itself.
ICONS = {
    RUN_STARTED: "▶️",
    AWAITING_REVIEW: "⏸️",
    DECISION: "🫵",
    IMPLEMENTING: "🛠️",
    IMPLEMENTED: "📦",
    PR_OPENED: "🔀",
    ESCALATION: "⚠️",
    RUN_FINISHED: "✅",
    ERROR: "❌",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class CrewEvent:
    """One thing that happened, addressed to a human reading a channel."""

    kind: str
    role: str
    summary: str
    thread_id: str = ""
    detail: str = ""
    timestamp: str = field(default_factory=_now)

    def render(self) -> str:
        """A single readable line, plus an indented detail line if present."""
        icon = ICONS.get(self.kind, "•")
        head = f"{icon} **{self.role}** · {self.summary}"
        if self.thread_id:
            head += f"  `{self.thread_id}`"
        return f"{head}\n{self.detail}" if self.detail else head


class CrewEventSink(Protocol):
    """Where crew activity goes. Emitting must never break a run."""

    async def emit(self, event: CrewEvent) -> None: ...


class NullEventSink:
    """Default. Drops everything — the daemon runs with no log channel bound."""

    async def emit(self, event: CrewEvent) -> None:  # noqa: ARG002
        return None


@dataclass
class RecordingEventSink:
    """In-memory sink for tests: assert on what the crew reported."""

    events: list[CrewEvent] = field(default_factory=list)

    async def emit(self, event: CrewEvent) -> None:
        self.events.append(event)

    @property
    def kinds(self) -> list[str]:
        return [e.kind for e in self.events]

    def of_kind(self, kind: str) -> list[CrewEvent]:
        return [e for e in self.events if e.kind == kind]


# ─── HITL decorator ─────────────────────────────────────────────────────────


@dataclass
class LoggingHITL:
    """Wraps any ``HITLContract`` to report gates and decisions.

    A decorator rather than a change to ``DiscordHITL``: the contract is the
    framework's most-cited seam (Ch.3 §3.8), and observability should not be a
    reason to edit it. Any surface — Discord, web, stdin — gains the same log
    by being wrapped.
    """

    inner: object  # HITLContract
    sink: CrewEventSink
    role_hint: str = "crew"

    async def review(self, request):  # noqa: ANN001 — framework type
        role = getattr(request, "role_name", None) or self.role_hint
        thread_id = getattr(request, "thread_id", "") or ""
        turn = getattr(request, "turn", None)
        await self.sink.emit(
            CrewEvent(
                kind=AWAITING_REVIEW,
                role=role,
                thread_id=thread_id,
                summary=f"waiting for your review{f' (turn {turn})' if turn else ''}",
            )
        )
        decision = await self.inner.review(request)
        action = getattr(decision, "action", str(decision))
        feedback = getattr(decision, "feedback", None)
        await self.sink.emit(
            CrewEvent(
                kind=DECISION,
                role=role,
                thread_id=thread_id,
                summary=f"you chose **{action}**",
                detail=f"> {feedback}" if feedback else "",
            )
        )
        return decision

    def __getattr__(self, name: str):
        # Anything else on the wrapped contract (channel_for, is_mapped, …)
        # passes straight through, so the decorator is drop-in.
        return getattr(self.inner, name)
