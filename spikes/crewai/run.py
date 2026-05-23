"""CrewAI-spike entrypoint.

Usage (default mock, no API key):
    cd spikes/crewai
    python run.py

Optional real-LLM smoke test (unscored, ~$0.02 at claude-haiku-4-5):
    cp ../../.env.example ../../.env  # then paste ANTHROPIC_API_KEY
    python run.py --real-llm

Produces:
    out/final_announcement.txt
    out/run_trace.json

Implementation notes (rubric evidence):
- CrewAI's `Crew.kickoff()` runs all tasks in sequence; it does not support
  interrupting between tasks for a HITL gate without using `human_input=True`
  which calls stdin. To get a deterministic, scripted gate we run each Task
  as its own one-task Crew kickoff and put the HITL logic *between* runs.
- The "publisher_tool requires escalation" rule is enforced by attaching
  the tool to the agent only after founder approval — CrewAI has no
  declarative `must_escalate` concept.
- Memory across turns is threaded manually via `context=` on the second Task.
- Trace capture is also manual: we log each kickoff and HITL turn.
- Mock LLM substitution requires subclassing `crewai.LLM` and bypassing
  litellm (see `llm.py`). Less clean than the custom spike's
  one-method Protocol — itself rubric evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from jsonschema import validate
from crewai import Crew, Task

# spikes/crewai/run.py → spikes/ on path so shared resolves
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hitl import FounderDecision, ScriptedHITL  # noqa: E402
from llm import build_llm  # noqa: E402
from roles import MARKETING_META, build_marketing_agent  # noqa: E402
from shared import load_dotenv  # noqa: E402
from tools import PublisherTool  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas" / "venture_brief.schema.json"
BRIEF = ROOT / "scenarios" / "fixtures" / "passly_brief.json"
RESPONSES = ROOT / "scenarios" / "fixtures" / "founder_responses.json"
DOTENV = ROOT / ".env"
OUT = Path(__file__).parent / "out"
MAX_REVISIONS = 1

# Pick up ANTHROPIC_API_KEY from .env when --real-llm is passed.
load_dotenv(DOTENV)


def draft_task(agent, brief: dict) -> Task:
    return Task(
        description=(
            "Draft a launch announcement for the venture described in the "
            f"Venture Brief below. Match the voice. Respect every constraint. "
            "Keep under 150 words.\n\n"
            f"VENTURE BRIEF:\n{json.dumps(brief, ensure_ascii=False, indent=2)}"
        ),
        expected_output="The announcement text only — no preamble, no headings.",
        agent=agent,
    )


def revise_task(agent, prior: str, feedback: str) -> Task:
    return Task(
        description=(
            "Revise the prior draft based on the founder's feedback. "
            "Return the new draft only.\n\n"
            f"PRIOR DRAFT:\n{prior}\n\nFOUNDER FEEDBACK:\n{feedback}"
        ),
        expected_output="The revised announcement text only.",
        agent=agent,
    )


def kickoff_one(task: Task) -> str:
    crew = Crew(agents=[task.agent], tasks=[task], verbose=False)
    result = crew.kickoff()
    # CrewAI returns CrewOutput; .raw is the assembled text
    return str(result.raw if hasattr(result, "raw") else result).strip()


def main(real_llm: bool) -> None:
    brief = json.loads(BRIEF.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validate(instance=brief, schema=schema)

    hitl = ScriptedHITL(RESPONSES)
    publisher = PublisherTool()
    agent = build_marketing_agent(build_llm(real_llm))
    trace: list[dict] = []

    def event(role: str | None, action: str, inp, out) -> None:
        trace.append({"ts": time.time(), "role": role, "action": action, "input": inp, "output": out})

    event(None, "run_start", {"venture_id": brief["venture_id"]}, None)

    # Turn 1 — draft
    draft = kickoff_one(draft_task(agent, brief))
    event(MARKETING_META.name, "draft_content", {"has_prior": False}, draft)

    approved: str | None = None
    for turn in range(1, MAX_REVISIONS + 2):
        decision: FounderDecision = hitl.review(artifact=draft, turn=turn)
        event(
            "founder",
            "hitl_review",
            {"turn": turn, "draft_preview": draft[:120]},
            {"action": decision.action, "feedback": decision.feedback},
        )
        if decision.action == "approve":
            approved = draft
            break
        if decision.action == "kill":
            event(None, "run_killed", None, None)
            _write(trace, None)
            return
        if decision.action == "reject":
            if turn > MAX_REVISIONS:
                event(None, "revision_budget_exhausted", None, None)
                _write(trace, None)
                return
            draft = kickoff_one(revise_task(agent, draft, decision.feedback or ""))
            event(MARKETING_META.name, "revise_content", {"has_prior": True}, draft)

    assert approved is not None
    # Tool access enforcement: attach publisher_tool only now that escalation is satisfied.
    if "publisher_tool" not in MARKETING_META.tools:
        raise PermissionError("role does not hold publisher_tool")
    agent.tools = [publisher]  # late attachment as escalation gate
    publish_result = publisher._run(text=approved)
    event(
        MARKETING_META.name,
        "publisher_tool.publish",
        {"chars": len(approved)},
        publish_result,
    )
    event(None, "run_end", None, {"status": "shipped"})
    _write(trace, approved)
    print(f"status=shipped events={len(trace)}")


def _write(trace: list[dict], approved: str | None) -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / "run_trace.json").write_text(
        json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if approved:
        (OUT / "final_announcement.txt").write_text(approved, encoding="utf-8")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="CrewAI spike — Passly launch")
    p.add_argument(
        "--real-llm",
        action="store_true",
        help="Use Anthropic claude-haiku-4-5 via litellm instead of the "
             "deterministic MockCrewLLM. Requires ANTHROPIC_API_KEY.",
    )
    args = p.parse_args()
    main(args.real_llm)
