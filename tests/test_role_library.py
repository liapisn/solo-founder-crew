"""Tests for the Role Library catalogue and the Crew Generator algorithm."""
from __future__ import annotations

from copy import deepcopy

import pytest

from solo_founder_crew import (
    CrewGenerator,
    CrewRule,
    DEFAULT_RULES,
    ROLE_LIBRARY,
    Role,
    VentureBrief,
    make_customer_support,
    make_finance,
    make_marketing,
    make_product,
    make_sales,
)


# ─── Role Library catalogue ──────────────────────────────────────────────────


def test_role_library_has_five_factories() -> None:
    assert set(ROLE_LIBRARY) == {
        "marketing",
        "product",
        "customer_support",
        "sales",
        "finance",
    }


@pytest.mark.parametrize(
    "factory,name,must_escalate",
    [
        (make_marketing, "marketing", "final_approval_before_publish"),
        (make_product, "product", "spec_finalisation"),
        (make_customer_support, "customer_support", "refund_request"),
        (make_sales, "sales", "deal_close"),
        (make_finance, "finance", "payment_dispatch"),
    ],
)
def test_role_factories_produce_expected_role(
    brief: VentureBrief, factory, name: str, must_escalate: str
) -> None:
    role: Role = factory(brief)
    assert role.name == name
    assert must_escalate in role.decision_rights.must_escalate
    # System prompt embeds the venture's name + voice
    assert brief.name in role.system_prompt
    assert brief.voice.tone in role.system_prompt


def test_marketing_role_can_draft_and_revise(brief: VentureBrief) -> None:
    role = make_marketing(brief)
    assert role.may_perform("draft_content")
    assert role.may_perform("revise_content")
    assert not role.may_perform("publish")


def test_factories_produce_immutable_roles(brief: VentureBrief) -> None:
    """The same factory called twice with the same brief produces
    equal but independently frozen Role instances."""
    a = make_marketing(brief)
    b = make_marketing(brief)
    assert a == b  # frozen dataclasses with identical fields are equal


# ─── Crew Generator — DEFAULT_RULES at each stage ────────────────────────────


def _brief_at_stage(brief: VentureBrief, stage: str) -> VentureBrief:
    """Synthesise a brief variant at a different stage."""
    data = deepcopy(brief.as_dict())
    data["stage"] = stage
    return VentureBrief(data)


def test_pre_launch_crew(brief: VentureBrief) -> None:
    """Default Passly brief is stage='pre-launch'."""
    result = CrewGenerator(brief=brief).generate()
    assert result.role_names() == ("marketing", "product")
    assert {d.role_name for d in result.fired()} == {"marketing", "product"}
    assert {d.role_name for d in result.skipped()} == {
        "customer_support",
        "sales",
        "finance",
    }


def test_launched_crew(brief: VentureBrief) -> None:
    result = CrewGenerator(brief=_brief_at_stage(brief, "launched")).generate()
    assert result.role_names() == (
        "marketing",
        "product",
        "customer_support",
        "sales",
    )
    assert "finance" in {d.role_name for d in result.skipped()}


def test_growth_crew(brief: VentureBrief) -> None:
    result = CrewGenerator(brief=_brief_at_stage(brief, "growth")).generate()
    # Product drops out at growth (dedicated hires assumed); finance enters.
    assert result.role_names() == (
        "marketing",
        "customer_support",
        "sales",
        "finance",
    )
    assert "product" in {d.role_name for d in result.skipped()}


def test_audit_log_captures_reasons(brief: VentureBrief) -> None:
    result = CrewGenerator(brief=brief).generate()
    # Every default rule produces exactly one decision entry.
    assert len(result.decisions) == len(DEFAULT_RULES)
    for d in result.decisions:
        assert d.reason  # never empty


# ─── Custom rules override ───────────────────────────────────────────────────


def test_custom_rules_override_defaults(brief: VentureBrief) -> None:
    """Callers can supply their own rule set — e.g. a fintech wanting
    finance from day one."""
    fintech_rules = (
        CrewRule(
            role_name="marketing",
            applies=lambda b: True,
            reason="Always.",
        ),
        CrewRule(
            role_name="finance",
            applies=lambda b: True,  # finance from pre-launch
            reason="Fintech ventures need finance role immediately.",
        ),
    )
    result = CrewGenerator(brief=brief, rules=fintech_rules).generate()
    assert result.role_names() == ("marketing", "finance")


def test_unknown_role_in_rule_raises(brief: VentureBrief) -> None:
    bad_rule = (
        CrewRule(role_name="not_in_library", applies=lambda b: True, reason="x"),
    )
    with pytest.raises(KeyError, match="not_in_library"):
        CrewGenerator(brief=brief, rules=bad_rule).generate()
