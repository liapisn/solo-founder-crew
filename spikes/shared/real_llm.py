"""Optional real-LLM client for the spike's --real-llm smoke test.

Satisfies the same LLMClient Protocol as MockLLM so each spike's adapter
treats them interchangeably. Default spike runs use the mock; this is
only invoked when `--real-llm` is passed.

Requires:
    pip install anthropic
    export ANTHROPIC_API_KEY=...

One call per spike run, claude-haiku-4-5, ~$0.02 per smoke test. Not
scored — exists only to prove each framework's runtime LLM integration
works end-to-end. See docs/spike-charter.md §"LLM stance".
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from .mock_llm import LLMResponse


@dataclass
class RealLLM:
    model: str = "claude-haiku-4-5"
    max_tokens: int = 1024
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        try:
            import anthropic  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "RealLLM requires `pip install anthropic`. "
                "Run without --real-llm to use MockLLM."
            ) from e
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "RealLLM requires ANTHROPIC_API_KEY to be set. "
                "Run without --real-llm to use MockLLM."
            )

    def complete(self, system: str, user: str) -> LLMResponse:
        import anthropic

        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # First content block, text type.
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        idx = len(self.calls)
        self.calls.append(
            {
                "call_index": idx,
                "model": self.model,
                "system": system,
                "user": user,
                "output": text,
                "stop_reason": resp.stop_reason,
                "usage": {
                    "input_tokens": resp.usage.input_tokens,
                    "output_tokens": resp.usage.output_tokens,
                },
            }
        )
        return LLMResponse(text=text, call_index=idx)
