"""Tests for the Implementer port — M2 Phase 3, the engineering role's diff.

Everything here runs against `FakeImplementer` and the pure
`detect_escalations` policy: no coding agent, no git, no network. That split
mirrors the daemon's Discord layer — the real adapter
(`ClaudeCodeImplementer`) is exercised live, the contract is pinned here.

Pins six behaviours:

1. Escalation detection fires on dependency manifests.
2. Escalation detection fires on schema/data migrations.
3. An ordinary code change raises no escalation at all.
4. Escalations are reported in the role's own declaration order.
5. An agent that changed nothing is an empty result, never a PR.
6. A failed agent surfaces as an error result, never a silent success.
"""
from __future__ import annotations

from pathlib import Path

from solo_founder_crew.adapters.implementer import (
    DEPENDENCY_CHANGE,
    SCHEMA_OR_DATA_MIGRATION,
    FakeImplementer,
    ImplementResult,
    detect_escalations,
)

# ─── escalation policy ──────────────────────────────────────────────────────


def test_dependency_manifests_escalate():
    for path in (
        "api/requirements.txt",
        "api/requirements-dev.txt",
        "pyproject.toml",
        "web/package.json",
        "web/package-lock.json",
        "uv.lock",
    ):
        assert detect_escalations([path]) == (DEPENDENCY_CHANGE,), path


def test_migrations_escalate():
    for path in (
        "supabase/migrations/0002_add_thing.sql",
        "api/migrations/003_backfill.py",
        "db/schema.sql",
    ):
        assert SCHEMA_OR_DATA_MIGRATION in detect_escalations([path]), path


def test_ordinary_code_changes_do_not_escalate():
    files = [
        "api/app/services/member_service.py",
        "web/app/page.tsx",
        "README.md",
        "docs/dev-flow.md",
        "api/tests/test_http.py",
    ]
    assert detect_escalations(files) == ()


def test_escalations_follow_the_roles_declaration_order():
    """make_engineering lists dependency_change before
    schema_or_data_migration; the founder should always see that order."""
    files = ["supabase/migrations/0002_x.sql", "api/requirements.txt"]
    assert detect_escalations(files) == (DEPENDENCY_CHANGE, SCHEMA_OR_DATA_MIGRATION)


def test_a_requirements_like_name_that_is_not_a_manifest_is_ignored():
    assert detect_escalations(["docs/requirements-discussion.md"]) == ()


# ─── the port's contract ────────────────────────────────────────────────────


async def test_fake_reports_a_pushed_branch_and_derived_escalations():
    impl = FakeImplementer(files=("api/requirements.txt", "api/app/main.py"))
    result = await impl.implement("Add Google Wallet support", branch="eng/gw")

    assert result.branch == "eng/gw"
    assert result.pushed is True
    assert result.ok
    assert result.escalations == (DEPENDENCY_CHANGE,)
    assert impl.calls == [{"proposal": "Add Google Wallet support", "branch": "eng/gw"}]


async def test_an_agent_that_changed_nothing_is_empty_not_ok():
    """No diff must never become a pull request."""
    result = await FakeImplementer(files=()).implement("no-op", branch="eng/noop")

    assert result.is_empty
    assert not result.ok
    assert result.escalations == ()


async def test_a_failed_agent_surfaces_as_an_error():
    impl = FakeImplementer(error="Coding agent exceeded 900s and was stopped.")
    result = await impl.implement("something", branch="eng/slow")

    assert not result.ok
    assert "900s" in result.error
    assert result.pushed is False


def test_result_defaults_are_safe():
    """A bare result must not look like a successful, pushed change."""
    result = ImplementResult(branch="eng/x")
    assert result.is_empty and not result.ok and not result.pushed


# ─── the agent's environment ────────────────────────────────────────────────
# The daemon has the venture's secrets loaded from .env. A child process must
# not inherit them, and must hold no credential that could push or merge.


def test_child_env_strips_repository_and_venture_credentials(tmp_path, monkeypatch):
    from solo_founder_crew.adapters.implementer import ClaudeCodeImplementer

    for planted in (
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "RESEND_API_KEY",
        "DISCORD_BOT_TOKEN",
        "DATABASE_URL",
        "APPLE_CERT_PASSWORD",
        "SUPABASE_SECRET_KEY",
    ):
        monkeypatch.setenv(planted, f"{planted}_SHOULD_NOT_LEAK")

    env = ClaudeCodeImplementer._child_env(tmp_path)

    leaked = [k for k, v in env.items() if "SHOULD_NOT_LEAK" in v]
    assert leaked == [], f"secrets reached the coding agent: {leaked}"


