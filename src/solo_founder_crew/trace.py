"""Structured run trace.

Every action the framework dispatches — role LLM calls, founder
decisions at HITL gates, tool invocations — appends a `TraceEvent`
to a `RunTrace`. The trace is the single source of truth for:

- Founder visibility (what did the crew do, when, why).
- Ch.5 evaluation (rubric scoring, reproducibility).
- Failure debugging (what was the state when X happened).

The shape is intentionally narrow: role / action / input / output /
optional decision / ISO timestamp. Anything richer is encoded into
the input or output strings (truncated to keep traces readable).

Citable in Ch.3 §"Observability" and Ch.5.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clip(value: Any, max_chars: int = 400) -> str:
    """Serialise + truncate a value for inclusion in the trace.

    Keeps trace files readable when nodes pass large payloads through.
    """
    s = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return s if len(s) <= max_chars else s[: max_chars - 1] + "…"


@dataclass
class TraceEvent:
    role: str
    action: str
    input: str = ""
    output: str = ""
    decision: str | None = None
    timestamp: str = field(default_factory=_now)


@dataclass
class RunTrace:
    """An append-only log of TraceEvents for a single Crew run."""

    scenario: str = ""
    events: list[TraceEvent] = field(default_factory=list)

    def record(
        self,
        role: str,
        action: str,
        input: Any = "",
        output: Any = "",
        decision: str | None = None,
    ) -> None:
        self.events.append(
            TraceEvent(
                role=role,
                action=action,
                input=_clip(input),
                output=_clip(output),
                decision=decision,
            )
        )

    def write(self, path: Path | str) -> None:
        Path(path).write_text(
            json.dumps(
                {"scenario": self.scenario, "events": [asdict(e) for e in self.events]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def __len__(self) -> int:
        return len(self.events)
