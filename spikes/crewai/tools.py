"""Tool stub for the CrewAI spike.

Rubric evidence (tool access control): CrewAI tools are passed via
`Agent(tools=[...])`. The Agent decides when to invoke them based on prompt
reasoning. There is no built-in `must_escalate_before_tool` policy — so we
keep `publisher_tool` *off* the agent's tool list until founder approval is
recorded in `run.py`, then attach it for the publish step. That is the
custom-baseline's `enforce_tool_access` requirement expressed CrewAI-style:
not declarative, but gated by attachment timing.
"""
from __future__ import annotations

from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class PublishInput(BaseModel):
    text: str = Field(..., description="The approved announcement to ship.")


class PublisherTool(BaseTool):
    name: str = "publisher_tool"
    description: str = (
        "Publish an approved announcement. Only invocable AFTER the founder "
        "has explicitly approved the draft."
    )
    args_schema: type[BaseModel] = PublishInput
    last_published: str | None = None

    def _run(self, text: str) -> dict[str, Any]:
        self.last_published = text
        return {"status": "shipped", "channel": "stub", "chars": len(text)}
