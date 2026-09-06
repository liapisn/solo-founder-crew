# Chapter 5 — Evaluation rubric (pre-registered instrument)

**Status:** **v1.0 — FROZEN 2026-08-17.** Authored 2026-08-16 as v0.1; corrected
to v0.2 on 2026-08-17; frozen at v1.0 the same day, before any scored run of
Part 12. No run had been executed in either condition at the time of the freeze
commit, and the commit ordering in `git log` is the evidence for that claim.
**Harness:** `solo-founder-crew/evaluation/` (PRs #22–#25). Two corrections came
out of building it: exhaustion arrives at the fourth gate (§3.2, §4 S10), and
E1's test count is now 264 rather than the 175 Ch.3 §3.10 quotes — §3.10 says "on
the date of writing" so it stands, but Ch.5 must report the count at evaluation
time. **E1's reading stays 264**, the figure at the time it was read
(2026-08-26); the suite has since grown to 315 through harness work done *after*
the reading (PRs #24, #25 — the Condition B protocol tests and the §7 schema
change). Ch.5 reports 264 as the evaluation-time count and may note the current
figure, but the recorded reading is not restated to match a later suite.
**Freeze condition:** satisfied. This document was committed unchanged *before*
the first scored run of Part 12. Any edit from the freeze commit onward is an
amendment, recorded in §12 with a reason, rather than a silent revision.
**Owner:** Nikos Liapis. **Consumes:** `05_Drafts/Ch3_10_Evidence_Pack.md`,
Ch.3 §3.10 (Table 3.8), §3.2 (Table 3.1, objectives O1–O7).
**Feeds:** Parts 12–14 (case-study runs, decision logs, rubric applied), Ch.4
prose (Part 15), Ch.5 evaluation chapter.

---

## 1. What this instrument is for

Chapter 3 §3.10 fixes the evaluation posture and names five dimensions
(E1–E5) without operationalising them to the point of execution. This
document closes that gap: it states, in advance of any scored run, what will
be measured, how, on which scenarios, against which comparison condition, and
what counts as a good or bad result. Pre-registration is the point. The author
of the artifact is also its evaluator, so the only credible defence against
favourable scoring is that the instrument was fixed before the data existed.

The evaluation is a **sandbox demonstration**, per the project's standing
posture: synthetic Passly scenarios, rubric-based comparison against a
synthesised solo-founder baseline, no live customer data. Within Design
Science Research this is the *evaluation* step following construction (Hevner
et al., 2004, §4; Peffers et al., 2007); it is not a field study and makes no
claim to be one.

**Method lineage.** The instrument is the same family as the Part 7 spike
rubric (`solo-founder-crew/docs/spike-charter.md`): criteria and weights
declared before coding, 1–5 per criterion, weighted total, every cell
justified by evidence in a scorecard so that no number stands alone. That
lineage is asserted in §3.10 and is honoured here.

---

## 2. The structural decision: scored versus measured

The five §3.10 dimensions are not the same kind of thing, and forcing them
into one 1–5 table would be dishonest. E1 and E4 are properties a test runner
either confirms or refutes; E5 is a quantity read off an instrument; only E2
and E3 require human judgement. The rubric therefore has two panels.

| Panel | Dimensions | Instrument | Comparative? |
|---|---|---|---|
| **A — Scored** | E2 (output quality), E3 (founder usability) | 1–5 anchored rubric, weighted, max **60** | Yes — framework vs. baseline |
| **B — Measured** | E1 (correctness), E4 (reproducibility), E5 (cost), plus M1–M2 (effort, latency) | Direct reading; no judgement | E1 framework-only; E4, E5, M1, M2 comparative |

This split is itself a defensibility asset and should be stated in the Ch.5
prose. The framework's substantive claims — that authority is enforced, that
runs are reproducible, that founder attention is conserved — live almost
entirely in **Panel B**, where the author's judgement does not enter. Panel A,
the subjective panel, is where the framework is *least* expected to dominate,
because both conditions call the same model on the same brief. A result in
which Panel A comes out near-parity and Panel B separates the conditions is
the honest expected shape of the finding, and predicting it in advance is
worth more than a uniformly flattering table.

---

## 3. Conditions

### 3.1 Condition F — the framework

`solo-founder-crew` Author Flow, driven from `scenarios/fixtures/passly_brief.json`,
marketing role, `MockLLM` for the determinism runs and `AnthropicLLM`
(`claude-haiku-4-5`) for the live-scored runs. Founder decisions supplied by
the scripted responses in `scenarios/fixtures/founder_responses.json`, extended
to ten scenarios (§4). Publishing goes through `publisher_tool` under
`DecisionRights`.

### 3.2 Condition B — the synthesised baseline

A "no framework" workflow: the solo founder works in a generic chat interface,
in one thread, and drafts → revises → publishes by hand. To make the
comparison about the *operating model* rather than the model, Condition B is
held identical to Condition F on everything except the framework:

- **Same LLM and settings** — `claude-haiku-4-5`, same temperature.
- **Same brief content** — the Venture Brief pasted into the opening prompt as
  prose, since a chat UI has no schema. Converting the schema to prose *is*
  part of the baseline's cost and is timed. *(Amended 2026-08-20 — see §12. The
  prose is generated by `render_brief_prose()`, so the conversion is counted in
  M1 as one `paste_brief` interaction but is no longer timed into M2.)*
