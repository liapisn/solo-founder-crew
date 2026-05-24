"""LangGraph-spike entrypoint.

Usage (default mock, no API key):
    cd spikes/langgraph
    python run.py

Optional real-LLM smoke test (unscored, ~$0.02 at claude-haiku-4-5):
    # .env at repo root must contain ANTHROPIC_API_KEY
    python run.py --real-llm
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import validate

# spikes/langgraph/run.py → spikes/ APPENDED to path so `shared` resolves
# without spikes/langgraph/ shadowing the installed langgraph package as a
# namespace-package fragment (which would make `from langgraph.graph import …`
# resolve back to the spike's local graph.py — a circular import).
sys.path.append(str(Path(__file__).resolve().parents[1]))

from graph import build_graph  # noqa: E402
from hitl import ScriptedHITL  # noqa: E402
from llm import build_llm  # noqa: E402
from roles import MARKETING  # noqa: E402
from shared import load_dotenv  # noqa: E402
from tools import PublisherTool  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas" / "venture_brief.schema.json"
BRIEF = ROOT / "scenarios" / "fixtures" / "passly_brief.json"
RESPONSES = ROOT / "scenarios" / "fixtures" / "founder_responses.json"
DOTENV = ROOT / ".env"
OUT = Path(__file__).parent / "out"

# Pick up ANTHROPIC_API_KEY from .env when --real-llm is passed.
load_dotenv(DOTENV)


def main(real_llm: bool) -> None:
    brief = json.loads(BRIEF.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validate(instance=brief, schema=schema)

    app = build_graph()
    final = app.invoke({
        "brief": brief,
        "role": MARKETING,
        "llm": build_llm(real_llm),
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
    p = argparse.ArgumentParser(description="LangGraph spike — Passly launch")
    p.add_argument(
        "--real-llm",
        action="store_true",
        help="Use Anthropic claude-haiku-4-5 via langchain-anthropic "
             "instead of the deterministic MockChatModel. Requires "
             "ANTHROPIC_API_KEY.",
    )
    args = p.parse_args()
    main(args.real_llm)
