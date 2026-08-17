"""Condition B — the synthesised baseline. A bare chat loop, no framework.

Rubric §3.2. This is the "no framework" condition: one thread, one model, no
roles, no decision rights, no escalation, no trace, no gate. The founder drafts,
revises and publishes by hand.

**It imports nothing from ``solo_founder_crew`` on purpose.** Not the LLM class,
not the dotenv helper, not the brief loader. If the baseline shared framework
code, "no framework" would be a claim the code contradicts. The only shared
things are data — the same brief JSON and the same scenario definitions.

Why not a consumer chat app: Condition F runs ``claude-haiku-4-5``. A chat app
serves a much stronger model and cannot be pinned, so any difference would be
attributable to the model rather than to the operating model — the exact
confound rubric §3.2 exists to prevent. Same model, same settings, no framework.

    python -m evaluation.baseline_repl --scenario S1

Commands at the prompt:

    /brief      paste the Venture Brief prose (counts as ONE interaction)
    /approve    terminal: you would ship this
    /kill       terminal: you would not ship this at all
    /stop       terminal: you gave up revising (the exhausted analogue)
    /undo       drop the last exchange (mistyped, not a founder decision)
    /help       show this

Everything else you type is a prompt to the model and counts as one interaction.
Timing excludes your think-time by construction: only model latency is summed.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from evaluation.decision_log import DecisionLog, now_iso, render_brief_prose, sha256
from evaluation.scenarios import MAX_REVISIONS, BY_ID

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIEF_PATH = REPO_ROOT / "scenarios" / "fixtures" / "passly_brief.json"
DEFAULT_OUT = REPO_ROOT.parent / "Diplomatic" / "05_Drafts" / "Ch5_Eval_Runs"
MODEL = "claude-haiku-4-5"
MAX_TOKENS = 1024

TERMINAL = {"/approve": "shipped", "/kill": "killed", "/stop": "exhausted"}


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


def main() -> int:
    ap = argparse.ArgumentParser(description="Condition B — baseline chat loop")
    ap.add_argument("--scenario", required=True, help="scenario id, e.g. S1")
    ap.add_argument("--rep", type=int, default=1)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    scenario = BY_ID.get(args.scenario)
    if scenario is None:
        raise SystemExit(f"unknown scenario: {args.scenario} (have {', '.join(BY_ID)})")

    load_env(REPO_ROOT / ".env")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not set (looked in env and ../.env)")
    import anthropic

    client = anthropic.Anthropic()
    brief = json.loads(BRIEF_PATH.read_text(encoding="utf-8"))
    brief_prose = render_brief_prose(brief)

    run_id = f"{scenario.id}-B-{args.rep:02d}"
    log = DecisionLog(
        run_id=run_id,
        scenario=scenario.id,
        condition="B",
        llm=MODEL,
        role="n/a (no roles in the baseline)",
        notes=f"{scenario.title} · channel={scenario.channel} · baseline chat loop",
    )

    print(f"\n── Condition B · {run_id} · {MODEL} ──")
    print(f"Scenario {scenario.id}: {scenario.title}")
    print("\nTHE TASK (paste or retype this as you would):\n")
    print(f"  {scenario.task}\n")
    if scenario.decisions:
        print("YOUR SCRIPTED FEEDBACK, in order — use these verbatim when you reject:")
        for i, (action, feedback) in enumerate(scenario.decisions, 1):
            print(f"  {i}. {action}" + (f": {feedback}" if feedback else ""))
    print(
        f"\nRevision cap for comparability: {MAX_REVISIONS} revisions "
        f"({MAX_REVISIONS + 1} drafts). /help for commands.\n"
    )

    messages: list[dict[str, str]] = []
    last_reply = ""
    t_start = time.perf_counter()

    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\naborted — no log written")
            return 130
        if not line:
            continue

        if line == "/help":
            print(__doc__.split("Commands at the prompt:")[1].split("Everything else")[0])
            continue

        if line == "/undo":
            if len(messages) >= 2:
                messages = messages[:-2]
                if log.founder_interactions:
                    log.founder_interactions.pop()
                print(f"(dropped last exchange; {len(messages)//2} remain)")
            else:
                print("(nothing to undo)")
            continue

        if line in TERMINAL:
            status = TERMINAL[line]
            log.termination_path = status
            log.add({"shipped": "approve", "killed": "kill", "exhausted": "stop"}[status])
            if status == "shipped" and last_reply:
                artefacts = args.out / "artifacts"
                artefacts.mkdir(parents=True, exist_ok=True)
                path = artefacts / f"{run_id}.txt"
                path.write_text(last_reply, encoding="utf-8")
                log.artifact_path = str(path.relative_to(args.out))
                log.final_artifact_sha256 = sha256(last_reply)
                log.add("copy_out")
                print(f"(saved final artefact to {path})")
            break

        if line == "/brief":
            user_text = brief_prose
            log.add("paste_brief", chars_typed=len(brief_prose))
            print(f"(sent the brief — {len(brief_prose)} chars, counted as 1 interaction)")
        else:
            user_text = line
            log.add("prompt", chars_typed=len(line))

        messages.append({"role": "user", "content": user_text})
        t0 = time.perf_counter()
        resp = client.messages.create(
            model=MODEL, max_tokens=MAX_TOKENS, messages=messages
        )
        log.llm_latency_s = round(log.llm_latency_s + (time.perf_counter() - t0), 3)
        reply = "".join(
            b.text for b in resp.content if getattr(b, "type", "") == "text"
        )
        messages.append({"role": "assistant", "content": reply})
        last_reply = reply
        log.tokens["input"] += resp.usage.input_tokens
        log.tokens["output"] += resp.usage.output_tokens
        log.turns = len(messages) // 2
        print(f"\nclaude> {reply}\n")

    log.wall_clock_s = round(time.perf_counter() - t_start, 3)
    log.timestamp_terminal = now_iso()
    path = log.write(args.out)
    print(
        f"\n{run_id}: {log.termination_path} · turns={log.turns} · "
        f"interactions={log.interaction_count} · "
        f"tok={log.tokens['input']}/{log.tokens['output']} · "
        f"llm={log.llm_latency_s}s\nwrote {path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