def test_child_env_disables_git_and_gh_credentials(tmp_path):
    from solo_founder_crew.adapters.implementer import ClaudeCodeImplementer

    env = ClaudeCodeImplementer._child_env(tmp_path)

    # Blank git config → no credential helper is reachable.
    assert Path(env["GIT_CONFIG_GLOBAL"]).read_text() == ""
    assert env["GIT_CONFIG_SYSTEM"] == env["GIT_CONFIG_GLOBAL"]
    # Empty gh config dir → a stored `gh auth login` is invisible.
    assert Path(env["GH_CONFIG_DIR"]).is_dir()
    assert list(Path(env["GH_CONFIG_DIR"]).iterdir()) == []
    # Never sit waiting on a credential prompt in an unattended run.
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_child_env_keeps_what_the_agent_genuinely_needs(tmp_path, monkeypatch):
    from solo_founder_crew.adapters.implementer import ClaudeCodeImplementer

    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("HOME", "/Users/someone")
    env = ClaudeCodeImplementer._child_env(tmp_path)

    assert env["PATH"] == "/usr/bin"
    assert env["HOME"] == "/Users/someone"  # claude reads its own auth from HOME


# ─── ImplementedPRTool: only one outcome opens a pull request ───────────────


def _tool(impl, api):
    from solo_founder_crew.adapters.github_pr import ImplementedPRTool

    return ImplementedPRTool(implementer=impl, repo="liapisn/passly", api=api)


async def test_a_clean_change_opens_one_draft_pr_carrying_its_own_telemetry():
    from solo_founder_crew.adapters.github_pr import FakeGitHubAPI

    api = FakeGitHubAPI()
    impl = FakeImplementer(
        files=("api/app/services/pass_service.py",),
        diffstat=" 1 file changed, 12 insertions(+)",
        num_turns=8,
        duration_ms=35_700,
        cost_usd=0.3392,
    )
    url = await _tool(impl, api).__call__("Add Google Wallet support\n\nDetails here.")

    assert url == "https://github.com/liapisn/passly/pull/1"
    (pr,) = api.pull_requests
    assert pr["draft"] is True, "must never be mergeable without the founder"
    assert pr["base"] == "main"
    assert pr["head"] == impl.calls[0]["branch"]
    assert pr["title"] == "Add Google Wallet support"
    # The PR carries its own case-study record.
    assert "1 file changed, 12 insertions(+)" in pr["body"]
    assert "8 turns" in pr["body"] and "36s" in pr["body"] and "$0.3392" in pr["body"]
    # And the approved proposal it came from.
    assert "Details here." in pr["body"]
    # git push created the branch, so the API is never asked to.
    assert api.branches == {} and api.commits == []


async def test_an_escalating_diff_opens_no_pull_request():
    from solo_founder_crew.adapters.github_pr import FakeGitHubAPI

    api = FakeGitHubAPI()
    impl = FakeImplementer(files=("api/requirements.txt", "api/app/main.py"))
    message = await _tool(impl, api).__call__("Add a caching layer")

    assert api.pull_requests == [], "escalation must gate the PR"
    assert DEPENDENCY_CHANGE in message
    assert "pushed to" in message, "the work must not be lost"


async def test_an_empty_diff_opens_no_pull_request():
    from solo_founder_crew.adapters.github_pr import FakeGitHubAPI

    api = FakeGitHubAPI()
    message = await _tool(FakeImplementer(files=()), api).__call__("Do nothing")

    assert api.pull_requests == []
    assert "changed nothing" in message


async def test_a_failed_agent_opens_no_pull_request():
    from solo_founder_crew.adapters.github_pr import FakeGitHubAPI

    api = FakeGitHubAPI()
    impl = FakeImplementer(error="Coding agent exceeded 900s and was stopped.")
    message = await _tool(impl, api).__call__("Something hard")

    assert api.pull_requests == []
    assert "Implementation failed" in message and "900s" in message


async def test_branch_names_do_not_collide_across_runs():
    """A retry after a failure must not abort at `git worktree add`."""
    from solo_founder_crew.adapters.github_pr import FakeGitHubAPI

    impl = FakeImplementer()
    tool = _tool(impl, FakeGitHubAPI())
    await tool("Add subtract")
    await tool("Add subtract")

    first, second = (c["branch"] for c in impl.calls)
    assert first != second
    assert first.startswith("engineering/add-subtract-")


# ─── daemon wiring: live agent is opt-in ───────────────────────────────────


def test_dev_flow_is_off_until_both_settings_are_present():
    from solo_founder_crew.app import make_pr_tool
    from solo_founder_crew.config import RuntimeConfig

    def cfg(**kw):
        return RuntimeConfig(
            brief_path=Path("brief.json"), model="mock", checkpointer_url="memory",
            guild_id=None, discord_token=None, **kw,
        )

    assert not cfg().dev_flow_enabled
    assert make_pr_tool(cfg()) is None
    # A repo without a local checkout to work in is still not enough.
    assert make_pr_tool(cfg(pr_repo="liapisn/passly")) is None


async def test_build_tools_falls_back_to_a_stub_pr_tool():
    """An unconfigured daemon must still run, with no side effects."""
    from solo_founder_crew.app import build_tools

    tools = build_tools()
    assert "pr_tool" in tools._tools

    async def spy(text: str) -> str:
        return f"opened:{text}"

    assert await build_tools(pr_tool=spy)._tools["pr_tool"]("x") == "opened:x"
