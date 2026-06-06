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
from solo_founder_crew.crew import AuthorFlowResult, Crew
from solo_founder_crew.crew_generator import (
    DEFAULT_RULES,
    CrewGenerationResult,
    CrewGenerator,
    CrewRule,
    RuleDecision,
)
from solo_founder_crew.hitl import (
    FounderDecision,
    HITLContract,
    InteractiveHITL,
    ScriptedHITL,
)
from solo_founder_crew.hitl_request import (
    DEFAULT_OPTIONS,
    Artifact,
    FounderResponse,
    HITLRequest,
    ReviewOption,
)
from solo_founder_crew.llm import (
    LLMClient,
    LLMResponse,
    MockLLM,
    QueueExhausted,
    RealLLM,
    load_dotenv,
)
from solo_founder_crew.role import DecisionRights, Role
from solo_founder_crew.roles_library import (
    ROLE_LIBRARY,
    RoleFactory,
    make_customer_support,
    make_engineering,
    make_finance,
    make_marketing,
    make_product,
    make_sales,
)
from solo_founder_crew.runtime import (
    AuthorFlowGraph,
    AuthorFlowState,
    build_author_graph,
)
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
    # Component 2 — Role primitives + library
    "Role",
    "DecisionRights",
    "RoleFactory",
    "ROLE_LIBRARY",
    "make_marketing",
    "make_product",
    "make_engineering",
    "make_customer_support",
    "make_sales",
    "make_finance",
    # Component 3 — Crew Generator
    "CrewGenerator",
    "CrewGenerationResult",
    "CrewRule",
    "RuleDecision",
    "DEFAULT_RULES",
    # Component 4 — Crew + Orchestration Runtime
    "Crew",
    "AuthorFlowResult",
    "AuthorFlowGraph",
    "AuthorFlowState",
    "build_author_graph",
    # Component 4 (cont.) — tools + trace
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
    "InteractiveHITL",
    "HITLRequest",
    "Artifact",
    "ReviewOption",
    "FounderResponse",
    "DEFAULT_OPTIONS",
    # LLM substrate
    "LLMClient",
    "LLMResponse",
    "MockLLM",
    "RealLLM",
    "QueueExhausted",
    "load_dotenv",
]