- **Same founder feedback** — the identical scripted feedback string for that
  scenario, typed into the thread.
- **Same stopping rule** — up to three revisions, i.e. four drafts, matching
  the Author Flow's cap. The runtime routes a rejection to *revise* while
  `turn <= max_revisions` and to *exhausted* otherwise, so exhaustion arrives at
  the fourth gate, not the third.
- **Manual publish** — copy-paste to the destination, timed, with no
  escalation check.

**The baseline is synthesised, not recruited.** It is a reconstructed
without-framework workflow performed by the author, not a cohort of real
founders. This is the instrument's principal limitation, it is named here
rather than in a footnote, and §9 states what follows from it.

**Operator of record.** *(Superseded 2026-08-20 — see §12. The paragraph is kept
as written, because an instrument's pre-registered position is part of the record
even once it is overtaken. What replaced it follows immediately below.)*

> Every Condition B run is executed by hand by the author, in a chat interface,
> in real time. This is fixed here because M1 and M2 are readings of *human*
> effort and elapsed time: an agent executing the same scripted protocol would
> produce a valid artefact but an invalid M2, and the schema→prose conversion
> timed above would collapse to a figure that means nothing. Preparatory
> materials — the ten opening prompts, the blank decision-log records, the
> scoring workbook — are machine-generated from this document and carry no
> measurement; the runs themselves are not. Condition F is likewise executed by
> the author.

**Operator of record, as amended.** The 19 scored Condition B runs (10 live-scored
+ 9 E4b) are a **scripted replay**, executed by `evaluation/run_condition_b.py`.
Three hand runs are retained in `Ch5_Eval_Runs/B_hand_validation/` as the
fidelity check against them.

The reasoning above did not survive contact with the harness, in the direction
that matters: by the time the protocol was stable, nothing was left for a human
to get right. `render_brief_prose()` had always generated the brief; `/task` and
`/next` then supplied the task and every feedback string verbatim. What "by hand"
still protected was the operator's typing, and ~~six of the first nine attempts~~
*(corrected 2026-08-29 — see §12)* **five of the first eight attempts** were
discarded for protocol slips — one of which reached the model as a stray prompt
and inflated M1 *against* the baseline, the direction a single-author evaluation
can least afford. The five are archived individually in
`Ch5_Eval_Runs/_superseded/discarded_runs/`, one directory per discard, against
three kept hand runs in `Ch5_Eval_Runs/B_hand_validation/`.

Neither reading is harmed, and this is checkable rather than asserted:

- **M1** is protocol-determined. Its value is fixed by §3.2's fixed protocol and
  §4's founder script, not by who presses the keys; every interaction the founder
  would perform is still counted, `paste_brief` and `copy_out` included.
- **M2** is read from summed model latency, not elapsed human time — see the
  amended §6 row. Under a hand run the two diverge widely; under the replay
  `wall_clock_s` and `llm_latency_s` agree to the millisecond (S1-B-01: 21.832 vs
  21.831), which is the arithmetic tell that no human time is inside the figure.

What is genuinely lost is the timing of the schema→prose conversion, which bullet
2 above pre-registered as a timed cost. It is now generated, so it is counted in
M1 as one `paste_brief` interaction but no longer contributes seconds to M2. The
loss runs *against* the baseline's M2 and is recorded rather than recovered.

Condition F is likewise executed by the author, via `run_condition_f.py`.

---

## 4. Scenario set (N = 10)

Ten scenarios drawn from the Passly brief and the Chunky Cookie Bar demo shop,
so that the Ch.4 application and the Ch.5 evaluation share one authored set —
the synergy the roadmap anticipates. Each scenario is one Author Flow task
under the marketing role unless the role column says otherwise.

