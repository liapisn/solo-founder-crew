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

# Condition B, live — scripted replay, the way the scored runs are produced
python -m evaluation.run_condition_b --scenarios S1,S2

# Condition B, live — the interactive REPL, one scenario at a time
python -m evaluation.baseline_repl --scenario S1
```

Output goes to `Diplomatic/05_Drafts/Ch5_Eval_Runs/` (override with `--out`):
one decision log per run, `artifacts/<run_id>.txt`, `traces/<run_id>.trace.json`,
and a `summary_F_*.json` / `summary_B_live.json` carrying the Panel B readings.

`drafts/<run_id>.txt` holds the last draft of a run that ended **killed** or
**exhausted**. M3 asks whether the adversarial probes were refused or absorbed
and it is comparative: Condition F keeps its draft in the `RunTrace` even when
the run is killed, so the baseline has to keep one too. It is deliberately not
`artifacts/`, which stays exactly the shipped set the blinded Panel A reads.

## The two conditions

**Condition F** (`run_condition_f.py`) drives the Author Flow with the role taken
from the **Role Library** (`make_marketing`), not an inline `Role` — the
evaluation has to exercise Component 2 as shipped. `RecordingHITL` replays each
scenario's scripted decisions while writing them into the decision log; it is a
third implementation of the `HITLContract` seam, written without touching
`Crew`, `Role` or tool code, which is itself §3.8 evidence.

**Condition B** is a bare chat loop: one thread, one model, no roles, no decision
rights, no escalation, no trace, no gate. **It imports nothing from
`solo_founder_crew`** — not the LLM class, not the dotenv helper. If the baseline
shared framework code, "no framework" would be a claim the code contradicts. The
only shared things are data: the same brief JSON, the same scenario definitions.

It has two entry points that produce the same log:

- `run_condition_b.py` — scripted replay, and how the scored runs are produced.
  Sends exactly what the REPL's `/brief`, `/task` and `/next` send, in the same
  order. A run produced here and a run produced by hand are indistinguishable in
  the archive.
- `baseline_repl.py` — the interactive loop. `/brief`, `/task` and `/next` send
  fixed content verbatim, so nothing is transcribed by hand here either; see
  *Nothing is typed* below.

`run_condition_b.py` does not import `run_condition_f` — that module pulls the
framework in transitively — so its similarity helper is duplicated deliberately.

Both call `claude-haiku-4-5` with `max_tokens=1024`, matching `AnthropicLLM`'s
defaults. This is deliberate and load-bearing: a consumer chat app serves a
stronger model and cannot be pinned, so any difference would be attributable to
the model rather than to the operating model — the confound rubric §3.2 exists to
prevent.

## Nothing is typed

Six of the first nine baseline attempts were discarded for operator slips
rather than model failures, each costing live calls: a terminal command sent
before the task, `/nex` reaching the model as a prompt (which inflated M1 by one
*against* the baseline), a task pasted one character short, an operator answering
the model instead of sending the scripted rejection. So the REPL now supplies
every fixed string itself:

| Command | Sends |
|---|---|
| `/brief` | the Venture Brief prose, one `paste_brief` interaction |
| `/task` | `scenario.task`, verbatim, one `prompt` interaction |
| `/next` | the next scripted decision — the exact feedback string for a rejection, or `/approve`, `/kill`, `/stop` |

A run is `/brief`, `/task`, `/next`, `/next` … with nothing transcribed. Two
guards back that up: `/next` and the terminal commands are refused until the
brief *and* the task have been sent, and any input starting with `/` that is not
a known command is refused and never sent. Nothing in this protocol legitimately
starts with `/`. Both are operator guards, not part of the instrument — they
change no scenario, no prompt, no model setting and no interaction accounting.

The task check reads "has a `prompt` interaction been logged", not "is there a
reply on screen". `/brief` is itself a message to the model, so it produces a
reply on its own; the guard's first version tested that reply and so passed the
moment the brief was sent, which let `/brief` `/approve` ship the model's answer
*to the brief* as the artefact with no task ever sent. That is the slip the guard
was added for, and it took a test to notice it was still open.

The final rejection of an *exhausted* scenario maps to `/stop` rather than being
sent as a prompt; sending it would produce a fifth draft and overshoot the cap
Condition F enforces.

`DecisionLog` records the prompt text, not just `chars_typed`. Length matching is
not provenance — S1-B-01's 110 and 161 happen to agree — and §8 step 7 asks for
independent re-scorability.

**This weakens rubric §3.2 as written.** It pre-registers Condition B as
performed by the author, which was true when the operator transcribed the brief,
the task and every feedback string. Nothing is left for a human to get right, so
§3.2 needs amending before the rubric freezes. M2 is read from `llm_latency_s`
(model time only) in both conditions, so none of this changes a reported number;
`wall_clock_s` is still written but under a scripted replay measures the script.

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
