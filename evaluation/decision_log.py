"""The per-run decision log, shared by both conditions.

Rubric §7 fixes this schema. Condition F fills it from the framework's
``RunTrace`` and the recording HITL wrapper; Condition B fills it from what the
founder does at the REPL. That asymmetry is itself a finding — nothing in a bare
chat loop produces this record for free, which is what E3/A4 (trace legibility)
measures.

``interaction_count`` (M1) is written into every log from schema version 2 on;
see :data:`SCHEMA_VERSION` for what that means for the runs already archived.

Also here: :func:`render_brief_prose`, which flattens the Venture Brief to the
prose block Condition B receives. Generating it from the same JSON the framework
loads is the only way to claim both conditions saw the same brief content
(rubric §3.2).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
"""2 adds ``interaction_count`` (M1) to the written record.

A ``schema_version`` has to identify a shape, so adding a key bumps it. Logs in
``Ch5_Eval_Runs/`` written before this are version 1 and omit the key; M1 is
``len(founder_interactions)`` there, so nothing is lost and no archived run needs
rewriting to be re-scored.
"""


def now_iso() -> str:
    """Local time with offset, matching the rubric's example timestamps."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Interaction:
    """One discrete act requiring the founder's attention (rubric §6, M1).

    Reading output is not an interaction; acting on it is. ``kind`` is
    ``approve`` | ``reject`` | ``kill`` | ``prompt`` | ``paste_brief`` | ``copy_out``.
    """

    seq: int
    kind: str
    at: str = field(default_factory=now_iso)
    feedback: str | None = None
    chars_typed: int = 0


@dataclass
class GatedAction:
    action: str
    escalated: bool
    resolved: str | None = None


@dataclass
class DecisionLog:
    """One run, either condition. Serialised to one JSON file per run."""

    run_id: str
    scenario: str
    condition: str  # "F" | "B"
    llm: str
    role: str
    timestamp_start: str = field(default_factory=now_iso)
    timestamp_terminal: str | None = None
    termination_path: str | None = None
    turns: int = 0
    founder_interactions: list[Interaction] = field(default_factory=list)
    gated_actions: list[GatedAction] = field(default_factory=list)
    tokens: dict[str, int] = field(default_factory=lambda: {"input": 0, "output": 0})
    llm_latency_s: float = 0.0
    wall_clock_s: float = 0.0
    final_artifact_sha256: str | None = None
    artifact_path: str | None = None
    schema_version: int = SCHEMA_VERSION
    notes: str = ""

    def add(self, kind: str, feedback: str | None = None, chars_typed: int = 0) -> None:
        self.founder_interactions.append(
            Interaction(
                seq=len(self.founder_interactions) + 1,
                kind=kind,
                feedback=feedback,
                chars_typed=chars_typed,
            )
        )

    @property
    def interaction_count(self) -> int:
        """M1 — the headline oversight-effort number."""
        return len(self.founder_interactions)

    def to_dict(self) -> dict[str, Any]:
        """The serialised form, with ``interaction_count`` written explicitly.

        M1 is the headline metric and was absent from the file: ``asdict`` walks
        dataclass fields and a property is not one, so a third party re-scoring
        from a single log had to compute it. It is emitted next to the list it
        summarises.

        Derived here rather than stored as a field on purpose. A stored count is
        a second source of truth that can disagree with
        ``founder_interactions`` — a log claiming M1 = 6 over five recorded
        interactions is worse than a log that makes you count.
        """
        data: dict[str, Any] = {}
        for key, value in asdict(self).items():
            if key == "founder_interactions":
                data["interaction_count"] = self.interaction_count
            data[key] = value
        return data

    def write(self, out_dir: Path) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{self.run_id}.json"
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path


def render_brief_prose(brief: dict[str, Any]) -> str:
    """Flatten the Venture Brief to the prose block Condition B receives.

    Deterministic and total: every field the framework injects into a role's
    system prompt appears here, so the baseline is not quietly starved of
    context. Condition B's disadvantage must come from having no operating
    model, not from having less information.
    """
    d, p, c, v, k = (
        brief.get("domain", {}),
        brief.get("product", {}),
        brief.get("customer", {}),
        brief.get("voice", {}),
        brief.get("constraints", {}),
    )
    bullet = lambda items: "\n".join(f"- {i}" for i in items)  # noqa: E731

    parts = [
        f"VENTURE: {brief.get('name')} ({brief.get('venture_id')}) — stage: {brief.get('stage')}",
        f"Industry: {d.get('industry')}. Geography: {', '.join(d.get('geography', []))}. "
        f"Languages: {', '.join(d.get('language', []))}.",
        "",
        f"WHAT IT IS: {p.get('one_liner')}",
        "Value propositions:",
        bullet(p.get("value_props", [])),
        f"Channels: {', '.join(p.get('channels', []))}.",
        "",
        f"CUSTOMER: {c.get('segment')}",
        "Jobs to be done:",
        bullet(c.get("jobs_to_be_done", [])),
        "Objections they raise:",
        bullet(c.get("objections", [])),
        "",
        f"VOICE: {v.get('tone')}",
        "Do:",
        bullet(v.get("do", [])),
        "Don't:",
        bullet(v.get("dont", [])),
        "",
        f"CONSTRAINTS: budget €{k.get('budget_eur_per_month')}/month.",
        "Out of scope:",
        bullet(k.get("out_of_scope", [])),
        "Compliance:",
        bullet(k.get("compliance_notes", [])),
    ]
    return "\n".join(parts).strip() + "\n"
