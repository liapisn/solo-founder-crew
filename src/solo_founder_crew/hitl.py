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
from typing import Protocol


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

    `artifact` is the draft / proposal / payload the founder is being
    asked to review. `turn` is the 1-indexed gate turn (so a contract
    can branch on first vs subsequent revisions).
    """

    async def review(self, artifact: str, *, turn: int) -> FounderDecision: ...


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

    async def review(self, artifact: str, *, turn: int) -> FounderDecision:
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

    async def review(self, artifact: str, *, turn: int) -> FounderDecision:
        print(f"\n── FOUNDER GATE  turn {turn} ──")
        print(artifact.rstrip())
        print(f"── end of artifact ─────────────")
        while True:
            choice = input("Action [approve/reject/kill]: ").strip().lower()
            if choice == "approve":
                return FounderDecision(action="approve")
            if choice == "kill":
                return FounderDecision(action="kill")
            if choice == "reject":
                feedback = input("Feedback (one line, optional): ").strip()
                return FounderDecision(action="reject", feedback=feedback or None)
            print("invalid; expected one of: approve | reject | kill")
