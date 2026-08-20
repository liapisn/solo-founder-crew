"""Condition B — scripted replay of the baseline chat loop.

Same condition as :mod:`evaluation.baseline_repl`, driven from the scenario
definitions instead of from a keyboard. It sends exactly what the REPL's
``/brief``, ``/task`` and ``/next`` send, in the same order, and writes the same
``DecisionLog``. A run produced here and a run produced by hand are
indistinguishable in the archive, which is the point.

**Why this exists.** Rubric §3.2 pre-registers Condition B as performed by the
author, and that was written when the operator genuinely transcribed the brief,
the task and every feedback string. It is no longer true of the machinery:
``render_brief_prose`` generates the brief, ``/task`` sends the task verbatim and
``/next`` plays the scripted decision. Nothing is left for a human to get right,
and six of the first nine hand attempts were discarded for protocol slips that
cost live calls. Replaying the protocol removes that failure mode and makes the
condition re-runnable by a third party, which is the independent re-scorability
§8 step 7 asks for and which a hand-run condition cannot offer.

**M2 is read from ``llm_latency_s``**, model time only, in both conditions — so
automating the keystrokes changes no reported number. ``wall_clock_s`` is still
recorded but is not the M2 figure; here it would measure the script, not a
founder.

**It imports nothing from ``solo_founder_crew``.** Not the LLM class, not the
dotenv helper, not the brief loader — the same constraint ``baseline_repl``
holds, and for the same reason: if the baseline shared framework code, "no
framework" would be a claim the code contradicts. ``run_condition_f`` is not
imported either, because that module pulls the framework in transitively.

    python -m evaluation.run_condition_b --scenarios S4,S5 --out <dir>
    python -m evaluation.run_condition_b --scenarios S2,S3,S8 --rep-start 2 --repeat 3
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import time
from pathlib import Path
from typing import Any

from evaluation.decision_log import (
    DecisionLog,
    now_iso,
    render_brief_prose,
    sha256,
)
from evaluation.scenarios import MAX_REVISIONS, SCENARIOS, BY_ID

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIEF_PATH = REPO_ROOT / "scenarios" / "fixtures" / "passly_brief.json"
DEFAULT_OUT = REPO_ROOT.parent / "Diplomatic" / "05_Drafts" / "Ch5_Eval_Runs"
MODEL = "claude-haiku-4-5"
MAX_TOKENS = 1024


def load_env(path: Path) -> None:
    """Minimal KEY=VALUE reader — deliberately not the framework's load_dotenv."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and not os.environ.get(key):
            os.environ[key] = value


def run_one(scenario, rep: int, client, brief_prose: str, out_dir: Path) -> DecisionLog:
    """One baseline run. Mirrors baseline_repl's loop exactly."""
    run_id = f"{scenario.id}-B-{rep:02d}"
    log = DecisionLog(
        run_id=run_id,
        scenario=scenario.id,
        condition="B",
        llm=MODEL,
        role="n/a (no roles in the baseline)",
        notes=f"{scenario.title} · channel={scenario.channel} · baseline chat loop "
        f"(scripted replay)",
    )
    messages: list[dict[str, str]] = []
    last_reply = ""
    t_start = time.perf_counter()

    def send(text: str, kind: str) -> None:
        nonlocal last_reply
        log.add(kind, feedback=None if kind == "paste_brief" else text,
                chars_typed=len(text))
        messages.append({"role": "user", "content": text})
        t0 = time.perf_counter()
        resp = client.messages.create(
            model=MODEL, max_tokens=MAX_TOKENS, messages=messages
        )
        log.llm_latency_s = round(log.llm_latency_s + (time.perf_counter() - t0), 3)
        reply = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        messages.append({"role": "assistant", "content": reply})
        last_reply = reply
        log.tokens["input"] += resp.usage.input_tokens
        log.tokens["output"] += resp.usage.output_tokens
        log.turns = len(messages) // 2

    send(brief_prose, "paste_brief")      # /brief
    send(scenario.task, "prompt")          # /task

    scripted = list(scenario.decisions)
    for idx, (action, feedback) in enumerate(scripted):
        last = idx == len(scripted) - 1
        exhausted_last = scenario.expected_status == "exhausted" and last
        if action == "reject" and not exhausted_last:
            send(feedback, "prompt")       # /next -> verbatim feedback
            continue
        status = {"approve": "shipped", "kill": "killed", "reject": "exhausted"}[action]
        log.termination_path = status
        log.add({"shipped": "approve", "killed": "kill", "exhausted": "stop"}[status])
        if status == "shipped" and last_reply:
            artefacts = out_dir / "artifacts"
            artefacts.mkdir(parents=True, exist_ok=True)
            path = artefacts / f"{run_id}.txt"
            path.write_text(last_reply, encoding="utf-8")
            log.artifact_path = str(path.relative_to(out_dir))
            log.final_artifact_sha256 = sha256(last_reply)
            log.add("copy_out")
        break

    log.wall_clock_s = round(time.perf_counter() - t_start, 3)
    log.timestamp_terminal = now_iso()
    log.write(out_dir)
    return log


def pairwise_similarity(out_dir: Path, sid: str, reps: list[int]) -> list[float]:
    """Normalised similarity across a scenario's repeats (E4b)."""
    texts = []
    for rep in reps:
        p = out_dir / "artifacts" / f"{sid}-B-{rep:02d}.txt"
        if p.is_file():
            texts.append(p.read_text(encoding="utf-8"))
    return [
        round(difflib.SequenceMatcher(None, texts[i], texts[j]).ratio(), 4)
        for i in range(len(texts))
        for j in range(i + 1, len(texts))
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Condition B — scripted baseline runs")
    ap.add_argument("--scenarios", help="comma-separated ids, e.g. S4,S5")
    ap.add_argument("--repeat", type=int, default=1, help="runs per scenario")
    ap.add_argument("--rep-start", type=int, default=1, help="first rep number")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    load_env(REPO_ROOT / ".env")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not set (looked in env and ../.env)")
    import anthropic

    client = anthropic.Anthropic()
    brief_prose = render_brief_prose(
        json.loads(BRIEF_PATH.read_text(encoding="utf-8"))
    )
    ids = args.scenarios.split(",") if args.scenarios else [s.id for s in SCENARIOS]
    unknown = [i for i in ids if i not in BY_ID]
    if unknown:
        raise SystemExit(f"unknown scenario(s): {', '.join(unknown)}")
    chosen = [BY_ID[i] for i in ids]

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    reps = list(range(args.rep_start, args.rep_start + args.repeat))

    logs: list[DecisionLog] = []
    for scenario in chosen:
        for rep in reps:
            log = run_one(scenario, rep, client, brief_prose, out_dir)
            logs.append(log)
            print(
                f"{log.run_id:12} {log.termination_path:10} "
                f"turns={log.turns} interactions={log.interaction_count} "
                f"tok={log.tokens['input']}/{log.tokens['output']} "
                f"llm={log.llm_latency_s}s"
            )

    summary: dict[str, Any] = {
        "condition": "B",
        "generated": now_iso(),
        "llm": MODEL,
        "driver": "run_condition_b.py (scripted replay)",
        "repeat": args.repeat,
        "rep_start": args.rep_start,
        "max_revisions": MAX_REVISIONS,
        "runs": len(logs),
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
            s.id: pairwise_similarity(out_dir, s.id, reps) for s in chosen
        }
    (out_dir / "summary_B_live.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nwrote {len(logs)} logs + summary_B_live.json to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
