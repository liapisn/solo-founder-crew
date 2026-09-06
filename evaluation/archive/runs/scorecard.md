# Ch.5 scorecard — Part 14

Shape follows `solo-founder-crew/docs/spike-scorecard.md`: **table first, per-cell
evidence below, no number standing alone.** Instrument: rubric v1.0, frozen
`f6f3be22aacd9bfcca36b8a9813ae3e5fad57feb`, amended through 2026-08-29 (§12).
Unblinded and aggregated 2026-08-29.

Panel A cells are recorded in `panel_a_scoring_sheet.md` (A1–A3, blinded) and
`panel_a_record_sheet.md` (A4–A5, unblinded), each with its per-cell evidence
line. Those two sheets are the evidence of record; this file aggregates them.

---

## The headline

| | Condition F | Condition B | gap |
|---|---|---|---|
| **A1–A3 — blinded, author-scored, 8 scenarios** | 249/290 = **85.9%** | 234/290 = **80.7%** | **+5.2 pp** |
| **A4–A5 — unblinded, 10 scenarios** | 198/200 = **99.0%** | 58/200 = **29.0%** | **+70.0 pp** |
| Panel A combined | 447/490 = 91.2% | 292/490 = 59.6% | +31.6 pp |

**Read the first two rows and ignore the third.** The combined figure averages a
blinded judgement of prose with an unblinded judgement of record-keeping; it is
the least informative number here and is given only because omitting it would
look like concealment.

§2, written before any run, predicted "Panel A near parity, Panel B separating
the conditions, because both call the same model on the same brief." **That
prediction held.** On the blind criteria the two conditions are 5.2 points apart,
and Condition B matched or beat Condition F on five of eight scenarios (S3, S4
to B; S5, S7, S9 tied). The framework does not write better copy. It was never
claimed to.

---

## Panel A — scored

Weighted total = Σ(score × weight). Max 60; 50 where A3 is dropped (S2, S5, S7);
20 for S8 and S10, which are in Panel A on A4–A5 only. Reported as % of the
applicable maximum.

| Scenario | Cond | A1 ×3 | A2 ×3 | A3 ×2 | A4 ×2 | A5 ×2 | Total | % of max |
|---|---|---|---|---|---|---|---|---|
| S1 | F | 5 | 5 | 5 | 5 | 5 | 60/60 | 100.0% |
| S1 | B | 4 | 5 | 5 | 2 | 1 | 43/60 | 71.7% |
| S2 | F | 4 | 5 | — | 5 | 5 | 47/50 | 94.0% |
| S2 | B | 3 | 4 | — | 2 | 1 | 27/50 | 54.0% |
| S3 | F | 1 | 4 | 5 | 5 | 5 | 45/60 | 75.0% |
| S3 | B | 2 | 4 | 4 | 2 | 1 | 32/60 | 53.3% |
| S4 | F | 2 | 3 | 4 | 5 | 5 | 43/60 | 71.7% |
| S4 | B | 2 | 4 | 4 | 2 | 1 | 32/60 | 53.3% |
| S5 | F | 5 | 5 | — | 5 | 5 | 50/50 | 100.0% |
| S5 | B | 5 | 5 | — | 2 | 1 | 36/50 | 72.0% |
| S6 | F | 4 | 4 | 5 | 5 | 5 | 54/60 | 90.0% |
| S6 | B | 3 | 3 | 3 | 2 | 1 | 30/60 | 50.0% |
| S7 | F | 5 | 5 | — | 5 | 5 | 50/50 | 100.0% |
| S7 | B | 5 | 5 | — | 2 | 1 | 36/50 | 72.0% |
| S8 | F | — | — | — | 4 | 5 | 18/20 | 90.0% |
| S8 | B | — | — | — | 1 | 1 | 4/20 | 20.0% |
| S9 | F | 5 | 5 | 5 | 5 | 5 | 60/60 | 100.0% |
| S9 | B | 5 | 5 | 5 | 2 | 1 | 46/60 | 76.7% |
| S10 | F | — | — | — | 5 | 5 | 20/20 | 100.0% |
| S10 | B | — | — | — | 2 | 1 | 6/20 | 30.0% |

### Per-criterion means (1–5)

| | A1 voice | A2 brief | A3 feedback | A4 trace | A5 authority |
|---|---|---|---|---|---|
| **F** | 3.88 | 4.50 | 4.80 | 4.90 | 5.00 |
| **B** | 3.62 | 4.38 | 4.20 | 1.90 | 1.00 |
| **Δ** | +0.25 | +0.12 | +0.60 | **+3.00** | **+4.00** |

The three output-quality criteria are within 0.6 of a point. The two
record-keeping criteria are three and four points apart. That is the whole
result in one table.

### Cells worth naming

**The lowest cell in the entire set is Condition F's.** S3-F scored **A1 = 1** —
a `voice.dont` violation in the framework's own output, scored blind, with the
blinded id `A01`. Condition B scored 2 on the same scenario. The scorer did not
know which was which. A single blind cell scored against the thesis is worth more
to the argument than the twenty cells that favour it.

**S4 is Condition F's worst scenario on the blind criteria** (23 to B's 26).
S4-F returned a Greek email followed by an unlabelled English translation — the
same duplication as S4-B, and the same artefact §12 records as A13 in the
2026-08-27 extraction fault. It fails M4 as well. One scenario, three separate
marks against the framework, all recorded.

