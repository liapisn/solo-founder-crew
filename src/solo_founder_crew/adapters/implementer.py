"""Implementer adapters — turning an approved proposal into a real diff.

The engineering role's decision rights already permit ``open_pull_request``
outright (``roles_library.make_engineering``): branching and opening a PR is
safe because it does not touch ``main``. Until now the tooling under-delivered
that right — ``GitHubPRTool`` committed the proposal text as a markdown file,
so the "change" the founder reviewed was a design note, not code.

This module closes that gap. An ``Implementer`` takes the *approved* proposal
and produces an actual branch with an actual diff. The merge gate is untouched:
the agent gains the ability to write anything and still cannot ship anything.

Design notes worth citing in Ch.3 §3.5 / §3.7 and Ch.4:

- **Protocol-driven.** ``Implementer`` is a Protocol with a real adapter
  (``ClaudeCodeImplementer``) and an in-memory double (``FakeImplementer``) —
  the same recipe as ``HITLContract``, ``LLMClient`` and ``GitHubAPI``. That is
  a fourth independently-substitutable service on one architectural pattern.
- **Decision rights enforced against the artefact, not the prompt.**
  ``detect_escalations`` inspects the files the agent actually changed. A touch
  to a dependency manifest or a migration raises the role's
  ``dependency_change`` / ``schema_or_data_migration`` escalations, so the
  model is checked against output rather than trusted to the system prompt.
- **No push capability in-process.** The coding agent is spawned without any
  credential that could push or merge (see ``_child_env``); the adapter pushes
  afterwards, outside the agent. The most consequential thing the agent itself
  can do is write files into a disposable worktree.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Protocol

# ─── Result ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ImplementResult:
    """What one implementation attempt produced.

    The telemetry fields are not incidental: cost, turn count and wall-clock
    per run are the per-flow measurements Ch.4's evaluation reports, captured
    as a by-product of doing the work rather than as a separate exercise.
    """

    branch: str
    files_changed: tuple[str, ...] = ()
    diffstat: str = ""
    escalations: tuple[str, ...] = ()
    pushed: bool = False

    # Telemetry (real adapter only; the fake leaves these at their defaults).
    session_id: str = ""
    num_turns: int = 0
    duration_ms: int = 0
    cost_usd: float = 0.0

    error: str = ""

    @property
    def is_empty(self) -> bool:
        """The agent ran but changed nothing — never open a PR for this."""
        return not self.files_changed

    @property
    def ok(self) -> bool:
        return not self.error and not self.is_empty


class Implementer(Protocol):
    """Turns an approved proposal into a pushed branch."""

    async def implement(self, proposal: str, *, branch: str) -> ImplementResult: ...


# ─── Escalation detection ───────────────────────────────────────────────────

DEPENDENCY_CHANGE = "dependency_change"
SCHEMA_OR_DATA_MIGRATION = "schema_or_data_migration"

# Basenames that mean "the dependency set moved".
_DEPENDENCY_FILES = frozenset(
    {
        "pyproject.toml",
        "poetry.lock",
        "uv.lock",
        "Pipfile",
        "Pipfile.lock",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
    }
)

# Path fragments that mean "the schema or stored data moved".
_MIGRATION_DIRS = ("migrations/", "migration/")


def _is_dependency_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    if name in _DEPENDENCY_FILES:
        return True
    # requirements.txt, requirements-dev.txt, requirements-vercel.txt, …
    return name.startswith("requirements") and name.endswith(".txt")


def _is_migration_file(path: str) -> bool:
    lowered = path.lower()
    if any(fragment in lowered for fragment in _MIGRATION_DIRS):
        return True
    return lowered.endswith(".sql")


def detect_escalations(files: Iterable[str]) -> tuple[str, ...]:
    """Which of the engineering role's ``must_escalate`` actions this diff hits.

    Returned in the role's own declaration order so the founder always sees the
    same sequence. An empty tuple means the change sits entirely inside what
    the role may do alone.
    """
    found: list[str] = []
    paths = list(files)
    if any(_is_dependency_file(p) for p in paths):
        found.append(DEPENDENCY_CHANGE)
    if any(_is_migration_file(p) for p in paths):
        found.append(SCHEMA_OR_DATA_MIGRATION)
    return tuple(found)


# ─── Fake (tests, CI, offline) ──────────────────────────────────────────────


@dataclass
class FakeImplementer:
    """Deterministic ``Implementer`` — no agent, no network, no git.

    Used by the suite and by any dry run: CI must never spawn a coding agent.
    Set ``files`` to whatever diff you want to simulate; escalations are still
    derived through the real ``detect_escalations``, so the policy under test
    is the production one.
    """

    files: tuple[str, ...] = ("README.md",)
    diffstat: str = " 1 file changed, 1 insertion(+)"
    error: str = ""
    num_turns: int = 0
    duration_ms: int = 0
    cost_usd: float = 0.0
    calls: list[dict[str, str]] = field(default_factory=list)

    async def implement(self, proposal: str, *, branch: str) -> ImplementResult:
        self.calls.append({"proposal": proposal, "branch": branch})
        if self.error:
            return ImplementResult(branch=branch, error=self.error)
        return ImplementResult(
            branch=branch,
            files_changed=self.files,
            diffstat=self.diffstat,
            escalations=detect_escalations(self.files),
            pushed=bool(self.files),
            num_turns=self.num_turns,
            duration_ms=self.duration_ms,
            cost_usd=self.cost_usd,
        )


# ─── Real adapter ───────────────────────────────────────────────────────────

# Environment handed to the coding agent. An allowlist, not a denylist: the
# daemon process has the venture's secrets loaded from .env (Discord bot token,
# Resend key, Anthropic key), and a child process must not inherit them simply
# because nobody thought to strip them.
_ENV_ALLOWLIST = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "LANG",
    "LC_ALL",
    "TERM",
    "TMPDIR",
    "ANTHROPIC_API_KEY",  # the agent's own model credential — not a capability
)


@dataclass
class ClaudeCodeImplementer:
    """Runs headless Claude Code in a throwaway git worktree.

    ``repo_path`` is a checkout of the target repository (it supplies
    ``origin``); the worktree is created under ``worktree_root`` from
    ``origin/<base_branch>``, so the founder's working tree is never touched
    and cannot collide with an in-flight run.

    The worktree also carries no gitignored files, which is why the agent never
    sees ``api/.env`` — the Apple certificate password, the Resend key and
    ``DATABASE_URL`` are simply not on disk in there.

    **Residual risk, stated rather than hidden.** The agent runs with full bash
    (``--permission-mode bypassPermissions``) and a real ``HOME``, so it can
    read the user's home directory and reach the network. What it cannot do is
    push or merge: no GitHub credential is in its environment, ``gh`` is
    pointed at an empty config directory, and git's global/system config is
    blanked so no credential helper is available. Every result therefore lands
    as a reviewable diff before anything merges.
    """

    repo_path: Path
    worktree_root: Path
    base_branch: str = "main"
    timeout_seconds: float = 900.0
    claude_bin: str = "claude"

    # ── plumbing ────────────────────────────────────────────────────────

    def _git(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd or self.repo_path),
            capture_output=True,
            text=True,
            check=False,
        )

    def _git_ok(self, *args: str, cwd: Path | None = None) -> str:
        result = self._git(*args, cwd=cwd)
        if result.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(args)} failed ({result.returncode}): "
                f"{result.stderr.strip()[:300]}"
            )
        return result.stdout

    @staticmethod
    def _child_env(sandbox: Path) -> dict[str, str]:
        """Minimal environment for the agent — no repository credentials."""
        env = {k: v for k, v in os.environ.items() if k in _ENV_ALLOWLIST}
        # Blank git config so no credential helper is reachable, and point the
        # GitHub CLI at an empty config dir so a stored gh login is invisible.
        blank = sandbox / "gitconfig"
        blank.touch()
        gh_dir = sandbox / "gh"
        gh_dir.mkdir(exist_ok=True)
        env["GIT_CONFIG_GLOBAL"] = str(blank)
        env["GIT_CONFIG_SYSTEM"] = str(blank)
        env["GH_CONFIG_DIR"] = str(gh_dir)
        env["GIT_TERMINAL_PROMPT"] = "0"
        return env

    @staticmethod
    def _prompt(proposal: str) -> str:
        return (
            "You are the engineering role of a solo founder's AI crew. The "
            "founder has already reviewed and APPROVED the proposal below. "
            "Implement it in this repository.\n\n"
            "Rules:\n"
            "- Make the smallest change that fully implements the proposal.\n"
            "- Match the surrounding code's style, naming and comment density.\n"
            "- Run the project's tests and linter, and leave them passing.\n"
            "- Do NOT commit, push, or create branches — the harness does that.\n"
            "- If the change requires a new dependency or a database migration, "
            "make it anyway but say so clearly in your final message: those "
            "require separate founder approval.\n\n"
            "APPROVED PROPOSAL\n"
            "-----------------\n"
            f"{proposal.strip()}\n"
        )

    # ── the port ────────────────────────────────────────────────────────

    async def implement(self, proposal: str, *, branch: str) -> ImplementResult:
        self.worktree_root.mkdir(parents=True, exist_ok=True)
        sandbox = Path(tempfile.mkdtemp(prefix="sfc-sandbox-", dir=str(self.worktree_root)))
        tree = Path(tempfile.mkdtemp(prefix="sfc-tree-", dir=str(self.worktree_root)))
        # mkdtemp created it; git worktree add wants to create it itself.
        tree.rmdir()

        try:
            self._git_ok("fetch", "origin", self.base_branch)
            self._git_ok(
                "worktree", "add", "-b", branch, str(tree), f"origin/{self.base_branch}"
            )
            return await self._run_in(tree, sandbox, proposal, branch)
        except Exception as exc:  # surface, never crash the daemon
            return ImplementResult(branch=branch, error=f"{type(exc).__name__}: {exc}")
        finally:
            self._cleanup(tree, sandbox, branch)

    async def _run_in(
        self, tree: Path, sandbox: Path, proposal: str, branch: str
    ) -> ImplementResult:
        proc = await asyncio.create_subprocess_exec(
            self.claude_bin,
            "-p",
            self._prompt(proposal),
            "--permission-mode",
            "bypassPermissions",
            "--output-format",
            "json",
            cwd=str(tree),
            env=self._child_env(sandbox),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ImplementResult(
                branch=branch,
                error=f"Coding agent exceeded {self.timeout_seconds:.0f}s and was stopped.",
            )

        telemetry = _parse_result_json(stdout.decode("utf-8", "replace"))
        if proc.returncode != 0 or telemetry.get("is_error"):
            detail = telemetry.get("result") or stderr.decode("utf-8", "replace")[:300]
            return ImplementResult(
                branch=branch,
                error=f"Coding agent failed: {detail or 'no output'}",
                **_telemetry_fields(telemetry),
            )

        files = tuple(
            line[3:].strip()
            for line in self._git_ok("status", "--porcelain", cwd=tree).splitlines()
            if line.strip()
        )
        if not files:
            return ImplementResult(branch=branch, **_telemetry_fields(telemetry))

        self._git_ok("add", "-A", cwd=tree)
        self._git_ok(
            "-c",
            "user.name=solo-founder-crew",
            "-c",
            "user.email=crew@localhost",
            "commit",
            "-m",
            _commit_message(proposal),
            cwd=tree,
        )
        diffstat = self._git_ok("diff", "--stat", "HEAD~1", "HEAD", cwd=tree).strip()
        # Push from the adapter, in the normal environment — the agent never
        # held a credential that could do this.
        self._git_ok("push", "-u", "origin", branch, cwd=tree)

        return ImplementResult(
            branch=branch,
            files_changed=files,
            diffstat=diffstat,
            escalations=detect_escalations(files),
            pushed=True,
            **_telemetry_fields(telemetry),
        )

    def _cleanup(self, tree: Path, sandbox: Path, branch: str) -> None:
        if tree.exists():
            self._git("worktree", "remove", "--force", str(tree))
        self._git("worktree", "prune")
        # The branch lives on the remote now; the local ref is disposable.
        self._git("branch", "-D", branch)
        shutil.rmtree(sandbox, ignore_errors=True)


# ─── helpers ────────────────────────────────────────────────────────────────


def _parse_result_json(stdout: str) -> dict:
    """`claude -p --output-format json` prints one JSON object. Be forgiving:
    a crashed agent may print nothing, or noise before the object."""
    stripped = stdout.strip()
    if not stripped:
        return {}
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        for line in reversed(stripped.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
    return {}


def _telemetry_fields(t: dict) -> dict:
    return {
        "session_id": str(t.get("session_id", "")),
        "num_turns": int(t.get("num_turns", 0) or 0),
        "duration_ms": int(t.get("duration_ms", 0) or 0),
        "cost_usd": float(t.get("total_cost_usd", 0.0) or 0.0),
    }


def _commit_message(proposal: str) -> str:
    for line in proposal.splitlines():
        s = line.strip().lstrip("#").strip()
        if s:
            return s[:72].rstrip()
    return "Implement approved engineering proposal"
