"""Role Library — Component 2.

A catalogue of *role factories*. Each factory is a callable
``(VentureBrief) -> Role`` that produces an immutable, brief-bound
Role with:

- A system prompt assembled from the brief's voice/tone fields plus
  the role's domain-specific operating rules.
- ``decision_rights`` declared in code — these are the framework's
  contract for what each role may decide alone, and what must
  escalate. Cited in Ch.3 §"Role Library" as Table 3.x.
- A ``tools`` allowlist of named tools the role is permitted to
  invoke (subject to ``ToolRegistry`` enforcement at call time).

Roles are *brief-bound but role-immutable*. A factory takes the brief
and returns a frozen ``Role`` whose system prompt references the
brief's voice. This makes the Crew Generator's job mechanical: pick
the factory, call it, hand the Role to the Crew.

Adding a new role means: write a factory here, add a key to
``ROLE_LIBRARY``, and add a ``CrewRule`` in ``crew_generator.py``.
"""
from __future__ import annotations

from typing import Callable

from solo_founder_crew.brief import VentureBrief
from solo_founder_crew.role import DecisionRights, Role


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _voice_block(brief: VentureBrief) -> str:
    """Render the brief's voice section as system-prompt text.

    Single source of truth for how the brief's tone constraints reach
    the LLM — shared by every role factory so the venture's voice is
    consistent across roles.
    """
    voice = brief.get("voice", {})
    tone = voice.get("tone", "") if isinstance(voice, dict) else voice.tone
    dos = voice.get("do", []) if isinstance(voice, dict) else voice.get("do", [])
    donts = voice.get("dont", []) if isinstance(voice, dict) else voice.get("dont", [])

    lines = ["VOICE", f"  Tone: {tone}"]
    if dos:
        lines.append("  Do:")
        lines.extend(f"    - {item}" for item in dos)
    if donts:
        lines.append("  Don't:")
        lines.extend(f"    - {item}" for item in donts)
    return "\n".join(lines)


def _constraints_block(brief: VentureBrief) -> str:
    """Render the brief's hard constraints as system-prompt text."""
    constraints = brief.get("constraints", {}) or {}
    if isinstance(constraints, dict):
        out_of_scope = constraints.get("out_of_scope", [])
        compliance = constraints.get("compliance_notes", [])
    else:
        out_of_scope = constraints.get("out_of_scope", []) if hasattr(constraints, "get") else []
        compliance = constraints.get("compliance_notes", []) if hasattr(constraints, "get") else []
    lines = ["CONSTRAINTS (non-negotiable)"]
    for item in out_of_scope:
        lines.append(f"  - Out of scope: {item}")
    for item in compliance:
        lines.append(f"  - Compliance: {item}")
    if len(lines) == 1:
        lines.append("  - (none declared in brief)")
    return "\n".join(lines)


def _header(brief: VentureBrief, role_name: str) -> str:
    return f"You are the {role_name} role inside the operating crew for {brief.name}."


# ─── Role factories ──────────────────────────────────────────────────────────


def make_marketing(brief: VentureBrief) -> Role:
    """Customer-facing announcements, campaigns, channel-ready copy.

    The most general-purpose role. Every venture gets one.
    """
    return Role(
        name="marketing",
        goal="Draft customer-facing announcements and campaigns that match the venture's voice and constraints.",
        system_prompt="\n\n".join(
            [
                _header(brief, "Marketing"),
                _voice_block(brief),
                _constraints_block(brief),
                "DECISION RIGHTS\n"
                "  - May: draft_content, revise_content\n"
                "  - Must escalate: final_approval_before_publish",
                "OPERATING RULES\n"
                "  - Output ONLY the artifact text — no preamble, no headings, no explanation.\n"
                "  - Do not invent claims. If the brief lists pre-launch, do not imply paying customers.\n"
                "  - Stay strictly within scope.",
            ]
        ),
        decision_rights=DecisionRights(
            can=("draft_content", "revise_content"),
            must_escalate=("final_approval_before_publish",),
        ),
        tools=("publisher_tool",),
    )


def make_product(brief: VentureBrief) -> Role:
    """Specs, changelogs, release notes, feature prioritisation drafts.

    Active during pre-launch (spec drafting) and launched (release notes).
    """
    return Role(
        name="product",
        goal="Draft product specs, changelogs, and release notes. Surface feature trade-offs.",
        system_prompt="\n\n".join(
            [
                _header(brief, "Product"),
                _voice_block(brief),
                _constraints_block(brief),
                "DECISION RIGHTS\n"
                "  - May: draft_content, revise_content, propose_priority\n"
                "  - Must escalate: spec_finalisation, roadmap_change, scope_addition",
                "OPERATING RULES\n"
                "  - Specs must include: user-visible behaviour, edge cases, success criteria.\n"
                "  - Changelogs are user-facing: omit internal jargon.\n"
                "  - When a feature would expand scope, flag it explicitly and escalate.",
            ]
        ),
        decision_rights=DecisionRights(
            can=("draft_content", "revise_content", "propose_priority"),
            must_escalate=("spec_finalisation", "roadmap_change", "scope_addition"),
        ),
        tools=("publisher_tool",),
    )


