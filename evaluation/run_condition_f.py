"""Condition F — the framework. Drives S1–S10 through the Author Flow.

Rubric §3.1. Every run emits one decision log (§7) and one artefact file, so
Panel B (§6) is read off files rather than off this script's stdout.

    # deterministic, no API key, no cost — the E4a reading
    python -m evaluation.run_condition_f --repeat 3

    # the live scored runs
    python -m evaluation.run_condition_f --live

    # one scenario, live
    python -m evaluation.run_condition_f --live --scenarios S8

Outputs land in ``Diplomatic/05_Drafts/Ch5_Eval_Runs/`` by default (``--out``
overrides), because the runs are thesis evidence rather than repo artefacts.

The role comes from the **Role Library** (``make_marketing``), not an inline
Role: the evaluation must exercise Component 2 as shipped, otherwise it scores a
bespoke object the thesis does not describe.
"""
from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import time
from pathlib import Path
from typing import Any

from solo_founder_crew import (
    Crew,
    FounderDecision,
    LLMResponse,
    MockLLM,
    ToolRegistry,
    VentureBrief,
    load_dotenv,
    make_marketing,
)

from evaluation.decision_log import DecisionLog, GatedAction, now_iso, sha256
from evaluation.scenarios import MAX_REVISIONS, Scenario, select

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIEF_PATH = REPO_ROOT / "scenarios" / "fixtures" / "passly_brief.json"
DEFAULT_OUT = REPO_ROOT.parent / "Diplomatic" / "05_Drafts" / "Ch5_Eval_Runs"
MODEL = "claude-haiku-4-5"
PUBLISH_ACTION = "final_approval_before_publish"


class TimingLLM:
    """Wraps an LLMClient to time each call. Satisfies the same Protocol.

    Latency is how M2 is compared across conditions: founder think-time is
    excluded by definition (rubric §6), so what remains is the model's time.
    Delegates ``calls`` so E5 token reading is unaffected.
    """

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.latencies: list[float] = []

    def complete(self, system: str, user: str) -> LLMResponse:
        t0 = time.perf_counter()
        resp = self.inner.complete(system, user)
        self.latencies.append(time.perf_counter() - t0)
        return resp

    @property
    def calls(self) -> list[dict[str, Any]]:
        return getattr(self.inner, "calls", [])


class RecordingHITL:
    """Replays a scenario's scripted decisions while recording them into the log.

    This is the ``HITLContract`` seam doing exactly what §3.8 claims it does — a
    third implementation alongside ``ScriptedHITL`` and ``DiscordHITL``, written
    without touching Crew, Role or tool code.
    """

    def __init__(self, scenario: Scenario, log: DecisionLog) -> None:
        self.scenario = scenario
        self.log = log
        self.gates = 0

    async def review(self, request: Any) -> FounderDecision:
        if self.gates >= len(self.scenario.decisions):
            raise RuntimeError(
                f"{self.scenario.id}: gate {self.gates + 1} reached but only "
                f"{len(self.scenario.decisions)} scripted decisions exist. The "
                f"revision cap (MAX_REVISIONS={MAX_REVISIONS}) and the script "
                f"disagree — see evaluation/scenarios.py."
            )
        action, feedback = self.scenario.decisions[self.gates]
        self.gates += 1
        self.log.turns = max(self.log.turns, getattr(request, "turn", self.gates))
        self.log.add(action, feedback=feedback)
        self.log.gated_actions.append(
            GatedAction(
                action=getattr(request, "action", PUBLISH_ACTION),
                escalated=True,
                resolved=action,
            )
        )
        return FounderDecision(action=action, feedback=feedback)


def build_tools() -> tuple[ToolRegistry, dict[str, str]]:
    """Publisher tool gated on the escalated action, per the Role Library's grant."""
    published: dict[str, str] = {}

    async def publisher(text: str) -> str:
        published["text"] = text
        return f"shipped:{len(text)}chars"

    registry = ToolRegistry()
    registry.register("publisher_tool", publisher, escalates=PUBLISH_ACTION)
    return registry, published


async def run_one(
    scenario: Scenario, brief: VentureBrief, *, live: bool, rep: int, out_dir: Path
) -> DecisionLog:
    run_id = f"{scenario.id}-F-{rep:02d}"
    inner = _live_llm() if live else MockLLM(responses=list(scenario.mock_responses))
    llm = TimingLLM(inner)
    log = DecisionLog(
        run_id=run_id,
        scenario=scenario.id,
        condition="F",
        llm=MODEL if live else "MockLLM",
        role="marketing",
        notes=f"{scenario.title} · channel={scenario.channel} · {scenario.exercises}",
    )
    hitl = RecordingHITL(scenario, log)
    tools, _ = build_tools()
    crew = Crew(
        brief=brief, roles=[make_marketing(brief)], llm=llm, hitl=hitl, tools=tools
    )

    t0 = time.perf_counter()
    result = await crew.author_flow(
        task_description=scenario.task,
        role="marketing",
        max_revisions=MAX_REVISIONS,
        thread_id=f"{run_id}",
    )
    log.wall_clock_s = round(time.perf_counter() - t0, 3)
    log.timestamp_terminal = now_iso()
    log.termination_path = result.status
    log.llm_latency_s = round(sum(llm.latencies), 3)
    log.tokens = {
        "input": sum(c.get("usage", {}).get("input_tokens", 0) for c in llm.calls),
        "output": sum(c.get("usage", {}).get("output_tokens", 0) for c in llm.calls),
    }

    artefacts = out_dir / "artifacts"
    artefacts.mkdir(parents=True, exist_ok=True)
    final = result.approved_artifact or ""
    if final:
        path = artefacts / f"{run_id}.txt"
        path.write_text(final, encoding="utf-8")
        log.artifact_path = str(path.relative_to(out_dir))
        log.final_artifact_sha256 = sha256(final)
    traces = out_dir / "traces"
    traces.mkdir(parents=True, exist_ok=True)
    result.trace.write(traces / f"{run_id}.trace.json")

    if result.status != scenario.expected_status:
        log.notes += (
            f" — WARNING: expected status {scenario.expected_status!r}, "
            f"got {result.status!r}"
        )
    log.write(out_dir)
    return log


