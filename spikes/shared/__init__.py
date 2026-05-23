"""Shared utilities for the Part 7 framework spike.

Provides a deterministic MockLLM and a structured run trace so all three
candidate implementations (custom, CrewAI, LangGraph) can be scored
against the same fixtures with zero API cost.
"""
from .mock_llm import (
    DEFAULT_RESPONSES,
    DRAFT_V1,
    DRAFT_V2,
    LLMClient,
    LLMResponse,
    MockLLM,
    QueueExhausted,
)
from .real_llm import RealLLM
from .trace import RunTrace, TraceEvent

__all__ = [
    "DEFAULT_RESPONSES",
    "DRAFT_V1",
    "DRAFT_V2",
    "LLMClient",
    "LLMResponse",
    "MockLLM",
    "QueueExhausted",
    "RealLLM",
    "RunTrace",
    "TraceEvent",
]
