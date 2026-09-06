"""Unit tests for the HITLRequest envelope (Component 5).

Covers the Python mirror in ``hitl_request.py`` and its agreement with the
JSON Schema in ``schemas/hitl_request.schema.json`` — the single source of
truth cited in Ch.3 §3.7/§3.8. One test per claim worth defending.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from solo_founder_crew import (
    DEFAULT_OPTIONS,
    Artifact,
    FounderResponse,
    HITLRequest,
    ReviewOption,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "src" / "solo_founder_crew"
SCHEMA_PATH = PACKAGE_ROOT / "schemas" / "hitl_request.schema.json"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator(schema: dict) -> jsonschema.Draft202012Validator:
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def _minimal(**overrides) -> HITLRequest:
    base = dict(
        request_id="r1",
        thread_id="run-1",
        venture_id="passly",
        turn=1,
        role_name="marketing",
        action="final_approval_before_publish",
        artifact=Artifact(content="hello"),
    )
    base.update(overrides)
    return HITLRequest(**base)


# ─── Derived defaults ────────────────────────────────────────────────────────


def test_channel_defaults_to_kebab_cased_role() -> None:
    # snake_case role -> kebab-case logical channel (schema pattern requires it)
    req = _minimal(role_name="customer_support")
    assert req.channel == "customer-support"


def test_role_display_name_defaults_to_title_case() -> None:
    req = _minimal(role_name="customer_support")
    assert req.role_display_name == "Customer Support"


def test_explicit_channel_is_respected() -> None:
    req = _minimal(role_name="marketing", channel="ads-report")
    assert req.channel == "ads-report"


def test_default_options_are_the_canonical_three() -> None:
    actions = [o.action for o in _minimal().options]
    assert actions == ["approve", "reject", "kill"]
    assert DEFAULT_OPTIONS[1].action == "reject"
    assert DEFAULT_OPTIONS[1].requires_feedback is True


# ─── Schema agreement ─────────────────────────────────────────────────────────


def test_minimal_payload_validates(validator) -> None:
    validator.validate(_minimal().to_interrupt_payload())


def test_rich_payload_validates(validator) -> None:
    req = _minimal(
        role_name="customer_support",
        escalation_reason="needs founder sign-off",
        artifact=Artifact(content="draft", summary="refund case"),
        context={"task_description": "handle ticket 42"},
    )
    validator.validate(req.to_interrupt_payload())


def test_payload_omits_unset_optionals_rather_than_nulling_them() -> None:
    # schema is additionalProperties:false / no null — unset optionals must
    # be absent, not present-as-null.
    payload = _minimal().to_interrupt_payload()
    assert "escalation_reason" not in payload
    assert "summary" not in payload["artifact"]
    assert "context" not in payload


# ─── Round-trip ───────────────────────────────────────────────────────────────


def test_payload_round_trips() -> None:
    req = _minimal(
        role_name="finance",
        escalation_reason="why",
        artifact=Artifact(content="body", summary="s"),
        context={"task_description": "t"},
    )
    back = HITLRequest.from_interrupt_payload(req.to_interrupt_payload())
    assert back.request_id == req.request_id
    assert back.thread_id == req.thread_id
    assert back.venture_id == req.venture_id
    assert back.turn == req.turn
    assert back.role_name == "finance"
    assert back.channel == "finance"
    assert back.action == req.action
    assert back.escalation_reason == "why"
    assert back.artifact.content == "body"
    assert back.artifact.summary == "s"
    assert [o.action for o in back.options] == ["approve", "reject", "kill"]


def test_with_artifact_returns_a_copy_carrying_new_content() -> None:
    req = _minimal()
    revised = req.with_artifact("revised body", summary="v2")
    assert revised.artifact.content == "revised body"
    assert revised.artifact.summary == "v2"
    # original untouched (frozen dataclass)
    assert req.artifact.content == "hello"
    assert revised.request_id == req.request_id


def test_option_lookup() -> None:
    req = _minimal()
    assert req.option_for("reject").requires_feedback is True
    assert req.option_for("nope") is None


# ─── FounderResponse ───────────────────────────────────────────────────────────


def test_founder_response_maps_to_decision() -> None:
    resp = FounderResponse(request_id="r1", action="reject", feedback="warmer")
    decision = resp.to_decision()
    assert decision.action == "reject"
    assert decision.feedback == "warmer"


def test_founder_response_validates_against_schema(validator, schema) -> None:
    sub = jsonschema.Draft202012Validator(schema["$defs"]["FounderResponse"])
    sub.validate({"request_id": "r1", "action": "approve"})
    sub.validate({"request_id": "r1", "action": "reject", "feedback": "x"})


def test_custom_options_round_trip() -> None:
    req = _minimal(
        options=(
            ReviewOption(action="approve", label="Ship it"),
            ReviewOption(action="kill", label="Abort"),
        )
    )
    back = HITLRequest.from_interrupt_payload(req.to_interrupt_payload())
    assert [(o.action, o.label) for o in back.options] == [
        ("approve", "Ship it"),
        ("kill", "Abort"),
    ]
