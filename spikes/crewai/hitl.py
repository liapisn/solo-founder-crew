"""Scripted HITL gate, reused identically across all three spikes.

Rubric evidence (HITL ergonomics): CrewAI Task supports `human_input=True`
which pauses for stdin — useful for real founder review but inflexible for
deterministic spike runs. We bypass it and run the gate *between* CrewAI
kickoffs in `run.py`. That bypass is itself the rubric signal.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FounderDecision:
    action: str
    feedback: str | None = None


class ScriptedHITL:
    def __init__(self, responses_path: Path):
        data = json.loads(responses_path.read_text(encoding="utf-8"))
        self._turns = {t["turn"]: t for t in data["turns"]}

    def review(self, *, artifact: str, turn: int) -> FounderDecision:
        t = self._turns[turn]
        return FounderDecision(action=t["action"], feedback=t.get("feedback"))
