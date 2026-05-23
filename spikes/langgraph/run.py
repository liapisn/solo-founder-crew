"""LangGraph-spike entrypoint.

Usage:
    export ANTHROPIC_API_KEY=...
    cd spikes/langgraph
    pip install -r requirements.txt
    python run.py
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

from graph import build_graph, make_llm
from hitl import ScriptedHITL
from roles import MARKETING
from tools import PublisherTool

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas" / "venture_brief.schema.json"
BRIEF = ROOT / "scenarios" / "fixtures" / "passly_brief.json"
RESPONSES = ROOT / "scenarios" / "fixtures" / "founder_responses.json"
OUT = Path(__file__).parent / "out"


def main() -> None:
    brief = json.loads(BRIEF.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validate(instance=brief, schema=schema)

    app = build_graph()
    final = app.invoke({
        "brief": brief,
        "role": MARKETING,
        "llm": make_llm(),
        "hitl": ScriptedHITL(RESPONSES),
        "publisher": PublisherTool(),
        "trace": [],
    })

    OUT.mkdir(exist_ok=True)
    (OUT / "run_trace.json").write_text(
        json.dumps(final.get("trace", []), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if final.get("approved"):
        (OUT / "final_announcement.txt").write_text(final["approved"], encoding="utf-8")

    status = "shipped" if final.get("approved") else "ended"
    print(f"status={status} events={len(final.get('trace', []))}")


if __name__ == "__main__":
    main()
