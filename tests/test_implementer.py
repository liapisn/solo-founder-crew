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

import subprocess
from pathlib import Path

import pytest

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
    # `existing` defaults to False — a proposal cuts a new branch from the
    # base; only a CI fix continues one (see test_ci_fix.py).
    assert impl.calls == [
        {
            "proposal": "Add Google Wallet support",
            "branch": "eng/gw",
            "existing": "False",
        }
    ]


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


# ─── ClaudeCodeImplementer: worktree lifecycle ──────────────────────────────
# Exercised with a stub `claude` binary — real git, real worktrees, no agent
# and no network. This is what caught the relative-path bug: the daemon
# configures ../passly and ./data/worktrees, and those resolved differently
# for mkdtemp (daemon cwd) than for git (cwd=repo_path), so the worktree was
# created *inside the target repository* and the agent got a cwd that did not
# exist.


def _run(*args, cwd):
    subprocess.run(args, cwd=str(cwd), check=True, capture_output=True)


def _git_out(*args, cwd) -> str:
    """Read-only git query. Defined at module level so async tests do not call
    a blocking process API inline (ruff ASYNC221)."""
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False
    ).stdout


@pytest.fixture
def target_repo(tmp_path):
    """A clone with a local bare origin, so pushes work without a network."""
    origin, work = tmp_path / "origin.git", tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    _run("git", "config", "user.email", "t@t.t", cwd=work)
    _run("git", "config", "user.name", "test", cwd=work)
    (work / "README.md").write_text("# target\n")
    _run("git", "add", "-A", cwd=work)
    _run("git", "commit", "-qm", "initial", cwd=work)
    _run("git", "branch", "-M", "main", cwd=work)
    _run("git", "push", "-q", "-u", "origin", "main", cwd=work)
    return origin, work


def _stub_claude(tmp_path, *, body: str) -> str:
    """A fake `claude` that records its argv, edits the tree, then prints the
    result JSON. The argv goes to ``tmp_path/claude-argv`` so tests can assert
    on the flags the adapter passes — the tier is a spend decision, and the
    only evidence it took effect is what reached the command line."""
    script = tmp_path / "claude-stub"
    script.write_text(
        "#!/bin/sh\n"
        f'for a in "$@"; do echo "$a"; done > {tmp_path / "claude-argv"}\n'
        f"{body}\n"
        'echo \'{"is_error":false,"num_turns":3,"duration_ms":1234,'
        '"total_cost_usd":0.05,"session_id":"stub-session","result":"done"}\'\n'
    )
    script.chmod(0o755)
    return str(script)


def _argv(tmp_path) -> list[str]:
    return (tmp_path / "claude-argv").read_text().splitlines()


def _flag(argv: list[str], name: str) -> str:
    """The value following ``name`` in a recorded argv."""
    return argv[argv.index(name) + 1]


def test_relative_paths_are_resolved_at_construction(tmp_path, monkeypatch):
    """The regression: ../passly and ./data/worktrees must not stay relative."""
    from solo_founder_crew.adapters.implementer import ClaudeCodeImplementer

    monkeypatch.chdir(tmp_path)
    (tmp_path / "repo").mkdir()

    impl = ClaudeCodeImplementer(
        repo_path=Path("repo"), worktree_root=Path("./data/worktrees")
    )

    assert impl.repo_path.is_absolute()
    assert impl.worktree_root.is_absolute()
    assert impl.worktree_root == (tmp_path / "data/worktrees").resolve()


