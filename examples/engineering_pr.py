"""Engineering role end-to-end: draft a proposal → founder approves → draft PR opens.

This is the M2 Phase 2 counterpart to ``passly_launch.py``. The
engineering role drafts a short proposal artefact; the founder
approves through the HITL gate; the runtime invokes ``pr_tool`` which
opens a **draft** pull request on a configured GitHub repository.

By default the example runs against a ``FakeGitHubAPI`` so it is
safe to execute with no credentials and no network. Pass
``--live`` to use the real GitHub API; that requires:

  - ``ANTHROPIC_API_KEY``  (for the engineering role's LLM, if also
                            running ``--real-llm``)
  - ``GITHUB_TOKEN``        (with ``repo`` scope, or fine-grained
                             read/write on Contents + Pull requests
                             for the target repo)
  - ``SFC_PR_REPO``         (e.g. ``liapisn/passly``)
  - optional ``SFC_PR_BASE_BRANCH``  (default ``main``)

Run:
    cd solo-founder-crew
    python examples/engineering_pr.py                  # mock + FakeGitHubAPI
    python examples/engineering_pr.py --real-llm       # Opus + FakeGitHubAPI
    python examples/engineering_pr.py --real-llm --live  # Opus + real GitHub

The ``--live`` flag opens a real draft PR on the configured repo.
Drafts are never auto-mergeable — the founder must promote and merge
on GitHub. CI will run as configured; the existing
``pr-review-notify`` workflow will post the PR to Discord when CI
passes (Dev Flow's notify-only merge gate).
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
)
from solo_founder_crew.adapters.github_pr import (
    FakeGitHubAPI,
    GitHubPRTool,
    make_github_pr_tool,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIEF_PATH = REPO_ROOT / "scenarios" / "fixtures" / "passly_brief.json"


# Canned engineering proposal used when --real-llm is NOT passed. The
# real-LLM path produces something similar (and richer) from Opus.
MOCK_PROPOSAL = """\
Proposal: WalletPassIssuer service for the MVP

Provides a single entry point for issuing Apple/Google Wallet passes
to a tenant. Inputs: tenant_id, pass_template, customer_email.
Output: a signed wallet URL.

Implementation notes:
- New module solo_founder_crew/passly/wallet_pass_issuer.py
- Idempotent; rate-limited 60 rpm/tenant.
- No third-party SDK; uses Apple PassKit signing directly.

Risks flagged:
- Apple cert rotation policy (annual; requires founder action).
- One-time GDPR review of the pass payload contents.
"""


def build_llm(real: bool) -> LLMClient:
    if real:
        # Opus for the engineering role — the framework's per-role
        # routing (M2.5) shows this is the right tier for
        # consequential/open-ended proposals.
        return AnthropicLLM(model="claude-opus-4-7")
    return MockLLM(responses=[MOCK_PROPOSAL], model="mock-opus")


def build_pr_tool(live: bool) -> GitHubPRTool:
    if live:
        # Reads SFC_PR_REPO / SFC_PR_BASE_BRANCH from env; uses
        # RealGitHubAPI which validates GITHUB_TOKEN at construction.
        return make_github_pr_tool()
    # Default: in-memory fake, no network, no credentials.
    return GitHubPRTool(repo="liapisn/passly-demo", api=FakeGitHubAPI())


async def main(real_llm: bool, live: bool) -> None:
    load_dotenv(REPO_ROOT / ".env")

    brief = VentureBrief.from_file(BRIEF_PATH)
    engineering = make_engineering(brief)

    pr_tool = build_pr_tool(live)

    tools = ToolRegistry()
    tools.register("pr_tool", pr_tool, escalates="merge_to_main")

    crew = Crew(
        brief=brief,
        roles=[engineering],
        llm=build_llm(real_llm),
        hitl=ScriptedHITL([FounderDecision(action="approve")]),
        tools=tools,
    )

    print(
        f"\n── Engineering proposal flow "
        f"(LLM = {'Anthropic Opus' if real_llm else 'mock-opus'}, "
        f"PR backend = {'real GitHub' if live else 'FakeGitHubAPI'}) ──"
    )

    result = await crew.author_flow(
        task_description=(
            "Propose how to add a WalletPassIssuer service for the MVP. "
            "Cover inputs, outputs, idempotency, rate-limits, and any "
            "risks the founder must approve."
        ),
        role="engineering",
        publish_tool="pr_tool",
    )

    print(f"  status: {result.status}  events: {len(result.trace)}")
    print(f"  PR URL: {result.final_state.get('publish_result')}")
    if isinstance(pr_tool.api, FakeGitHubAPI):
        api = pr_tool.api
        print(f"  fake-api branches created: {list(api.branches)}")
        print(
            f"  fake-api committed file: "
            f"{api.commits[0]['path'] if api.commits else '(none)'}"
        )
    print("  proposal first line:")
    print(
        f"    {(result.approved_artifact or '').splitlines()[0]!r}"
        if result.approved_artifact
        else "    (no artifact)"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Engineering role → draft PR (M2 Phase 2 demo)"
    )
    p.add_argument(
        "--real-llm",
        action="store_true",
        help="Use Anthropic Opus instead of the canned mock proposal. "
        "Requires ANTHROPIC_API_KEY.",
    )
    p.add_argument(
        "--live",
        action="store_true",
        help="Open a real draft PR on GitHub (FakeGitHubAPI otherwise). "
        "Requires GITHUB_TOKEN + SFC_PR_REPO.",
    )
    args = p.parse_args()
    asyncio.run(main(args.real_llm, args.live))
