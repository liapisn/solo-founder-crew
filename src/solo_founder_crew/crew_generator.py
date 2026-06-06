"""Component 3 — Crew Generator.

Given a Venture Brief, decide which roles to instantiate and bind them
to the venture's voice.

Selection is **rule-driven and auditable**: every decision (include
this role / exclude that role) carries a human-readable reason. This
matters because the founder must be able to understand *why* their
crew has these roles and not others — opaque ML-driven selection would
defeat the framework's transparency premise.

The default rule set (``DEFAULT_RULES``) is the framework's opinionated
answer to "what does a solo-founder digital venture need at each
stage?". It's expressible as a table for Ch.3:

  | Role             | When it fires (rule predicate)                |
  |------------------|-----------------------------------------------|
  | marketing        | always                                        |
  | product          | stage in {pre-launch, launched}               |
  | engineering      | always (digital ventures are software)        |
  | customer_support | stage in {launched, growth}                   |
  | sales            | stage in {launched, growth}                   |
  | finance          | stage == growth                               |

Callers can pass their own rules (per-venture overrides, future
industry-specific rule packs).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

from solo_founder_crew.brief import VentureBrief
from solo_founder_crew.role import Role
from solo_founder_crew.roles_library import ROLE_LIBRARY, RoleFactory


# ─── Rule type ───────────────────────────────────────────────────────────────


Predicate = Callable[[VentureBrief], bool]


@dataclass(frozen=True)
class CrewRule:
    """One rule in the Crew Generator's policy.

    Attributes
    ----------
    role_name:
        Key into the ``RoleFactory`` registry (default: ``ROLE_LIBRARY``).
    applies:
        Predicate ``(brief) -> bool`` deciding whether this rule fires
        for the given brief.
    reason:
        Human-readable justification recorded in the audit log whether
        the rule fires or not.
    """

    role_name: str
    applies: Predicate
    reason: str


# ─── Default rules ───────────────────────────────────────────────────────────


def _stage(brief: VentureBrief) -> str:
    return brief.get("stage", "pre-launch")


DEFAULT_RULES: tuple[CrewRule, ...] = (
    CrewRule(
        role_name="marketing",
        applies=lambda b: True,
        reason="Marketing is universal — every venture needs customer-facing copy.",
    ),
    CrewRule(
        role_name="product",
        applies=lambda b: _stage(b) in ("pre-launch", "launched"),
        reason="Pre-launch and launched ventures still need spec and changelog drafting; growth-stage usually has dedicated product hires.",
    ),
    CrewRule(
        role_name="engineering",
        applies=lambda b: True,
        reason="Digital-only ventures are software products; engineering is needed from pre-launch (building the MVP) through growth (extending and maintaining it).",
    ),
    CrewRule(
        role_name="customer_support",
        applies=lambda b: _stage(b) in ("launched", "growth"),
        reason="No customers to support pre-launch; the role activates once the product is in use.",
    ),
    CrewRule(
        role_name="sales",
        applies=lambda b: _stage(b) in ("launched", "growth"),
        reason="A solo founder should not run cold outreach pre-launch — the offer is not ready to qualify against.",
    ),
    CrewRule(
        role_name="finance",
        applies=lambda b: _stage(b) == "growth",
        reason="Bookkeeping load becomes material at growth stage; pre-launch and early-launched founders can do it in batch.",
    ),
)


# ─── Result type ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RuleDecision:
    """Audit-log entry for a single rule evaluation."""

    role_name: str
    selected: bool
    reason: str


@dataclass(frozen=True)
class CrewGenerationResult:
    """The output of ``CrewGenerator.generate()``.

    ``roles`` is what you pass to ``Crew(...)``. ``decisions`` is the
    audit trail — every rule that fired and every rule that did not,
    with the reason captured at generation time. Both are immutable.
    """

    roles: tuple[Role, ...]
    decisions: tuple[RuleDecision, ...]

    def role_names(self) -> tuple[str, ...]:
        return tuple(r.name for r in self.roles)

    def fired(self) -> tuple[RuleDecision, ...]:
        return tuple(d for d in self.decisions if d.selected)

    def skipped(self) -> tuple[RuleDecision, ...]:
        return tuple(d for d in self.decisions if not d.selected)


# ─── Generator ───────────────────────────────────────────────────────────────


@dataclass
class CrewGenerator:
    """Rule-based crew composer.

    Construct with a brief and optionally custom rules / a custom
    registry. ``generate()`` applies every rule in order and returns
    a ``CrewGenerationResult``.

    Order matters: rules are applied in the order given, and the
    resulting role list preserves that order. Phase-4 author flows
    will use the first role by default, so list-order is the seniority
    hint.
    """

    brief: VentureBrief
    rules: Sequence[CrewRule] = field(default_factory=lambda: DEFAULT_RULES)
    registry: dict[str, RoleFactory] = field(
        default_factory=lambda: dict(ROLE_LIBRARY)
    )

    def generate(self) -> CrewGenerationResult:
        roles: list[Role] = []
        decisions: list[RuleDecision] = []
        for rule in self.rules:
            applies = rule.applies(self.brief)
            decisions.append(
                RuleDecision(
                    role_name=rule.role_name,
                    selected=applies,
                    reason=rule.reason,
                )
            )
            if not applies:
                continue
            factory = self.registry.get(rule.role_name)
            if factory is None:
                raise KeyError(
                    f"Rule fired for role {rule.role_name!r} but no factory "
                    f"is registered in the role library "
                    f"(have: {sorted(self.registry)})"
                )
            roles.append(factory(self.brief))
        return CrewGenerationResult(roles=tuple(roles), decisions=tuple(decisions))
