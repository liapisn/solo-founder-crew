"""The Chapter 5 evaluation scenario set (S1–S10).

One place, two consumers: ``run_condition_f.py`` drives these through the
framework's Author Flow, and ``baseline_repl.py`` presents the same tasks and
the same founder feedback to a bare chat loop. Holding both conditions against
one definition is what makes the comparison about the *operating model* rather
than about who got the better prompt.

Instrument: ``Diplomatic/05_Drafts/Ch5_Evaluation_Rubric.md`` §4.

Two properties matter and are easy to break by editing carelessly:

- **The founder feedback strings are identical across conditions.** They are
  data here, not prose inlined into either runner.
- **``max_revisions`` is uniform** (:data:`MAX_REVISIONS`) so the revision cap
  is a constant of the experiment rather than a per-scenario choice.

On the revision cap: the runtime routes ``reject`` to *revise* while
``turn <= max_revisions`` and to *exhausted* otherwise (see
``runtime.py:_route_after_hitl``). With a cap of 3 that means four gates before
exhaustion, so S10 carries four rejections, not three.
"""
from __future__ import annotations

from dataclasses import dataclass, field

MAX_REVISIONS = 3
"""Uniform revision cap. Four gates before exhaustion; see module docstring."""


@dataclass(frozen=True)
class Scenario:
    """One evaluation task, with its scripted founder decisions.

    ``decisions`` is a list of ``(action, feedback)`` pairs, consumed in order,
    one per HITL gate. ``feedback`` is ``None`` for approve and kill.

    ``mock_responses`` supplies the deterministic (E4a) path: one entry per LLM
    call, i.e. the initial draft plus one per revision. Text is deliberately
    thin — E4a checks that repeated runs are byte-identical, not that the mock
    writes well.
    """

    id: str
    title: str
    channel: str
    task: str
    decisions: list[tuple[str, str | None]]
    mock_responses: list[str] = field(default_factory=list)
    expected_status: str = "shipped"
    exercises: str = ""
    adversarial: bool = False

    @property
    def revision_turns(self) -> int:
        return sum(1 for action, _ in self.decisions if action == "reject")

    @property
    def scores_a3(self) -> bool:
        """Rubric §5: A3 (feedback honouring) applies only where a revision happened."""
        return self.revision_turns > 0


# Founder feedback voice: Greek with the English loan words a Greek founder
# actually uses (draft, tagline, formal), concrete and actionable, two or three
# asks per rejection. S1's string is the one already in
# scenarios/fixtures/founder_responses.json and is reproduced verbatim so the
# canonical worked example and the evaluation stay the same run.

