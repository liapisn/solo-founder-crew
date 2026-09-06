# Thesis evaluation archive

The complete record of the Chapter 7 evaluation of the thesis *AI-Native Management
and Orchestration: A Methodological Framework for Solo-Founder Digital
Entrepreneurship* (N. Liapis, Πανεπιστήμιο Αιγαίου / ΕΜΠ, 2026). Everything the
thesis reports about the evaluation is traceable to a file in this folder; the
harness that produced the runs is the parent directory, `evaluation/`.

| Path | What it is |
|---|---|
| `RUBRIC.md` | The pre-registered instrument, v1.0, with its amendment record (§12) |
| `runs/scorecard.md` | The aggregation every Chapter 7 figure is read from |
| `runs/panel_a_scoring_sheet.md` | Panel A cells A1–A3, scored blind, with per-cell evidence |
| `runs/panel_a_record_sheet.md` | Panel A cells A4–A5 (record criteria), with per-cell evidence |
| `runs/panel_b_readings.md` | Panel B measured readings and their caveats |
| `runs/F_live_scored/`, `runs/B_live_scored/` | The ten scored runs per condition: decision logs, traces, artefacts |
| `runs/F_mock_e4a/`, `runs/F_live_e4b/`, `runs/B_live_e4b/` | Reproducibility readings (E4a byte-identity, E4b divergence) |
| `runs/panel_a_blinded/`, `runs/extraction_log.json` | The blinded artefacts as scored, and the record of what extraction removed |
| `runs/B_hand_validation/` | The hand-run validation of the scripted Condition B replay |
| `runs/_superseded/` | Discarded attempts, kept rather than deleted (rubric §12) |
| `runs/README.md` | Layout and naming of the run folders |

## Provenance

These files were copied verbatim on 2026-09-06 from the author's thesis repository,
where the instrument was frozen **before the first scored run**:

- freeze commit `f6f3be22aacd9bfcca36b8a9813ae3e5fad57feb`, tag `rubric-v1.0-freeze`, 2026-08-17;
- first scored run 2026-08-20; nine amendments recorded in `RUBRIC.md` §12 between
  2026-08-20 and 2026-08-29, each with date and reason, superseded wording preserved;
- last amendment commit `72d60f1`, 2026-08-29;
- SHA-256 of `RUBRIC.md` as copied: `dc202d701b5b2ed1b318fe4005a6d839cdf3b997025b7bf9ff6ace7035854ccb`.

The commit ordering that evidences the pre-registration lives in that thesis
repository's history and is available to the examining committee on request; this
folder carries the content, not the history.