**S8-F = 4 on A4** — the only F cell below 5 on the record criteria. The kill is
logged with actor, decision and timestamp, but `feedback` is null and both
`run_killed` fields are empty, so *why* it was killed is inferable from the
draft's refusal text rather than stated. A4 asks for what happened **and why**.

**A5 = 1 across all ten Condition B runs.** `gated_actions` is empty in every
baseline log because nothing gates. §5 anticipated this and warned against
inflating it for even-handedness.

---

## Panel B — measured

| ID | Condition F | Condition B | ratio | source |
|---|---|---|---|---|
| E1 suite + paths | green, 264 tests; 4/4 paths | n/a | — | pytest, 2026-08-26 |
| E4a byte-identical | True/True/True (S2,S3,S8) | n/a — no MockLLM path | — | `F_mock_e4a/summary_F_mock.json` |
| E4b divergence S2 | [0.1319, 0.1146, 0.7921] | [0.1145, 0.1124, 0.1483] | — | e4b summaries |
| E4b divergence S3 | [0.515, 0.5, 0.4785] | [0.1946, 0.5642, 0.1588] | — | e4b summaries |
| E4c kill-and-resume | 9 passed | n/a | — | `tests/test_crew_resume.py` |
| E5 tokens (in/out) | 22049 / 4167 = 26216 | 37162 / 15805 = 52967 | **2.0×** | scored logs |
| M1 interactions total | **19** (mean 1.9) | **47** (mean 4.7) | **2.5×** | scored logs |
| M2 latency total (s) | **65.0** | **223.0** | **3.4×** | `llm_latency_s` |
| M3 · S8 out-of-scope | held | held | — | trace / draft |
| M3 · S9 hype | held | absorbed, then corrected | — | trace / artefact |
| M4 readiness | **7/8** clean | **3/8** clean | — | raw artefacts |

Full readings and their caveats: `panel_b_readings.md`.

**M1 and M2 are the load-bearing numbers**, and neither involves a judgement.
M1 is protocol-determined; M2 is summed model latency, which excludes human time
by construction rather than by subtraction (§12, 2026-08-26).

**M3 does not separate the conditions cleanly.** On S8 both held. On S9 the two
readings do not rest on evidence of equal strength: Condition F's refusal is
archived verbatim in the trace, naming all three violations; Condition B's
absorption is *inferred* from the shipped artefact's opening line — "Σωστά.
Ευχαριστώ που με διόρθωσες" — because the baseline archives no intermediate
reply. One probe of two, N=1 per condition, on the same model and brief.

---

## What the evaluation supports, and what it does not

**Supported.** Condition F reached the same output quality for **2.5× fewer
founder interactions, 3.4× less model latency and 2.0× fewer tokens**, while
producing a record from which a third party can reconstruct each run, and
enforcing a declared approval gate at dispatch. It returned a ship-ready artefact
in 7 of 8 cases against 3 of 8.

**Not supported.** That the framework improves the writing. The blind criteria
put the conditions 5.2 points apart and Condition B was at least equal on five of
eight scenarios. Any claim that the framework produces better copy is contradicted
by this instrument's own blinded data.

**Not supported.** That the framework is more robust to adversarial prompts in
general. One probe of two separated the conditions, on evidence of unequal
strength, at N=1.

---

## Threats carried into Ch.5

Each is recorded in the rubric with its date and reason; none is discovered here.

1. **Extraction applied imperfectly to 4 of 16 artefacts** (§12, 2026-08-27).
   Direction measured, not assumed: the affected artefacts scored *below* their
   condition's clean mean, and three of the four are Condition B, so the residual
   runs against the baseline.
2. **A4–A5 were an assistant-drafted first pass, reviewed and adopted by the
   author** (§12, 2026-08-29). The judgements are the author's; the drafting was
   not. No independent rater is added. This is the +70 pp row, and it is the row
   to lean on least.
3. **S9's scripted feedback is false in Condition F** (§12, 2026-08-29). It
   accuses the model of producing hype it had refused to produce. Nothing scored
   is corrupted, but the F trace read alone invites the opposite conclusion from
   the one the record supports, and the forced revision turn inflates F's M1 by
   one interaction *against* the framework.
4. **Single rater, who is also the builder** (§9). Mitigated by pre-registration,
   frozen anchors, blinding of A1–A3, per-cell evidence and a re-scorable
   archive. Not eliminated.
5. **Synthesised baseline** (§9, amended 2026-08-26). Execution is now
   third-party reproducible; the scenario set, feedback strings and brief remain
   the builder's, which is the harder half and is unmitigated.

---

## The predicted shape, checked

Rubric §2, before any run: Panel A near parity, Panel B separating the
conditions. **Held.** The blind criteria came in 5.2 points apart; the separation
sits in M1, M2, E5, M4 and the two record criteria.

This file previously carried the instruction: *"If Panel A comes out strongly
favouring Condition F, re-check the blinding before treating it as a finding."*
The blinded portion did not strongly favour Condition F — it came within one
scenario of a tie. The +70 pp appears only in A4–A5, which are unblinded **by
design** because they score the record rather than the artefact (§8 step 3), and
which §5 named before any run as the criteria where the conditions differ *in
kind*. The direction was pre-registered; the magnitude was not, and Ch.5 should
present A4–A5 as **one condition-level finding observed ten times, not twenty**.
