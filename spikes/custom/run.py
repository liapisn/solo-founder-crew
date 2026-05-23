"""Custom-spike entrypoint.

Usage (default, no API key, deterministic mock):
    cd spikes/custom
    python run.py

Optional real-LLM smoke test (unscored, ~$0.02):
    export ANTHROPIC_API_KEY=...
    pip install -r requirements.txt
    python run.py --real-llm

Produces:
    out/final_announcement.txt
    out/run_trace.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from jsonschema import validate

import sys

# Add `spikes/` to sys.path so `shared` resolves the same way `llm`,
# `runtime`, etc. resolve from the local spike directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hitl import ScriptedHITL  # noqa: E402
from llm import LLM, MockBackedLLM, RealBackedLLM  # noqa: E402
from roles import MARKETING  # noqa: E402
from runtime import Runtime  # noqa: E402
from shared import load_dotenv  # noqa: E402
from tools import PublisherTool  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas" / "venture_brief.schema.json"
BRIEF = ROOT / "scenarios" / "fixtures" / "passly_brief.json"
RESPONSES = ROOT / "scenarios" / "fixtures" / "founder_responses.json"
DOTENV = ROOT / ".env"
OUT = Path(__file__).parent / "out"

# Load .env early so RealLLM construction finds ANTHROPIC_API_KEY when
# --real-llm is passed. No-op when .env doesn't exist.
load_dotenv(DOTENV)


def select_llm(real: bool) -> LLM:
    return RealBackedLLM() if real else MockBackedLLM()


async def main(real_llm: bool) -> None:
    brief = json.loads(BRIEF.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validate(instance=brief, schema=schema)

    runtime = Runtime(
        brief=brief,
        role=MARKETING,
        hitl=ScriptedHITL(RESPONSES),
        publisher=PublisherTool(),
        llm=select_llm(real_llm),
    )
    result = await runtime.run()

    OUT.mkdir(exist_ok=True)
    (OUT / "run_trace.json").write_text(
        json.dumps(runtime.trace_as_jsonable(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if result["approved"]:
        (OUT / "final_announcement.txt").write_text(result["approved"], encoding="utf-8")

    print(f"status={result['status']} events={len(runtime.trace)}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Custom asyncio spike — Passly launch")
    p.add_argument(
        "--real-llm",
        action="store_true",
        help="Use Anthropic claude-haiku-4-5 instead of the deterministic mock. "
             "Requires ANTHROPIC_API_KEY and `pip install anthropic`.",
    )
    args = p.parse_args()
    asyncio.run(main(args.real_llm))
