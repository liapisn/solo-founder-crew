"""Passly launch with a *real* interactive HITL gate.

Same scenario as ``examples/passly_launch.py``, but the founder
decision comes from stdin instead of a JSON fixture. This is the
worked example that shows the production HITL path — the graph
genuinely pauses at the gate, waits for input, and resumes once the
founder responds.

Run:
    .venv/bin/python examples/passly_interactive.py
    .venv/bin/python examples/passly_interactive.py --real-llm

At each gate, you'll be prompted:
    Action [approve/reject/kill]:

If you reject, you'll be asked for one-line feedback; the LLM uses it
to revise. Approve to publish. Kill to abort.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from solo_founder_crew import (
    Crew,
    InteractiveHITL,
    MockLLM,
    RealLLM,
    ToolRegistry,
    VentureBrief,
    load_dotenv,
    make_marketing,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIEF_PATH = REPO_ROOT / "scenarios" / "fixtures" / "passly_brief.json"
OUT_DIR = REPO_ROOT / "examples" / "out"


# Plenty of mock responses in the queue so the user can reject as many
# times as MAX_REVISIONS allows. Each rejection consumes one entry.
DRAFT_RESPONSES = [
    "Introducing Passly — digital wallet passes and AI marketing for Greek SMBs.\n\n"
    "Loyalty offers live in Apple/Google Wallet. AI drafts campaigns, "
    "owner ships in two clicks. Pre-launch, early-access available.\n",
    "Έρχεται το Passly — επανέλαβε στους πελάτες σου ότι σε θυμούνται.\n\n"
    "Passes loyalty στο Apple/Google Wallet. AI γράφει την καμπάνια, "
    "εσύ τη στέλνεις σε 2 κλικ. Pre-launch, ψάχνουμε early-access.\n",
    "Passly — for the καφέ owner who wants regulars back without learning a marketing tool.\n",
]


async def main(real_llm: bool) -> None:
    load_dotenv(REPO_ROOT / ".env")

    brief = VentureBrief.from_file(BRIEF_PATH)
    role = make_marketing(brief)

    tools = ToolRegistry()

    async def publisher(text: str) -> str:
        return f"shipped:{len(text)}chars"

    tools.register("publisher_tool", publisher, escalates="final_approval_before_publish")

    llm = RealLLM() if real_llm else MockLLM(responses=DRAFT_RESPONSES)
    hitl = InteractiveHITL()

    crew = Crew(brief=brief, roles=[role], llm=llm, hitl=hitl, tools=tools)
    print(
        f"Starting Passly author flow with InteractiveHITL "
        f"(LLM = {'Anthropic Haiku' if real_llm else 'mock'})…"
    )
    result = await crew.author_flow(
        task_description=(
            "Draft a launch announcement for this venture. Match the voice. "
            "Respect every constraint. Keep under 150 words."
        ),
        max_revisions=2,
    )

    print(
        f"\n── result ──\nstatus    = {result.status}\n"
        f"thread_id = {result.thread_id}\nevents    = {len(result.trace)}"
    )
    OUT_DIR.mkdir(exist_ok=True)
    if result.approved_artifact:
        out_path = OUT_DIR / "final_announcement_interactive.txt"
        out_path.write_text(result.approved_artifact, encoding="utf-8")
        print(f"approved artifact written to {out_path}")
    result.trace.write(OUT_DIR / "run_trace_interactive.json")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Passly with interactive HITL")
    p.add_argument("--real-llm", action="store_true")
    args = p.parse_args()
    asyncio.run(main(args.real_llm))
