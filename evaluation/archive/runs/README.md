# Ch.5 evaluation runs

**The harness is the authority.** `solo-founder-crew/evaluation/` holds the
scenario set, both condition runners, and the decision-log schema. This folder is
where its output lands — one decision log per run, `artifacts/<run_id>.txt`,
`traces/<run_id>.trace.json`, and `summary_F_*.json`.

```bash
python -m evaluation.run_condition_f --repeat 3   # E4a, deterministic, no key
python -m evaluation.run_condition_f --live       # the 10 scored F runs
python -m evaluation.baseline_repl --scenario S1  # Condition B, one at a time
```

## What is authoritative where

| Question | Answer lives in |
|---|---|
| Dimensions, anchors, weights, scoring procedure, validity threats | `Ch5_Evaluation_Rubric.md` (frozen v1.0, `f6f3be2`) |
| Scenario tasks, founder decision scripts, revision cap | `evaluation/scenarios.py` |
| What a founder interaction is; decision-log schema | `evaluation/decision_log.py`, `evaluation/README.md` |
| The prose brief Condition B receives | `render_brief_prose()` — generated, not hand-written |

Nothing here should restate any of the above. A second copy of the control is
worse than no copy: it looks authoritative and drifts silently.

## Scope, from the frozen rubric

47 runs. 20 live-scored (10 scenarios x F/B), plus E4 determinism re-runs on the
fixed **S2, S3, S8** subset — 18 Condition F, 9 Condition B. E4a is Condition F
only: `baseline_repl.py` imports nothing from the framework and has no `MockLLM`
path, so Condition B's determinism evidence is E4b, reported and not gated.

**Nothing is scored until all 47 runs are complete** (rubric §8 step 2).

## Two scoring decisions, fixed before any run

Neither is in the rubric or the harness; both would otherwise be improvised
during scoring, which is what pre-registration exists to prevent.

**1. A1's voice referent.** S2, S5 and S7 produce copy aimed at an SMB's *own
customers*, while the brief's `voice` block is Passly's. Governing reading: all
copy is authored by Passly in its house voice, on the shop's behalf. A1's
"concrete SMB examples" therefore means *concrete detail specific to this SMB*,
not *examples of different SMB types*. A reading of the frozen anchor, not a
change to it — rubric §5 is untouched.

**2. M3 is read from the turn-1 draft.** S8 and S9 both invite a violation that
the scripted founder response then corrects, so reading M3 from the approved
artefact would score the founder rather than the condition, and both conditions
would pass. The measurement is whether the first draft took the bait. Rubric §6
sources M3 from "S8, S9 outputs"; this fixes that to the turn-1 output. The
harness does not compute M3 — it is a manual read off the artefacts.

## Harness change during the run phase

`baseline_repl.py` changed twice on 2026-08-20, after Condition F was already
complete and after two valid Condition B runs (S1-B-01, S2-B-01).

- `dfb8869` — `/approve`, `/kill` and `/stop` are refused while the brief has not
  been sent or no draft exists.
- `dd45ada` — `/next` plays the scenario's next scripted decision itself, and the
  decision log now records the prompt text rather than only its length.
- `f2e13c6` — an input starting with `/` that is not a known command is refused
  rather than sent to the model.

Recorded here because a harness edit mid-run phase is the sort of thing that
should be declared rather than discovered. It changes no scenario, no prompt, no
model setting and no interaction accounting — it declines to *record* a run the
rubric would require discarding. **Five** early baseline attempts were discarded
and are in `_superseded/discarded_runs/`, one directory each *(corrected
2026-08-29: this paragraph said four and listed four reasons, omitting the typo
run; rubric §12 carries the correction)*: `S1-B-01.json`, approved on the first
draft without playing the scripted rejection; `attempt2/`, approved before the
task was sent; `S2_no_brief/`, the brief never sent; `S3_unscripted/`, answering
the model's own suggestion instead of either scripted rejection; and `S3_typo/`,
where a mistyped `/nex/next` reached the model as a stray prompt — the discard
that motivated `f2e13c6`, and the one that inflated M1 against the baseline.

`/next` is the load-bearing one. Until it existed, the identical-strings-across-
conditions property rested on the operator retyping Greek correctly, and the log
recorded only how many characters were typed, never which. S1-B-01 and S2-B-01
are verifiable only because their `chars_typed` (110/161, 232) match the scripted
lengths exactly — sound, but circumstantial. Every run from S3 onward carries the
text itself.

## `_superseded/`

Prep materials written 2026-08-17 to 2026-08-20, before the `solo-founder-crew`
repo was reachable from the drafting session. They were extrapolated from the
rubric and duplicated work `evaluation/` had already done properly: a second
scenario set with different founder strings, a Condition B protocol assuming a
generic chat app rather than `baseline_repl.py`, and blank decision logs that
would have collided with harness output in this very directory.

Kept rather than deleted because the reasoning in them produced the rubric
corrections that preceded the freeze, and because a visibly superseded artefact
is safer than one silently removed. **Do not run anything from it.**

## Operator of record — superseded 2026-08-20

Before the freeze I recorded that Condition B would be executed by hand by the
author, on the grounds that M1 and M2 read human effort and elapsed time. That
reasoning was already weaker than it looked: `render_brief_prose()` had always
generated the brief prose, which is the one conversion rubric §3.2 explicitly
costs and times. Three operator guards and two new commands (`/task`, `/next`)
then removed the remaining transcription, and at that point "by hand" protected
nothing — five of the first eight attempts had been discarded for protocol slips
*(corrected 2026-08-29 from "six of the first nine"; see rubric §12)*, each
costing live calls.

The scored set is therefore produced by `evaluation/run_condition_b.py`, which
sends exactly what `/brief`, `/task` and `/next` send, in the same order.

**What this does and does not change.**

- **M1 is unaffected.** It counts interactions, and the count is fixed by the
  protocol, not by who presses the key.
- **M2 is read from `llm_latency_s`** — model time only — in both conditions.
  `run_condition_f` already reported `m2_llm_latency_s_by_scenario`, so the two
  conditions were always on this measure. `wall_clock_s` is still written but is
  not the M2 figure; in a scripted run it measures the script.
- **§3.2's "performed by the author" is no longer literally true** of the scored
  runs and Ch.5 must say so rather than inherit the sentence unexamined.

**Evidence the replay is faithful.** S1, S2 and S3 were each run both ways. The
hand runs are preserved in `B_hand_validation/` and agree with their scripted
counterparts on turns, interaction count and termination path in all three
cases. All 19 scripted runs were checked against `scenarios.py`: every task and
every feedback string went in verbatim.

**Blinding is intact.** `run_condition_b.py` prints only a summary line, never
the model's replies, so no scored Condition B artefact has been read by anyone.
