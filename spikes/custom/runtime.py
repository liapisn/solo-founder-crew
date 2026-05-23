"""Orchestration runtime — custom asyncio baseline.

Component 4 of the framework, minimal version. Owns: memory across turns,
trace capture, dispatching role actions, and enforcing tool access. The
scenario flow is hardcoded for the spike (draft -> HITL -> [revise -> HITL]
-> publish); the framework version would generalize this.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from hitl import FounderDecision, ScriptedHITL
from llm import LLM
from roles import Role
from tools import PublisherTool, enforce_tool_access


@dataclass
class TraceEvent:
    ts: float
    role: str | None
    action: str
    input: Any
    output: Any


@dataclass
class Runtime:
    brief: dict
    role: Role
    hitl: ScriptedHITL
    publisher: PublisherTool
    llm: LLM
    max_revisions: int = 1
    trace: list[TraceEvent] = field(default_factory=list)

    def _record(self, *, role: str | None, action: str, inp: Any, out: Any) -> None:
        self.trace.append(
            TraceEvent(ts=time.time(), role=role, action=action, input=inp, output=out)
        )

    def _draft_prompt(self, prior: str | None, feedback: str | None) -> str:
        sections = [
            "VENTURE BRIEF (authoritative):",
            json.dumps(self.brief, ensure_ascii=False, indent=2),
            "",
            "TASK: Draft a launch announcement for this venture. "
            "Match the voice. Respect every constraint. Keep under 150 words.",
        ]
        if prior is not None:
            sections += [
                "",
                "PRIOR DRAFT (founder rejected):",
                prior,
                "",
                f"FOUNDER FEEDBACK: {feedback or ''}",
                "Produce a revised draft that addresses the feedback.",
            ]
        return "\n".join(sections)

    async def _perform_draft(self, *, prior: str | None, feedback: str | None) -> str:
        action = "revise_content" if prior is not None else "draft_content"
        if not self.role.may_perform(action):
            raise PermissionError(f"role={self.role.name} cannot {action}")
        user = self._draft_prompt(prior, feedback)
        text = await self.llm.complete(system=self.role.system_prompt, user=user)
        self._record(role=self.role.name, action=action, inp={"has_prior": prior is not None}, out=text)
        return text

    async def run(self) -> dict:
        self._record(role=None, action="run_start", inp={"venture_id": self.brief["venture_id"]}, out=None)

        draft = await self._perform_draft(prior=None, feedback=None)
        approved: str | None = None

        for turn in range(1, self.max_revisions + 2):  # turn 1 = first review, then up to max_revisions revisions
            decision: FounderDecision = await self.hitl.review(artifact=draft, turn=turn)
            self._record(
                role="founder",
                action="hitl_review",
                inp={"turn": turn, "draft_preview": draft[:120]},
                out={"action": decision.action, "feedback": decision.feedback},
            )
            if decision.action == "approve":
                approved = draft
                break
            if decision.action == "kill":
                self._record(role=None, action="run_killed", inp=None, out=None)
                return {"status": "killed", "approved": None}
            if decision.action == "reject":
                if turn > self.max_revisions:
                    self._record(role=None, action="revision_budget_exhausted", inp=None, out=None)
                    return {"status": "exhausted", "approved": None}
                draft = await self._perform_draft(prior=draft, feedback=decision.feedback)

        assert approved is not None
        enforce_tool_access(
            self.role, self.publisher.name, escalation_satisfied=True
        )
        publish_result = self.publisher.publish(approved)
        self._record(
            role=self.role.name,
            action="publisher_tool.publish",
            inp={"chars": len(approved)},
            out=publish_result,
        )
        self._record(role=None, action="run_end", inp=None, out={"status": "shipped"})
        return {"status": "shipped", "approved": approved}

    def trace_as_jsonable(self) -> list[dict]:
        return [
            {
                "ts": e.ts,
                "role": e.role,
                "action": e.action,
                "input": e.input,
                "output": e.output,
            }
            for e in self.trace
        ]
