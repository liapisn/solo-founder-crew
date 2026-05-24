"""solo-founder-crew — framework primitives.

Public API as of Phase 1 (no runtime / Crew yet — those arrive in
Phase 2). Importing from this module is the supported way to use the
framework; submodule paths are implementation details and may move.

  from solo_founder_crew import (
      VentureBrief,
      Role, DecisionRights,
      ToolRegistry, ToolPermissionError,
      HITLContract, FounderDecision, ScriptedHITL,
      TraceEvent, RunTrace,
      LLMClient, MockLLM, RealLLM, load_dotenv,
  )

Each name above maps to a citable concept in Chapter 3 of the thesis.
"""
from __future__ import annotations

from solo_founder_crew.brief import VentureBrief
from solo_founder_crew.hitl import FounderDecision, HITLContract, ScriptedHITL
from solo_founder_crew.llm import (
    LLMClient,
    LLMResponse,
    MockLLM,
    QueueExhausted,
    RealLLM,
    load_dotenv,
)
from solo_founder_crew.role import DecisionRights, Role
from solo_founder_crew.tools import (
    Tool,
    ToolPermissionError,
    ToolRegistry,
    ToolSpec,
)
from solo_founder_crew.trace import RunTrace, TraceEvent

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Component 1 — Venture Brief
    "VentureBrief",
    # Component 2 — Role primitives
    "Role",
    "DecisionRights",
    # Component 4 (partial) — tools + trace, runtime in Phase 2
    "Tool",
    "ToolSpec",
    "ToolRegistry",
    "ToolPermissionError",
    "RunTrace",
    "TraceEvent",
    # Component 5 — HITL Contract
    "HITLContract",
    "FounderDecision",
    "ScriptedHITL",
    # LLM substrate
    "LLMClient",
    "LLMResponse",
    "MockLLM",
    "RealLLM",
    "QueueExhausted",
    "load_dotenv",
]
