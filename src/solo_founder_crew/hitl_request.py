"""Component 5 — the HITL decision request envelope.

Python mirror of ``solo_founder_crew/schemas/hitl_request.schema.json``. The schema is the
single source of truth; these dataclasses are the thin, typed in-process
representation the runtime and the HITL surfaces pass around.

Motivation. The original ``HITLContract.review(artifact, *, turn)``
signature handed the founder only a string. That is enough for a stdin
gate, but a *remote* surface (a webhook, an SMS line, a Discord channel)
cannot route or render a bare string: it has no way to know which venture
raised the request, which role is asking, what action is being gated, or
which responses the founder may give. ``HITLRequest`` carries exactly that
context, so the same contract can be rendered anywhere without the surface
reaching into runtime internals.

The founder's reply is the mirror image, ``FounderResponse``, which maps
one-to-one onto the existing ``FounderDecision`` (``hitl.py``) plus the
``request_id`` needed to route the answer back to the correct parked run.

Citable in Ch.3 §3.7 (the enriched interrupt payload) and §3.8 (the HITL
Contract).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from solo_founder_crew.hitl import FounderDecision


@dataclass(frozen=True)
class ReviewOption:
    """One founder response a gate accepts. Renders as a button / keyword."""

    action: str  # "approve" | "reject" | "kill"
    label: str
    requires_feedback: bool = False


# The canonical three — used when a gate does not override them.
DEFAULT_OPTIONS: tuple[ReviewOption, ...] = (
    ReviewOption(action="approve", label="Approve", requires_feedback=False),
    ReviewOption(action="reject", label="Send back", requires_feedback=True),
    ReviewOption(action="kill", label="Kill run", requires_feedback=False),
)


@dataclass(frozen=True)
class Artifact:
    """The payload under review. An object (not a bare string) so a surface
    can show a summary plus full content, and so non-text payloads fit the
    same envelope later."""

    content: str
    content_type: str = "text/markdown"
    summary: str | None = None


@dataclass(frozen=True)
class HITLRequest:
    """A typed, transport-agnostic decision request raised at a HITL gate.

    Field order and names track ``hitl_request.schema.json``. ``channel``
    and ``role_display_name`` default lazily (see ``__post_init__``) so the
    runtime can construct a request with the minimum it knows and let the
    surface fill sensible defaults.
    """

    request_id: str
    thread_id: str
    venture_id: str
    turn: int
    role_name: str
    action: str
    artifact: Artifact
    channel: str | None = None
    role_display_name: str | None = None
    escalation_reason: str | None = None
    options: tuple[ReviewOption, ...] = DEFAULT_OPTIONS
    urgency: str = "blocking"  # "blocking" | "fyi"
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # frozen dataclass: use object.__setattr__ for derived defaults
        if self.channel is None:
            # Channels are kebab-case logical keys; role names are snake_case.
            object.__setattr__(self, "channel", self.role_name.replace("_", "-"))
        if self.role_display_name is None:
            object.__setattr__(
                self, "role_display_name", self.role_name.replace("_", " ").title()
            )

    def option_for(self, action: str) -> ReviewOption | None:
        for opt in self.options:
            if opt.action == action:
                return opt
        return None

    def to_interrupt_payload(self) -> dict[str, Any]:
        """Serialise for ``langgraph.types.interrupt(...)``.

        Only JSON-able values — this is what gets checkpointed, so it must
        not contain live objects (the same discipline ``AuthorFlowState``
        follows; see ``runtime.py``).
        """
        role: dict[str, Any] = {"name": self.role_name}
        if self.role_display_name is not None:
            role["display_name"] = self.role_display_name

        artifact: dict[str, Any] = {
            "content": self.artifact.content,
            "content_type": self.artifact.content_type,
        }
        if self.artifact.summary is not None:
            artifact["summary"] = self.artifact.summary

        payload: dict[str, Any] = {
            "request_id": self.request_id,
            "thread_id": self.thread_id,
            "venture_id": self.venture_id,
            "turn": self.turn,
            "role": role,
            "action": self.action,
            "artifact": artifact,
            "options": [
                {
                    "action": o.action,
                    "label": o.label,
                    "requires_feedback": o.requires_feedback,
                }
                for o in self.options
            ],
            "urgency": self.urgency,
        }
        # Optional fields: include only when set, to stay valid under the
        # schema's additionalProperties:false / no-null contract.
        if self.channel is not None:
            payload["channel"] = self.channel
        if self.escalation_reason is not None:
            payload["escalation_reason"] = self.escalation_reason
        if self.context:
            payload["context"] = self.context
        return payload

    @classmethod
    def from_interrupt_payload(cls, payload: dict[str, Any]) -> "HITLRequest":
        """Inverse of ``to_interrupt_payload`` — rebuild after a resume."""
        role = payload.get("role", {})
        art = payload.get("artifact", {})
        opts = payload.get("options") or []
        return cls(
            request_id=payload["request_id"],
            thread_id=payload["thread_id"],
            venture_id=payload["venture_id"],
            turn=payload["turn"],
            role_name=role.get("name", ""),
            role_display_name=role.get("display_name"),
            action=payload["action"],
            artifact=Artifact(
                content=art.get("content", ""),
                content_type=art.get("content_type", "text/markdown"),
                summary=art.get("summary"),
            ),
            channel=payload.get("channel"),
            escalation_reason=payload.get("escalation_reason"),
            options=tuple(
                ReviewOption(
                    action=o["action"],
                    label=o["label"],
                    requires_feedback=o.get("requires_feedback", False),
                )
                for o in opts
            )
            or DEFAULT_OPTIONS,
            urgency=payload.get("urgency", "blocking"),
            context=payload.get("context", {}),
        )

    def with_artifact(self, content: str, *, summary: str | None = None) -> "HITLRequest":
        """Return a copy carrying a new artifact (e.g. a revised draft)."""
        return replace(self, artifact=Artifact(content=content, summary=summary))


@dataclass(frozen=True)
class FounderResponse:
    """The founder's reply to a :class:`HITLRequest`.

    Maps one-to-one onto ``FounderDecision`` plus the ``request_id`` used to
    correlate the answer with the parked run. The runtime drops
    ``request_id`` once correlated and routes on ``to_decision()``.
    """

    request_id: str
    action: str  # "approve" | "reject" | "kill"
    feedback: str | None = None
    responder: str | None = None
    responded_at: str | None = None

    def to_decision(self) -> FounderDecision:
        return FounderDecision(action=self.action, feedback=self.feedback)
