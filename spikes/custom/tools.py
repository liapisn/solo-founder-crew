"""Tool stubs + access control.

Component 4 (tool access) of the framework. Tools are dumb stubs in the spike;
the interesting part is the enforce() function — it shows how a custom runtime
expresses the "Marketing can hold publisher_tool but cannot invoke it until
the founder approves" rule declaratively, by reading the Role itself.
"""
from __future__ import annotations

from dataclasses import dataclass

from roles import Role


class ToolAccessError(RuntimeError):
    pass


@dataclass
class PublisherTool:
    """Pretends to publish an announcement. Just records the call for the trace."""
    name: str = "publisher_tool"
    last_published: str | None = None

    def publish(self, text: str) -> dict:
        self.last_published = text
        return {"status": "shipped", "channel": "stub", "chars": len(text)}


def enforce_tool_access(
    role: Role,
    tool_name: str,
    *,
    escalation_satisfied: bool,
) -> None:
    """Block tool invocation unless the role holds the tool AND any
    must_escalate action tied to publication has been satisfied."""
    if tool_name not in role.tools:
        raise ToolAccessError(
            f"role={role.name!r} does not hold tool {tool_name!r}"
        )
    if (
        "final_approval_before_publish" in role.decision_rights.must_escalate
        and not escalation_satisfied
    ):
        raise ToolAccessError(
            f"role={role.name!r} requires founder approval before {tool_name!r}"
        )
