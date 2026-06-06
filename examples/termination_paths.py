"""The four Author Flow termination paths, as reproducible traces.

Generates one run per terminal outcome of the canonical Author Flow
(``draft → review → (revise → review)* → publish``) using a deterministic
``MockLLM`` and a ``ScriptedHITL``, and writes each run's trace to
``examples/out/``. This is the citable source for Ch.3 §3.9 "Box 3.2 — the
four termination paths": the event counts printed here are the ones the
prose should quote, and they match the assertions in
``tests/test_author_flow.py``.

Run:
    .venv/bin/python examples/termination_paths.py

Deterministic and free — no model calls. Re-run anytime to regenerate.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from solo_founder_crew import (
    Crew,
    FounderDecision,
    MockLLM,
    ScriptedHITL,
    ToolRegistry,
    VentureBrief,
    make_marketing,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIEF_PATH = REPO_ROOT / "scenarios" / "fixtures" / "passly_brief.json"
OUT_DIR = REPO_ROOT / "examples" / "out"

DRAFT_V1 = "Introducing Passly — wallet passes and AI marketing for Greek SMBs.\n"
DRAFT_V2 = "Έρχεται το Passly — οι πελάτες σου, ένα tap μακριά.\n"

# (name, founder decisions in order, mock draft responses, max_revisions)
PATHS = [
    ("approve", [FounderDecision("approve")], [DRAFT_V1], 1),
    (
        "reject_then_approve",
        [FounderDecision("reject", feedback="warmer, more Greek"), FounderDecision("approve")],
        [DRAFT_V1, DRAFT_V2],
        1,
    ),
    ("kill", [FounderDecision("kill")], [DRAFT_V1], 1),
    (
        "exhausted",
        [FounderDecision("reject", feedback="no"), FounderDecision("reject", feedback="still no")],
        [DRAFT_V1, DRAFT_V2],
        1,
    ),
]


def _tools() -> ToolRegistry:
    tools = ToolRegistry()

    async def publisher(text: str) -> str:
        return f"shipped:{len(text)}chars"

    tools.register("publisher_tool", publisher, escalates="final_approval_before_publish")
    return tools


async def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    brief = VentureBrief.from_file(BRIEF_PATH)
    role = make_marketing(brief)

    rows = []
    for name, decisions, responses, max_revisions in PATHS:
        crew = Crew(
            brief=brief,
            roles=[role],
            llm=MockLLM(responses=responses),
            hitl=ScriptedHITL(decisions),
            tools=_tools(),
        )
        result = await crew.author_flow(
            task_description="Draft a launch announcement.",
            max_revisions=max_revisions,
        )
        out = OUT_DIR / f"trace_{name}.json"
        result.trace.write(out)
        actions = [e.action for e in result.trace.events]
        rows.append((name, result.status, len(result.trace), actions))

    width = max(len(r[0]) for r in rows)
    print("\nFour Author Flow termination paths (deterministic):\n")
    print(f"  {'path'.ljust(width)}  status      events  action sequence")
    print(f"  {'-' * width}  ----------  ------  ---------------")
    for name, status, n, actions in rows:
        print(f"  {name.ljust(width)}  {status.ljust(10)}  {n:>6}  {' → '.join(actions)}")
    print(f"\nTraces written to {OUT_DIR}/trace_*.json")


if __name__ == "__main__":
    asyncio.run(main())
