"""Tests for the Condition B protocol — the guards and the scripted sends.

These cover what the *record* depends on rather than what the instrument
measures. Six of the first nine hand attempts were discarded for operator slips
(a terminal command before the task, ``/nex`` reaching the model as a prompt, a
task pasted one character short), and each cost live calls. The guards that
closed those holes were verified by simulation against a stub; this file commits
that simulation so CI holds it.

The stub client makes every test here free and offline: ``run_condition_b.run_one``
takes the client as a parameter, and ``baseline_repl.main`` is driven through
``input`` with a fake ``anthropic`` module in ``sys.modules``. No test in this file
reaches the network.
"""
from __future__ import annotations

import ast
import builtins
import json
import sys
import types
from pathlib import Path

import pytest

from evaluation import baseline_repl, run_condition_b
from evaluation.decision_log import render_brief_prose
from evaluation.scenarios import BY_ID

BRIEF_PATH = Path(__file__).resolve().parents[1] / "scenarios" / "fixtures" / "passly_brief.json"


class StubClient:
    """Records what was sent and replies deterministically."""

    def __init__(self) -> None:
        self.sent: list[list[dict[str, str]]] = []
        self.messages = self  # so client.messages.create(...) resolves here

    def create(self, *, model, max_tokens, messages):  # noqa: ARG002 - API shape
        self.sent.append([dict(m) for m in messages])
        block = types.SimpleNamespace(type="text", text=f"draft {len(self.sent)}")
        usage = types.SimpleNamespace(input_tokens=10, output_tokens=20)
        return types.SimpleNamespace(content=[block], usage=usage)

    @property
    def prompts(self) -> list[str]:
        """The user text of each call, in order."""
        return [call[-1]["content"] for call in self.sent]


@pytest.fixture
def brief_prose() -> str:
    return render_brief_prose(json.loads(BRIEF_PATH.read_text(encoding="utf-8")))


# ── run_condition_b: the scripted replay ────────────────────────────────────


@pytest.mark.parametrize("scenario_id", sorted(BY_ID))
def test_replay_reaches_expected_status(scenario_id, brief_prose, tmp_path):
    scenario = BY_ID[scenario_id]
    log = run_condition_b.run_one(scenario, 1, StubClient(), brief_prose, tmp_path)

    assert log.termination_path == scenario.expected_status
    assert (tmp_path / f"{scenario_id}-B-01.json").is_file()


@pytest.mark.parametrize("scenario_id", sorted(BY_ID))
def test_replay_sends_brief_then_task_then_feedback_verbatim(
    scenario_id, brief_prose, tmp_path
):
    """The identical-strings-across-conditions property, asserted end to end."""
    scenario = BY_ID[scenario_id]
    client = StubClient()
    run_condition_b.run_one(scenario, 1, client, brief_prose, tmp_path)

    sent_rejections = [f for a, f in scenario.decisions if a == "reject"]
    if scenario.expected_status == "exhausted":
        sent_rejections = sent_rejections[:-1]  # the last one maps to /stop

    assert client.prompts == [brief_prose, scenario.task, *sent_rejections]


@pytest.mark.parametrize("scenario_id", sorted(BY_ID))
def test_replay_interaction_count_is_brief_task_and_decisions(
    scenario_id, brief_prose, tmp_path
):
    """M1. paste_brief + task prompt + one per decision, plus copy_out on ship."""
    scenario = BY_ID[scenario_id]
    log = run_condition_b.run_one(scenario, 1, StubClient(), brief_prose, tmp_path)

    expected = 2 + len(scenario.decisions)
    if scenario.expected_status == "shipped":
        expected += 1  # copy_out — the framework's publisher_tool does this
    assert log.interaction_count == expected


def test_replay_ships_to_artifacts_and_never_to_drafts(brief_prose, tmp_path):
    log = run_condition_b.run_one(BY_ID["S1"], 1, StubClient(), brief_prose, tmp_path)

    assert (tmp_path / "artifacts" / "S1-B-01.txt").is_file()
    assert not (tmp_path / "drafts" / "S1-B-01.txt").exists()
    assert log.final_artifact_sha256 and len(log.final_artifact_sha256) == 64
    assert any(i.kind == "copy_out" for i in log.founder_interactions)


