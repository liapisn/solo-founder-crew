"""`Crew` — the public entry point for running a flow.

A `Crew` ties together a Venture Brief, a set of Roles, and the three
runtime services (LLM, HITL, ToolRegistry). One Crew belongs to one
venture; many runs / flows can happen against the same Crew.

The public surface is intentionally narrow:

    crew = Crew(brief=…, roles=[marketing], llm=…, hitl=…, tools=…)
    result = await crew.author_flow(task_description="Draft a launch announcement")
    print(result.status, result.approved_artifact)
    result.trace.write("trace.json")

Citable in Ch.3 §"Crew Generator" (the algorithmic side) and §"Public
API" (this entry point).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from solo_founder_crew.brief import VentureBrief
from solo_founder_crew.hitl import HITLContract
from solo_founder_crew.llm import LLMClient
from solo_founder_crew.role import Role
from solo_founder_crew.runtime import (
    AuthorFlowState,
    DRAFT_ACTION,
    build_author_graph,
)
from solo_founder_crew.tools import ToolRegistry
from solo_founder_crew.trace import RunTrace


@dataclass(frozen=True)
class AuthorFlowResult:
    """Outcome of `crew.author_flow(...)`.

    `status` is one of "shipped" | "killed" | "exhausted".
    `approved_artifact` is the final approved text iff status == "shipped".
    `trace` is the structured run log — same shape as the spike traces.
    `final_state` is the LangGraph terminal state (kept for debugging).
    """

    status: str
    approved_artifact: str | None
    trace: RunTrace
    final_state: dict


@dataclass
class Crew:
    """One venture's operating crew.

    A Crew is constructed once and may run many flows. Its services
    (LLM, HITL, ToolRegistry) are reused across runs; the trace can be
    reset between runs via `crew.reset_trace()` if needed.

    The minimal usable shape is one role + one LLM + one HITL gate +
    one tool. The Crew Generator (Phase 3) will produce these
    automatically from a Venture Brief.
    """

    brief: VentureBrief
    roles: Sequence[Role]
    llm: LLMClient
    hitl: HITLContract
    tools: ToolRegistry
    trace: RunTrace = field(default_factory=RunTrace)

    def role(self, name: str) -> Role:
        """Look up a role by name. Raises KeyError if absent."""
        for r in self.roles:
            if r.name == name:
                return r
        raise KeyError(
            f"No role named {name!r} in crew "
            f"(have: {[r.name for r in self.roles]})"
        )

    def reset_trace(self) -> RunTrace:
        """Replace the trace with a fresh one (e.g. between runs)."""
        self.trace = RunTrace()
        return self.trace

    async def author_flow(
        self,
        *,
        task_description: str,
        role: Role | str | None = None,
        publish_tool: str = "publisher_tool",
        max_revisions: int = 1,
    ) -> AuthorFlowResult:
        """Run the canonical solo-founder author flow.

        ``role`` defaults to the crew's sole role; pass a name or Role
        explicitly when the crew has more than one. ``publish_tool``
        must be in the named role's ``tools`` allowlist (the
        ToolRegistry enforces this at invoke time).
        """
        chosen_role = self._resolve_role(role)
        if not chosen_role.may_perform(DRAFT_ACTION):
            raise PermissionError(
                f"Role {chosen_role.name!r} cannot perform {DRAFT_ACTION!r} "
                f"(decision_rights.can={chosen_role.decision_rights.can})"
            )
        if publish_tool not in chosen_role.tools:
            raise PermissionError(
                f"Role {chosen_role.name!r} does not hold publish_tool "
                f"{publish_tool!r} (tools={chosen_role.tools})"
            )

        # Set scenario name on the trace for serialised output.
        if not self.trace.scenario:
            self.trace.scenario = f"author_flow::{self.brief.venture_id}"

        graph = build_author_graph(
            role=chosen_role,
            llm=self.llm,
            hitl=self.hitl,
            tools=self.tools,
            trace=self.trace,
        )

        initial: AuthorFlowState = {
            "brief": self.brief.as_dict(),
            "role": {
                "name": chosen_role.name,
                "tools": list(chosen_role.tools),
            },
            "task_description": task_description,
            "max_revisions": max_revisions,
            "publish_tool": publish_tool,
            "turn": 0,
        }
        final = await graph.compiled.ainvoke(initial)

        return AuthorFlowResult(
            status=final.get("status", "unknown"),
            approved_artifact=final.get("approved_artifact"),
            trace=self.trace,
            final_state=dict(final),
        )

    # ─── Internals ──────────────────────────────────────────────────────────

    def _resolve_role(self, role: Role | str | None) -> Role:
        if isinstance(role, Role):
            return role
        if isinstance(role, str):
            return self.role(role)
        if len(self.roles) == 1:
            return self.roles[0]
        raise ValueError(
            f"Crew has {len(self.roles)} roles; specify which with role=<name>"
        )
