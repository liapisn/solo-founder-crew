"""Role definitions for the CrewAI spike.

Maps the framework's Role concept onto CrewAI's `Agent` class. The mismatch
worth noting (rubric: role parameterization): CrewAI's Agent has no native
notion of decision_rights or must_escalate. We keep them in a sidecar
`RoleMeta` and reference the same fields in the backstory prose so the LLM
sees them — but enforcement is manual, in `tools.py` and `run.py`.
"""
from __future__ import annotations

from dataclasses import dataclass

from crewai import Agent


@dataclass(frozen=True)
class RoleMeta:
    """Sidecar carrying the framework's declarative role attributes that
    CrewAI's Agent does not natively model."""
    name: str
    can: tuple[str, ...]
    must_escalate: tuple[str, ...]
    tools: tuple[str, ...]


MARKETING_META = RoleMeta(
    name="marketing",
    can=("draft_content", "revise_content"),
    must_escalate=("final_approval_before_publish",),
    tools=("publisher_tool",),
)

_MARKETING_BACKSTORY = """\
You are the Marketing role inside a solo-founder operating crew.

DECISION RIGHTS
- You may: draft_content, revise_content
- You must escalate to the founder for: final_approval_before_publish

OPERATING RULES
- Speak in the venture's voice as defined in the Venture Brief.
- Stay strictly within scope and constraints.
- Do not invent claims. Do not imply live customer pilots if the venture is
  pre-launch. Obey the brief's do/dont lists.
- Output ONLY the announcement text — no preamble, no markdown headings,
  no explanation.
"""


def build_marketing_agent(llm_model: str) -> Agent:
    return Agent(
        role="Marketing for solo-founder ventures",
        goal=(
            "Draft customer-facing announcements that match the venture's "
            "voice and constraints."
        ),
        backstory=_MARKETING_BACKSTORY,
        llm=llm_model,            # CrewAI delegates to litellm
        allow_delegation=False,
        verbose=False,
        max_iter=1,               # one LLM call per task — keeps the spike's call budget honest
        tools=[],                 # tools are attached at runtime so we can gate publishing
    )
