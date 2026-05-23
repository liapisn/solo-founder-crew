"""Thin Anthropic SDK wrapper.

Isolated so the rest of the runtime is LLM-agnostic. The spike uses
claude-opus-4-7 (per spike charter) and keeps to one call per role action.
"""
from __future__ import annotations

import os
from typing import Protocol

from anthropic import AsyncAnthropic

MODEL = "claude-opus-4-7"
MAX_TOKENS = 1024


class LLM(Protocol):
    async def complete(self, *, system: str, user: str) -> str: ...


class AnthropicLLM:
    def __init__(self, client: AsyncAnthropic | None = None):
        self._client = client or AsyncAnthropic(
            api_key=os.environ["ANTHROPIC_API_KEY"]
        )

    async def complete(self, *, system: str, user: str) -> str:
        resp = await self._client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # spike: single text block per response
        return resp.content[0].text.strip()
