# Condition B — operator protocol

Derived from **rubric v1.0** (frozen `f6f3be2`), §3.2, §6 and §7. Carries no
measurement. Read once before the first run; do not improvise mid-block.

## Standing rules

- **One thread per run.** New chat, no memory, no custom instructions, no
  system prompt. Close it when the run terminates.
- **Model:** `claude-haiku-4-5`, same temperature as Condition F. Record the
  exact model string in the log; if the provider silently rotates it, that is an
  E4b finding, not a nuisance.
- **Stopping rule:** up to three revisions, i.e. four drafts. Rejection routes to
  *revise* while `turn <= max_revisions` and to *exhausted* otherwise — so
  exhaustion arrives at the **fourth** gate, not the third (S10 carries four
  rejections).
- **Feedback is scripted.** Type the scenario's feedback string from
  `founder_responses.json` verbatim. Do not improve it, even when it is
  obviously improvable and the model is obviously about to misread it. The
  script is the control.
- **Publish manually.** Copy-paste to the destination and time it. No escalation
  check exists in this condition; that absence is the measurement.

## Timing (M2)

Start the clock when the opening prompt is **submitted**, not when composing it
begins — except that the schema→prose conversion **is** timed and counted
(§3.2), so do that conversion inside the run and record it as the first
interaction. Stop at terminal state. Exclude founder think-time: pause the clock
while reading output and deciding, resume when acting.

Practically: log wall-clock timestamps at each act and subtract think-gaps
afterwards, rather than trying to run a stopwatch and a chat at once.

## Counting interactions (M1)

A founder interaction is **any discrete act requiring the founder's attention**:

| Counts | Does not count |
|---|---|
| One approve | Reading output |
| One reject-with-feedback | Waiting for a response |
| One manual edit | Scrolling back |
| One copy-paste step | Deciding |
| One prompt typed | |

Reading output is not an interaction; acting on it is. Count as you go, in the
log, not from memory afterwards.

## Opening prompt

Per rubric §3.2 and the freeze-time resolution, the **full Venture Brief is
pasted verbatim as prose**, since a chat UI has no schema. Template:

```
<VENTURE BRIEF, converted to prose from
 solo-founder-crew/scenarios/fixtures/passly_brief.json — verbatim content,
 prose formatting only. Conversion time is counted and logged.>

Task: <scenario task line, from the §4 table>
Channel: <email | sms | apple_wallet>

Draft the copy.
```

> The ten task lines are in `02_CONDITION_B_PROMPTS.md`. The prose brief is
> **not** pre-supplied, on purpose: §3.2 counts the conversion as baseline cost
> and times it, so handing you a finished one would delete a measured quantity.
> You convert it, on the clock. How often is still open — see that file.

## Adversarial scenarios

S8 (out-of-scope: physical POS) and S9 (hype framing) are the two runs where the
temptation to help the baseline along will be strongest. Do not. If Condition B
absorbs the out-of-scope request, that is M3 = fail for B and it is a finding.
Rubric §5 says the same thing about A4: *a chat scrollback scoring 2 is a
finding, not a slight.*

## After each run

1. Save the final artefact verbatim to `artifacts/<run_id>.txt`.
2. `shasum -a 256 artifacts/<run_id>.txt` → into the log.
3. Fill the log completely. A blank field after the run is over cannot be
   honestly recovered.
4. Read token usage from the provider console → `tokens`.
5. **Do not score anything.** (§8 step 2.)

## Inputs — resolved

- `passly_brief.json` — received 2026-08-20. **Not** pre-converted to prose; see above.
- `founder_responses.json` — received, but it was the single reject/approve spike
  fixture, not a ten-scenario set. Rubric §3.1 anticipated this ("extended to ten
  scenarios"). The extension is `founder_responses.EXTENDED.json` in this folder
  and was **signed off 2026-08-20**, before any run. Changing a string now means
  discarding every run already executed.
