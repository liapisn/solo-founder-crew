"""LLM bridge for the LangGraph spike.

Rubric evidence (lock-in & cost / dev experience): LangGraph itself
imposes no LLM contract. The nodes in `graph.py` just call
`state['llm'].invoke([(role, content), …]).content`. That's a duck
type, not a base class — anything that supplies `.invoke(messages)`
returning an object with `.content` works.

For the spike that means:
- Mock path: a 25-line class with one `invoke()` method. No subclassing,
  no pydantic model contract, no parser format.
- Real path: stock `ChatAnthropic(model="claude-haiku-4-5")` from
  langchain-anthropic. Standard binding.

Compare with the CrewAI spike, where stubbing required subclassing a
~25-arg class and wrapping output in CrewAI's parser format.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_anthropic import ChatAnthropic

# Append (don't insert at 0) — see run.py for why.
sys.path.append(str(Path(__file__).resolve().parents[1]))
from shared import MockLLM, RealLLM  # noqa: E402


@dataclass
class _Result:
    """Minimal AIMessage-shape duck type. LangGraph nodes only read .content."""

    content: str


class MockChatModel:
    """Duck-typed LangChain chat model wrapping a shared.MockLLM queue.

    `messages` arrives as a list of (role, content) tuples or langchain
    message objects (BaseMessage subclasses). We accept either shape.
    """

    def __init__(self, client: MockLLM | None = None):
        self._mock = client or MockLLM()

    def invoke(self, messages: list[Any], *_, **__) -> _Result:
        system_parts: list[str] = []
        user_parts: list[str] = []
        for m in messages:
            if isinstance(m, tuple):
                role, content = m
            else:
                role = getattr(m, "type", "user")
                content = getattr(m, "content", str(m))
            if role == "system":
                system_parts.append(str(content))
            else:
                user_parts.append(str(content))
        resp = self._mock.complete(
            system="\n".join(system_parts), user="\n".join(user_parts)
        )
        return _Result(content=resp.text)


def build_llm(real: bool) -> Any:
    """Choose the LLM backend for the graph's `llm` state slot.

    Mock: a MockChatModel bound to a fresh MockLLM queue.
    Real: stock ChatAnthropic(model='claude-haiku-4-5') — langchain
    handles everything. Pre-validate the API key via RealLLM so failure
    surfaces with a clearer message than ChatAnthropic's would.
    """
    if real:
        RealLLM()  # construction-only check; instance discarded
        return ChatAnthropic(model="claude-haiku-4-5", max_tokens=1024)
    return MockChatModel()
