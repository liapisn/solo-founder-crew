"""Component 2 — Role primitives.

A `Role` is the framework's unit of typed work. It bundles:

- A name and a one-line goal (what the role is for).
- A system prompt the LLM receives when the role acts (its voice).
- Declarative **decision rights**: which actions the role may perform
  alone, and which require founder escalation. This is the
  framework's answer to the typical agent-framework gap where role
  authority is implicit in prose; here it is data the runtime checks.
- A tool allowlist: the names of tools the role is permitted to invoke
  (subject to escalation).

The full Role catalogue lives in `solo_founder_crew.roles_library`
(Phase 3). This module provides the primitive types only.

Citable in Ch.3 §"Role Library" — the spec for how roles are defined.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionRights:
    """What a Role may do on its own, and what it must escalate.

    `can` lists action names the role may execute without founder
    approval. `must_escalate` lists actions that require founder
    sign-off before they happen.

    Both are tuples of action-name strings. The runtime (Component 4)
    enforces these at action dispatch time; the prose chapter
    references the same field names so spec and code stay coupled.
    """

    can: tuple[str, ...]
    must_escalate: tuple[str, ...]

    def may_perform(self, action: str) -> bool:
        return action in self.can


@dataclass(frozen=True)
class Role:
    """A parameterised role definition.

    Roles are immutable (`frozen=True`) so a Crew Generator can hand
    out the same Role instance to multiple runs without state leakage.

    `system_prompt` is the LLM-facing voice. By convention it embeds
    the venture's tone constraints from the Venture Brief — but the
    Role itself is brief-agnostic; the Crew Generator (Component 3)
    is what substitutes brief content into the prompt template.

    `tools` lists the *names* of tools (resolved against a
    `ToolRegistry` at runtime). Holding a tool name here is necessary
    but not sufficient: invocation also requires
    `decision_rights.must_escalate` to be satisfied at runtime.
    """

    name: str
    goal: str
    system_prompt: str
    decision_rights: DecisionRights
    tools: tuple[str, ...] = ()

    def may_perform(self, action: str) -> bool:
        return self.decision_rights.may_perform(action)
