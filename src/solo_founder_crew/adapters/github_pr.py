"""GitHub PR adapter — M2 Phase 2 `pr_tool` for the engineering role.

The engineering role's Author Flow produces a proposal artefact (a
short design note: what to build, where, with what trade-offs). On
founder approval, this adapter turns that artefact into a **draft
pull request** on a configured GitHub repository:

1. Read the current SHA of the target ``base_branch``.
2. Create a branch ``engineering/proposal-<slug>`` from that SHA.
3. Commit a new file ``docs/proposals/<slug>.md`` containing the
   artefact text (so the proposal is reviewable as a diff, not only
   as a PR body).
4. Open a **draft** PR from the new branch to ``base_branch``, with
   the artefact text as the PR body.

The PR is opened as a draft on purpose: drafts are not
auto-mergeable, so this adapter cannot ship code. The founder
promotes the draft to ready-for-review on GitHub (where the full diff
and review tooling live) and merges from there. CI runs unattended
and — via the existing ``.github/workflows/pr-review-notify.yml`` —
posts a Discord notification when it passes. Together those two
pieces deliver the Dev Flow's "notify-only" merge gate described in
``docs/dev-flow.md``.

Design notes worth citing in Ch.3 §3.5 / §3.7 prose:

- **Protocol-driven**: the adapter depends on a ``GitHubAPI`` Protocol,
  not on ``httpx`` directly. ``RealGitHubAPI`` is the production
  implementation (lazy-imports ``httpx``, uses ``GITHUB_TOKEN``);
  ``FakeGitHubAPI`` is the in-memory test double. This is the same
  Protocol-with-fake pattern used for ``HITLContract`` and
  ``LLMClient`` — three independently-substitutable services on the
  same architectural recipe.
- **Constructor-time validation**: missing token, empty repo string,
  or invalid base-branch surface as ``RuntimeError`` when the tool is
  built, not on first call. (Same pattern as ``AnthropicLLM``.)
- **No merge capability**: by construction the tool cannot give an
  agent merge rights. The most consequential action the adapter can
  take is to *propose* a change; the act of shipping remains the
  founder's. This is the framework's decision-rights model rendered
  to the GitHub surface.
"""
from __future__ import annotations

import base64
import os
import re
import secrets
from dataclasses import dataclass, field
from typing import Any, Protocol


# ─── GitHubAPI Protocol + implementations ────────────────────────────────────


class GitHubAPI(Protocol):
    """The narrow surface ``GitHubPRTool`` needs from a GitHub client.

    Four operations: read a branch's commit SHA, create a new branch
    from a SHA, commit a file to a branch, open a draft PR. Anything
    richer would couple the tool to a specific client library.
    """

    def get_branch_sha(self, repo: str, branch: str) -> str: ...
    def create_branch(self, repo: str, name: str, from_sha: str) -> None: ...
    def commit_file(
        self,
        repo: str,
        branch: str,
        path: str,
        content: str,
        message: str,
    ) -> str: ...
    def open_pull_request(
        self,
        repo: str,
        *,
        head: str,
        base: str,
        title: str,
        body: str,
        draft: bool,
    ) -> str: ...


