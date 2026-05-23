"""LLM bridge for the custom spike.

Exposes a single `LLM` Protocol (async) that the runtime depends on. Two
implementations:

- `MockBackedLLM` — wraps `shared.MockLLM` (response queue, no API key).
  Default for `python run.py` so the spike is free and deterministic.
- `RealBackedLLM` — wraps `shared.RealLLM` (Anthropic SDK, Haiku).
  Activated by `python run.py --real-llm`. Exists for the unscored
  smoke test in docs/spike-charter.md §"LLM stance".

Both shared clients are sync; this module runs them on a worker thread
via `asyncio.to_thread`, keeping the spike's async runtime contract
unchanged.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Protocol

# spike layout: spikes/custom/llm.py → spikes/ on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared import LLMResponse, MockLLM, RealLLM  # noqa: E402


class LLM(Protocol):
    async def complete(self, *, system: str, user: str) -> str: ...


class MockBackedLLM:
    def __init__(self, client: MockLLM | None = None):
        self._client = client or MockLLM()

    async def complete(self, *, system: str, user: str) -> str:
        resp: LLMResponse = await asyncio.to_thread(
            self._client.complete, system, user
        )
        return resp.text


class RealBackedLLM:
    def __init__(self, model: str = "claude-haiku-4-5"):
        # Construction validates ANTHROPIC_API_KEY + anthropic import.
        self._client = RealLLM(model=model)

    async def complete(self, *, system: str, user: str) -> str:
        resp: LLMResponse = await asyncio.to_thread(
            self._client.complete, system, user
        )
        return resp.text