| # | Scenario | Channel | Founder script | Exercises |
|---|---|---|---|---|
| S1 | Launch announcement for Passly | email | reject-then-approve | Baseline of the §3.9 worked example |
| S2 | Loyalty-card offer copy, Chunky Cookie Bar | apple_wallet | approve first turn | Shortest happy path |
| S3 | Καφές promotion, Greek only | sms | reject ×2, approve | Revision depth, voice under length limits |
| S4 | Re-engagement message, lapsed customers | email | reject, approve | Feedback honouring |
| S5 | Pass-update push, stamps goal reached | apple_wallet | approve | Terse-format adherence |
| S6 | SMB onboarding welcome, κομμωτήριο | email | reject, approve | Segment specificity |
| S7 | Objection-handling copy ("felt spammy") | email | approve | Brief `customer.objections` adherence |
| S8 | Out-of-scope probe: physical POS integration | email | kill | `constraints.out_of_scope` enforcement (O7) |
| S9 | Hype probe: prompt invites "revolutionary" framing | email | reject, approve | `voice.dont` adherence under pressure |
| S10 | Revision exhaustion: founder rejects at every gate | email | reject ×4 | Exhausted termination path |

S8 and S9 are adversarial by design: they invite the model to violate a brief
constraint, and the interesting measurement is whether the constraint holds in
each condition. S8 and S10 also cover two of the four termination paths, which
keeps the scenario set connected to E1.

*(Amended 2026-08-29 — see §12. S9's scripted reject text assumes the model
complied with the hype prompt. In Condition F it refused, so the founder's line
answers something that did not happen. The scripted feedback is unchanged and
the run is not re-executed; the fault is disclosed.)*

**Runs per scenario.** Condition F and Condition B, once each live-scored
(20 live runs). The E4 determinism readings are taken on a fixed three-scenario
subset — **S2, S3, S8** — rather than on all ten. Determinism is a property of the
runtime, not a per-scenario score, and these three span the shortest happy path,
the deepest revision chain and an adversarial probe. Each subset scenario gets
three Condition F re-runs under `MockLLM` (E4a) and three under `AnthropicLLM`
(E4b), and three Condition B re-runs under `claude-haiku-4-5` for E4b only.

**Total 47 runs:** 20 live-scored, 18 further Condition F re-runs, 9 further
Condition B re-runs. ~~Nineteen of the 47 are executed by hand in Condition B
(10 live + 9 E4b re-runs), per the operator-of-record rule in §3.2.~~
*(Amended 2026-08-20 — see §12.)* Those nineteen Condition B runs are a scripted
replay of the same protocol, per the amended operator-of-record rule in §3.2;
three separate hand runs are retained in `Ch5_Eval_Runs/B_hand_validation/` as
the fidelity check and are **not** part of the scored set.

Condition B has no `MockLLM` path — a generic chat interface cannot be given a
stub model — so E4a is a Condition F reading only. The asymmetry is stated here
rather than papered over; Condition B's determinism evidence is E4b, which is
reported and not gated.

---

## 5. Panel A — the scored rubric

Score 1–5 per criterion. Weighted total = Σ(score × weight). Maximum = 5 ×
(3+3+2+2+2) = **60** per condition per scenario. Anchors are given for 1, 3
and 5; even scores are interpolations.

### E2 — Output quality (weight 8 of 12)

| Criterion | W | 1 | 3 | 5 |
|---|---:|---|---|---|
| **A1 Voice fidelity** — conformance to `voice.tone`, `voice.do`, `voice.dont` | 3 | Violates a `dont` (hype word, revenue promise, or a pilot claim), or the Greek reads as machine translation | Tone broadly right; no `dont` violated; one or two flat or generic passages | Reads as warm plain Greek written by a peer; concrete SMB examples; nothing a native speaker would flag |
| **A2 Brief adherence** — value props, JTBD, objections, `out_of_scope` | 3 | Contradicts the brief or strays out of scope | Consistent with the brief; uses at least one value prop or JTBD, generically | Grounded in specific brief content, and correctly declines anything out of scope |
| **A3 Feedback honouring** — the revision does what the founder asked | 2 | Ignores the feedback, or changes something else instead | Addresses the feedback partially, or addresses it while regressing another aspect | Every element of the feedback is visibly addressed and nothing previously good is lost |

*A3 is scored only on scenarios with at least one revision turn (S1, S3, S4,
S6, S9, S10). On approve-first-turn scenarios the criterion is dropped and the
maximum for that scenario falls to 50; totals are reported as percentages of
the applicable maximum so scenarios remain comparable.*

### E3 — Founder usability (weight 4 of 12)

| Criterion | W | 1 | 3 | 5 |
|---|---:|---|---|---|
| **A4 Trace legibility** — can a third party reconstruct what happened and why? | 2 | No durable record beyond raw output | A record exists but reconstruction needs the author's memory | Every step recoverable from the artefact alone: role, action, input, output, decision, timestamp |
| **A5 Authority transparency** — is it visible, before the fact, which actions need the founder? | 2 | Nothing declares what is gated; the founder finds out by watching | Gating is described somewhere in prose but not enforced or inspectable as data | Decision rights are inspectable data, enforced at dispatch, and the gate is legible in the record |

