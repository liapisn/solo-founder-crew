"""`Crew` — the public entry point for running a flow.

A `Crew` ties together a Venture Brief, a set of Roles, and the three
runtime services (LLM, HITL, ToolRegistry). One Crew belongs to one
venture; many runs / flows can happen against the same Crew.

The public surface is intentionally narrow:

    crew = Crew(brief=…, roles=[marketing], llm=…, hitl=…, tools=…)
    result = await crew.author_flow(task_description="Draft a launch announcement")
    print(result.status, result.approved_artifact, result.thread_id)
    result.trace.write("trace.json")

Phase 4 note — the HITL gate inside the graph is a LangGraph
``interrupt()`` call. ``Crew.author_flow`` is responsible for driving
the interrupt loop: when the graph pauses, fetch a ``FounderDecision``
via ``self.hitl.review(...)``, then resume with ``Command(resume=…)``.
The graph's checkpointer persists state across the interrupt so
nothing is lost between pause and resume (and, with a persistent
checkpointer like ``SqliteSaver``, across process restarts).

Citable in Ch.3 §"Crew Generator" (algorithmic side) and §"Public
API" (this entry point).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Sequence

from langgraph.types import Command

from solo_founder_crew.brief import VentureBrief
from solo_founder_crew.hitl import HITLContract
from solo_founder_crew.hitl_request import HITLRequest
from solo_founder_crew.llm import LLMClient
from solo_founder_crew.role import Role
from solo_founder_crew.runtime import (
    AuthorFlowState,
    DRAFT_ACTION,
    build_author_graph,
)
from solo_founder_crew.tools import ToolRegistry
from solo_founder_crew.trace import RunTrace

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver


@dataclass(frozen=True)
class AuthorFlowResult:
    """Outcome of `crew.author_flow(...)`.

    ``status`` is one of "shipped" | "killed" | "exhausted".
    ``approved_artifact`` is the final approved text iff status == "shipped".
    ``trace`` is the structured run log.
    ``thread_id`` identifies the run for checkpointer-based resume.
    ``final_state`` is the LangGraph terminal state (kept for debugging).
    """

    status: str
    approved_artifact: str | None
    trace: RunTrace
    thread_id: str
    final_state: dict


@dataclass
class Crew:
    """One venture's operating crew.

    A Crew is constructed once and may run many flows. Services
    (LLM, HITL, ToolRegistry) are reused across runs. The optional
    ``checkpointer`` allows cross-process pause/resume; default is
    in-memory.
    """

    brief: VentureBrief
    roles: Sequence[Role]
    llm: LLMClient
    hitl: HITLContract
    tools: ToolRegistry
    trace: RunTrace = field(default_factory=RunTrace)
    checkpointer: "BaseCheckpointSaver | None" = None

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
        thread_id: str | None = None,
    ) -> AuthorFlowResult:
        """Run the canonical solo-founder author flow.

        Drives the LangGraph interrupt loop: when the graph pauses at
        the HITL gate, this method calls ``self.hitl.review(...)`` and
        resumes with the decision. Returns when the graph reaches a
        terminal node (publish / kill / exhausted).

        ``thread_id`` identifies the run for checkpointer-based
        resume; one is auto-generated if not passed. The id is
        returned on the ``AuthorFlowResult`` so callers can resume
        later from a different process (with a persistent
        checkpointer).
        """
        chosen_role = self._resolve_role(role)
        self._preflight(chosen_role, publish_tool)

        if not self.trace.scenario:
            self.trace.scenario = f"author_flow::{self.brief.venture_id}"
        if thread_id is None:
            thread_id = f"run-{uuid.uuid4().hex[:12]}"

        graph = build_author_graph(
            role=chosen_role,
            llm=self.llm,
            tools=self.tools,
            trace=self.trace,
            checkpointer=self.checkpointer,
        )
        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

        initial: AuthorFlowState = {
            "brief": self.brief.as_dict(),
            "role": {"name": chosen_role.name, "tools": list(chosen_role.tools)},
            "task_description": task_description,
            "max_revisions": max_revisions,
            "publish_tool": publish_tool,
            "thread_id": thread_id,
            "turn": 0,
        }

        next_input: Any = initial
        final: dict[str, Any] = {}
        while True:
            final = await graph.compiled.ainvoke(next_input, config=config)
            interrupt_value = await self._pending_interrupt(graph.compiled, config)
            if interrupt_value is None:
                break

            # The graph is paused at the HITL gate. Reconstruct the typed
            # request from the checkpointed payload and hand it to the
            # configured contract (stdin, fixture, Discord, …).
            request = HITLRequest.from_interrupt_payload(interrupt_value)
            decision = await self.hitl.review(request)
            self.trace.record(
                role="founder",
                action="hitl_review",
                input=request.artifact.content,
                output=decision.feedback or "",
                decision=decision.action,
            )
            next_input = Command(
                resume={
                    "action": decision.action,
                    "feedback": decision.feedback,
                }
            )

        return AuthorFlowResult(
            status=final.get("status", "unknown"),
            approved_artifact=final.get("approved_artifact"),
            trace=self.trace,
            thread_id=thread_id,
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

    def _preflight(self, role: Role, publish_tool: str) -> None:
        if not role.may_perform(DRAFT_ACTION):
            raise PermissionError(
                f"Role {role.name!r} cannot perform {DRAFT_ACTION!r} "
                f"(decision_rights.can={role.decision_rights.can})"
            )
        if publish_tool not in role.tools:
            raise PermissionError(
                f"Role {role.name!r} does not hold publish_tool "
                f"{publish_tool!r} (tools={role.tools})"
            )

    @staticmethod
    async def _pending_interrupt(
        compiled, config: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Read interrupt payload from the checkpointer if the graph is paused.

        Returns the dict the ``hitl_node`` passed to ``interrupt(...)``,
        or ``None`` if the graph is in a terminal state.

        Uses the **async** state API (``aget_state``): an async checkpointer
        like ``AsyncSqliteSaver`` forbids synchronous access from the running
        event loop, so the sync ``get_state`` only worked with ``MemorySaver``.
        ``aget_state`` works for both.
        """
        state = await compiled.aget_state(config)
        if not state.tasks:
            return None
        for task in state.tasks:
            for inter in getattr(task, "interrupts", ()) or ():
                # LangGraph interrupt payload is on .value
                if getattr(inter, "value", None) is not None:
                    return inter.value
        return None