@pytest.mark.parametrize("scenario_id", ["S8", "S10"])  # killed, exhausted
def test_replay_keeps_the_draft_of_a_non_shipped_run(scenario_id, brief_prose, tmp_path):
    """M3 is comparative: Condition F keeps its killed draft, so B must too.

    drafts/, never artifacts/ — the blinded Panel A set stays exactly the
    shipped artefacts and cannot be contaminated by a re-run.
    """
    log = run_condition_b.run_one(BY_ID[scenario_id], 1, StubClient(), brief_prose, tmp_path)

    assert (tmp_path / "drafts" / f"{scenario_id}-B-01.txt").read_text(encoding="utf-8")
    assert not (tmp_path / "artifacts" / f"{scenario_id}-B-01.txt").exists()
    assert log.artifact_path is None
    assert log.final_artifact_sha256 is None


def test_baseline_imports_nothing_from_the_framework():
    """Rubric §3.2. If the baseline shared framework code, "no framework" would
    be a claim the code contradicts.

    Checked over the parsed import statements, not the source text — both modules
    discuss ``solo_founder_crew`` in prose, and that is the point of the prose.
    ``run_condition_f`` is excluded too: it pulls the framework in transitively.
    """
    forbidden = ("solo_founder_crew", "evaluation.run_condition_f")
    for module in (run_condition_b, baseline_repl):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for name in imported:
            assert not any(name.startswith(bad) for bad in forbidden), (
                f"{Path(module.__file__).name} imports {name}"
            )


# ── baseline_repl: the interactive guards ───────────────────────────────────


def drive(monkeypatch, tmp_path, scenario_id: str, typed: list[str]):
    """Run baseline_repl.main() against a stub client and a scripted keyboard."""
    client = StubClient()
    fake_anthropic = types.SimpleNamespace(Anthropic=lambda *a, **k: client)
    monkeypatch.setitem(sys.modules, "anthropic", fake_anthropic)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-real-key")
    monkeypatch.setattr(
        baseline_repl,
        "load_env",
        lambda path: None,  # never read the developer's real .env
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["baseline_repl", "--scenario", scenario_id, "--out", str(tmp_path)],
    )

    queue = list(typed)

    def fake_input(prompt: str = "") -> str:
        if not queue:
            raise EOFError
        return queue.pop(0)

    monkeypatch.setattr(builtins, "input", fake_input)
    code = baseline_repl.main()
    return code, client


def read_log(tmp_path: Path, run_id: str) -> dict:
    return json.loads((tmp_path / f"{run_id}.json").read_text(encoding="utf-8"))


def test_terminal_is_refused_before_the_brief(monkeypatch, tmp_path, capsys):
    """Two of the first four S1/S2 attempts approved before the task was sent,
    so the baseline was about to be scored on A2 having never seen the brief."""
    code, client = drive(monkeypatch, tmp_path, "S1", ["/approve"])

    out = capsys.readouterr().out
    assert "refusing to terminate" in out
    assert "/brief has not been sent" in out
    assert code == 130  # EOF after the refusal — the loop stayed alive
    assert client.sent == []
    assert not list(tmp_path.glob("*.json"))


def test_terminal_is_refused_after_the_brief_but_before_the_task(
    monkeypatch, tmp_path, capsys
):
    """The slip the guard was added for, and the one it used to miss.

    ``/brief`` is itself a message to the model, so it sets ``last_reply``. The
    guard's original ``if not last_reply`` therefore passed the moment the brief
    was sent, and this sequence shipped the reply *to the brief* as S1's
    artefact. Guarding on a ``prompt`` interaction closes it.
    """
    code, _ = drive(monkeypatch, tmp_path, "S1", ["/brief", "/approve"])

    out = capsys.readouterr().out
    assert "refusing to terminate" in out
    assert "the task has not been sent" in out
    assert code == 130
    assert not list(tmp_path.glob("*.json")), "shipped a run with no task sent"
    assert not (tmp_path / "artifacts").exists()


@pytest.mark.parametrize("terminal", ["/approve", "/kill", "/stop"])
def test_every_terminal_command_is_guarded(monkeypatch, tmp_path, capsys, terminal):
    drive(monkeypatch, tmp_path, "S1", [terminal])
    assert "refusing to terminate" in capsys.readouterr().out


def test_a_mistyped_command_is_never_sent(monkeypatch, tmp_path, capsys):
    """`/nex` reached the model once: it cost a turn, put an off-task reply into
    the context later drafts saw, and inflated M1 from 6 to 7 — bias against the
    baseline, the direction a single-author evaluation cannot afford."""
    code, client = drive(
        monkeypatch, tmp_path, "S1", ["/brief", "/task", "/nex", "/next"]
    )

    out = capsys.readouterr().out
    assert "unknown command '/nex'" in out
    assert "/nex" not in "".join(client.prompts)
    assert code == 130