A4 and A5 are the criteria on which the two conditions genuinely differ in
kind, and the scorer should resist the temptation to be generous to Condition
B to appear even-handed. A chat scrollback scoring 2 on A4 is a finding, not a
slight.

---

## 6. Panel B — measured dimensions

No judgement. Each is a reading, reported with its raw artefact.

| ID | Dimension | Measure | Condition | Source of reading | Pass condition |
|---|---|---|---|---|---|
| **E1** | Functional correctness | Full suite green; all four Author-Flow termination paths reachable and asserted | F only | `pytest` output; `examples/termination_paths.py`; `tests/test_author_flow.py`; `summary_F_*.json` → `e1_termination_paths_seen` | Suite passes; 4/4 paths |
| **E4a** | Determinism | Byte-identical output across 3 re-runs under `MockLLM`, on the §4 subset (S2, S3, S8) | F only | Hash of final artefact | 3/3 identical per subset scenario |
| **E4b** | Live-run divergence | Pairwise similarity across 3 re-runs under Haiku, on the §4 subset (S2, S3, S8) | F, B | Normalised edit distance on final artefact | Reported, not gated |
| **E4c** | Cross-process resume | Run interrupted at the gate, process killed, resumed, completed | F only | `Crew.resume`; `tests/test_crew_resume.py`; `data/runs.json` | Completes to terminal state |
| **E5** | Cost envelope | Input + output tokens per approved artefact; € at Haiku list price | F, B | `AnthropicLLM.calls[*].usage`; baseline read from the provider console | Reported per scenario and as a mean |
| **M1** | Founder oversight effort | Discrete founder interactions to reach an approved artefact (decisions, keystroke-level edits, copy-paste steps) | F, B | Decision log (§7) | Reported; lower is better |
| **M2** | Model latency to terminal state *(amended 2026-08-26 — see §12; pre-registered as "wall-clock to approved artefact … from decision log timestamps")* | Summed model latency from task start to terminal state, i.e. founder think-time excluded by construction rather than by subtraction | F, B | Decision log `llm_latency_s` | Reported; lower is better |
| **M3** | Constraint holds under adversarial probe | Did the out-of-scope / hype probe get refused or absorbed? | F, B | S8, S9 outputs | Binary per scenario |
| **M4** | Artefact readiness | Did the condition return one shippable artefact, or a set of candidates the founder must still choose between and clean up? | F, B | Raw artefact, before the §8 extraction | Binary per scenario; reported, not gated |

M1 is the operational form of the time-to-market objective (O2) and is
probably the most consequential number in the chapter, because it is where an
operating-model claim can be shown rather than argued. Its definition is
therefore fixed here in detail: a *founder interaction* is any discrete act
requiring the founder's attention — one approve, one reject-with-feedback, one
manual edit, one copy-paste, one prompt typed. Reading output is not an
interaction; acting on it is.

**M2, and why the amendment narrows rather than widens the claim.** As frozen,
M2 was elapsed time with think-time excluded — which requires deciding, per
pause, whether the founder was thinking or working, by the person whose condition
is being measured. The readings instead sum `llm_latency_s`, the model's own time,
which excludes human time by construction and needs no judgement. It is the
narrower quantity: it cannot capture a founder's oversight burden, and M1 carries
that instead. It is also the only form under which the amended §3.2 replay and a
hand run are comparable at all. `wall_clock_s` is still recorded in every log, and
is the figure a future hand-run study would read.

M3 exists because a constraint that holds only when unchallenged has not been
demonstrated to hold.

---

## 7. Decision log schema

Part 12's outstanding item is "structured rubric runs **+ decision logging**".
Every run in either condition emits one record. Condition F's is generated
from `RunTrace`; Condition B's is emitted by the baseline loop, which is itself
part of the baseline's honesty — nothing in a chat UI produces this for free.

*(Amended 2026-08-26 — see §12. The illustration below is brought into agreement
with what `evaluation/decision_log.py` writes: the interaction key is `kind`, not
`type`; the timing, token and versioning fields are shown; and `interaction_count`
is written from schema version 2 onward. The 50 runs already archived are version
1 and omit that one key, where M1 is `len(founder_interactions)` — so no archived
run is rewritten, which is what keeps the commit ordering of `Ch5_Eval_Runs/`
worth anything.)*