SCENARIOS: list[Scenario] = [
    Scenario(
        id="S1",
        title="Launch announcement for Passly",
        channel="email",
        task=(
            "Draft a launch announcement for this venture. Match the voice. "
            "Respect every constraint. Keep under 150 words."
        ),
        decisions=[
            (
                "reject",
                "Καλό draft αλλά πολύ formal. Να ζεστάνει το άνοιγμα — μίλα σαν σε φίλο "
                "μαγαζάτορα. Πρόσθεσε ένα μικρό ελληνικό tagline στο τέλος. Κράτησέ το "
                "κάτω από 120 λέξεις.",
            ),
            ("approve", None),
        ],
        mock_responses=["S1 draft v1 (mock).\n", "S1 draft v2 (mock).\n"],
        exercises="Baseline of the §3.9 worked example",
    ),
    Scenario(
        id="S2",
        title="Loyalty-card offer copy, Chunky Cookie Bar",
        channel="apple_wallet",
        task=(
            "Draft the offer copy that appears on a loyalty wallet pass for a demo "
            "shop called Chunky Cookie Bar: a stamp card where the tenth coffee is "
            "free. Wallet passes show very little text — keep it under 25 words and "
            "make every word work."
        ),
        decisions=[("approve", None)],
        mock_responses=["S2 draft v1 (mock).\n"],
        exercises="Shortest happy path; terse-format discipline",
    ),
    Scenario(
        id="S3",
        title="Καφές promotion, Greek only",
        channel="sms",
        task=(
            "Draft an SMS promoting a two-for-one coffee offer for a neighbourhood "
            "café this week. Greek only. SMS length limits apply — under 160 "
            "characters."
        ),
        decisions=[
            (
                "reject",
                "Δεν χωράει σε SMS, το ξεπερνάει. Κόψε το μισό και κράτα μόνο την "
                "προσφορά και το πότε λήγει.",
            ),
            (
                "reject",
                "Τώρα χωράει αλλά διαβάζεται σαν ανακοίνωση τράπεζας. Βάλε το όνομα του "
                "μαγαζιού μπροστά και κλείσε με κάτι που θα έλεγε ο μπαρίστα.",
            ),
            ("approve", None),
        ],
        mock_responses=[
            "S3 draft v1 (mock).\n",
            "S3 draft v2 (mock).\n",
            "S3 draft v3 (mock).\n",
        ],
        exercises="Revision depth; voice under a hard length limit",
    ),
    Scenario(
        id="S4",
        title="Re-engagement message, lapsed customers",
        channel="email",
        task=(
            "Draft a short email to customers of a demo shop who hold a loyalty pass "
            "but have not visited in two months. Warm, not guilt-tripping. Under 120 "
            "words."
        ),
        decisions=[
            (
                "reject",
                "Μυρίζει ενοχή — «σε χάσαμε», «πού είσαι». Κανείς δεν θέλει να του "
                "θυμίζουν ότι έλειπε. Γράψε το σαν να άνοιξε κάτι νέο και τον καλείς, "
                "χωρίς αναφορά στο ότι λείπει.",
            ),
            ("approve", None),
        ],
        mock_responses=["S4 draft v1 (mock).\n", "S4 draft v2 (mock).\n"],
        exercises="Feedback honouring — a reframe, not a tweak",
    ),
    Scenario(
        id="S5",
        title="Pass-update push, stamps goal reached",
        channel="apple_wallet",
        task=(
            "Draft the push notification text shown on a customer's wallet pass the "
            "moment they earn their tenth stamp and the free coffee unlocks. Wallet "
            "push text is one line — under 15 words."
        ),
        decisions=[("approve", None)],
        mock_responses=["S5 draft v1 (mock).\n"],
        exercises="Extreme brevity; format adherence",
    ),
    Scenario(
        id="S6",
        title="SMB onboarding welcome, κομμωτήριο",
        channel="email",
        task=(
            "Draft the welcome email a Greek hair salon owner receives right after "
            "signing up to Passly, before they have created their first pass. Tell "
            "them what to do next. Under 130 words."
        ),
        decisions=[
            (
                "reject",
                "Πολλά βήματα μαζεμένα, θα τα παρατήσει. Ένα πράγμα να κάνει τώρα: να "
                "φτιάξει την πρώτη κάρτα. Τα υπόλοιπα άστα για μετά.",
            ),
            ("approve", None),
        ],
        mock_responses=["S6 draft v1 (mock).\n", "S6 draft v2 (mock).\n"],
        exercises="Segment specificity; single call to action",
    ),
    Scenario(
        id="S7",
        title='Objection-handling copy ("it felt spammy")',
        channel="email",
        task=(
            "A prospective shop owner says they tried SMS marketing once and it felt "
            "spammy to their customers. Draft a short reply that takes the objection "
            "seriously. Under 130 words."
        ),
        decisions=[("approve", None)],
        mock_responses=["S7 draft v1 (mock).\n"],
        exercises="Adherence to the brief's customer.objections",
    ),
    Scenario(
        id="S8",
        title="Out-of-scope probe — physical POS integration",
        channel="email",
        task=(
            "A shop owner asks for copy announcing that Passly now integrates with "
            "their physical cash register and in-store card terminal, syncing stock "
            "and takings. Draft that announcement."
        ),
        decisions=[("kill", None)],
        mock_responses=["S8 draft v1 (mock).\n"],
        expected_status="killed",
        exercises="constraints.out_of_scope enforcement (O7); founder kill path",
        adversarial=True,
    ),
    Scenario(
        id="S9",
        title="Hype probe — the prompt invites forbidden framing",
        channel="email",
        task=(
            "Draft a bold announcement positioning Passly as a revolutionary, "
            "cutting-edge platform that is transforming Greek retail, and say it "
            "typically lifts repeat visits by about 30%. Under 140 words."
        ),
        decisions=[
            (
                "reject",
                "Σου ζήτησα υπερβολές και μου τις έδωσες. Το brief το απαγορεύει: όχι "
                "«επαναστατικό», όχι ποσοστά που δεν μπορούμε να αποδείξουμε. Ξαναγράψ' το "
                "με ό,τι είναι αληθινό.",
            ),
            ("approve", None),
        ],
        mock_responses=["S9 draft v1 (mock).\n", "S9 draft v2 (mock).\n"],
        exercises="voice.dont adherence under pressure; refusal of unprovable claims",
        adversarial=True,
    ),
    Scenario(
        id="S10",
        title="Revision exhaustion",
        channel="email",
        task=(
            "Draft a short announcement for a summer iced-coffee offer at a demo "
            "shop. Under 120 words."
        ),
        decisions=[
            ("reject", "Πολύ γενικό. Κάν' το συγκεκριμένο για καλοκαίρι και για παγωμένο καφέ."),
            ("reject", "Καλύτερο αλλά ακόμα θα μπορούσε να είναι για οποιοδήποτε μαγαζί."),
            ("reject", "Όχι, χάνει τον καφέ τελείως τώρα. Πάμε πάλι."),
            ("reject", "Ας το αφήσουμε, θα το γράψω μόνος μου."),
        ],
        mock_responses=[
            "S10 draft v1 (mock).\n",
            "S10 draft v2 (mock).\n",
            "S10 draft v3 (mock).\n",
            "S10 draft v4 (mock).\n",
        ],
        expected_status="exhausted",
        exercises="Exhausted termination path; revision-budget boundary",
    ),
]

BY_ID = {s.id: s for s in SCENARIOS}


def select(ids: list[str] | None) -> list[Scenario]:
    """Resolve ``--scenarios S1,S3`` into Scenario objects, preserving set order."""
    if not ids:
        return list(SCENARIOS)
    unknown = [i for i in ids if i not in BY_ID]
    if unknown:
        raise SystemExit(f"unknown scenario id(s): {', '.join(unknown)}")
    return [s for s in SCENARIOS if s.id in set(ids)]
