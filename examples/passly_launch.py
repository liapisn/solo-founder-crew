"""End-to-end Passly launch via the framework.

This is the same scenario the Part 7 spikes ran, now expressed entirely
through `solo_founder_crew` public API — no spike code. It serves three
purposes:

1. **Phase 2 acceptance test.** If this runs, the framework can do
   everything the custom spike did.
2. **Worked example for Ch.3 prose.** The thesis can quote this file
   verbatim as the smallest end-to-end usage.
3. **Acceptance criterion for Chapter 4 (Passly).** The Passly repo
   imports `solo_founder_crew` and writes scripts of exactly this
   shape.

Run:
    cd solo-founder-crew
    python examples/passly_launch.py            # mock, no API key
    python examples/passly_launch.py --real-llm # claude-haiku-4-5
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from solo_founder_crew import (
    Crew,
    DecisionRights,
    MockLLM,
    RealLLM,
    Role,
    ScriptedHITL,
    ToolRegistry,
    VentureBrief,
    load_dotenv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIEF_PATH = REPO_ROOT / "scenarios" / "fixtures" / "passly_brief.json"
RESPONSES_PATH = REPO_ROOT / "scenarios" / "fixtures" / "founder_responses.json"
OUT_DIR = REPO_ROOT / "examples" / "out"


# Mock responses for the no-API-key path. Scenario-specific text lives
# here, NOT in the framework — the framework only knows about a queue
# of strings.

DRAFT_V1 = """\
Introducing Passly — digital wallet passes and AI-assisted marketing
designed for Greek small and medium businesses.

Passly enables café and salon owners to issue loyalty passes and
promotional offers that customers store directly in Apple Wallet or
Google Wallet. The platform provides AI-generated campaign drafts
which the business owner can review and dispatch via SMS or email.

Passly is currently in a pre-launch phase. Early-access participation
is available to qualifying Greek SMBs.
"""

DRAFT_V2 = """\
Έρχεται το Passly — και θα σου δώσει πίσω τους πελάτες που ξέχασες ότι έχεις.

Φτιάξε passes επιβράβευσης και προσφορές για το καφέ ή το κομμωτήριό
σου σε λίγα λεπτά. Ζουν μέσα στο Apple ή Google Wallet — δεν
χρειάζεται να κατεβάσει εφαρμογή. Η AI γράφει την καμπάνια, εσύ τη
στέλνεις με δύο κλικ μέσω SMS ή email.

Όλα στα ελληνικά, GDPR-φιλικά. Είμαστε σε pre-launch και ψάχνουμε
early-access μαγαζάτορες που θέλουν να το δοκιμάσουν πρώτοι.

Στο Passly, η επόμενη επίσκεψη του πελάτη ξεκινά από το πορτοφόλι του.
"""

MARKETING_SYSTEM_PROMPT = """\
You are the Marketing role inside a solo-founder operating crew.

DECISION RIGHTS
- You may: draft_content, revise_content
- You must escalate to the founder for: final_approval_before_publish

OPERATING RULES
- Speak in the venture's voice as defined in the Venture Brief.
- Stay strictly within scope and constraints.
- Do not invent claims. Do not imply live customer pilots if the venture
  is pre-launch. Obey the brief's do/dont lists.
- Output ONLY the announcement text — no preamble, no markdown
  headings, no explanation.
"""


def build_marketing_role() -> Role:
    """Phase 3's Role Library will produce this from a Venture Brief.
    For Phase 2 we instantiate it inline so the framework's surface is
    the only thing under test."""
    return Role(
        name="marketing",
        goal="Draft customer-facing announcements that match the venture's voice and constraints.",
        system_prompt=MARKETING_SYSTEM_PROMPT,
        decision_rights=DecisionRights(
            can=("draft_content", "revise_content"),
            must_escalate=("final_approval_before_publish",),
        ),
        tools=("publisher_tool",),
    )


def build_publisher_tool_registry() -> ToolRegistry:
    """Stub publisher tool. Production code would dispatch to Apple/
    Google Wallet APIs or whatever channels the brief lists."""
    last_published: dict[str, str] = {}

    async def publisher(text: str) -> str:
        last_published["text"] = text
        return f"shipped:{len(text)}chars"

    registry = ToolRegistry()
    registry.register(
        "publisher_tool", publisher, escalates="final_approval_before_publish"
    )
    return registry


async def main(real_llm: bool) -> None:
    load_dotenv(REPO_ROOT / ".env")

    brief = VentureBrief.from_file(BRIEF_PATH)
    role = build_marketing_role()
    tools = build_publisher_tool_registry()
    hitl = ScriptedHITL.from_file(RESPONSES_PATH)
    llm = RealLLM() if real_llm else MockLLM(responses=[DRAFT_V1, DRAFT_V2])

    crew = Crew(brief=brief, roles=[role], llm=llm, hitl=hitl, tools=tools)
    result = await crew.author_flow(
        task_description=(
            "Draft a launch announcement for this venture. Match the voice. "
            "Respect every constraint. Keep under 150 words."
        )
    )

    OUT_DIR.mkdir(exist_ok=True)
    if result.approved_artifact:
        (OUT_DIR / "final_announcement.txt").write_text(
            result.approved_artifact, encoding="utf-8"
        )
    result.trace.write(OUT_DIR / "run_trace.json")

    print(
        f"status={result.status} events={len(result.trace)} "
        f"chars={len(result.approved_artifact or '')}"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Passly launch via solo_founder_crew")
    p.add_argument("--real-llm", action="store_true")
    args = p.parse_args()
    asyncio.run(main(args.real_llm))
