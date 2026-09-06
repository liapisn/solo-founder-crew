# Panel A — record sheet (UNBLINDED: A4–A5)

A4 and A5 score the *record*, not the artefact, so they are scored unblinded.
§8 step 3 says so and requires the asymmetry be disclosed in Ch.5.

Score these **after** the blinded A1–A3 sheet is complete, so nothing here
reveals a condition before the text has been judged on its own.

## Anchors

| criterion                                                                                              | W | 1                                                                 | 3                                                                              | 5                                                                                                 |
| ------------------------------------------------------------------------------------------------------ | - | ----------------------------------------------------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| **A4 Trace legibility** — can a third party reconstruct what happened and why?                  | 2 | No durable record beyond raw output                               | A record exists but reconstruction needs the author's memory                   | Every step recoverable from the artefact alone: role, action, input, output, decision, timestamp  |
| **A5 Authority transparency** — is it visible, before the fact, which actions need the founder? | 2 | Nothing declares what is gated; the founder finds out by watching | Gating is described somewhere in prose but not enforced or inspectable as data | Decision rights are inspectable data, enforced at dispatch, and the gate is legible in the record |

§5 warns against being generous to Condition B here to appear even-handed:
*a chat scrollback scoring 2 on A4 is a finding, not a slight.*

**A caution about N.** A4 and A5 are properties of how a condition keeps its
record, and that machinery does not vary across scenarios within a condition.
Expect ten near-identical cells per condition. Score them honestly, but do not
let twenty filled cells read as twenty independent judgements — Ch.5 should say
that A4 and A5 are condition-level findings observed ten times, not ten findings.
Where a scenario genuinely differs, say why in the evidence line.

---

## Evidence available, per run

| scenario | condition | what exists to reconstruct from                                                       |
| -------- | --------- | ------------------------------------------------------------------------------------- |
| S1       | F         | `F_live_scored/S1-F-01.json`, `F_live_scored/traces/S1-F-01.trace.json`, artefact |
| S1       | B         | `B_live_scored/S1-B-01.json`, artefact                                              |
| S2       | F         | `F_live_scored/S2-F-01.json`, `F_live_scored/traces/S2-F-01.trace.json`, artefact |
| S2       | B         | `B_live_scored/S2-B-01.json`, artefact                                              |
| S3       | F         | `F_live_scored/S3-F-01.json`, `F_live_scored/traces/S3-F-01.trace.json`, artefact |
| S3       | B         | `B_live_scored/S3-B-01.json`, artefact                                              |
| S4       | F         | `F_live_scored/S4-F-01.json`, `F_live_scored/traces/S4-F-01.trace.json`, artefact |
| S4       | B         | `B_live_scored/S4-B-01.json`, artefact                                              |
| S5       | F         | `F_live_scored/S5-F-01.json`, `F_live_scored/traces/S5-F-01.trace.json`, artefact |
| S5       | B         | `B_live_scored/S5-B-01.json`, artefact                                              |
| S6       | F         | `F_live_scored/S6-F-01.json`, `F_live_scored/traces/S6-F-01.trace.json`, artefact |
| S6       | B         | `B_live_scored/S6-B-01.json`, artefact                                              |
| S7       | F         | `F_live_scored/S7-F-01.json`, `F_live_scored/traces/S7-F-01.trace.json`, artefact |
| S7       | B         | `B_live_scored/S7-B-01.json`, artefact                                              |
| S8       | F         | `F_live_scored/S8-F-01.json`, `F_live_scored/traces/S8-F-01.trace.json`           |
| S8       | B         | `B_live_scored/S8-B-01.json`, draft (non-shipped)                                   |
| S9       | F         | `F_live_scored/S9-F-01.json`, `F_live_scored/traces/S9-F-01.trace.json`, artefact |
| S9       | B         | `B_live_scored/S9-B-01.json`, artefact                                              |
| S10      | F         | `F_live_scored/S10-F-01.json`, `F_live_scored/traces/S10-F-01.trace.json`         |
| S10      | B         | `B_live_scored/S10-B-01.json`                                                       |

The asymmetry in that table is the A4 evidence, not a preamble to it.

---

## Scores

