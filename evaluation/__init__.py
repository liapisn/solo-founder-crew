"""Chapter 5 evaluation harness.

Not part of the framework — this package *uses* ``solo_founder_crew`` to produce
thesis evidence, and ``baseline_repl`` deliberately uses none of it. Run both
entry points as modules from the repo root so the package resolves:

    python -m evaluation.run_condition_f --repeat 3
    python -m evaluation.baseline_repl --scenario S1

Instrument: ``Diplomatic/05_Drafts/Ch5_Evaluation_Rubric.md``.
"""