```json
{
  "run_id": "S3-F-01",
  "scenario": "S3",
  "condition": "F",
  "llm": "claude-haiku-4-5",
  "role": "marketing",
  "timestamp_start": "2026-08-20T10:14:02+03:00",
  "timestamp_terminal": "2026-08-20T10:14:39+03:00",
  "termination_path": "shipped",
  "turns": 2,
  "interaction_count": 3,
  "founder_interactions": [
    {"seq": 1, "kind": "reject", "at": "...", "feedback": "...", "chars_typed": 110},
    {"seq": 2, "kind": "approve", "at": "...", "feedback": null, "chars_typed": 0},
    {"seq": 3, "kind": "copy_out", "at": "...", "feedback": null, "chars_typed": 0}
  ],
  "gated_actions": [
    {"action": "publish", "escalated": true, "resolved": "approve"}
  ],
  "tokens": {"input": 0, "output": 0},
  "llm_latency_s": 4.98,
  "wall_clock_s": 5.013,
  "final_artifact_sha256": "...",
  "artifact_path": "...",
  "schema_version": 2,
  "notes": ""
}
```

`termination_path` is one of `shipped` | `killed` | `exhausted`; `kind` is one of
`approve` | `reject` | `kill` | `prompt` | `paste_brief` | `copy_out`. M2 is read
from `llm_latency_s` (§6); `interaction_count` is M1 and is derived from
`founder_interactions` at serialisation, so the two cannot disagree.

Logs land in `05_Drafts/Ch5_Eval_Runs/` as one JSON per run plus a
`scorecard.md` in the shape of `solo-founder-crew/docs/spike-scorecard.md` —
table first, per-cell evidence below, no number standing alone.

---

## 8. Scoring procedure

1. **Freeze** this document; commit it; record the freeze commit hash in §12.
   *(Done 2026-08-17.)*
2. **Run** all scenarios in both conditions, emitting decision logs and
   artefacts. Do not score during this phase.
3. **Extract, then blind** the artefacts for Panel A. *(Amended 2026-08-20 —
   see §12.)* The conditions do not return the same kind of object: Condition F
   returns one drafted artefact, Condition B frequently returns a set of
   candidate variants with commentary. Structure alone therefore identifies the
   condition, and A1–A3 would not be comparing like with like. Before blinding,
   one **extraction rule** is applied mechanically and identically to both:

   a. The scored artefact is the deliverable copy only — the text as it would
      reach the customer.
   b. Where an output offers several candidates, the scored one is whichever the
      output itself recommends; where it recommends none, the first.
   c. Removed: labelling headings, character and word counts, rationale or
      "why this works" sections, glossed translations, placeholder inventories,
      and any commentary addressed to the founder rather than the customer.
   d. Kept verbatim: the copy itself, including emoji, line breaks and
      placeholders that would survive to send.
   e. Both the raw and the extracted artefact are archived, so a third party can
      audit the extraction as well as the score.

   *(Amended 2026-08-27 — see §12. This rule was applied **imperfectly**: 4 of
   the 16 scored artefacts (A12, A13, A15, A16) reached the scorer still carrying
   material 3b or 3c required removed. The scores stand and the residual is
   disclosed, with its direction measured. What follows describes the rule as
   pre-registered, not as executed.)*

   The difference extraction removes is real and is not discarded: it is
   measured as **M4** (§6). Extraction is performed before the scorer reads
   anything, and extracted files carry no condition label. Blinding is
   feasible for A1–A3 *on the extracted copy*, which scores the text alone. It is *not* feasible for
   A4–A5, which score the record rather than the artefact; those are scored
   unblinded and that asymmetry is disclosed in Ch.5.
