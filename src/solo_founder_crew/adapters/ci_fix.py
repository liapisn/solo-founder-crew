"""CI fix flow — sending the engineering role back at its own red pull request.

Until now the Dev Flow ended at the push: ``ImplementedPRTool`` opened a draft
PR and the run terminated. Nothing in the crew observed what CI then said, and
``pr-review-notify.yml`` only spoke when CI passed — so a red build was
*silent*, indistinguishable from a build still running. The agent could not
learn it had shipped something broken, and neither could the founder.

This module closes the loop, deliberately without closing it automatically:

1. The workflow now notifies on red too, naming the jobs that failed.
2. The founder types ``/fix <pr>``.
3. ``CIFixFlow`` reads the failing jobs and their logs from the Actions API,
   hands them to the same ``Implementer`` that wrote the code, and pushes the
   result onto the *same* branch — so the existing pull request updates in
   place and CI re-runs against it.

Design notes worth citing in Ch.3 §3.7 (HITL contract) and Ch.4:

- **The retry bound is the founder.** No polling loop, no automatic
  re-iteration, no ``max_attempts`` counter to tune. Each attempt costs one
  human decision, which is the cheapest available guard against an agent
  burning spend in a loop against a failure it cannot fix — a flaky network
  fetch, say, or a problem that was already on ``main``.
- **Same decision rights, same gate.** The fix runs through the same
  ``Implementer``, so ``detect_escalations`` still inspects what it actually
  changed, and the pull request stays a draft. ``merge_to_main`` is untouched.
- **A narrow read-only Protocol.** ``ChecksAPI`` is three methods, separate
  from ``GitHubAPI`` rather than bolted onto it: the PR tool writes, this
  reads, and neither should carry the other's surface. Same
  Protocol-with-fake recipe as everywhere else in the package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from solo_founder_crew.adapters.github_pr import RealGitHubAPI

# ─── What the flow reads ────────────────────────────────────────────────────


@dataclass(frozen=True)
class PullRequestInfo:
    """The parts of a pull request this flow needs."""

    number: int
    title: str
    head_branch: str
    head_sha: str
    state: str = "open"  # "open" | "closed"
    draft: bool = True
    merged: bool = False
    url: str = ""

    @property
    def is_fixable(self) -> bool:
        """A closed or merged PR has no branch worth pushing to."""
        return self.state == "open" and not self.merged


@dataclass(frozen=True)
class CheckFailure:
    """One failed Actions job on the head commit."""

    name: str  # job name, e.g. "web · build"
    job_id: int
    workflow: str = "CI"
    failed_step: str = ""
    url: str = ""


class ChecksAPI(Protocol):
    """The read-only surface ``CIFixFlow`` needs from GitHub.

    Three operations: read a pull request, find the failed jobs on its head
    commit, read one job's log. Anything wider would let this flow write, and
    writing is the ``Implementer``'s job (and the founder's).
    """

    def get_pull_request(self, repo: str, number: int) -> PullRequestInfo: ...
    def failing_checks(self, repo: str, sha: str) -> tuple[CheckFailure, ...]: ...
    def job_log(self, repo: str, job_id: int) -> str: ...


# ─── Real implementation ────────────────────────────────────────────────────


@dataclass
class RealChecksAPI(RealGitHubAPI):
    """Production ``ChecksAPI``, reusing ``RealGitHubAPI``'s auth and client.

    Reads the Actions API rather than the combined check-runs endpoint: a
    check run's id and the Actions job id it renders are different namespaces,
    and only the job id can be turned into a log.
    """

    def get_pull_request(self, repo: str, number: int) -> PullRequestInfo:
        data = self._request("GET", f"/repos/{repo}/pulls/{number}")
        return PullRequestInfo(
            number=int(data["number"]),
            title=str(data.get("title", "")),
            head_branch=str(data["head"]["ref"]),
            head_sha=str(data["head"]["sha"]),
            state=str(data.get("state", "open")),
            draft=bool(data.get("draft", False)),
            merged=bool(data.get("merged", False)),
            url=str(data.get("html_url", "")),
        )

    def failing_checks(self, repo: str, sha: str) -> tuple[CheckFailure, ...]:
        runs = self._request(
            "GET", f"/repos/{repo}/actions/runs", params={"head_sha": sha}
        )
        failures: list[CheckFailure] = []
        for run in (runs or {}).get("workflow_runs", []):
            if run.get("conclusion") != "failure":
                continue
            jobs = self._request(
                "GET",
                f"/repos/{repo}/actions/runs/{run['id']}/jobs",
                params={"filter": "latest"},
            )
            for job in (jobs or {}).get("jobs", []):
                if job.get("conclusion") != "failure":
                    continue
                step = next(
                    (
                        s.get("name", "")
                        for s in job.get("steps", [])
                        if s.get("conclusion") == "failure"
                    ),
                    "",
                )
                failures.append(
                    CheckFailure(
                        name=str(job.get("name", "?")),
                        job_id=int(job["id"]),
                        workflow=str(run.get("name", "CI")),
                        failed_step=str(step),
                        url=str(job.get("html_url", "")),
                    )
                )
        return tuple(failures)

    def job_log(self, repo: str, job_id: int) -> str:
        """Plain text, not JSON: this endpoint 302s to a signed log URL."""
        import httpx

        url = f"{self._base_url}/repos/{repo}/actions/jobs/{job_id}/logs"
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            resp = client.get(url, headers=self._headers())
        if resp.status_code >= 400:
            return f"(could not read the log for job {job_id}: HTTP {resp.status_code})"
        return resp.text


@dataclass
class FakeChecksAPI:
    """In-memory ``ChecksAPI`` for tests and dry runs."""

    pull_requests: dict[int, PullRequestInfo] = field(default_factory=dict)
    failures: tuple[CheckFailure, ...] = ()
    logs: dict[int, str] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def get_pull_request(self, repo: str, number: int) -> PullRequestInfo:
        self.calls.append(f"get_pull_request:{number}")
        if number not in self.pull_requests:
            raise RuntimeError(f"GitHub API GET /repos/{repo}/pulls/{number} failed (404)")
        return self.pull_requests[number]

    def failing_checks(self, repo: str, sha: str) -> tuple[CheckFailure, ...]:
        self.calls.append(f"failing_checks:{sha}")
        return self.failures

    def job_log(self, repo: str, job_id: int) -> str:
        self.calls.append(f"job_log:{job_id}")
        return self.logs.get(job_id, "")


# ─── The flow ───────────────────────────────────────────────────────────────


@dataclass
class CIFixFlow:
    """``await flow(22)`` — read PR #22's failing CI, fix it, push to its branch.

    Returns a line of prose for whoever asked (the Discord command replies with
    it); the detail goes to the activity log through ``sink``.

    ``branch_prefix`` is a guard, not a technicality: it keeps ``/fix`` pointed
    at branches the crew itself opened, so a mistyped number cannot hand a
    coding agent someone else's pull request. Set it to ``""`` to allow any
    branch.
    """

    implementer: Any  # Implementer Protocol (structural; avoids a hard import)
    repo: str
    api: ChecksAPI | None = None
    sink: Any = None  # CrewEventSink — activity log; None disables reporting
    branch_prefix: str = "engineering/"
    log_tail_chars: int = 6000  # per job — the tail is where the error is
    max_jobs: int = 3

    def __post_init__(self) -> None:
        if "/" not in self.repo.strip("/"):
            raise RuntimeError(f"repo must look like 'owner/name' (got {self.repo!r}).")
        if self.api is None:
            self.api = RealChecksAPI()

    async def _report(self, kind: str, summary: str, detail: str = "") -> None:
        """Best-effort activity log. A failure here must not affect the run."""
        if self.sink is None:
            return
        from solo_founder_crew.events import CrewEvent

        await self.sink.emit(
            CrewEvent(kind=kind, role="engineering", summary=summary, detail=detail)
        )

    async def __call__(self, pr_number: int) -> str:
        from solo_founder_crew.events import (
            ERROR,
            ESCALATION,
            IMPLEMENTED,
            IMPLEMENTING,
        )

        api = self.api
        assert api is not None  # set in __post_init__

        try:
            pr = api.get_pull_request(self.repo, pr_number)
        except Exception as exc:  # noqa: BLE001 — a bad number is a normal typo
            return f"Could not read PR #{pr_number}: {exc}"

        if not pr.is_fixable:
            state = "merged" if pr.merged else pr.state
            return (
                f"PR #{pr_number} is {state} — there is nothing to fix on a "
                f"branch that is no longer in play."
            )
        if self.branch_prefix and not pr.head_branch.startswith(self.branch_prefix):
            return (
                f"PR #{pr_number} is on `{pr.head_branch}`, which the crew did "
                f"not open (expected a `{self.branch_prefix}` branch). Refusing "
                f"to point a coding agent at it."
            )

        failures = api.failing_checks(self.repo, pr.head_sha)
        if not failures:
            return (
                f"No failed CI job on PR #{pr_number}'s head commit "
                f"(`{pr.head_sha[:7]}`). Either CI is green, or it has not "
                f"finished yet — nothing to fix."
            )

        report = self._build_report(pr, failures)
        names = ", ".join(f.name for f in failures[: self.max_jobs])
        await self._report(
            IMPLEMENTING,
            f"fixing red CI on PR #{pr.number}",
            f"Failed: {names}. Working on `{pr.head_branch}` in a worktree.",
        )

        result = await self.implementer.implement(
            report, branch=pr.head_branch, existing=True
        )

        if result.error:
            await self._report(ERROR, "CI fix failed", f"```\n{result.error}\n```")
            return f"The fix attempt on PR #{pr_number} failed: {result.error}"
        if result.is_empty:
            await self._report(
                IMPLEMENTED,
                f"no fix pushed for PR #{pr.number}",
                "The agent read the failure and changed nothing.",
            )
            return (
                f"The agent read PR #{pr_number}'s failing job and changed "
                f"nothing — it judged the failure not to be this branch's "
                f"doing (a flake, or something already broken on "
                f"`{pr.head_branch}`'s base). Worth reading the job yourself: "
                f"{failures[0].url or 'see the PR checks'}"
            )

        telemetry = (
            f"{result.num_turns} turns · {result.duration_ms / 1000:.0f}s · "
            f"${result.cost_usd:.4f}"
        )
        await self._report(
            IMPLEMENTED,
            f"pushed a fix to PR #{pr.number}",
            f"```\n{result.diffstat.strip()}\n```\n{telemetry}",
        )
        summary = (
            f"Pushed a fix to `{pr.head_branch}` — PR #{pr_number} updated and "
            f"CI is re-running. {len(result.files_changed)} file(s), {telemetry}."
        )
        if result.escalations:
            actions = ", ".join(result.escalations)
            await self._report(
                ESCALATION,
                f"the fix needs your approval: **{actions}**",
                f"Pushed to `{pr.head_branch}`; the PR is still a draft.",
            )
            summary += (
                f" ⚠ It needed **{actions}**, which is yours to approve — "
                f"review before you promote the draft."
            )
        return summary

    def _build_report(
        self, pr: PullRequestInfo, failures: tuple[CheckFailure, ...]
    ) -> str:
        """The failing-CI brief handed to the coding agent.

        Log *tails*, capped per job: the error is at the end, the middle is
        install noise, and a whole Actions log will not fit in a prompt.
        """
        api = self.api
        assert api is not None
        lines = [
            f"Pull request #{pr.number}: {pr.title}",
            f"Branch: {pr.head_branch} (head {pr.head_sha[:7]})",
            f"Failed jobs: {len(failures)}",
        ]
        shown = failures[: self.max_jobs]
        for f in shown:
            log = api.job_log(self.repo, f.job_id)
            tail = log[-self.log_tail_chars :] if log else "(no log available)"
            if log and len(log) > self.log_tail_chars:
                tail = "…(earlier output trimmed)…\n" + tail
            step = f" — failing step: {f.failed_step}" if f.failed_step else ""
            lines += [
                "",
                f"## {f.workflow} / {f.name}{step}",
                "```",
                tail.strip(),
                "```",
            ]
        if len(failures) > len(shown):
            lines.append(
                f"\n({len(failures) - len(shown)} further failed job(s) not "
                f"shown — fix these first.)"
            )
        return "\n".join(lines)


def make_ci_fix_flow(
    *,
    implementer: Any,
    repo: str | None = None,
    api: ChecksAPI | None = None,
    sink: Any = None,
) -> CIFixFlow:
    """Factory mirroring ``make_implemented_pr_tool``, reading the same env."""
    import os

    resolved_repo = repo or os.getenv("SFC_PR_REPO", "")
    if not resolved_repo:
        raise RuntimeError(
            "make_ci_fix_flow requires repo (argument or SFC_PR_REPO). "
            "Example: 'liapisn/passly'."
        )
    return CIFixFlow(implementer=implementer, repo=resolved_repo, api=api, sink=sink)
