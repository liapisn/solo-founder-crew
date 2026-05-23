"""Structured run trace for the Part 7 framework spike.

Each candidate implementation must emit the same trace shape so the
Observability criterion is scored on *how easy the framework makes it
to capture this*, not on what each implementation chose to record.

Trace contract (one event per significant step):
  - role:    "marketing" | "founder" | "publisher" | "system"
  - action:  short verb, e.g. "draft", "review", "revise", "publish"
  - input:   inbound payload summary (truncated)
  - output:  outbound payload summary (truncated)
  - decision: optional founder decision: "approve" | "reject" | "kill"
  - timestamp: ISO-8601

Persisted as run_trace.json next to final_announcement.txt.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clip(value: Any, n: int = 400) -> str:
    s = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return s if len(s) <= n else s[: n - 1] + "…"


@dataclass
class TraceEvent:
    role: str
    action: str
    input: str
    output: str
    decision: str | None = None
    timestamp: str = field(default_factory=_now)


@dataclass
class RunTrace:
    scenario: str = "passly_launch"
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

    def write(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {"scenario": self.scenario, "events": [asdict(e) for e in self.events]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
