"""Tests for the GitHub PR tool — M2 Phase 2 `pr_tool` for engineering.

The adapter depends on a `GitHubAPI` Protocol, not on `httpx` directly,
so these tests run entirely against `FakeGitHubAPI` — no network, no
token, no GitHub credentials needed. The shape of the call sequence
the tool makes against the API is the contract under test.

Pins five behaviours:

1. End-to-end happy path produces a draft PR with the expected title,
   branch name, and committed proposal file.
2. The tool refuses construction without a valid `owner/name` repo.
3. The `make_github_pr_tool` factory reads `SFC_PR_REPO` from env.
4. The tool integrates with `ToolRegistry` + the engineering role's
   `decision_rights` — invocation requires `merge_to_main` escalation.
5. Title/slug derivation handles awkward inputs (markdown headers,
   long titles, blank leading lines) deterministically.
"""
from __future__ import annotations

import pytest

from solo_founder_crew import (
    DecisionRights,
    Role,
    ToolPermissionError,
    ToolRegistry,
    make_engineering,
)
from solo_founder_crew.adapters.github_pr import (
    FakeGitHubAPI,
    GitHubPRTool,
    _derive_title,
    _slugify,
    make_github_pr_tool,
)


PROPOSAL = """\
Proposal: add WalletPassIssuer service

Provides a single entry point for issuing Apple/Google Wallet passes
to a tenant. Inputs: tenant_id, pass_template, customer_email.
Outputs: a signed wallet URL.

Idempotent; rate-limited 60 rpm/tenant. PR opens a draft branch;
merge to main awaits founder approval.
"""


# ─── End-to-end against FakeGitHubAPI ────────────────────────────────────────


async def test_open_pr_creates_branch_commit_and_draft_pr() -> None:
    api = FakeGitHubAPI()
    tool = GitHubPRTool(repo="liapisn/passly", api=api)

    url = await tool(PROPOSAL)

    # PR opened
    assert url == "https://github.com/liapisn/passly/pull/1"
    assert len(api.pull_requests) == 1
    pr = api.pull_requests[0]
    assert pr["draft"] is True  # never auto-mergeable
    assert pr["base"] == "main"
    assert pr["title"] == "Proposal: add WalletPassIssuer service"
    assert pr["body"].startswith("Proposal: add WalletPassIssuer service")

    # Branch created from main, prefixed deterministically
    assert pr["head"] in api.branches
    assert pr["head"].startswith("engineering/proposal-")

    # Proposal file committed under docs/proposals/<slug>.md
    assert len(api.commits) == 1
    commit = api.commits[0]
    assert commit["path"].startswith("docs/proposals/")
    assert commit["path"].endswith(".md")
    assert "WalletPassIssuer" in commit["content"]


# ─── Construction-time guards ────────────────────────────────────────────────


def test_construction_rejects_invalid_repo() -> None:
    """``repo`` must be ``owner/name``; missing slash is rejected at
    construction so the error surfaces before any tool call."""
    api = FakeGitHubAPI()
    with pytest.raises(RuntimeError, match="owner/name"):
        GitHubPRTool(repo="passly", api=api)


def test_construction_rejects_empty_repo() -> None:
    api = FakeGitHubAPI()
    with pytest.raises(RuntimeError, match="owner/name"):
        GitHubPRTool(repo="", api=api)


# ─── Factory reads env vars ──────────────────────────────────────────────────


def test_make_github_pr_tool_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FakeGitHubAPI()
    monkeypatch.setenv("SFC_PR_REPO", "liapisn/from-env")
    monkeypatch.setenv("SFC_PR_BASE_BRANCH", "develop")
    tool = make_github_pr_tool(api=api)
    assert tool.repo == "liapisn/from-env"
    assert tool.base_branch == "develop"


