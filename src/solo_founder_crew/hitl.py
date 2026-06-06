"""Component 5 — Human-in-the-Loop Contract.

The HITL Contract is the framework's named seam for founder authority.
It defines:

- `FounderDecision`: the shape of what the founder returns at each gate
  (`approve`, `reject(feedback)`, `kill`).
- `HITLContract` Protocol: the runtime's interface for asking the
  founder. Two implementations live here:

  * `ScriptedHITL` — reads decisions from a JSON fixture. The test
    double used by every spike run and every framework test.
  * `interrupt()`-based production gate — arrives in Phase 4. It uses
    LangGraph's native `interrupt()` primitive plus a checkpointer so
    the founder can pause and resume across process restarts.

The Contract is the only API the runtime knows about. Swapping
implementations does not touch Crew, Role, or Tool code.

Citable in Ch.3 §"HITL Contract".
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from solo_founder_crew.hitl_request import HITLRequest


@dataclass(frozen=True)
class FounderDecision:
    """The founder's response at a HITL gate.

    `action` is one of: `approve` | `reject` | `kill`.
    `feedback` is the founder's free-text guidance, present iff action == `reject`.
    """

    action: str  # "approve" | "reject" | "kill"
    feedback: str | None = None


class HITLContract(Protocol):
    """The single async method the runtime calls at each gate.

    `request` is a :class:`~solo_founder_crew.hitl_request.HITLRequest` —
    the typed, transport-agnostic decision envelope (artifact under review,
    asking role, logical channel, gated action, allowed options, and the
    correlation/resume ids). An implementation renders it to whatever
    surface it owns (stdin, a fixture, a Discord channel) and returns the
    founder's :class:`FounderDecision`.
    """

    async def review(self, request: "HITLRequest") -> FounderDecision: ...


class ScriptedHITL:
    """Fixture-driven HITL gate for deterministic test runs.

    Construct from a JSON file matching the schema used by the spikes
    (turns: list of {turn, action, feedback?}), or by passing a list
    of `FounderDecision` directly.
    """

    def __init__(self, decisions: list[FounderDecision]) -> None:
        self._by_turn: dict[int, FounderDecision] = {
            i + 1: d for i, d in enumerate(decisions)
        }

    @classmethod
    def from_file(cls, path: Path | str) -> "ScriptedHITL":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        decisions: list[FounderDecision] = []
        for t in data.get("turns", []):
            decisions.append(
                FounderDecision(action=t["action"], feedback=t.get("feedback"))
            )
        return cls(decisions)

    async def review(self, request: "HITLRequest") -> FounderDecision:
        turn = request.turn
        if turn not in self._by_turn:
            raise RuntimeError(
                f"ScriptedHITL exhausted: no decision for turn {turn} "
                f"(have turns {sorted(self._by_turn)})"
            )
        return self._by_turn[turn]


class InteractiveHITL:
    """Terminal-based HITL gate. Prompts the founder on stdin.

    Used for manual testing and for the worked-example demos in this
    repo. Production deployments swap this for a UI/webhook/queue
    implementation that satisfies the same ``HITLContract`` Protocol.
    """

    async def review(self, request: "HITLRequest") -> FounderDecision:
        print(
            f"\n── FOUNDER GATE  turn {request.turn} — "
            f"{request.role_display_name} · #{request.channel} ──"
        )
        if request.escalation_reason:
            print(request.escalation_reason)
        print(request.artifact.content.rstrip())
        print("── end of artifact ─────────────")
        actions = [o.action for o in request.options]
        while True:
            choice = input(f"Action [{'/'.join(actions)}]: ").strip().lower()
            if choice == "approve" and "approve" in actions:
                return FounderDecision(action="approve")
            if choice == "kill" and "kill" in actions:
                return FounderDecision(action="kill")
            if choice == "reject" and "reject" in actions:
                feedback = input("Feedback (one line, optional): ").strip()
                return FounderDecision(action="reject", feedback=feedback or None)
            print(f"invalid; expected one of: {' | '.join(actions)}")