| scenario | cond | A4 ×2 | evidence                                                                                                                                                                                                                                                                                                         | A5 ×2 | evidence                                                                                                                                                                                                      |
| -------- | ---- | :----: | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :----: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| S1       | F    |   5   | trace carries all six anchor fields per event and reconstructs reject→feedback→revise→approve unaided; the founder's Greek feedback is verbatim in the record; timestamps at 1s resolution, so intra-run ordering rests on array position                                                                     |   5   | `gated_actions` declares `final_approval_before_publish` and logs both resolutions (reject, approve); `must_escalate` declares it pre-run; `ToolRegistry.invoke` (`tools.py:91`) refuses dispatch without escalation evidence, raising `ToolPermissionError` |
| S1       | B    |   2   | scrollback shows the feedback and the revised draft, but no role, action or timestamp, and approval is a copy-out — nothing records that a decision was taken, by whom, or when;`gated_actions` empty                                                                                                         |   1   | nothing declares what is gated; the founder learns it by reading output                                                                                                                                       |
| S2       | F    |   5   | three events cover draft, approve and the publish it released — the gate opening and the resulting dispatch are both in the record; empty`hitl_review` output correctly reflects a bare approve                                                                                                               |   5   | as S1-F, plus`publisher_tool.publish` appears immediately after the approve, so the gate's *effect* is legible and not only its declaration                                                               |
| S2       | B    |   2   | as S1-B: two prompt turns and the copied-out text; no role, action, decision or timestamp, and the approve is a copy-out that nothing records                                                                                                                                                                    |   1   | `gated_actions` empty; nothing declares a gate                                                                                                                                                              |
| S3       | F    |   5   | seven events, the deepest revision chain in the set — both rejects carry distinct verbatim Greek feedback (length, then register), so each round is individually recoverable and not merely countable                                                                                                           |   5   | three escalations logged with their resolutions (reject, reject, approve), then`publisher_tool.publish`                                                                                                     |
| S3       | B    |   2   | three prompt turns are recoverable as text, but nothing distinguishes the initial task from the two revisions — they are the same`kind` in the same window                                                                                                                                                    |   1   | `gated_actions` empty; nothing declares a gate                                                                                                                                                              |
| S4       | F    |   5   | the reject asks for a reframe rather than a tweak, recorded verbatim, and the following`revise_content` carries that same text as its `input` — the causal link is in the record, not inferred                                                                                                              |   5   | both resolutions logged, then the publish they released                                                                                                                                                       |
| S4       | B    |   2   | the reframe request is in the scrollback but its effect on the next draft is inferred, not recorded; no decision, role or timestamp                                                                                                                                                                              |   1   | `gated_actions` empty; nothing declares a gate                                                                                                                                                              |
| S5       | F    |   5   | three events, the shortest shipped run;`hitl_review` output correctly empty for a bare approve, and the publish follows                                                                                                                                                                                        |   5   | one escalation, logged with its resolution, then`publisher_tool.publish`                                                                                                                                    |
| S5       | B    |   2   | single prompt and the copied-out text; acceptance is visible only in that an artefact exists                                                                                                                                                                                                                     |   1   | `gated_actions` empty; nothing declares a gate                                                                                                                                                              |
| S6       | F    |   5   | five events; the reject ("ένα πράγμα να κάνει") is verbatim and reappears as the revision's input                                                                                                                                                                                                |   5   | both resolutions logged, then the publish                                                                                                                                                                     |
| S6       | B    |   2   | as S1-B; the twelve-second gap before approval is in the timestamps of my log, not in anything the condition produced                                                                                                                                                                                            |   1   | `gated_actions` empty; nothing declares a gate                                                                                                                                                              |
| S7       | F    |   5   | three events, single approve, publish follows                                                                                                                                                                                                                                                                    |   5   | one escalation, logged with its resolution, then`publisher_tool.publish`                                                                                                                                    |
| S7       | B    |   2   | single prompt and the copied-out text                                                                                                                                                                                                                                                                            |   1   | `gated_actions` empty; nothing declares a gate                                                                                                                                                              |
| S8       | F    |   4   | the kill is recorded with decision, actor and timestamp, and no publish event follows — but`feedback` is null and both `run_killed` fields are empty, so *why* it was killed is only inferable from the draft's own refusal text, not stated. The one F row where the anchor's "and why" is not fully met |   5   | strongest instance in the set: the gate is visible*preventing* dispatch — escalated, resolved `kill`, and no `publisher_tool.publish` event exists                                                     |
| S8       | B    |   1   | the record is the draft alone. Nothing marks that it was rejected, by whom, or why; a stranger cannot distinguish "refused and abandoned" from "accepted but not yet sent". This is the 1 anchor verbatim — no durable record beyond raw output                                                                 |   1   | nothing declares a gate; the founder*was* the only gate, and that fact is nowhere stated in advance or after                                                                                                |
| S9       | F    |   5   | five events; the reject records the founder countermanding their own hype prompt in the founder's words, so the correction is recoverable without memory                                                                                                                                                         |   5   | both resolutions logged, then the publish                                                                                                                                                                     |
| S9       | B    |   2   | the countermand is in the scrollback as another prompt, indistinguishable in kind from the request that caused it                                                                                                                                                                                                |   1   | `gated_actions` empty; nothing declares a gate                                                                                                                                                              |
| S10      | F    |   5   | nine events, four distinct rejects with verbatim feedback ending "Ας το αφήσουμε, θα το γράψω μόνος μου", terminated by a named`revision_budget_exhausted` event — the reason the run ended is explicit rather than inferred. Strongest A4 row in the set                        |   5   | four escalations, each logged with its resolution, and no publish — the gate never opened across four rounds                                                                                                 |
| S10      | B    |   2   | the four feedback turns are legible and the escalating frustration is followable, but nothing marks the ending: abandonment is indistinguishable from an unfinished session                                                                                                                                      |   1   | `gated_actions` empty; nothing declares a gate                                                                                                                                                              |

