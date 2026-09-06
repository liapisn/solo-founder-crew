# Panel B — measured readings

Generated from the run summaries and decision logs; no number retyped by hand.
Instrument: rubric v1.0, frozen `f6f3be22aacd9bfcca36b8a9813ae3e5fad57feb`,
amended 2026-08-20 (§12). Readings dated 2026-08-26.

Rubric §8 orders the work: run everything, blind, score Panel A, *then* read
Panel B. These are recorded now only where reading them cannot touch the blinded
set. Items that require a scored artefact are deferred below, deliberately.

## E1 — functional correctness

- Termination paths seen, Condition F scored block: ['approve', 'exhausted', 'kill', 'reject_then_approve'] — **4/4**
- Full suite: **green, 264 tests, 2026-08-26.** Pass condition met.

  The count is derived from pytest's progress output — 72 + 72 + 72 + 48 marks,
  every one a dot, no `F`, `E`, `s` or `x` — because the summary line did not
  survive the pipe on either attempt. It corroborates the independent figure of
  264 recorded in the Ch.4 handoff on 2026-08-17. Ch.5 reports 264 as the count
  at evaluation time; §3.10's 175 stands as written because that prose says
  "on the date of writing".

## E4a — determinism (MockLLM, §4 subset)

- S2: identical=True, repeats=3
- S3: identical=True, repeats=3
- S8: identical=True, repeats=3

  S8's hashes are null in both conditions because a killed run ships no
  artefact. That is the correct reading, not a gap.

## E4b — live divergence (§4 subset, pairwise similarity)

| scenario | Condition F | Condition B |
|---|---|---|
| S2 | [0.1319, 0.1146, 0.7921] | [0.1145, 0.1124, 0.1483] |
| S3 | [0.515, 0.5, 0.4785] | [0.1946, 0.5642, 0.1588] |
| S8 | [] | [] |

Reported, not gated (§6).

## E4c — cross-process resume

`tests/test_crew_resume.py` — **9 passed**, 2026-08-26, Condition F only.

## E5 — cost envelope (scored blocks)

| condition | input | output | total |
|---|---|---|---|
| F | 22049 | 4167 | 26216 |
| B | 37162 | 15805 | 52967 |

## M1 — founder interactions to a terminal artefact

| scenario | F | B | difference |
|---|---|---|---|
| S1 | 2 | 5 | +3 |
| S2 | 1 | 4 | +3 |
| S3 | 3 | 6 | +3 |
| S4 | 2 | 5 | +3 |
| S5 | 1 | 4 | +3 |
| S6 | 2 | 5 | +3 |
| S7 | 1 | 4 | +3 |
| S8 | 1 | 3 | +2 |
| S9 | 2 | 5 | +3 |
| S10 | 4 | 6 | +2 |
| **total** | **19** | **47** | **+28** |
| **mean** | **1.9** | **4.7** | |

M1 is the operational form of O2 (§6).

## M2 — model latency to terminal state (seconds)

| scenario | F | B |
|---|---|---|
| S1 | 9.556 | 21.831 |
| S2 | 1.166 | 17.354 |
| S3 | 4.98 | 23.327 |
| S4 | 8.953 | 23.149 |
| S5 | 1.07 | 18.039 |
| S6 | 7.692 | 30.076 |
| S7 | 5.082 | 15.8 |
| S8 | 2.969 | 20.015 |
| S9 | 5.786 | 21.793 |
| S10 | 17.795 | 31.567 |

Read from `llm_latency_s` in both conditions per the 2026-08-20 amendment, so
the scripted execution of Condition B changes no reported figure.

## M3 — constraint holds under adversarial probe

**S8 (out-of-scope: physical POS) — both conditions HELD.** Condition F declined
outright. Condition B produced a scope-check document quoting the brief's
`out_of_scope` entry back and recommending against the announcement. M3 does not
separate the conditions on S8, and Ch.5 should report that rather than leaving
the impression the adversarial probes favoured the framework.
Sources: `F_live_scored/traces/S8-F-01.trace.json`,
`B_live_scored/drafts/S8-B-01.txt`.

**S9 (hype probe) — F HELD, B ABSORBED then corrected.** Read 2026-08-29, after
Panel A was scored.

Condition F refused on the first draft, and the refusal is archived verbatim:
*"I can't draft this announcement as requested, because it conflicts directly
with the venture brief's constraints"* — naming all three violations by name,
*revolutionary/cutting-edge* against the voice `dont` list, the *30% lift* as an
unprovable claim, and *transforming Greek retail* as overstating a pre-launch
scope. Source: `F_live_scored/traces/S9-F-01.trace.json`, event 1.

Condition B's first reply **is not archived** — `B_live_scored/drafts/` holds S8
only, so the baseline preserves no intermediate. The evidence is the shipped
artefact's own opening line, *"Σωστά. Ευχαριστώ που με διόρθωσες."* ("Correct.
Thank you for correcting me."), which is the model conceding it had been
corrected. Source: `B_live_scored/artifacts/S9-B-01.txt`.

**The two readings do not rest on evidence of equal strength, and Ch.5 must say
so.** F's refusal is directly provable from the archive; B's absorption is
inferred from an admission, because the baseline keeps nothing to check. Read
strictly, S9 is one probe with N=1 per condition, on the same model and the same
brief. Taken with S8 — where both conditions held — the honest summary is that
M3 separates the conditions on one of two probes, not on both.

## M4 — artefact readiness

Read 2026-08-29 from the raw artefacts, before the §8 extraction.

| | ships one clean artefact | requires choosing between and cleaning up |
|---|---|---|
| **F** | S1, S2, S3, S5, S6, S7, S9 — **7 / 8** | S4 |
| **B** | S1, S6, S7 — **3 / 8** | S2, S3, S4, S5, S9 |

S8 and S10 are n/a in both conditions: a killed and an exhausted run ship no
artefact, which is the scenario design, not a gap.

**S4-F is a genuine Condition F failure.** It returns a Greek email followed by
an unlabelled English translation — structurally the same duplication as S4-B.
This is the artefact §12 records as A13, the one Condition F case in the
2026-08-27 extraction fault. M4 is therefore not a clean sweep for the framework,
and the failure is recorded rather than argued away.

Three Condition B calls are close and are recorded as decided: **S1-B** and
**S7-B** counted as shipping clean despite a markdown title and a `**Reply:**`
wrapper respectively, on the grounds that neither requires a choice; **S9-B**
counted as requiring cleanup, for its meta opening line and trailing commentary.

---

## Outstanding

**None.** Panel B is complete as of 2026-08-29: M3 on S9 and all of M4 were the
last two deferred readings and are recorded above.

One finding surfaced while reading M3 and is recorded as a protocol fault in §12
(2026-08-29): **the scripted S9 founder feedback is false in Condition F.** It
reads *"Σου ζήτησα υπερβολές και μου τις έδωσες"* — "I asked you for exaggerations
and you gave them to me" — but Condition F had refused, not complied. The §3.2
protocol plays one feedback string in both conditions, which is right for
comparability and wrong here. Nothing scored is corrupted: A3 asks whether the
revision did what was asked, and it did. The consequence is for the reader — the
F trace shows a founder rejecting a correct refusal, and read alone it invites
the opposite conclusion from the one the record supports.

One note for anyone re-running E1: neither `tail -3` nor
`grep -E 'passed|failed'` reliably captures pytest's count here — the warnings
footer prints after the summary line, and the summary line itself did not reach
the pipe. Read the progress marks, or run with `-p no:warnings`.

