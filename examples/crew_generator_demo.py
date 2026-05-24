"""Crew Generator demo.

Loads the Passly brief, runs the Crew Generator at three different
stages (pre-launch / launched / growth), and prints the audit log so
the rule-fired-or-not decisions are visible.

This is the smallest end-to-end demonstration of Phase 3. It produces
no LLM calls — Crew Generation is deterministic and brief-local.

Run:
    cd solo-founder-crew
    .venv/bin/python examples/crew_generator_demo.py
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from solo_founder_crew import CrewGenerator, VentureBrief

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIEF_PATH = REPO_ROOT / "scenarios" / "fixtures" / "passly_brief.json"


def show(brief: VentureBrief, label: str) -> None:
    result = CrewGenerator(brief=brief).generate()
    stage = brief.get("stage", "pre-launch")
    print(f"\n── {label}  (stage={stage}) ──")
    print(f"  selected roles: {', '.join(result.role_names()) or '(none)'}")
    for d in result.decisions:
        mark = "✓" if d.selected else "·"
        print(f"  {mark} {d.role_name:18s}  — {d.reason}")


def main() -> None:
    passly = VentureBrief.from_file(BRIEF_PATH)

    # Original brief (stage=pre-launch)
    show(passly, "Passly as written")

    # Variant: same brief, stage=launched (synthetic — what the crew would
    # look like once Passly ships and starts taking customers).
    launched_data = deepcopy(passly.as_dict())
    launched_data["stage"] = "launched"
    show(VentureBrief(launched_data), "Passly variant — launched")

    # Variant: stage=growth.
    growth_data = deepcopy(passly.as_dict())
    growth_data["stage"] = "growth"
    show(VentureBrief(growth_data), "Passly variant — growth")


if __name__ == "__main__":
    main()
