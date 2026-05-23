"""Tool stub + access enforcement, identical contract to the custom spike.

Rubric evidence (tool access control): LangGraph nodes can call tools
freely from inside Python — there is no built-in per-node tool allowlist.
We enforce it ourselves with `enforce_tool_access()`, called inside the
publish node. Identical pattern to the custom spike, which means the
*expressiveness* of tool gating is on us in both cases.
"""
from __future__ import annotations

from dataclasses import dataclass

from roles import Role


class ToolAccessError(RuntimeError):
    pass


@dataclass
class PublisherTool:
    name: str = "publisher_tool"
    last_published: str | None = None

    def publish(self, text: str) -> dict:
        self.last_published = text
        return {"status": "shipped", "channel": "stub", "chars": len(text)}


def enforce_tool_access(role: Role, tool_name: str, *, escalation_satisfied: bool) -> None:
    if tool_name not in role.tools:
        raise ToolAccessError(f"role={role.name!r} does not hold tool {tool_name!r}")
    if (
        "final_approval_before_publish" in role.decision_rights.must_escalate
        and not escalation_satisfied
    ):
        raise ToolAccessError(
            f"role={role.name!r} requires founder approval before {tool_name!r}"
        )