@dataclass
class RealGitHubAPI:
    """Production ``GitHubAPI`` backed by GitHub's REST v3 API.

    Lazy-imports ``httpx`` (already pulled in transitively by
    ``langchain-anthropic``) so the package stays importable on
    systems without HTTP libraries. Validates ``GITHUB_TOKEN`` at
    construction; the token needs ``repo`` scope (or the fine-grained
    equivalent: read/write on Contents + Pull requests for the target
    repo).
    """

    timeout_seconds: float = 30.0
    _token: str = field(init=False)
    _base_url: str = field(default="https://api.github.com", init=False)

    def __post_init__(self) -> None:
        try:
            import httpx  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "RealGitHubAPI requires `httpx`. Install it or use "
                "FakeGitHubAPI in tests."
            ) from e
        token = os.getenv("GITHUB_TOKEN", "")
        if not token:
            raise RuntimeError(
                "RealGitHubAPI requires GITHUB_TOKEN to be set "
                "(in the environment or loaded from .env via load_dotenv())."
            )
        self._token = token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        import httpx

        url = f"{self._base_url}{path}"
        with httpx.Client(timeout=self.timeout_seconds) as client:
            resp = client.request(method, url, headers=self._headers(), **kwargs)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"GitHub API {method} {path} failed "
                f"({resp.status_code}): {resp.text[:300]}"
            )
        return resp.json() if resp.content else None

    def get_branch_sha(self, repo: str, branch: str) -> str:
        data = self._request("GET", f"/repos/{repo}/git/ref/heads/{branch}")
        return data["object"]["sha"]

    def create_branch(self, repo: str, name: str, from_sha: str) -> None:
        self._request(
            "POST",
            f"/repos/{repo}/git/refs",
            json={"ref": f"refs/heads/{name}", "sha": from_sha},
        )

    def commit_file(
        self,
        repo: str,
        branch: str,
        path: str,
        content: str,
        message: str,
    ) -> str:
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        data = self._request(
            "PUT",
            f"/repos/{repo}/contents/{path}",
            json={"message": message, "content": encoded, "branch": branch},
        )
        return data["commit"]["sha"]

    def open_pull_request(
        self,
        repo: str,
        *,
        head: str,
        base: str,
        title: str,
        body: str,
        draft: bool,
    ) -> str:
        data = self._request(
            "POST",
            f"/repos/{repo}/pulls",
            json={
                "title": title,
                "head": head,
                "base": base,
                "body": body,
                "draft": draft,
            },
        )
        return data["html_url"]


@dataclass
class FakeGitHubAPI:
    """In-memory ``GitHubAPI`` for tests and dry-runs.

    Records every operation it would have performed so tests can
    assert on the call sequence. ``base_sha`` is whatever string you
    want returned from ``get_branch_sha``; ``next_pr_number`` controls
    the URL ``open_pull_request`` synthesises.
    """

    base_sha: str = "deadbeef" * 5
    next_pr_number: int = 1
    branches: dict[str, str] = field(default_factory=dict)
    commits: list[dict[str, Any]] = field(default_factory=list)
    pull_requests: list[dict[str, Any]] = field(default_factory=list)

    def get_branch_sha(self, repo: str, branch: str) -> str:
        return self.base_sha

    def create_branch(self, repo: str, name: str, from_sha: str) -> None:
        self.branches[name] = from_sha

    def commit_file(
        self,
        repo: str,
        branch: str,
        path: str,
        content: str,
        message: str,
    ) -> str:
        sha = f"commit-{len(self.commits) + 1}"
        self.commits.append(
            {
                "repo": repo,
                "branch": branch,
                "path": path,
                "content": content,
                "message": message,
                "sha": sha,
            }
        )
        return sha

    def open_pull_request(
        self,
        repo: str,
        *,
        head: str,
        base: str,
        title: str,
        body: str,
        draft: bool,
    ) -> str:
        pr = {
            "repo": repo,
            "head": head,
            "base": base,
            "title": title,
            "body": body,
            "draft": draft,
            "number": self.next_pr_number,
        }
        self.pull_requests.append(pr)
        url = f"https://github.com/{repo}/pull/{self.next_pr_number}"
        self.next_pr_number += 1
        return url


# ─── Slug + title derivation ────────────────────────────────────────────────


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str, *, max_len: int = 48) -> str:
    """Reduce arbitrary text to a stable, URL-safe slug.

    Used to derive both the branch name and the proposal filename from
    the artefact's first line. Deterministic for a given input so
    re-running the tool against an identical proposal would produce a
    branch collision (which is good — surfaces duplicate work).
    """
    lowered = text.lower().strip()
    slug = _SLUG_RE.sub("-", lowered).strip("-")
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or "proposal"


def _derive_title(artifact: str, *, max_len: int = 72) -> str:
    """Take the first non-empty line of the artefact as the PR title."""
    for line in artifact.splitlines():
        s = line.strip().lstrip("#").strip()
        if s:
            return s[:max_len].rstrip()
    return "Engineering proposal"


# ─── The tool itself ────────────────────────────────────────────────────────


