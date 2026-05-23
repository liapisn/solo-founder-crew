"""Human-in-the-Loop gate.

Component 5 of the framework. For the spike, the founder is scripted from
fixtures so runs are deterministic. The interesting part for the rubric is
how *easy* it is to drop a gate anywhere in the flow — in the custom runtime,
it's just `await hitl.review(...)`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FounderDecision:
    action: str  # "approve" | "reject" | "kill"
    feedback: str | None = None


class ScriptedHITL:
    """Reads scripted founder responses from a JSON file. One turn per call."""

    def __init__(self, responses_path: Path):
        data = json.loads(responses_path.read_text(encoding="utf-8"))
        self._turns = {t["turn"]: t for t in data["turns"]}

    async def review(self, *, artifact: str, turn: int) -> FounderDecision:
        if turn not in self._turns:
            raise KeyError(f"no scripted founder response for turn {turn}")
        t = self._turns[turn]
        return FounderDecision(action=t["action"], feedback=t.get("feedback"))
