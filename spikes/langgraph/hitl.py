"""Scripted HITL gate for the LangGraph spike.

Rubric evidence (HITL ergonomics): LangGraph has first-class HITL via
`interrupt()` — a graph can pause, persist its state via a checkpointer,
and resume with new input. That's a strong fit for *real* founder review
but heavyweight for a deterministic spike. We model the same fixture-
driven gate as the other spikes here and *also* use LangGraph's interrupt
mechanism in `graph.py` so the run shows what the native pattern looks
like. This dual signal is itself the rubric note.
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

    def review(self, *, turn: int) -> FounderDecision:
        t = self._turns[turn]
        return FounderDecision(action=t["action"], feedback=t.get("feedback"))
