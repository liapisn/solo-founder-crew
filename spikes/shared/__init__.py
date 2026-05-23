"""Shared utilities for the Part 7 framework spike.

Provides a deterministic MockLLM and a structured run trace so all three
candidate implementations (custom, CrewAI, LangGraph) can be scored
against the same fixtures with zero API cost.
"""
from .mock_llm import MockLLM, MockLLMResponse
from .trace import RunTrace, TraceEvent

__all__ = ["MockLLM", "MockLLMResponse", "RunTrace", "TraceEvent"]
