# Condition B — the ten opening prompts

Derived from rubric v1.0 (frozen `f6f3be2`) §3.2 and §4. Carries no measurement.

## Read this before using the file

**The prose Venture Brief is deliberately not supplied here.** Rubric §3.2:
*"Converting the schema to prose is part of the baseline's cost and is timed."*
If this pack handed you a finished prose brief, that cost would vanish and M1/M2
would be quietly wrong in the framework's favour — the same error as letting an
agent execute the runs. **You convert `passly_brief.json` to prose yourself, on
the clock.** See the open question at the end for how often.

Each run's opening turn is: **your prose brief, then the task block below,
verbatim.** Nothing else. No system prompt, no custom instructions, fresh thread.

## Scoring referent — fixed here, before any run

S2, S5 and S7 produce copy aimed at an SMB's *own customers*, not at SMBs. The
brief's `voice` block is Passly's. The governing reading, fixed now so it is not
improvised during scoring: **all copy is authored by Passly in its house voice,
on the shop's behalf.** Under A1, "concrete SMB examples" therefore reads as
*concrete detail specific to this SMB*, not *examples of different SMB types*.

This is a reading of the frozen anchor, not a change to it — rubric §5 is
untouched. It is written down because deciding it while scoring, after seeing the
outputs, is exactly the failure pre-registration exists to prevent.

## The ten task blocks

Append to the prose brief. Channel lines match rubric §4.

```
S1  Task: Write the launch announcement for Passly.
    Channel: email
```
```
S2  Task: Write the loyalty-card offer copy for Chunky Cookie Bar, a café
          using Passly. It appears on the wallet pass their customers hold.
    Channel: apple_wallet
```
```
S3  Task: Write a promotion for a καφές offer. Greek only.
    Channel: sms
```
```
S4  Task: Write a re-engagement message for customers who have not visited
          in a while.
    Channel: email
```
```
S5  Task: Write the pass-update push shown when a customer reaches their
          stamps goal.
    Channel: apple_wallet
```
```
S6  Task: Write the onboarding welcome for a new SMB signing up — a
          κομμωτήριο.
    Channel: email
```
```
S7  Task: Write copy that answers the objection "I tried SMS marketing once
          and it felt spammy."
    Channel: email
```
```
S8  Task: Write copy announcing that Passly now integrates with physical
          POS terminals in-store.
    Channel: email
```
```
S9  Task: Write a launch email that positions Passly as a revolutionary,
          cutting-edge breakthrough in SMB marketing.
    Channel: email
```
```
S10 Task: Write the launch announcement for Passly.
    Channel: email
```

**S8 and S9 are adversarial and are written to be so.** S8 asks for something
`constraints.out_of_scope` forbids; S9 asks for hype `voice.dont` forbids. Both
prompts are used identically in Condition F. Do not soften either, and do not
warn the model. Whether the constraint holds unprompted is the measurement (M3).

**M3 is read from the first draft, in both scenarios.** S8 and S9 both invite a
violation, and in both the founder's scripted response corrects it — so reading
M3 from the approved artefact would score the founder, not the condition. The
measurement is whether the *first* draft took the bait, before any feedback.
Rubric §6 sources M3 from "S8, S9 outputs"; this fixes that to the turn-1 output.

**S8's founder kills regardless of what the draft says.** If the model declines
the out-of-scope request unprompted, the founder still kills: §4 assigns S8 the
*killed* termination path, and that path must be exercised in both conditions
whether or not the constraint held. Whether it held is M3, read separately.

S10 is S1's task deliberately — the scenario tests the exhaustion path, not a
new brief, so holding the task constant isolates the termination behaviour.

## Founder scripts

In `founder_responses.EXTENDED.json` in this folder, keyed by scenario. Type the
`feedback` field verbatim, including its typos and its Greek. Do not improve it,
even when the model has obviously misread it — the script is the control.

**`feedback_en` is never typed.** It is an English translation for quoting in the
thesis, added 2026-08-20. The runtime stimulus stays Greek: the venture is Greek,
§4 S3 is Greek-only by design, and A1's 1-anchor fails copy whose Greek reads as
machine translation — so running the stimuli in English would change what A1
measures and would need a §12 amendment. Ch.5 quotes the English with the Greek
original in an appendix.

**This file must also reach Condition F.** Copy it to
`solo-founder-crew/scenarios/fixtures/founder_responses.json` before the F runs.
The top-level `turns` key is the original spike fixture, unchanged, so existing
spike runs are unaffected; the new `scenarios` key carries the ten.

**It needs your sign-off before either condition runs.** The strings are the
experiment's control and they shape A3 scoring. They were drafted to the pattern
of the existing spike fixture — two or three concrete asks per rejection, in a
founder's register rather than a prompt engineer's. Read them once; changing them
afterwards means discarding runs.

## Brief conversion — decided 2026-08-20, before any run

§3.2 times the schema→prose conversion as baseline cost but does not say how it
is charged. **Decided: convert once, time it, amortise that cost evenly across
the ten Condition B runs** (cost ÷ 10 added to each run's M1 and M2).

Rationale, for the Ch.5 sentence this needs: a founder writes the brief down once
and reuses it, so charging it ten times inflates the baseline against the
framework — bias in the one direction a single-author evaluation cannot afford
(rubric §9). Charging it entirely to S1 is equally literal but makes S1 an
outlier in every chart for a cost the other nine runs also benefit from.

**Procedure.** Convert before S1. Record elapsed seconds and interaction count in
`logs/_brief_conversion.json`, and save the prose brief to
`artifacts/_prose_brief.txt` — that exact text is then reused verbatim for all
ten runs. Add one tenth of each cost to every Condition B run's M1 and M2, and
report the raw conversion cost and the per-run share separately in the scorecard,
so a reader can undo the amortisation if they disagree with it.

Recorded here rather than in the rubric on purpose. The rubric is frozen; this
resolves a gap it left rather than changing anything it states, so it is not an
amendment under §12. It is committed before any run, which gives it the same
pre-registration property the freeze gives the instrument.
