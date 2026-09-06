# Part 12 — run manifest

Generated from **Ch.5 evaluation rubric v1.0**, frozen at commit
`f6f3be22aacd9bfcca36b8a9813ae3e5fad57feb` (tag `rubric-v1.0-freeze`).
This manifest is derived from the frozen instrument and carries no measurement;
if it disagrees with the rubric, the rubric wins.

**47 runs. Nothing is scored until all 47 are complete** (rubric §8 step 2).
Scoring during the run phase is the single easiest way to lose the value the
freeze just bought.

## Condition F — 28 runs, Author Flow

| Block | Run IDs | Model | Reads |
|---|---|---|---|
| Live | `S1-F-01` … `S10-F-01` | `claude-haiku-4-5` | Panel A (A1–A5), E5, M1, M2, M3 |
| E4a determinism | `S2-F-M01`–`M03`, `S3-F-M01`–`M03`, `S8-F-M01`–`M03` | `MockLLM` | Byte-identical hashes, 3/3 per scenario |
| E4b divergence | `S2-F-02`–`04`, `S3-F-02`–`04`, `S8-F-02`–`04` | `claude-haiku-4-5` | Normalised edit distance |

Decision logs are generated from `RunTrace`; no blanks are pre-seeded here.
E1 (suite green, 4/4 termination paths) and E4c (kill-and-resume) are read from
the test runner, not from these runs.

## Condition B — 19 runs, all hand-executed

Operator of record: **the author** (rubric §3.2). Blank decision logs are
pre-seeded in `logs/`, one per run, in the §7 schema.

| Block | Run IDs | Reads |
|---|---|---|
| Live | `S1-B-01` … `S10-B-01` | Panel A (A1–A5), E5, M1, M2, M3 |
| E4b divergence | `S2-B-02`–`04`, `S3-B-02`–`04`, `S8-B-02`–`04` | Edit distance only; not Panel-A scored |

## Suggested execution order

1. Condition F live (10) — cheapest to run, and shakes out harness problems
   while nothing hand-timed is at stake.
2. Condition F determinism blocks (18) — unattended.
3. **Condition B live (10)** — the expensive block. One sitting if possible, so
   operator fatigue does not correlate with scenario order. If it must be split,
   split it after S5, not by condition or by adversarial/non-adversarial.
4. Condition B E4b re-runs (9).
5. Blind, then score (rubric §8 steps 3–4).

Running Condition B last means the baseline is executed by someone freshly
reminded of how the framework behaves. That is a known direction of bias and
it is already declared in rubric §9 under the synthesised-baseline threat. The
alternative — running B first — trades it for a harness-instability risk that
would contaminate the numbers outright. Running B last is the lesser problem;
noting here that the choice was made knowingly is the point.

## Artefact filing

Final artefacts to `artifacts/<run_id>.txt`, verbatim, no cleanup. The sha256 in
each decision log must be of that exact file. Blinding (§8 step 3) strips
provenance downstream; it does not license editing the source artefact.