def test_the_unknown_command_hint_lists_every_real_command(monkeypatch, tmp_path, capsys):
    drive(monkeypatch, tmp_path, "S1", ["/nope"])
    hint = capsys.readouterr().out

    for command in ("/brief", "/task", "/next", "/approve", "/kill", "/stop", "/undo", "/help"):
        assert command in hint, f"{command} missing from the unknown-command hint"


def test_brief_and_task_survive_the_unknown_command_catch_all(monkeypatch, tmp_path, brief_prose):
    """The catch-all sits after /next and the terminals and excludes /brief and
    /task — dispatch order, asserted, so no valid command is swallowed."""
    _, client = drive(monkeypatch, tmp_path, "S1", ["/brief", "/task"])

    assert client.prompts == [brief_prose, BY_ID["S1"].task]


def test_task_is_sent_verbatim_and_logged(monkeypatch, tmp_path):
    """S3-B-01's task went in at 144 characters against 145, a dropped full stop."""
    scenario = BY_ID["S3"]
    _, client = drive(monkeypatch, tmp_path, "S3", ["/brief", "/task"])

    assert client.prompts[-1] == scenario.task
    assert len(client.prompts[-1]) == len(scenario.task)


def test_next_plays_the_script_and_the_log_records_the_text(monkeypatch, tmp_path):
    """A run of /brief, /task, /next … with nothing transcribed by hand.

    The log has to carry the text, not just chars_typed: S1-B-01's 110 and 161
    happen to match, and coincidence is not provenance.
    """
    scenario = BY_ID["S1"]
    typed = ["/brief", "/task"] + ["/next"] * len(scenario.decisions)
    code, client = drive(monkeypatch, tmp_path, "S1", typed)

    assert code == 0
    data = read_log(tmp_path, "S1-B-01")
    assert data["termination_path"] == scenario.expected_status

    logged = [i.get("feedback") for i in data["founder_interactions"]]
    for _, feedback in scenario.decisions:
        if feedback:
            assert feedback in logged, "a scripted rejection was not sent verbatim"


def test_next_is_refused_before_brief_and_before_the_task(monkeypatch, tmp_path, capsys):
    drive(monkeypatch, tmp_path, "S1", ["/next"])
    assert "(send /brief first)" in capsys.readouterr().out

    # Same last_reply hole as the terminal guard: /brief alone used to satisfy
    # this, so /next played a scripted rejection against the reply to the brief.
    _, client = drive(monkeypatch, tmp_path, "S1", ["/brief", "/next"])
    assert "send the task first" in capsys.readouterr().out
    assert len(client.sent) == 1, "/next sent a decision before the task"


def test_undo_of_the_task_re_arms_the_guard(monkeypatch, tmp_path, capsys):
    """/undo pops the interaction, so the task counts as unsent again."""
    code, _ = drive(monkeypatch, tmp_path, "S1", ["/brief", "/task", "/undo", "/approve"])

    out = capsys.readouterr().out
    assert "the task has not been sent" in out
    assert code == 130


def test_exhausted_scenario_stops_rather_than_sending_a_fifth_draft(monkeypatch, tmp_path):
    """The final rejection maps to /stop; sending it would overshoot the cap
    Condition F enforces."""
    scenario = BY_ID["S10"]
    typed = ["/brief", "/task"] + ["/next"] * len(scenario.decisions)
    code, client = drive(monkeypatch, tmp_path, "S10", typed)

    assert code == 0
    data = read_log(tmp_path, "S10-B-01")
    assert data["termination_path"] == "exhausted"
    # brief + task + every rejection except the last, which became /stop
    assert len(client.sent) == 2 + scenario.revision_turns - 1


def test_repl_and_replay_produce_the_same_record(monkeypatch, tmp_path, brief_prose):
    """A scripted run and a hand run must be indistinguishable in the archive."""
    scenario = BY_ID["S1"]
    repl_dir = tmp_path / "repl"
    replay_dir = tmp_path / "replay"

    typed = ["/brief", "/task"] + ["/next"] * len(scenario.decisions)
    _, repl_client = drive(monkeypatch, repl_dir, "S1", typed)
    replay_client = StubClient()
    run_condition_b.run_one(scenario, 1, replay_client, brief_prose, replay_dir)

    assert repl_client.prompts == replay_client.prompts

    volatile = {"timestamp_start", "timestamp_terminal", "wall_clock_s", "llm_latency_s", "notes"}
    a = {k: v for k, v in read_log(repl_dir, "S1-B-01").items() if k not in volatile}
    b = {k: v for k, v in read_log(replay_dir, "S1-B-01").items() if k not in volatile}
    assert a == b