def _live_llm() -> Any:
    from solo_founder_crew import AnthropicLLM

    return AnthropicLLM(model=MODEL)


def _box32_path(log: DecisionLog) -> str:
    """Name the run's path the way Box 3.2 / examples/termination_paths.py do.

    ``status`` alone collapses two of the four paths: an approve on the first
    gate and an approve after revisions both report "shipped". E1 asks whether
    all four are *reachable*, so the distinction has to survive into the summary.
    """
    if log.termination_path != "shipped":
        return {"killed": "kill", "exhausted": "exhausted"}.get(
            log.termination_path or "", log.termination_path or "?"
        )
    rejections = sum(1 for i in log.founder_interactions if i.kind == "reject")
    return "reject_then_approve" if rejections else "approve"


def determinism_report(logs: list[DecisionLog]) -> dict[str, Any]:
    """E4a / E4b — group repeats by scenario and compare final artefacts.

    Identical hashes across repeats is the E4a pass. Where they differ (the live
    path), report pairwise similarity rather than a pass/fail: E4b is a reading,
    not a gate.
    """
    by_scenario: dict[str, list[DecisionLog]] = {}
    for log in logs:
        by_scenario.setdefault(log.scenario, []).append(log)

    out: dict[str, Any] = {}
    for sid, runs in sorted(by_scenario.items()):
        hashes = [r.final_artifact_sha256 for r in runs]
        entry: dict[str, Any] = {
            "repeats": len(runs),
            "identical": len(set(hashes)) == 1,
            "hashes": hashes,
        }
        if len(set(hashes)) > 1:
            entry["note"] = "artefacts differ — see e4b_similarity"
        out[sid] = entry
    return out


def pairwise_similarity(out_dir: Path, sid: str, reps: int) -> list[float]:
    """Normalised similarity across a scenario's repeats (E4b)."""
    texts = []
    for rep in range(1, reps + 1):
        p = out_dir / "artifacts" / f"{sid}-F-{rep:02d}.txt"
        if p.is_file():
            texts.append(p.read_text(encoding="utf-8"))
    ratios = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            ratios.append(
                round(difflib.SequenceMatcher(None, texts[i], texts[j]).ratio(), 4)
            )
    return ratios


async def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Condition F — framework runs")
    ap.add_argument("--live", action="store_true", help=f"use {MODEL} instead of MockLLM")
    ap.add_argument("--repeat", type=int, default=1, help="runs per scenario (E4a/E4b)")
    ap.add_argument("--scenarios", help="comma-separated ids, e.g. S1,S8")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    load_dotenv(REPO_ROOT / ".env")
    brief = VentureBrief.from_file(BRIEF_PATH)
    chosen = select(args.scenarios.split(",") if args.scenarios else None)
    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    logs: list[DecisionLog] = []
    for scenario in chosen:
        for rep in range(1, args.repeat + 1):
            log = await run_one(
                scenario, brief, live=args.live, rep=rep, out_dir=out_dir
            )
            logs.append(log)
            flag = "  ⚠" if "WARNING" in log.notes else ""
            print(
                f"{log.run_id:12} {log.termination_path:10} "
                f"turns={log.turns} interactions={log.interaction_count} "
                f"tok={log.tokens['input']}/{log.tokens['output']} "
                f"llm={log.llm_latency_s}s{flag}"
            )

    summary: dict[str, Any] = {
        "condition": "F",
        "generated": now_iso(),
        "llm": MODEL if args.live else "MockLLM",
        "repeat": args.repeat,
        "max_revisions": MAX_REVISIONS,
        "runs": len(logs),
        "e1_termination_paths_seen": sorted({_box32_path(log) for log in logs}),
        "e4_determinism": determinism_report(logs),
        "e5_tokens_total": {
            "input": sum(log.tokens["input"] for log in logs),
            "output": sum(log.tokens["output"] for log in logs),
        },
        "m1_interactions_by_scenario": {
            log.scenario: log.interaction_count for log in logs
        },
        "m2_llm_latency_s_by_scenario": {
            log.scenario: log.llm_latency_s for log in logs
        },
    }
    if args.repeat > 1:
        summary["e4b_similarity"] = {
            s.id: pairwise_similarity(out_dir, s.id, args.repeat) for s in chosen
        }

    name = f"summary_F_{'live' if args.live else 'mock'}.json"
    (out_dir / name).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nwrote {len(logs)} logs + {name} to {out_dir}")

    mismatches = [log.run_id for log in logs if "WARNING" in log.notes]
    if mismatches:
        print(f"status mismatches: {', '.join(mismatches)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
