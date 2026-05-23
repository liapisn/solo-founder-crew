"""Deterministic stub LLM for the Part 7 framework spike.

Honest framing
--------------
The Part 7 rubric scores **framework ergonomics**, not LLM output quality.
HITL ergonomics, role parameterisation, observability, dev experience —
none of these depend on what the model returns. The LLM is wallpaper.

So this stub doesn't try to be smart. It returns canned responses in
the order the caller supplied them. The caller (each spike adapter)
explicitly pre-loads `[DRAFT_V1, DRAFT_V2]` and we trust each candidate
framework to make exactly two role calls. If a framework makes an
unexpected extra call, the queue raises — and that's a useful signal
about framework chattiness, not a bug.

The canned drafts (DRAFT_V1 formal, DRAFT_V2 warmer + Greek tagline)
exist so the spike produces a worked example we can quote in Ch.3, not
because the routing matters.

The optional real-LLM path lives behind a separate `RealLLM` client
that satisfies the same Protocol (added when the first spike needs it).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


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

# Default response queue every spike pre-loads.
DEFAULT_RESPONSES: list[str] = [DRAFT_V1, DRAFT_V2]


@dataclass
class LLMResponse:
    text: str
    call_index: int


class LLMClient(Protocol):
    """Minimal LLM surface every spike adapter targets.

    Both MockLLM and (later) RealLLM satisfy this. Adapters in each
    candidate framework wrap this Protocol to fit their framework's
    expected LLM interface (CrewAI BaseLLM, LangChain BaseChatModel, etc.).
    """

    def complete(self, system: str, user: str) -> LLMResponse: ...


@dataclass
class MockLLM:
    """Pre-loaded response queue.

    Usage:
        llm = MockLLM(responses=[DRAFT_V1, DRAFT_V2])
        r1 = llm.complete(system=..., user=...)  # -> DRAFT_V1
        r2 = llm.complete(system=..., user=...)  # -> DRAFT_V2
        r3 = llm.complete(...)                   # -> raises QueueExhausted

    If a framework makes an unexpected extra LLM call, the exhaustion
    is the diagnostic — not a silent fallback. That goes in the
    scorecard under "Observability" / "Dev experience".
    """

    responses: list[str] = field(default_factory=lambda: list(DEFAULT_RESPONSES))
    model: str = "mock-claude-haiku-4-5"
    calls: list[dict[str, Any]] = field(default_factory=list)

    def complete(self, system: str, user: str) -> LLMResponse:
        idx = len(self.calls)
        if idx >= len(self.responses):
            raise QueueExhausted(
                f"MockLLM queue exhausted after {idx} call(s). "
                f"Spike expected exactly {len(self.responses)} LLM call(s). "
                f"Last user prompt: {user[:120]!r}"
            )
        text = self.responses[idx]
        self.calls.append(
            {
                "call_index": idx,
                "model": self.model,
                "system": system,
                "user": user,
                "output": text,
            }
        )
        return LLMResponse(text=text, call_index=idx)

    def reset(self) -> None:
        self.calls.clear()


class QueueExhausted(RuntimeError):
    """Raised when a spike makes more LLM calls than the queue holds."""
