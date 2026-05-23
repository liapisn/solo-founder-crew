"""Custom-spike entrypoint.

Usage:
    export ANTHROPIC_API_KEY=...
    cd spikes/custom
    pip install -r requirements.txt
    python run.py

Produces:
    out/final_announcement.txt
    out/run_trace.json
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from jsonschema import validate

from hitl import ScriptedHITL
from llm import AnthropicLLM
from roles import MARKETING
from runtime import Runtime
from tools import PublisherTool

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas" / "venture_brief.schema.json"
BRIEF = ROOT / "scenarios" / "fixtures" / "passly_brief.json"
RESPONSES = ROOT / "scenarios" / "fixtures" / "founder_responses.json"
OUT = Path(__file__).parent / "out"


async def main() -> None:
    brief = json.loads(BRIEF.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validate(instance=brief, schema=schema)

    runtime = Runtime(
        brief=brief,
        role=MARKETING,
        hitl=ScriptedHITL(RESPONSES),
        publisher=PublisherTool(),
        llm=AnthropicLLM(),
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
    asyncio.run(main())