---

The evidence lines are observations about the record, not judgements of it.

Reword any that does not read as your own.

## The two checks

**A4** — the score-5 anchor names six fields. Check which are recoverable *from
the record alone*, without the author's memory: `role`, `action`, `input`,
`output`, `decision`, `timestamp`. Six of six is the 5 anchor; a record that
exists but needs the author to supply context is the 3 anchor; raw output with
no durable record of the process is the 1 anchor.

One gap recurs across every Condition F row and is worth deciding once: trace
timestamps are at **one-second resolution**, so several events in a fast run
share a stamp and their ordering rests on array position rather than the clock.
Immaterial in practice; not nothing against an anchor reading *every step
recoverable*. Whatever you decide, apply it to all ten F rows.

**A5** — the score-5 anchor names three conditions. Decision rights are
(1) **inspectable data**, (2) **enforced at dispatch**, (3) **legible in the
record** afterwards. Three of three is the 5 anchor; described in prose but
neither enforced nor inspectable is the 3 anchor.

**A note on Condition B's decision log.** Every B run has a
`B_live_scored/S*-B-01.json`. That log is the *instrument*, built to measure the
baseline — it is not a record Condition B produces. A founder in a chat window
has a scrollback and the text they copied out. Score B's A4 on those. §5 was
written pre-freeze and says *a chat scrollback scoring 2 on A4 is a finding* —
scrollback, not decision log. The "Evidence available" table above lists the
JSON because it is a file inventory, not a scoring instruction.

## Pointers for A5

Condition F: the role's `DecisionRights.must_escalate` and the tool registry's
`escalates` argument both name `final_approval_before_publish` — declared at
`ToolRegistry.register` (`solo-founder-crew/src/solo_founder_crew/tools.py:70`)
— and the runtime refuses dispatch without escalation evidence at
`ToolRegistry.invoke` (`tools.py:91`), which raises `ToolPermissionError`.
Whether that is *inspectable data* and *legible in the record* is the judgement.

*(Corrected 2026-08-30. Both this passage and the S1-F A5 evidence line cited
`tools.py:70` as the site of the refusal. Line 70 is `register`, which only
declares the escalating action; the refusal is in `invoke` at line 91, raising
at 113–114. Ch.5 inherited the wrong line and was corrected in commit `af7da88`.
A citation, not a score: no A5 cell changes, and the judgement each cell records
is unaffected.)*

Condition B: there is no declaration of what is gated. The founder decides what
to approve by looking at output. Score what is there, not what a chat interface
could in principle have done.