@dataclass
class GitHubPRTool:
    """Async callable suitable for ``ToolRegistry.register("pr_tool", …)``.

    Construction args:

    - ``repo`` (e.g. ``"liapisn/passly"``) — target repository.
    - ``base_branch`` (default ``"main"``) — what the PR targets.
    - ``api`` — a ``GitHubAPI`` implementation; defaults to
      ``RealGitHubAPI()`` if not provided (which validates
      ``GITHUB_TOKEN`` at construction).
    - ``branch_prefix`` — prefix for the generated head-branch name.
    - ``proposal_dir`` — repo-relative directory the proposal markdown
      file is committed under.

    Calling the tool with ``await tool(artifact)`` returns the URL of
    the opened draft PR. The artefact's first line becomes the PR
    title; the full artefact becomes the PR body **and** is committed
    as ``<proposal_dir>/<slug>.md``.
    """

    repo: str
    base_branch: str = "main"
    api: GitHubAPI | None = None
    branch_prefix: str = "engineering/proposal-"
    proposal_dir: str = "docs/proposals"

    def __post_init__(self) -> None:
        if not self.repo or "/" not in self.repo:
            raise RuntimeError(
                f"GitHubPRTool requires repo in 'owner/name' form; got {self.repo!r}"
            )
        if self.api is None:
            self.api = RealGitHubAPI()

    async def __call__(self, artifact: str) -> str:
        title = _derive_title(artifact)
        slug = _slugify(title)
        branch = f"{self.branch_prefix}{slug}"
        path = f"{self.proposal_dir}/{slug}.md"

        api = self.api
        assert api is not None  # set in __post_init__
        base_sha = api.get_branch_sha(self.repo, self.base_branch)
        api.create_branch(self.repo, branch, base_sha)
        api.commit_file(
            self.repo,
            branch,
            path,
            artifact if artifact.endswith("\n") else artifact + "\n",
            f"Add engineering proposal: {title}",
        )
        url = api.open_pull_request(
            self.repo,
            head=branch,
            base=self.base_branch,
            title=title,
            body=artifact,
            draft=True,
        )
        return url


def make_github_pr_tool(
    *,
    repo: str | None = None,
    base_branch: str | None = None,
    api: GitHubAPI | None = None,
):
    """Factory mirroring ``make_discord_publisher`` in ``app.py``.

    Reads ``SFC_PR_REPO`` and ``SFC_PR_BASE_BRANCH`` from the
    environment when the corresponding argument is not passed. Returns
    a configured ``GitHubPRTool``.
    """
    resolved_repo = repo or os.getenv("SFC_PR_REPO", "")
    if not resolved_repo:
        raise RuntimeError(
            "make_github_pr_tool requires repo (positional or SFC_PR_REPO env var). "
            "Example: 'liapisn/passly'."
        )
    resolved_base = base_branch or os.getenv("SFC_PR_BASE_BRANCH", "main")
    return GitHubPRTool(repo=resolved_repo, base_branch=resolved_base, api=api)


# ─── M2 Phase 3: a PR containing a real diff ────────────────────────────────