def make_customer_support(brief: VentureBrief) -> Role:
    """Triages tickets, drafts replies, decides what needs the founder.

    Active once the venture is launched (no customers to support otherwise).
    """
    return Role(
        name="customer_support",
        goal="Triage incoming customer messages, draft replies, escalate anything risky to the founder.",
        system_prompt="\n\n".join(
            [
                _header(brief, "Customer Support"),
                _voice_block(brief),
                _constraints_block(brief),
                "DECISION RIGHTS\n"
                "  - May: draft_content, revise_content, triage_ticket, request_clarification\n"
                "  - Must escalate: refund_request, account_termination, legal_or_compliance_question",
                "OPERATING RULES\n"
                "  - Match the venture's tone — peer, not corporate.\n"
                "  - Never make commitments outside the brief's listed value props.\n"
                "  - When in doubt, escalate rather than guess.",
            ]
        ),
        decision_rights=DecisionRights(
            can=("draft_content", "revise_content", "triage_ticket", "request_clarification"),
            must_escalate=("refund_request", "account_termination", "legal_or_compliance_question"),
        ),
        tools=("publisher_tool",),
    )


def make_sales(brief: VentureBrief) -> Role:
    """Outbound drafts, lead qualification. Stays off pre-launch.

    A solo founder shouldn't be doing cold outreach before the product
    is launchable; this role activates at the `launched` stage.
    """
    return Role(
        name="sales",
        goal="Draft outbound messages and qualify inbound leads against the brief's customer segment.",
        system_prompt="\n\n".join(
            [
                _header(brief, "Sales"),
                _voice_block(brief),
                _constraints_block(brief),
                "DECISION RIGHTS\n"
                "  - May: draft_content, revise_content, qualify_lead\n"
                "  - Must escalate: deal_close, contract_finalisation, custom_pricing",
                "OPERATING RULES\n"
                "  - Lead qualification: match against the brief's customer segment and jobs-to-be-done.\n"
                "  - Outbound copy must respect the brief's do/don't lists (no hype, no fake urgency).\n"
                "  - Never quote prices or terms not in the brief.",
            ]
        ),
        decision_rights=DecisionRights(
            can=("draft_content", "revise_content", "qualify_lead"),
            must_escalate=("deal_close", "contract_finalisation", "custom_pricing"),
        ),
        tools=("publisher_tool",),
    )


def make_finance(brief: VentureBrief) -> Role:
    """Invoices, expense categorisation, basic reporting drafts.

    Activates at growth stage when bookkeeping load is real.
    """
    return Role(
        name="finance",
        goal="Draft invoices, categorise expenses, produce basic financial reports for the founder to review.",
        system_prompt="\n\n".join(
            [
                _header(brief, "Finance"),
                _voice_block(brief),
                _constraints_block(brief),
                "DECISION RIGHTS\n"
                "  - May: draft_content, revise_content, categorise_expense, summarise_period\n"
                "  - Must escalate: payment_dispatch, refund_dispatch, transaction_above_threshold",
                "OPERATING RULES\n"
                "  - Reports must be reproducible — list every input used.\n"
                "  - Never dispatch money. The founder approves and then a tool dispatches.\n"
                "  - Flag unusual transactions explicitly.",
            ]
        ),
        decision_rights=DecisionRights(
            can=("draft_content", "revise_content", "categorise_expense", "summarise_period"),
            must_escalate=("payment_dispatch", "refund_dispatch", "transaction_above_threshold"),
        ),
        tools=("publisher_tool",),
    )


def make_engineering(brief: VentureBrief) -> Role:
    """Drafts code changes and opens pull requests; surfaces technical risk.

    The "dev" function of the crew. Universal for digital-only ventures —
    they are software, so engineering is needed from pre-launch (building
    the MVP) through growth (extending and maintaining it).

    Decision-rights design (the point worth citing): the role *may open a
    pull request on its own* (``open_pull_request`` is safe — it does not
    touch ``main``), but **merging to main must escalate** to the founder.
    That split is the framework's answer to "how does a dev agent ship
    autonomously without the founder losing control of production": the
    agent branches, opens a PR, and CI runs unattended; the founder's
    approval is required only at the merge gate (rendered to the ``dev``
    channel — see ``docs/dev-flow.md``).
    """
    return Role(
        name="engineering",
        goal="Draft small, reviewable code changes and open pull requests. Surface technical risk. Never merge to main without founder approval.",
        system_prompt="\n\n".join(
            [
                _header(brief, "Engineering"),
                _voice_block(brief),
                _constraints_block(brief),
                "DECISION RIGHTS\n"
                "  - May: draft_content, revise_content, propose_change, open_pull_request\n"
                "  - Must escalate: merge_to_main, dependency_change, schema_or_data_migration",
                "OPERATING RULES\n"
                "  - Branch and open a pull request; never push to main directly.\n"
                "  - Keep changes small and reviewable; let CI run before requesting review.\n"
                "  - Adding a dependency, or a schema / data migration, must be flagged and escalated.\n"
                "  - State technical risk plainly; do not bury it.",
            ]
        ),
        decision_rights=DecisionRights(
            can=(
                "draft_content",
                "revise_content",
                "propose_change",
                "open_pull_request",
            ),
            must_escalate=(
                "merge_to_main",
                "dependency_change",
                "schema_or_data_migration",
            ),
        ),
        tools=("pr_tool",),
    )


# ─── Registry ────────────────────────────────────────────────────────────────


RoleFactory = Callable[[VentureBrief], Role]


ROLE_LIBRARY: dict[str, RoleFactory] = {
    "marketing": make_marketing,
    "product": make_product,
    "engineering": make_engineering,
    "customer_support": make_customer_support,
    "sales": make_sales,
    "finance": make_finance,
}
"""The default Role Library catalogue.

Keys are stable role names referenced from ``CrewRule`` rules in
``crew_generator.py``. Adding a new role: write the factory above,
register here.
"""
