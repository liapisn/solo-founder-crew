"""Tool primitives and the access-control registry.

A `Tool` is anything callable that the framework lets a Role invoke.
Tools sit *outside* the LLM call — they are concrete actions in the
world (publish a draft, send an email, write to a database).

`ToolRegistry` is the framework's enforcement point for the
Role + DecisionRights model:

- A Role can only invoke tools listed in its `role.tools` allowlist.
- The runtime (Component 4) must pass `escalation_satisfied=True`
  when a tool's action is in `role.decision_rights.must_escalate`.
- Both checks are explicit at call time — no global registry, no
  implicit capability, no runtime mutation of role state.

Citable in Ch.3 §"Tool access control" and §"HITL Contract" — the
escalation flag is where the HITL Contract surfaces in tool invocation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Protocol, TypeAlias

from solo_founder_crew.role import Role


class ToolPermissionError(PermissionError):
    """Raised when a Role attempts a tool it is not permitted to invoke,
    or when an escalating tool is invoked without escalation satisfied."""


# A Tool is an async callable taking the input arg as a string and
# returning a string result. Real-world tools may be much richer; for
# the framework's contract we keep the surface minimal and let callers
# serialise structured payloads themselves.
Tool: TypeAlias = Callable[[str], Awaitable[str]]


class ToolSpec(Protocol):
    """Optional richer-than-callable shape — anything with `name` and an
    async `__call__(arg) -> str`. Permits class-based tools (e.g. a
    `PublisherTool` carrying configuration) alongside plain callables."""

    name: str

    async def __call__(self, arg: str) -> str: ...


@dataclass
class ToolRegistry:
    """Central, role-aware tool dispatcher.

    Tools register once with a name; invocation goes through
    `invoke(role, name, arg)` and the registry enforces:

    1. The tool exists.
    2. The role's allowlist contains the tool's name.
    3. If the action implied by the tool is in
       `role.decision_rights.must_escalate`, the caller passed
       `escalation_satisfied=True`.

    The third check is the deliberate seam between tool access and the
    HITL Contract: the runtime is responsible for proving escalation
    has happened *before* asking the registry to invoke.
    """

    _tools: dict[str, Tool] = field(default_factory=dict)
    _escalates: dict[str, str] = field(default_factory=dict)

    def register(self, name: str, tool: Tool, *, escalates: str | None = None) -> None:
        """Register a tool by name.

        If `escalates` is given, invocation requires the calling Role
        to have that action in its `must_escalate` set AND the runtime
        to have provided escalation evidence.
        """
        self._tools[name] = tool
        if escalates is not None:
            self._escalates[name] = escalates

    def escalating_action(self, name: str) -> str | None:
        """The action a tool escalates on, or ``None`` if it is ungated.

        Exposed so callers can check a Role's declaration *before* a run
        starts rather than discovering the mismatch at invocation — by
        which point the draft has been written and the founder has
        already approved it. See ``Crew._preflight``.
        """
        return self._escalates.get(name)

    async def invoke(
        self,
        role: Role,
        name: str,
        arg: str,
        *,
        escalation_satisfied: bool = False,
    ) -> str:
        if name not in self._tools:
            raise KeyError(f"Tool {name!r} not registered")
        if name not in role.tools:
            raise ToolPermissionError(
                f"Role {role.name!r} is not allowed to invoke tool {name!r}"
            )
        escalating_action = self._escalates.get(name)
        if escalating_action is not None:
            if escalating_action not in role.decision_rights.must_escalate:
                raise ToolPermissionError(
                    f"Tool {name!r} requires escalation action "
                    f"{escalating_action!r} but role {role.name!r} does not "
                    f"declare it in decision_rights.must_escalate"
                )
            if not escalation_satisfied:
                raise ToolPermissionError(
                    f"Tool {name!r} requires escalation "
                    f"({escalating_action!r}) to be satisfied before invocation"
                )
        return await self._tools[name](arg)
