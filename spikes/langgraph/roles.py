"""Role definition for the LangGraph spike.

Rubric evidence (role parameterization): LangGraph itself has *no* Agent
or Role abstraction — it's a graph of state-transforming nodes. That means
we can shape Role exactly as we want (good for fit with the thesis
vocabulary) but we also have to define it from scratch (cost to the dev
experience score). Mirrors the custom spike's Role on purpose so the
comparison stays fair.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionRights:
    can: tuple[str, ...]
    must_escalate: tuple[str, ...] = ()


@dataclass(frozen=True)
class Role:
    name: str
    goal: str
    decision_rights: DecisionRights
    tools: tuple[str, ...]
    system_prompt: str

    def may_perform(self, action: str) -> bool:
        return action in self.decision_rights.can


MARKETING = Role(
    name="marketing",
    goal="Draft customer-facing announcements that match the venture's voice and constraints.",
    decision_rights=DecisionRights(
        can=("draft_content", "revise_content"),
        must_escalate=("final_approval_before_publish",),
    ),
    tools=("publisher_tool",),
    system_prompt=(
        "You are the Marketing role inside a solo-founder operating crew. "
        "Speak in the venture's voice as defined in the Venture Brief. "
        "Stay strictly within scope and constraints. Do not invent claims, "
        "do not imply live customer pilots if the venture is pre-launch, "
        "and obey the brief's do/dont lists. Output ONLY the announcement "
        "text — no preamble, no markdown headings, no explanation."
    ),
)
