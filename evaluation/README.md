# Chapter 5 evaluation harness

Runs the two conditions the thesis compares. The instrument — dimensions,
anchors, scenario set, scoring procedure, validity threats — lives in
[`Diplomatic/05_Drafts/Ch5_Evaluation_Rubric.md`](../../Diplomatic/05_Drafts/Ch5_Evaluation_Rubric.md).
This directory is only the machinery.

**Freeze the rubric before the first scored run.** Its pre-registration has no
external witness (the supervisor engages once, on the written draft), so the git
commit order *is* the evidence that the instrument predates the data. A frozen
rubric committed before any run in `Ch5_Eval_Runs/` is the claim; a rubric edited
afterwards is not.

## Run it

```bash
# from the repo root, with the venv active

# Condition F, deterministic — no API key, no cost. The E4a reading.
python -m evaluation.run_condition_f --repeat 3

# Condition F, live — the 10 scored runs
python -m evaluation.run_condition_f --live

# Condition B, live — one scenario at a time, by hand
python -m evaluation.baseline_repl --scenario S1
```

Output goes to `Diplomatic/05_Drafts/Ch5_Eval_Runs/` (override with `--out`):
one decision log per run, `artifacts/<run_id>.txt`, `traces/<run_id>.trace.json`,
and a `summary_F_*.json` carrying the Panel B readings.

## The two conditions

**Condition F** (`run_condition_f.py`) drives the Author Flow with the role taken
from the **Role Library** (`make_marketing`), not an inline `Role` — the
evaluation has to exercise Component 2 as shipped. `RecordingHITL` replays each
scenario's scripted decisions while writing them into the decision log; it is a
third implementation of the `HITLContract` seam, written without touching
`Crew`, `Role` or tool code, which is itself §3.8 evidence.

**Condition B** (`baseline_repl.py`) is a bare chat loop: one thread, one model,
no roles, no decision rights, no escalation, no trace, no gate. **It imports
nothing from `solo_founder_crew`** — not the LLM class, not the dotenv helper.
If the baseline shared framework code, "no framework" would be a claim the code
contradicts. The only shared things are data: the same brief JSON, the same
scenario definitions.

Both call `claude-haiku-4-5` with `max_tokens=1024`, matching `AnthropicLLM`'s
defaults. This is deliberate and load-bearing: a consumer chat app serves a
stronger model and cannot be pinned, so any difference would be attributable to
the model rather than to the operating model — the confound rubric §3.2 exists to
prevent.

## Reading M1 (founder oversight effort)

A *founder interaction* is any discrete act needing the founder's attention:
one approve, one reject-with-feedback, one prompt typed, one brief pasted, one
copy-out. Reading output is not an interaction; acting on it is.

Condition B accrues two kinds that Condition F does not:

- `paste_brief` — the framework injects the Venture Brief automatically every
  run; without a schema the founder re-supplies it per session. Counted as
  **one** interaction, not 400 keystrokes.
- `copy_out` — the framework's `publisher_tool` fires on approve; the baseline
  founder moves the text by hand.

That gap *is* what M1 measures. It is not an artefact of the harness.

## The revision cap

`MAX_REVISIONS = 3`, uniform across scenarios. The runtime routes a rejection to
*revise* while `turn <= max_revisions` and to *exhausted* otherwise
(`runtime.py:_route_after_hitl`), so four gates precede exhaustion and S10 carries
**four** rejections. `tests/test_evaluation_harness.py` asserts every scenario's
script agrees with the cap — a mismatch discovered during the live runs would
cost real calls and a discarded run.

## Editing scenarios

`scenarios.py` is the single definition both conditions read. Two properties
break quietly if you edit carelessly:

1. Founder feedback strings must stay **identical across conditions** — they are
   data here, not prose inlined into either runner.
2. Every rejection needs non-empty feedback, or A3 (feedback honouring) becomes
   unscorable for that scenario.

Both are asserted by the tests.

`scenarios/fixtures/founder_responses.json` is deliberately **untouched**: it is
S1's canonical fixture, consumed by `examples/passly_launch.py` and the existing
tests. The ten-scenario scripts live here instead so the worked example keeps
working.