async def test_worktree_is_created_outside_the_target_repo(target_repo, tmp_path, monkeypatch):
    """The worktree must land under worktree_root, never inside repo_path —
    and the target repo must be left with no trace of the run."""
    from solo_founder_crew.adapters.implementer import ClaudeCodeImplementer

    origin, work = target_repo
    elsewhere = tmp_path / "daemon-cwd"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)  # daemon cwd != repo_path, as in production

    impl = ClaudeCodeImplementer(
        repo_path=work,
        worktree_root=Path("./data/worktrees"),  # relative, as configured
        claude_bin=_stub_claude(tmp_path, body="echo hi > added.txt"),
        timeout_seconds=60,
    )
    result = await impl.implement("Add a file", branch="engineering/add-file")

    assert result.error == "", result.error
    assert result.pushed and result.files_changed == ("added.txt",)
    assert result.num_turns == 3 and result.cost_usd == 0.05

    # Pushed to the real origin.
    branches = _git_out("branch", cwd=origin)
    assert "engineering/add-file" in branches

    # No pollution of the target repository, and no leaked worktree.
    assert not (work / "data").exists(), "worktree was created inside the repo"
    listed = _git_out("worktree", "list", cwd=work)
    assert "sfc-tree-" not in listed, "worktree left registered"
    assert list((elsewhere / "data/worktrees").glob("sfc-tree-*")) == []


async def test_an_agent_that_writes_nothing_pushes_nothing(target_repo, tmp_path, monkeypatch):
    from solo_founder_crew.adapters.implementer import ClaudeCodeImplementer

    origin, work = target_repo
    monkeypatch.chdir(tmp_path)
    impl = ClaudeCodeImplementer(
        repo_path=work,
        worktree_root=Path("./wt"),
        claude_bin=_stub_claude(tmp_path, body="true"),
        timeout_seconds=60,
    )
    result = await impl.implement("Do nothing", branch="engineering/noop")

    assert result.is_empty and not result.pushed and not result.ok
    branches = _git_out("branch", cwd=origin)
    assert "engineering/noop" not in branches


# ─── ClaudeCodeImplementer: model / effort tiering ──────────────────────────
# `claude -p` with no --model runs whatever the founder's interactive CLI
# defaults to, and _child_env strips ANTHROPIC_MODEL — so the flag is the only
# way the venture's spend decision reaches the agent. These pin that it does.


async def test_the_tier_is_passed_on_the_command_line(target_repo, tmp_path, monkeypatch):
    from solo_founder_crew.adapters.implementer import ClaudeCodeImplementer

    _origin, work = target_repo
    monkeypatch.chdir(tmp_path)
    impl = ClaudeCodeImplementer(
        repo_path=work,
        worktree_root=Path("./wt"),
        claude_bin=_stub_claude(tmp_path, body="echo hi > added.txt"),
        timeout_seconds=60,
        model="opus",
        effort="max",
    )
    await impl.implement("Add a file", branch="engineering/tiered")

    argv = _argv(tmp_path)
    assert _flag(argv, "--model") == "opus"
    assert _flag(argv, "--effort") == "max"
    # The safety-relevant flags must survive alongside the new ones.
    assert _flag(argv, "--permission-mode") == "bypassPermissions"
    assert _flag(argv, "--output-format") == "json"


async def test_a_ci_fix_runs_on_its_own_cheaper_tier(target_repo, tmp_path, monkeypatch):
    """`/fix` is a named failure with a known smallest change — the founder can
    ask for it repeatedly, so it must not cost what an open-ended run does."""
    from solo_founder_crew.adapters.implementer import ClaudeCodeImplementer

    _origin, work = target_repo
    monkeypatch.chdir(tmp_path)
    impl = ClaudeCodeImplementer(
        repo_path=work,
        worktree_root=Path("./wt"),
        claude_bin=_stub_claude(tmp_path, body="echo fixed > added.txt"),
        timeout_seconds=60,
        model="opus",
        effort="max",
        fix_model="haiku",
        fix_effort="low",
    )
    await impl.implement("CI is red", branch="main", existing=True)

    argv = _argv(tmp_path)
    assert _flag(argv, "--model") == "haiku"
    assert _flag(argv, "--effort") == "low"


def test_default_tier_is_not_the_top_model() -> None:
    """A default that silently inherits the operator's interactive model is the
    bug this closes; pin the defaults so it cannot regress unnoticed."""
    from solo_founder_crew.adapters.implementer import ClaudeCodeImplementer

    impl = ClaudeCodeImplementer(repo_path=Path("."), worktree_root=Path("."))

    assert (impl.model, impl.effort) == ("sonnet", "high")
    assert (impl.fix_model, impl.fix_effort) == ("sonnet", "medium")