4. **Score** Panel A against the anchors, writing the one-line evidence
   justification for each cell as it is scored, not afterwards.

   *(Amended 2026-08-29 — see §12. A1–A3 were scored this way, by the author,
   blind. For A4–A5 the cells were prepared as an assistant-drafted first pass
   over the run records and then reviewed and adopted by the author, so the
   evidence lines were not written at the moment of scoring in the sense this
   step describes. The judgements are the author's; the drafting was not.)*
5. **Read** Panel B from the logs and the test runner.
6. **Unblind**, aggregate, and write the scorecard.
7. **Archive** every artefact and log so a supervisor can re-score
   independently. Re-scorability by a third party is the substitute the thesis
   offers for inter-rater reliability, which a single-author evaluation cannot
   have.

---

## 9. Threats to validity

Stated here so Ch.5 inherits them rather than discovering them at viva.

- **Single rater, who is also the builder.** Mitigated by pre-registration,
  anchored descriptors, blinding of A1–A3, per-cell evidence, and an archive
  that permits independent re-scoring. Not eliminated. The strongest response
  remains that the load-bearing claims sit in Panel B. *(Amended 2026-08-29 —
  see §12.)* A4–A5 were prepared as an assistant-drafted first pass and reviewed
  and adopted by the author. This does not add a second rater: the assistant
  worked with full knowledge of the framework and the anchors, so the cells
  remain a single perspective. The anchors were frozen twelve days earlier, and
  each evidence line names checkable content in a named archived file, so the
  cells can be audited against the record rather than against the rater.
- **Synthesised baseline.** Condition B is performed by someone who knows the
  framework's design and may unconsciously run the baseline well or badly. The
  fixed protocol in §3.2 constrains this; a recruited cohort would resolve it
  and is out of scope. *(Amended 2026-08-26 — see §12.)* The scripted replay
  narrows this threat without removing it: the baseline is no longer *executed*
  by an interested party, and the archive can be re-run by a third party to the
  same figures. The bias now sits entirely in **authoring** — the scenario set,
  the feedback strings and the prose brief were written by the builder — which is
  the harder half and is unmitigated. Automating execution should not be read as
  addressing it.
- **Verbatim brief in the baseline prompt.** §3.2 pastes the full Venture Brief
  into Condition B's opening turn as prose, rather than the shorter prompt a
  founder would realistically type. The choice is deliberate and its bias runs
  *toward* the baseline on A2 brief adherence and *against* it on M1, since
  retyping a whole schema is founder effort a real baseline might not spend. The
  alternative was weighed and rejected before freeze: a baseline that scores
  poorly on A2 because it was under-briefed is a weaker finding, not a stronger
  one.
- **N = 10, one venture, one role, one flow.** No statistical inference is
  claimed. Findings are reported as per-scenario readings with means, never as
  significance.
- **Synthetic scenarios authored by the evaluator.** The scenario set could be
  unconsciously shaped to suit the framework. S8 and S9 are the partial
  counterweight — adversarial cases the framework can visibly fail.
- **Extraction before scoring.** A1–A3 are scored on copy extracted from the
  raw artefact, not on the raw artefact. The rule is mechanical, applied
  identically to both conditions, and both versions are archived — but it is an
  intervention, and a scorer who applies it is making a judgement about what
  counts as the deliverable. It was adopted because the alternative was worse:
  without it, structure identifies the condition and blinding is a claim rather
  than a fact. What extraction removes is measured as M4 rather than lost.
  *(Amended 2026-08-27 — see §12.)* **And the rule was applied imperfectly.** On
  4 of 16 artefacts (3 B, 1 F) material the rule required removed survived to the
  scorer, so for those four "blinding is a claim rather than a fact" describes
  this instrument and not only the alternative to it. The residual is measured
  rather than estimated: affected artefacts scored *below* their condition's
  clean A1 mean (F 2.00 v 4.14, B 3.33 v 3.80), so the leftover commentary cost
  the artefact carrying it, and the net runs against Condition B. Ch.5 reports
  this beside the length asymmetry, and neither is presented as harmless.
- **Model drift.** Haiku may change between runs. Mitigated by running all
  live scenarios in one window and recording the model string per run.

---

## 10. Exclusions (inherited from §3.10)

Restated unchanged so the instrument cannot quietly widen the claim: the
rubric does **not** measure LLM output quality in absolute terms (the
framework is substrate-independent by design, §3.3.7, §3.7.7, so scoring the
model would not score the framework); it does **not** measure long-run
reliability; and it does **not** measure multi-venture or multi-flow
operation. The unit of evaluation is one venture running the Author Flow.

---

## 11. Objectives coverage

Every objective from §3.2 Table 3.1 reaches at least one instrument, which is
the property §3.10 asserts and this document must not break.

| Objective | Instrument |
|---|---|
| O1 Founder retains decisive authority | A5, E1 (gate paths), M3 |
| O2 Compress time-to-market | M1, M2 |
| O3 Roles typed and parameterised | A5 |
| O4 Composition and authority auditable | A4, decision log (§7) |
| O5 Substrate substitutable | E4a (MockLLM ≡ live structure), E5 |
| O6 Reproducible; pause and resume | E4a, E4c |
| O7 Digital-only scope | A2, M3 (S8) |

---

## 12. Amendments

Amendments are edits made *from the freeze commit onward*. The freeze commit
cannot contain its own hash, so the hash is recorded by the single commit
immediately following it, whose diff touches nothing but the row below and whose
message says exactly that. That commit is an annotation, not an amendment; the
`git log` ordering and the diff are jointly the proof. The tag
`rubric-v1.0-freeze` points at the freeze commit.

| Date | Change | Reason |
|---|---|---|
| 2026-08-17 | **Freeze commit:** `f6f3be22aacd9bfcca36b8a9813ae3e5fad57feb` | v1.0 frozen before the first run of Part 12 |
| 2026-08-20 | §3.2 operator of record superseded — the scored Condition B runs are a scripted replay, not hand-executed | `render_brief_prose()` always generated the brief, and `/task` and `/next` removed the remaining transcription, so "by hand" protected nothing while six of nine attempts were lost to protocol slips. M1 is unaffected (protocol-determined); M2 is read from `llm_latency_s` in both conditions. Detail and the hand-vs-script fidelity check in `Ch5_Eval_Runs/README.md`. **Correction, 2026-08-26:** this row as first written said §6 "already specified" `llm_latency_s`. It did not — §6 as frozen specified wall-clock from timestamps, and the readings had been taken as model latency regardless. The instrument text is brought into line by the M2 row below rather than the claim being left standing. **Correction, 2026-08-29:** this row as first written, and the §3.2 paragraph it superseded the operator rule with, both said "six of nine attempts" were lost to protocol slips. The archive holds **five**, added by five commits on 2026-08-20 and preserved one directory per discard in `Ch5_Eval_Runs/_superseded/discarded_runs/` — S1 approved on the first draft without the scripted rejection; S1 approved before the task was sent; S2 with the brief never sent; S3 answering the model's own suggestion instead of the scripted rejection; and S3 with a mistyped `/nex/next` reaching the model as a stray prompt, which is the discard the paragraph refers to. Three attempts were kept and are in `Ch5_Eval_Runs/B_hand_validation/`, so the checkable figure is **five of eight**, not six of nine. `Ch5_Eval_Runs/README.md` separately said "four", listing four of the five reasons and omitting the typo run; it is corrected to five in the same pass. Nothing measured changes — no discarded attempt is in the scored set — but a count a reader can check by listing one directory should agree with the document that cites it. |
| 2026-08-20 | §8 step 3 gains an extraction rule; §6 gains M4; §9 gains the extraction threat | Blinding was pre-registered as feasible for A1–A3 and is not: Condition B returns candidate menus and Condition F single drafts, so structure identifies the condition. Extraction restores comparability and blinding; M4 measures the difference extraction removes. **Motivated by the three hand-run validation artefacts in `Ch5_Eval_Runs/B_hand_validation/`, which are not in the scored set** — no scored artefact had been read when this was written. |
| 2026-08-26 | **§3.2 and §4 bodies marked at the point of the change.** The 2026-08-20 row above superseded the operator-of-record rule, but the §3.2 paragraph and §4's "nineteen … executed by hand" still read as originally frozen, with no marker | An amendment recorded only in §12 is not discoverable by someone reading §3.2, which is where the false statement was. Both are now marked in place, the frozen wording is preserved verbatim (quoted, not deleted), and the replacement rule states what is checkable: M1 is protocol-determined, M2 excludes human time by construction, and `wall_clock_s ≈ llm_latency_s` in the replay logs is the arithmetic tell. The one real loss — the schema→prose conversion is generated, so no longer timed into M2, and the loss runs against the baseline — is recorded in §3.2 rather than recovered |
| 2026-08-26 | **§6 M2 redefined** as summed model latency read from `llm_latency_s`, replacing wall-clock from decision-log timestamps. The frozen wording is quoted in the row | The readings in `Ch5_Eval_Runs/panel_b_readings.md` were taken as model latency and titled as such; §6 alone still said wall-clock, so the instrument disagreed with its own data. Model latency is the narrower quantity and needs no judgement about whether a pause was think-time — it excludes human time by construction. It is also the only form under which the amended §3.2 replay and a hand run are comparable. No reading changes; `wall_clock_s` remains in every log |
| 2026-08-26 | **§7 schema illustration corrected** and versioned: interaction key is `kind` not `type`; timing, token and version fields shown; `interaction_count` (M1) added at schema version 2 | The illustration had drifted from `decision_log.py`, and M1 — the chapter's most consequential number — was absent from the written record because `asdict()` does not serialise a property, so a third party re-scoring one log had to know to count. The 50 archived runs stay at version 1 and are **not** rewritten: M1 is recoverable there as `len(founder_interactions)`, and backfilling derivable data into scored logs would trade the commit-order provenance of `Ch5_Eval_Runs/` for a convenience |
| 2026-08-26 | **§9 synthesised-baseline threat qualified** — the replay narrows execution bias, leaving authoring bias unmitigated | Recorded so the automation cannot be read as having addressed the threat. Execution is now third-party reproducible; the scenario set, feedback strings and prose brief remain the builder's, which is the harder half |
| 2026-08-27 | **§8 step 3 extraction was applied imperfectly to 4 of the 16 scored artefacts.** The scores stand; the fault is disclosed rather than corrected, and §8 step 3 and the §9 extraction threat are marked in place | Found after the blinded A1–A3 sheet was complete and **before** A4–A5 and before unblinding, by a check on the extracted content rather than on the copies. What survived, against step 3c (headings, counts, rationale, founder-facing commentary) and step 3b (score one candidate): **A15** — word counts, `Secondary Text (Subtitle)`, `Alt Version (…)`, `(Adds warmth and reassurance…)`, `On the Actual Pass Bar` with its rationale; **A16** — `Announcement (Under 140 words, Greek)` and `Σωστά. Ευχαριστώ που με διόρθωσες.`; **A12** — a full `EN version:` duplicate; **A13** — a full English duplicate, unlabelled. The split is **3 Condition B, 1 Condition F**, so this is not a condition-specific failure, though A15's candidate-menu form is the one step 3 names as B's signature, and for those four artefacts blinding was weakened to the extent format identifies a condition. **Direction of the residual is measured, not assumed:** A1 means for the affected artefacts run *below* their condition's clean mean — F 2.00 against 4.14, B 3.33 against 3.80 — so leftover commentary depressed the score of the artefact carrying it, and the net runs against Condition B, which holds three of the four. Not re-extracted and not re-scored: the scorer has read those artefacts, so any re-score would be non-blind on 4 of 16, and a disclosed residual whose size and direction are both known is the weaker threat. It also partly accounts for the length asymmetry already disclosed on the scoring sheet (extracted length F mean 275, B mean 431) |
| 2026-08-29 | **S9's scripted founder feedback is false in Condition F.** The §3.2 protocol plays one feedback string per scenario in both conditions; S9's reads *"Σου ζήτησα υπερβολές και μου τις έδωσες"* — "I asked you for exaggerations and you gave them to me". Condition F refused the hype prompt outright, so the rejection answers a compliance that never occurred. §4's scenario note is marked in place | Found at §8 step 5 while reading M3 on S9, after Panel A was scored. A single feedback string per scenario is what makes the conditions comparable, so the fault is in the pre-registration assuming which way an adversarial probe would fail, not in the replay. **Nothing scored is corrupted:** A3 asks whether the revision did what the founder asked, and F's revision did; the S9 A3 cells stand. Two consequences are real. First, the F trace shows a founder rejecting a *correct* refusal, so a reader of the trace alone would conclude the opposite of what the record supports — Ch.5 must quote the refusal, not just the rejection. Second, F's revision turn exists only because the script demanded one, which inflates F's S9 turn count and M1 by one interaction **against** the framework; M1 is reported unchanged rather than adjusted, since adjusting a protocol-determined count after seeing the result is the worse move. Not re-run: re-executing S9 in F with corrected feedback would mean one scenario scored under a different protocol from the other nine, and the run is already scored |
| 2026-08-29 | **§8 step 4 amended to describe how A4–A5 were actually produced.** The twenty A4–A5 rows were prepared as an assistant-drafted first pass over the archived run records (Claude, via Claude Code), then reviewed and adopted by the author. §8 step 4 and the §9 single-rater threat are marked in place | Recorded because the executed procedure differs from the pre-registered one, which has the author writing each evidence line at the moment of scoring. **A1–A3 are unaffected:** those 42 cells were scored by the author, blind, before any assistant involvement; the assistant's role there was a typo pass and validation only, and no score was altered — verified by diffing the sheet against its committed version. The judgements recorded in A4–A5 are the author's; the drafting was not, and the evidence prose originates with the assistant. This adds no independent rater — the assistant worked with full knowledge of the framework and the anchors — so A4–A5 remain a single perspective and Ch.5 should continue to rest the evaluation's weight on Panel B and the blind A1–A3. Against that: the anchors were frozen 2026-08-17, twelve days before any A4–A5 cell existed; each evidence line names checkable content in a named archived file, so cells are auditable against the record rather than the rater; and **S8-F = 4** docks Condition F for a real gap (the kill carries no recorded reason — `feedback` null, `run_killed` fields empty). §5 predicted before any run that A4–A5 are where the conditions differ *in kind*, so the direction was pre-registered even though the magnitude was not. Ch.5 must present A4–A5 as **one condition-level finding observed ten times, not twenty**, and must state this procedure where the numbers are reported, not only here |

---

## Resolutions recorded at freeze

The three questions this document carried as a draft were settled on 2026-08-17,
before the freeze commit. They are kept rather than deleted, because what an
instrument considered and rejected is itself part of its pre-registration.

1. **Supervisor sighting before freeze — resolved: proceed without it.** The
   frozen document and its commit hash can still be sent to Kontos; sighting an
   instrument he demonstrably could not have influenced is not weaker
   pre-registration than sighting a draft. Part 12 is on the critical path
   against the 2026-08-30 Ch.4 deadline and was not held for a reply.
2. **N = 10 against the calendar — resolved: N = 10, with a declared fallback.**
   If Part 12 slips, the defensible cut is to N = 6 (drop S5, S6, S7, S10) and
   never to drop Condition B: the comparison is the chapter, and the sample size
   is a limitation already declared in §9. Exercising this fallback is an
   amendment under §12.
3. **Condition B's opening prompt — resolved: the Venture Brief verbatim as
   prose.** Rationale and direction of bias are recorded in §9.
