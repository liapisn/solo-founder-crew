"""Role abstraction with declarative decision rights.

Component 2 of the framework in microcosm. The point of this file is to show
how a custom implementation lets us shape Role exactly to the thesis vocabulary
(decision_rights.can / must_escalate, tool allowlists) without inheriting an
opinionated Agent class from a third-party framework.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DecisionRights:
    can: tuple[str, ...]
    must_escalate: tuple[str, ...] = ()


@dataclass(frozen=True)
class Role:
    name: str
    goal: str
    decision_rights: DecisionRights
    tools: tuple[str, ...] = ()
    system_prompt: str = ""

    def may_perform(self, action: str) -> bool:
        return action in self.decision_rights.can

    def must_escalate_for(self, action: str) -> bool:
        return action in self.decision_rights.must_escalate


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
