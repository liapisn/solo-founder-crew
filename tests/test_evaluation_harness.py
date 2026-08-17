"""Tests for the Chapter 5 evaluation harness.

The load-bearing test here is :func:`test_every_scenario_reaches_expected_status`.
A scenario whose scripted decisions disagree with ``MAX_REVISIONS`` either raises
mid-run or silently terminates on the wrong path — and if that is discovered
during the *live* scored runs it costs real calls and, worse, a run that has to
be discarded after the instrument was frozen. Catching it on the mock path is
free.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.decision_log import DecisionLog, render_brief_prose
from evaluation.run_condition_f import _box32_path, run_one
from evaluation.scenarios import BY_ID, MAX_REVISIONS, SCENARIOS, select
from solo_founder_crew import VentureBrief

BRIEF_PATH = Path(__file__).resolve().parents[1] / "scenarios" / "fixtures" / "passly_brief.json"


@pytest.fixture
def brief() -> VentureBrief:
    return VentureBrief.from_file(BRIEF_PATH)


def test_scenario_set_is_ten_with_unique_ids():
    assert len(SCENARIOS) == 10
    assert len({s.id for s in SCENARIOS}) == 10


def test_every_scenario_has_a_mock_response_per_llm_call():
    """One draft plus one per revision; a short queue raises QueueExhausted."""
    for s in SCENARIOS:
        expected_calls = 1 + s.revision_turns if s.expected_status != "exhausted" else s.revision_turns
        assert len(s.mock_responses) >= expected_calls, (
            f"{s.id}: {len(s.mock_responses)} mock responses for "
            f"~{expected_calls} LLM calls"
        )


def test_rejection_counts_stay_inside_the_revision_cap():
    """A scenario may exhaust the cap but must not overshoot it silently."""
    for s in SCENARIOS:
        if s.expected_status == "exhausted":
            assert s.revision_turns == MAX_REVISIONS + 1, (
                f"{s.id}: exhaustion needs {MAX_REVISIONS + 1} rejections with "
                f"MAX_REVISIONS={MAX_REVISIONS}, script has {s.revision_turns}"
            )
        else:
            assert s.revision_turns <= MAX_REVISIONS, f"{s.id} overshoots the cap"


def test_terminal_decision_is_last():
    for s in SCENARIOS:
        actions = [a for a, _ in s.decisions]
        assert actions[-1] in {"approve", "kill", "reject"}
        assert "approve" not in actions[:-1], f"{s.id}: approve before the last gate"


def test_reject_decisions_carry_feedback():
    """A rejection with no feedback makes A3 (feedback honouring) unscorable."""
    for s in SCENARIOS:
        for action, feedback in s.decisions:
            if action == "reject":
                assert feedback and feedback.strip(), f"{s.id}: empty rejection feedback"
            else:
                assert feedback is None


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario_id", sorted(BY_ID))
async def test_every_scenario_reaches_expected_status(scenario_id, brief, tmp_path):
    scenario = BY_ID[scenario_id]
    log = await run_one(scenario, brief, live=False, rep=1, out_dir=tmp_path)

    assert log.termination_path == scenario.expected_status
    assert "WARNING" not in log.notes
    assert log.interaction_count == len(scenario.decisions)
    assert (tmp_path / f"{log.run_id}.json").is_file()
    assert (tmp_path / "traces" / f"{log.run_id}.trace.json").is_file()


@pytest.mark.asyncio
async def test_shipped_run_writes_a_hashed_artefact(brief, tmp_path):
    log = await run_one(BY_ID["S1"], brief, live=False, rep=1, out_dir=tmp_path)
    assert log.final_artifact_sha256 and len(log.final_artifact_sha256) == 64
    assert (tmp_path / "artifacts" / "S1-F-01.txt").is_file()


@pytest.mark.asyncio
async def test_non_shipped_run_has_no_artefact(brief, tmp_path):
    for sid in ("S8", "S10"):  # killed, exhausted
        log = await run_one(BY_ID[sid], brief, live=False, rep=1, out_dir=tmp_path)
        assert log.final_artifact_sha256 is None
        assert log.artifact_path is None


@pytest.mark.asyncio
async def test_repeat_runs_are_byte_identical_under_mock(brief, tmp_path):
    """E4a. Determinism is structural — MockLLM returns responses[call_index]."""
    hashes = {
        (await run_one(BY_ID["S3"], brief, live=False, rep=r, out_dir=tmp_path)).final_artifact_sha256
        for r in (1, 2, 3)
    }
    assert len(hashes) == 1


@pytest.mark.asyncio
async def test_all_four_box32_paths_are_reachable(brief, tmp_path):
    """E1. ``status`` collapses two paths; ``_box32_path`` must separate them."""
    seen = set()
    for sid in ("S2", "S1", "S8", "S10"):  # approve, reject_then_approve, kill, exhausted
        log = await run_one(BY_ID[sid], brief, live=False, rep=1, out_dir=tmp_path)
        seen.add(_box32_path(log))
    assert seen == {"approve", "reject_then_approve", "kill", "exhausted"}


def test_select_filters_and_rejects_unknown_ids():
    assert [s.id for s in select(["S3", "S1"])] == ["S1", "S3"]  # set order preserved
    assert len(select(None)) == 10
    with pytest.raises(SystemExit):
        select(["S99"])


def test_render_brief_prose_carries_every_constraint():
    """Condition B must not be starved of context (rubric §3.2)."""
    brief = json.loads(BRIEF_PATH.read_text(encoding="utf-8"))
    prose = render_brief_prose(brief)
    for item in brief["constraints"]["out_of_scope"]:
        assert item in prose
    for item in brief["voice"]["dont"] + brief["voice"]["do"]:
        assert item in prose
    for item in brief["customer"]["objections"]:
        assert item in prose
    assert brief["product"]["one_liner"] in prose


def test_render_brief_prose_is_deterministic():
    brief = json.loads(BRIEF_PATH.read_text(encoding="utf-8"))
    assert render_brief_prose(brief) == render_brief_prose(brief)


def test_decision_log_counts_interactions_and_round_trips(tmp_path):
    log = DecisionLog(run_id="X-B-01", scenario="X", condition="B", llm="m", role="n/a")
    log.add("paste_brief", chars_typed=400)
    log.add("prompt", chars_typed=20)
    log.add("reject", feedback="πιο ζεστό")
    log.add("approve")
    assert log.interaction_count == 4

    path = log.write(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["founder_interactions"][2]["feedback"] == "πιο ζεστό"
    assert [i["seq"] for i in data["founder_interactions"]] == [1, 2, 3, 4]
