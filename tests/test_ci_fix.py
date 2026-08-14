"""Tests for the CI fix flow — sending the crew back at its own red PR.

Everything here runs against `FakeChecksAPI` + `FakeImplementer`: no GitHub,
no coding agent, no git. Same split as `test_implementer.py` — the real
adapters are exercised live, the contract is pinned here.

Pins eight behaviours:

1. A red PR hands the failing job's log to the implementer, on that PR's own
   branch, as a continuation (`existing=True`) rather than a fresh branch.
2. Green (or still-running) CI does no work at all.
3. A closed or merged PR is refused.
4. A branch the crew did not open is refused — a mistyped number must not
   point a coding agent at someone else's work.
5. Log tails are capped per job, so a 40MB Actions log cannot blow the prompt.
6. An agent that changed nothing reports the flake case, not success.
7. A failed agent surfaces as an error, never a silent success.
8. Escalations detected in the fix still reach the founder.
"""
from __future__ import annotations

import pytest

from solo_founder_crew.adapters.ci_fix import (
    CheckFailure,
    CIFixFlow,
    FakeChecksAPI,
    PullRequestInfo,
)
from solo_founder_crew.adapters.implementer import FakeImplementer
from solo_founder_crew.events import ERROR, ESCALATION, RecordingEventSink

# ─── fixtures ───────────────────────────────────────────────────────────────

BRANCH = "engineering/task-update-pkpass-member-field-4ad38b"


def _pr(**overrides) -> PullRequestInfo:
    base = dict(
        number=22,
        title="Task: Update pkpass Member Field",
        head_branch=BRANCH,
        head_sha="a" * 40,
        state="open",
        draft=True,
        merged=False,
        url="https://github.com/liapisn/passly/pull/22",
    )
    base.update(overrides)
    return PullRequestInfo(**base)


def _api(*, failures=(), logs=None, pr=None) -> FakeChecksAPI:
    pr = pr or _pr()
    return FakeChecksAPI(
        pull_requests={pr.number: pr},
        failures=tuple(failures),
        logs=logs or {},
    )


FAILURE = CheckFailure(
    name="web · build",
    job_id=94710086321,
    workflow="CI",
    failed_step="Run npm run build",
    url="https://github.com/liapisn/passly/actions/runs/1/job/94710086321",
)


def _flow(api: FakeChecksAPI, implementer: FakeImplementer, **overrides) -> CIFixFlow:
    return CIFixFlow(
        implementer=implementer, repo="liapisn/passly", api=api, **overrides
    )


# ─── the happy path ─────────────────────────────────────────────────────────


async def test_red_ci_drives_the_implementer_on_the_prs_own_branch():
    api = _api(
        failures=[FAILURE],
        logs={FAILURE.job_id: "Module not found: '@vercel/turbopack-next/...'"},
    )
    impl = FakeImplementer(files=("web/app/layout.tsx",))

    summary = await _flow(api, impl)(22)

    assert len(impl.calls) == 1
    call = impl.calls[0]
    # The PR's branch, continued — not a new branch off main. This is the
    # whole point: the existing pull request has to update in place.
    assert call["branch"] == BRANCH
    assert call["existing"] == "True"
    # The agent is told what actually broke.
    assert "web · build" in call["proposal"]
    assert "Run npm run build" in call["proposal"]
    assert "Module not found" in call["proposal"]
    assert "#22" in summary and BRANCH in summary


# ─── the cases that must do nothing ─────────────────────────────────────────


async def test_no_failing_job_does_no_work():
    impl = FakeImplementer()
    summary = await _flow(_api(failures=[]), impl)(22)

    assert impl.calls == []
    assert "nothing to fix" in summary


@pytest.mark.parametrize(
    "overrides,expected",
    [
        ({"state": "closed"}, "closed"),
        ({"state": "closed", "merged": True}, "merged"),
    ],
)
async def test_closed_and_merged_prs_are_refused(overrides, expected):
    api = _api(failures=[FAILURE], pr=_pr(**overrides))
    impl = FakeImplementer()

    summary = await _flow(api, impl)(22)

    assert impl.calls == []
    assert expected in summary


async def test_a_branch_the_crew_did_not_open_is_refused():
    api = _api(failures=[FAILURE], pr=_pr(head_branch="feature/hand-written"))
    impl = FakeImplementer()

    summary = await _flow(api, impl)(22)

    assert impl.calls == []
    assert "did not open" in summary


async def test_unknown_pr_number_is_a_message_not_a_crash():
    impl = FakeImplementer()
    summary = await _flow(_api(failures=[FAILURE]), impl)(999)

    assert impl.calls == []
    assert "#999" in summary


# ─── prompt hygiene ─────────────────────────────────────────────────────────


async def test_job_logs_are_tail_capped():
    huge = "noise\n" * 50_000 + "THE ACTUAL ERROR"
    api = _api(failures=[FAILURE], logs={FAILURE.job_id: huge})
    impl = FakeImplementer()

    await _flow(api, impl, log_tail_chars=500)(22)

    proposal = impl.calls[0]["proposal"]
    assert "THE ACTUAL ERROR" in proposal  # the tail is what matters
    assert len(proposal) < 2000
    assert "trimmed" in proposal


# ─── outcomes ───────────────────────────────────────────────────────────────


async def test_an_agent_that_changed_nothing_reports_the_flake_case():
    api = _api(failures=[FAILURE])
    impl = FakeImplementer(files=())

    summary = await _flow(api, impl)(22)

    assert "changed\nnothing" in summary or "changed nothing" in summary
    assert "flake" in summary


async def test_a_failed_agent_surfaces_as_an_error():
    api = _api(failures=[FAILURE])
    impl = FakeImplementer(error="Coding agent exceeded 900s and was stopped.")
    sink = RecordingEventSink()

    summary = await _flow(api, impl, sink=sink)(22)

    assert "failed" in summary
    assert any(e.kind == ERROR for e in sink.events)


async def test_an_escalating_fix_still_reaches_the_founder():
    api = _api(failures=[FAILURE])
    # A font resolution failure is exactly the kind of thing an agent "fixes"
    # by reaching for a dependency — which is the founder's call, not its own.
    impl = FakeImplementer(files=("web/package.json", "web/app/layout.tsx"))
    sink = RecordingEventSink()

    summary = await _flow(api, impl, sink=sink)(22)

    assert "dependency_change" in summary
    assert any(e.kind == ESCALATION for e in sink.events)
