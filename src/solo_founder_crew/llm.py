"""LLM client Protocol + reference implementations.

The framework's runtime depends only on the `LLMClient` Protocol:

    class LLMClient(Protocol):
        def complete(self, system: str, user: str) -> LLMResponse: ...

This narrow contract is the deliberate decoupling of framework code
from any specific LLM SDK. Three implementations ship in the package:

- `MockLLM`: pre-loaded response queue, no network, no API key. Used
  by tests and by the spike runners.
- `AnthropicLLM`: Anthropic SDK wrapper, parameterised on model name.
  Use to point different roles at different Claude tiers (Haiku for
  most, Sonnet for default, Opus for hard work). Lazy-imports
  `anthropic` so the package remains importable without the SDK.
- `RealLLM`: deprecated alias for `AnthropicLLM`, kept for
  backwards-compat with the Phase-1 examples and the spikes.

Additional adapters (OpenAI, Gemini, Azure, Bedrock, local Ollama)
satisfy the same Protocol without touching framework code; see the
roadmap M2.5 entry.

Citable in Ch.3 §"LLM substitution" and Ch.5 §"Reproducibility" — the
mock is what makes scoring runs free and deterministic; the
Anthropic adapter is what proves the Protocol is substrate-neutral
across at least three Claude tiers driving the same crew.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class LLMResponse:
    text: str
    call_index: int


class LLMClient(Protocol):
    """The single sync method any LLM backend must implement."""

    def complete(self, system: str, user: str) -> LLMResponse: ...


class QueueExhausted(RuntimeError):
    """Raised when a MockLLM caller makes more requests than the queue holds."""


@dataclass
class MockLLM:
    """Deterministic stub: pre-load responses in order, return them on
    each call. Raises `QueueExhausted` if the caller asks for more.

    The exhaustion is intentional — it surfaces unexpected LLM chatter
    in a framework integration as a loud failure, not silent drift.
    """

    responses: list[str] = field(default_factory=list)
    model: str = "mock-claude-haiku-4-5"
    calls: list[dict[str, Any]] = field(default_factory=list)

    def complete(self, system: str, user: str) -> LLMResponse:
        idx = len(self.calls)
        if idx >= len(self.responses):
            raise QueueExhausted(
                f"MockLLM queue exhausted after {idx} call(s) "
                f"(capacity {len(self.responses)}). "
                f"Last user prompt: {user[:120]!r}"
            )
        text = self.responses[idx]
        self.calls.append(
            {
                "call_index": idx,
                "model": self.model,
                "system": system,
                "user": user,
                "output": text,
            }
        )
        return LLMResponse(text=text, call_index=idx)


@dataclass
class AnthropicLLM:
    """Anthropic-backed LLMClient.

    Parameterised on ``model`` so a single class drives any Claude tier.
    Common choices today:

    - ``claude-haiku-4-5`` — cheap, fast; sensible default for the
      framework's "coordination brain" and any role whose work is
      bounded by the brief (Marketing, Customer Support, Sales).
    - ``claude-sonnet-4-6`` — middle tier; a reasonable upgrade when
      Haiku draft quality is marginal.
    - ``claude-opus-4-7`` — top tier; reserve for roles whose action
      is consequential or open-ended (Engineering architecture work,
      complex Finance analysis).

    The framework's ``role_llms`` map on ``Crew`` is the supported
    way to route per-role; see ``examples/per_role_models.py``.

    Lazy-imports ``anthropic`` so the package remains importable on
    systems without the SDK. Validates ``ANTHROPIC_API_KEY`` at
    construction so missing-credential failures surface early.
    """

    model: str = "claude-haiku-4-5"
    max_tokens: int = 1024
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        try:
            import anthropic  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "AnthropicLLM requires `pip install anthropic`. "
                "Use MockLLM if you do not need live calls."
            ) from e
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "AnthropicLLM requires ANTHROPIC_API_KEY to be set in the "
                "environment (or loaded from .env via load_dotenv())."
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


# Backwards-compat alias. Existing examples (passly_launch.py and the
# spike runners) still import RealLLM; new code should prefer
# AnthropicLLM directly.
RealLLM = AnthropicLLM


def load_dotenv(path: Path | str = ".env") -> bool:
    """Lightweight stdlib KEY=VALUE loader.

    Loads `path` into `os.environ`. Existing **non-empty** env vars are
    preserved; existing-empty values are treated as unset and replaced
    (matches python-dotenv semantics — and is the source of a real bug
    if you don't).

    Returns True if the file was read, False if it didn't exist.
    """
    p = Path(path)
    if not p.is_file():
        return False
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        if os.environ.get(key):
            continue
        os.environ[key] = value
    return True