@dataclass
class ImplementedPRTool:
    """``pr_tool`` that ships code rather than a proposal document.

    Composes an ``Implementer`` (which turns the approved proposal into a
    pushed branch) with the same ``GitHubAPI`` the proposal tool uses. Only
    ``open_pull_request`` is needed here — ``git push`` already created the
    branch and its commit, so ``create_branch`` and ``commit_file`` fall away.

    Three outcomes, and only one of them opens a pull request:

    - **Escalation required** — the diff touched a dependency manifest or a
      migration, both in the engineering role's ``must_escalate`` list. No PR;
      the founder is told what needs separate approval. The branch is still
      pushed, so the work is not lost and stays reviewable.
    - **Nothing changed** — the agent ran and produced no diff. No PR.
    - **Clean change** — a draft PR from the pushed branch.

    Draft, always: a draft PR cannot be auto-merged, so this tool still cannot
    ship. ``merge_to_main`` remains the founder's, exactly as before.
    """

    implementer: Any  # Implementer Protocol (structural; avoids a hard import)
    repo: str
    base_branch: str = "main"
    api: GitHubAPI | None = None
    branch_prefix: str = "engineering/"
    sink: Any = None  # CrewEventSink — activity log; None disables reporting

    def __post_init__(self) -> None:
        if "/" not in self.repo.strip("/"):
            raise RuntimeError(f"repo must look like 'owner/name' (got {self.repo!r}).")
        if self.api is None:
            self.api = RealGitHubAPI()

    def _branch_for(self, title: str) -> str:
        """Unique per run. Unlike the proposal tool — where a deterministic
        name usefully collides to surface duplicate work — an implementation
        run must never reuse a branch, or a retry after a failure would abort
        at ``git worktree add``."""
        return f"{self.branch_prefix}{_slugify(title)}-{secrets.token_hex(3)}"

    async def _report(self, kind: str, summary: str, detail: str = "") -> None:
        """Best-effort activity log. A failure here must not affect the run."""
        if self.sink is None:
            return
        from solo_founder_crew.events import CrewEvent

        await self.sink.emit(
            CrewEvent(kind=kind, role="engineering", summary=summary, detail=detail)
        )

    async def __call__(self, artifact: str) -> str:
        from solo_founder_crew.events import (
            ERROR,
            ESCALATION,
            IMPLEMENTED,
            IMPLEMENTING,
            PR_OPENED,
        )

        title = _derive_title(artifact)
        branch = self._branch_for(title)
        await self._report(
            IMPLEMENTING,
            f"implementing *{title}*",
            f"branch `{branch}` — a coding agent is working in a worktree.",
        )
        result = await self.implementer.implement(artifact, branch=branch)

        if result.error:
            await self._report(
                ERROR, "implementation failed", f"```\n{result.error}\n```"
            )
            return f"Implementation failed: {result.error}"
        if result.is_empty:
            await self._report(
                IMPLEMENTED, "the agent changed nothing — no pull request opened"
            )
            return (
                "The engineering agent ran but changed nothing, so no pull "
                "request was opened. The proposal may already be implemented, "
                "or it may need to be more specific."
            )
        await self._report(
            IMPLEMENTED,
            f"{len(result.files_changed)} file(s) changed",
            f"```\n{result.diffstat.strip()}\n```\n"
            f"{result.num_turns} turns · {result.duration_ms / 1000:.0f}s · "
            f"${result.cost_usd:.4f}",
        )
        if result.escalations:
            actions = ", ".join(result.escalations)
            files = ", ".join(result.files_changed[:10])
            await self._report(
                ESCALATION,
                f"needs your approval: **{actions}**",
                f"Pushed to `{result.branch}` — no PR opened until you say so.",
            )
            return (
                f"Escalation required ({actions}) before this can become a pull "
                f"request. The work is pushed to `{result.branch}` for review. "
                f"Files: {files}"
            )

        api = self.api
        assert api is not None  # set in __post_init__
        url = api.open_pull_request(
            self.repo,
            head=result.branch,
            base=self.base_branch,
            title=title,
            body=_pr_body(artifact, result),
            draft=True,
        )
        await self._report(PR_OPENED, f"opened a draft PR — {title}", url)
        return url


def _pr_body(artifact: str, result: Any) -> str:
    """The approved proposal, plus what the run actually cost.

    The telemetry block is deliberate: it makes each PR carry its own
    case-study record (turns, wall-clock, spend) rather than requiring a
    separate log to reconstruct what the crew did.
    """
    return "\n".join(
        [
            artifact.strip(),
            "",
            "---",
            "",
            "### Implementation",
            "",
            "```",
            result.diffstat.strip() or "(no diffstat)",
            "```",
            "",
            f"Agent run: {result.num_turns} turns · "
            f"{result.duration_ms / 1000:.0f}s · ${result.cost_usd:.4f}",
            "",
            "_Drafted and implemented by the solo-founder-crew engineering role. "
            "Opened as a draft: merging remains the founder's decision._",
        ]
    )


def make_implemented_pr_tool(
    *,
    implementer: Any,
    repo: str | None = None,
    base_branch: str | None = None,
    api: GitHubAPI | None = None,
    sink: Any = None,
) -> ImplementedPRTool:
    """Factory mirroring ``make_github_pr_tool``, reading the same env vars."""
    resolved_repo = repo or os.getenv("SFC_PR_REPO", "")
    if not resolved_repo:
        raise RuntimeError(
            "make_implemented_pr_tool requires repo (argument or SFC_PR_REPO). "
            "Example: 'liapisn/passly'."
        )
    return ImplementedPRTool(
        implementer=implementer,
        repo=resolved_repo,
        base_branch=base_branch or os.getenv("SFC_PR_BASE_BRANCH", "main"),
        api=api,
        sink=sink,
    )
