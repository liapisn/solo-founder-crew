"""LLM bridge for the CrewAI spike.

Rubric evidence (lock-in & cost / dev experience): CrewAI routes through
litellm by default — you pass a string like "anthropic/claude-haiku-4-5"
to Agent(llm=...) and it constructs `crewai.LLM(model=...)` under the
hood. To substitute a stub LLM you must subclass `crewai.LLM` and
override `.call()`. That's our `MockCrewLLM` below.

The substitution is feasible but tells you the framework wants you on
its litellm rails. Compared to the custom spike where the LLM
abstraction is a one-method Protocol you fully own, here we're
inheriting from a class with ~25 constructor args we don't care about.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from crewai import LLM as CrewLLM

# spike layout: spikes/crewai/llm.py → spikes/ on path for shared
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared import MockLLM, RealLLM  # noqa: E402


class MockCrewLLM(CrewLLM):
    """CrewAI LLM that returns canned responses from a shared.MockLLM
    queue, bypassing litellm entirely. Constructed with a sentinel
    model string so CrewAI's internal validation passes."""

    def __init__(self, client: MockLLM | None = None):
        # Sentinel uses a real provider prefix so litellm's introspection
        # at __init__ stays quiet. The actual litellm code path is never
        # invoked because we override .call() below.
        super().__init__(model="anthropic/claude-haiku-4-5")
        self._mock = client or MockLLM()

    def call(
        self,
        messages,
        tools=None,
        callbacks=None,
        available_functions=None,
        from_task=None,
        from_agent=None,
    ) -> str:
        # CrewAI passes either a string or a list of {"role","content"} dicts.
        # Collapse to (system, user) — the system message lands in the first
        # 'system' role item if present; everything else is user prose.
        system_parts: list[str] = []
        user_parts: list[str] = []
        if isinstance(messages, str):
            user_parts.append(messages)
        else:
            for m in messages:
                role = m.get("role", "user")
                content = m.get("content", "")
                if role == "system":
                    system_parts.append(content)
                else:
                    user_parts.append(content)
        resp = self._mock.complete(
            system="\n".join(system_parts), user="\n".join(user_parts)
        )
        # CrewAI's agent executor parses LLM output for "Thought: …\nFinal
        # Answer: …". Plain text gets rejected and CrewAI re-prompts,
        # blowing the call budget. We wrap the canned response so the
        # parser accepts it on the first call. This wrapping is a
        # rubric-relevant data point: it documents an extra coupling
        # CrewAI imposes on the LLM contract.
        return f"Thought: I drafted the announcement.\nFinal Answer: {resp.text}"


def build_llm(real: bool) -> CrewLLM:
    """Choose the LLM backend for an Agent.

    Mock path: returns a MockCrewLLM bound to a fresh MockLLM queue.
    Real path: returns a stock crewai.LLM(model='anthropic/claude-haiku-4-5')
    which goes through litellm. RealLLM is *not* used here — we let
    CrewAI's native binding carry the rubric signal for 'how does the
    framework integrate with a real model'.
    """
    if real:
        # Validate API key presence the same way RealLLM does, so failures
        # land before CrewAI tries (and gives a less-useful litellm error).
        RealLLM()  # construction-only check; instance discarded
        return CrewLLM(model="anthropic/claude-haiku-4-5", max_tokens=1024)
    return MockCrewLLM()
