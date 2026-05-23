"""Deterministic Mock LLM for the Part 7 framework spike.

Returns canned draft responses keyed on the *intent* in the user message:

- "draft"   → DRAFT_V1 (formal, restrained — what the Marketing role would
              produce on a first pass without founder feedback)
- "revise"  → DRAFT_V2 (warmer, adds a Greek tagline, ≤120 words — what the
              role would produce after the founder's scripted feedback in
              scenarios/fixtures/founder_responses.json)
- anything else → a generic acknowledgement string

The mock counts calls and exposes them for the run trace so the
Observability rubric criterion can be scored on what each framework
makes available, not on how chatty the LLM is.

Why a mock and not real LLM calls:
The Part 7 rubric scores *framework ergonomics*, not LLM output quality.
Three implementations using the same canned outputs make differences in
HITL wiring, role expressiveness, observability, and dev experience
visible without API spend or non-determinism. See docs/spike-charter.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DRAFT_V1 = """\
Introducing Passly — digital wallet passes and AI-assisted marketing
designed for Greek small and medium businesses.

Passly enables café and salon owners to issue loyalty passes and
promotional offers that customers store directly in Apple Wallet or
Google Wallet. No application download is required from the end
customer. The platform provides AI-generated campaign drafts which the
business owner can review and dispatch via SMS or email channels.

Passly is currently in a pre-launch phase. Early-access participation
is available to qualifying Greek SMBs.
"""

DRAFT_V2 = """\
Έρχεται το Passly — και θα σου δώσει πίσω τους πελάτες που ξέχασες ότι έχεις.

Φτιάξε passes επιβράβευσης και προσφορές για το καφέ ή το κομμωτήριό
σου σε λίγα λεπτά. Ζουν μέσα στο Apple ή Google Wallet του πελάτη — δεν
χρειάζεται να κατεβάσει εφαρμογή. Η AI γράφει την καμπάνια, εσύ τη
στέλνεις με δύο κλικ μέσω SMS ή email.

Όλα στα ελληνικά, GDPR-φιλικά, χωρίς ορολογία. Είμαστε σε pre-launch
και ψάχνουμε early-access μαγαζάτορες που θέλουν να το δοκιμάσουν
πρώτοι.

Στο Passly, η επόμενη επίσκεψη του πελάτη ξεκινά από το πορτοφόλι του.
"""

GENERIC_ACK = "Acknowledged."


@dataclass
class MockLLMResponse:
    """Structured response, mirrors the shape downstream adapters need."""

    text: str
    call_index: int
    matched_intent: str  # "draft" | "revise" | "other"


@dataclass
class MockLLM:
    """Pattern-routing mock that pretends to be an LLM.

    Adapters in each spike wrap this to satisfy their framework's LLM
    interface (CrewAI's BaseLLM, LangChain's BaseChatModel, or just a
    direct call for the custom spike).
    """

    model: str = "mock-claude-haiku-4-5"
    calls: list[dict[str, Any]] = field(default_factory=list)

    def complete(self, system: str, user: str) -> MockLLMResponse:
        """One-shot completion. system + user → text.

        Routing rules (case-insensitive on the user prompt):
          - contains "revise" or "feedback" → DRAFT_V2
          - contains "draft" or "announcement" → DRAFT_V1
          - otherwise → GENERIC_ACK
        """
        lowered = user.lower()
        if "revise" in lowered or "feedback" in lowered:
            text, intent = DRAFT_V2, "revise"
        elif "draft" in lowered or "announcement" in lowered:
            text, intent = DRAFT_V1, "draft"
        else:
            text, intent = GENERIC_ACK, "other"

        idx = len(self.calls)
        self.calls.append(
            {
                "call_index": idx,
                "model": self.model,
                "system": system,
                "user": user,
                "output": text,
                "matched_intent": intent,
            }
        )
        return MockLLMResponse(text=text, call_index=idx, matched_intent=intent)

    def reset(self) -> None:
        self.calls.clear()