def test_make_github_pr_tool_explicit_args_win(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeGitHubAPI()
    monkeypatch.setenv("SFC_PR_REPO", "liapisn/from-env")
    tool = make_github_pr_tool(repo="liapisn/explicit", api=api)
    assert tool.repo == "liapisn/explicit"


def test_make_github_pr_tool_missing_repo_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SFC_PR_REPO", raising=False)
    with pytest.raises(RuntimeError, match="SFC_PR_REPO"):
        make_github_pr_tool(api=FakeGitHubAPI())


# ─── Title + slug derivation ─────────────────────────────────────────────────


def test_title_handles_leading_markdown_header() -> None:
    assert _derive_title("# A: do X\nDetails …") == "A: do X"


def test_title_skips_blank_leading_lines() -> None:
    assert _derive_title("\n\n  Proposed change\nMore …") == "Proposed change"


def test_title_falls_back_when_artifact_empty() -> None:
    assert _derive_title("   \n\t\n") == "Engineering proposal"


def test_title_is_truncated_at_max_len() -> None:
    long = "x" * 200
    out = _derive_title(long, max_len=20)
    assert len(out) == 20


def test_slug_is_deterministic_and_url_safe() -> None:
    assert _slugify("Proposal: add a WalletPassIssuer service") == (
        "proposal-add-a-walletpassissuer-service"
    )
    # No leading or trailing dashes
    assert not _slugify("--leading and trailing--").startswith("-")
    assert not _slugify("--leading and trailing--").endswith("-")
    # Empty input has a stable fallback
    assert _slugify("") == "proposal"


def test_slug_truncates_long_input() -> None:
    long_title = "Proposal " * 20
    slug = _slugify(long_title, max_len=20)
    assert len(slug) <= 20
    assert not slug.endswith("-")


# ─── Integration with ToolRegistry + engineering role ────────────────────────


async def test_pr_tool_registers_against_tool_registry_and_enforces_escalation(
    brief,  # conftest fixture (VentureBrief)
) -> None:
    """The PR tool is registered under ``pr_tool`` and ``escalates``
    on ``merge_to_main`` — the same action the engineering role
    declares in its ``decision_rights.must_escalate``. End-to-end:
    only an escalated invocation succeeds."""
    api = FakeGitHubAPI()
    pr_tool = GitHubPRTool(repo="liapisn/passly", api=api)

    registry = ToolRegistry()
    registry.register("pr_tool", pr_tool, escalates="merge_to_main")

    engineering = make_engineering(brief)

    # No escalation evidence — registry refuses (defensive check, even
    # though Author Flow always sets escalation_satisfied=True on its
    # post-approve publish path).
    with pytest.raises(ToolPermissionError, match="escalation"):
        await registry.invoke(engineering, "pr_tool", PROPOSAL)

    # With escalation evidence, the PR is opened.
    url = await registry.invoke(
        engineering, "pr_tool", PROPOSAL, escalation_satisfied=True
    )
    assert url.startswith("https://github.com/liapisn/passly/pull/")


async def test_pr_tool_refuses_roles_without_pr_tool_in_allowlist(
    brief,
) -> None:
    """A role whose ``tools`` allowlist does not include ``pr_tool``
    cannot invoke it, even with escalation evidence."""
    api = FakeGitHubAPI()
    pr_tool = GitHubPRTool(repo="liapisn/passly", api=api)
    registry = ToolRegistry()
    registry.register("pr_tool", pr_tool, escalates="merge_to_main")

    # Marketing role does not hold pr_tool
    not_engineering = Role(
        name="marketing",
        goal="x",
        system_prompt="x",
        decision_rights=DecisionRights(
            can=("draft_content",),
            must_escalate=("merge_to_main",),  # technically declared, but…
        ),
        tools=("publisher_tool",),  # …allowlist missing pr_tool
    )
    with pytest.raises(ToolPermissionError, match="not allowed"):
        await registry.invoke(
            not_engineering, "pr_tool", PROPOSAL, escalation_satisfied=True
        )
