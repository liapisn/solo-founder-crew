"""Per-role model routing — the smallest end-to-end demo.

Demonstrates ``Crew.role_llms``: the same ``Crew`` runs two roles
backed by two *different* Claude tiers. Marketing uses Haiku (cheap,
fast, sufficient for brief-bound copy). Engineering uses Opus
(reserved for consequential or open-ended work — architecture
proposals, complex code changes).

The framework's only commitment is that every model satisfy the
``LLMClient`` Protocol; the routing map at the Crew level decides
*which* model serves *which* role. No node or runtime code knows
about tiers.

Run:
    cd solo-founder-crew
    python examples/per_role_models.py            # mock (no API key)
    python examples/per_role_models.py --real-llm # claude-haiku-4-5 + claude-opus-4-7

The mock path prints which canned response was served to which role.
The real path prints the actual model name recorded by each adapter
plus token usage, so you can confirm Anthropic's API received the
tier you asked for.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from solo_founder_crew import (
    AnthropicLLM,
    Crew,
    FounderDecision,
    LLMClient,
    MockLLM,
    ScriptedHITL,
    ToolRegistry,
    VentureBrief,
    load_dotenv,
    make_engineering,
    make_marketing,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIEF_PATH = REPO_ROOT / "scenarios" / "fixtures" / "passly_brief.json"


# Mock responses tagged so the printed output makes the routing
# decision visible. In the real-LLM path Anthropic supplies these.
HAIKU_MARKETING = (
    "[from Haiku] Introducing Passly — loyalty passes that live in your wallet, "
    "campaigns drafted by AI, sent in two clicks. Greek-first. Pre-launch.\n"
)
OPUS_ENGINEERING = (
    "[from Opus] Proposed: add a `WalletPassIssuer` service. Inputs: tenant_id, "
    "pass_template, customer_email. Outputs: wallet_url (Apple or Google). "
    "Idempotent; rate-limit 60 rpm/tenant. PR drafted on branch "
    "feat/wallet-issuer; CI pending; merge to main awaits founder approval.\n"
)


def build_tools() -> ToolRegistry:
    """One registry, two tools — one per role."""
    registry = ToolRegistry()

    async def publisher(text: str) -> str:
        return f"published:{len(text)}chars"

    async def pr(text: str) -> str:
        return f"pr_opened:{len(text)}chars"

    registry.register(
        "publisher_tool", publisher, escalates="final_approval_before_publish"
    )
    registry.register("pr_tool", pr, escalates="merge_to_main")
    return registry


def build_default_llm(real: bool) -> LLMClient:
    """Crew default — used by every role with no override."""
    if real:
        return AnthropicLLM(model="claude-haiku-4-5")
    return MockLLM(responses=[HAIKU_MARKETING], model="mock-haiku")


def build_engineering_llm(real: bool) -> LLMClient:
    """Engineering override — heavier tier for architecture work."""
    if real:
        return AnthropicLLM(model="claude-opus-4-7")
    return MockLLM(responses=[OPUS_ENGINEERING], model="mock-opus")


def _approve_now() -> ScriptedHITL:
    return ScriptedHITL([FounderDecision(action="approve")])


def _print_calls(label: str, llm: LLMClient) -> None:
    calls = getattr(llm, "calls", [])
    if not calls:
        print(f"  {label}: 0 calls")
        return
    for c in calls:
        usage = c.get("usage")
        usage_str = (
            f"  tokens in={usage['input_tokens']} out={usage['output_tokens']}"
            if usage
            else ""
        )
        print(
            f"  {label}: model={c['model']:<24}  "
            f"output={c['output'].splitlines()[0][:70]!r}{usage_str}"
        )


async def main(real_llm: bool) -> None:
    load_dotenv(REPO_ROOT / ".env")

    brief = VentureBrief.from_file(BRIEF_PATH)
    tools = build_tools()

    marketing = make_marketing(brief)
    engineering = make_engineering(brief)

    default_llm = build_default_llm(real_llm)
    engineering_llm = build_engineering_llm(real_llm)

    crew = Crew(
        brief=brief,
        roles=[marketing, engineering],
        llm=default_llm,
        hitl=_approve_now(),
        tools=tools,
        role_llms={"engineering": engineering_llm},
    )

    print(
        f"\n── Run 1: marketing flow (expected LLM = "
        f"{'Anthropic Haiku' if real_llm else 'mock default'}) ──"
    )
    r1 = await crew.author_flow(task_description="Draft a launch teaser.", role="marketing")
    print(f"  status: {r1.status}  events: {len(r1.trace)}")
    print("  artifact (first line):")
    print(f"    {(r1.approved_artifact or '').splitlines()[0]}")

    # Reset trace + HITL queue between runs so each run starts clean.
    crew.reset_trace()
    crew.hitl = _approve_now()

    print(
        f"\n── Run 2: engineering flow (expected LLM = "
        f"{'Anthropic Opus' if real_llm else 'mock override'}) ──"
    )
    r2 = await crew.author_flow(
        task_description="Propose a WalletPassIssuer service for the MVP.",
        role="engineering",
        publish_tool="pr_tool",
    )
    print(f"  status: {r2.status}  events: {len(r2.trace)}")
    print("  artifact (first line):")
    print(f"    {(r2.approved_artifact or '').splitlines()[0]}")

    print("\n── Adapter call logs (proves routing happened) ──")
    _print_calls("default_llm (marketing) ", default_llm)
    _print_calls("engineering_llm        ", engineering_llm)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Per-role model routing demo")
    p.add_argument(
        "--real-llm",
        action="store_true",
        help="Use Anthropic Haiku + Opus instead of the deterministic mocks. "
        "Requires ANTHROPIC_API_KEY.",
    )
    args = p.parse_args()
    asyncio.run(main(args.real_llm))
