# Roadmap — the crew as a company in Discord

Tracking doc for turning the framework (a demonstrated artifact) into a
*living company* the solo founder runs from Discord: channels per function,
agents that act, the founder approving from their phone.

**Scope note.** The milestone ladder (M1–M6) and the Passly go-live track
(B0–B6) are **product**, not the διπλωματική. The thesis contribution — the
five-component framework, the HITL Contract as a substitutable seam, the
operating-model demonstration — is already done and defensible (Ch.3). That part
of this roadmap is what the framework *enables*, built on top of it, and most of
it is post-thesis.

Two sections *are* in-thesis and are both complete: the **Ch.4 Passly demo**
(P0–P4) and the **Ch.5 evaluation harness** (`evaluation/`). They are recorded
here because they are engineering, and a roadmap that omits the largest recent
body of work is not a record. **No engineering item remains on the thesis
critical path** — what is left before submission is Panel A scoring and writing
(thesis Parts 14, 16–19).

**Two tracks, decoupled (decided 2026-06-27).** The thesis ships first —
prose → submit by 2026-09-30 on the existing sandbox/synthetic Passly demo;
no live product gates the submission. *Then* the real goal: **Passly live, a
first real Greek SMB onboarded.** The crew milestones below (M1–M6) are the
*capability ladder*; the **Passly go-live track** (B0–B6, near the bottom) is
the *product buildout* that consumes them and reaches a paying-real-customer
state. M1–M6 are necessary-but-not-sufficient for go-live — B0/B1/B2/B5 are
product layers the crew repo does not contain.

## The reusable spine (already built)

- **Typed authority** — each `Role` has its own `DecisionRights` (`can` /
  `must_escalate`) + tool allowlist. The safety model is core, not bolted on.
- **HITL Contract + `HITLRequest` envelope** — transport-agnostic; routes by
  logical `channel`.
- **`DiscordHITL` + `DiscordPyTransport`** — the founder gate rendered to
  Discord (buttons).
- **Crew Generator, runtime (Author Flow), trace, checkpointer** — compose,
  run, observe, pause/resume.
- **Restart-durable Author Flow** — `Crew.resume(thread_id)` + the daemon's
  `RunsRegistry` bring in-flight runs back online after a process restart;
  stale gate messages are edited so the founder can't tap a dead button.
- **Real outbound tools** behind the same `ToolRegistry` seam: Discord
  publish (`publisher_tool`), GitHub draft PR (`pr_tool`, engineering),
  and email (`email_tool`, marketing — Resend by default with a
  pluggable provider registry for SMTP / SendGrid / etc.).
- **Per-role model routing** — `Crew.role_llms` map; Marketing on Haiku,
  Engineering on Opus, any future role on any LLM via the substrate-
  neutral `LLMClient` Protocol.
- **Crew activity log** — `CrewEventSink` (`events.py`), the same
  Protocol-with-fake seam as `HITLContract` / `LLMClient` / `GitHubAPI`,
  reporting to `#crew-logs`: run started, draft waiting, founder decision,
  coding agent working, cost, PR opened. Before it, a live run could die with a
  bare `FileNotFoundError` and look from Discord like nothing had happened.
- **Operational recovery** — `/retry` brings back a run that died mid-flight
  (distinct from `Crew.resume`, which recovers a run whose *process* restarted);
  the publish gate is declared on every role holding `publisher_tool`, so the
  escalation cannot be bypassed by handing the tool to a new role.
- **Dev workflow** — CI (ruff+pytest) on push + PR; CI→Discord PR notify
  via channel webhook; the `engineering` role / Dev Flow. `/fix` sends the
  engineering role at a red CI run. The coding agent has its own model tier
  (`agent_llm`) rather than inheriting the founder's interactive model — spend
  was following the wrong dial.

## Milestones

| # | Milestone | What it adds | Status |
|---|-----------|--------------|--------|
| **M1** | Live crew daemon | Crew online as a local process; `/draft` `/ask` `/crew` `/status`; founder approves with buttons; durable across restarts (M1.5+M1.6 below); auto-created channels; per-role identity via webhooks | ✅ **closed** — happy path + restart-durability + stale-gate cleanup all verified live |
| **M2** | Real outbound tools | Replace stub publish with real, escalation-gated actions. **Done:** Phase 1 Discord publish; Phase 2 `pr_tool` (engineering → GitHub draft PR); Phase 2 `email_tool` (marketing → Resend, pluggable provider registry); Phase 3 `Implementer` (engineering → a **real diff**: headless Claude Code in a throwaway worktree, escalation checked against the files actually changed). **Deferred:** `update-a-sheet` (Google Sheets) — heavier API ceremony, defer until a concrete Finance flow needs it. | ✅ **built** (deferred sub-item noted) |
| **M2.5** | Per-role model routing | `Crew.role_llms` map: each role can be backed by a different model (e.g. Marketing → Haiku, Engineering → Opus). Demonstrates `LLMClient` Protocol neutrality across tiers; sets up multi-vendor (OpenAI, Gemini) without further runtime changes. | ✅ **built** — Anthropic tier routing landed; OpenAI + Gemini adapters deferred until needed |
| **M3** | Scheduled (proactive) work | Cron triggers: e.g. weekly ads report → #ads-report for review. First "it runs itself" moment | ⏳ |
| **M4** | Event-driven work | Inbound events → flows: a customer message → support triage → draft reply with buttons | ⏳ |
| **M5** | Flow library | Flows beyond Author Flow: triage (support), report (ads/finance), qualification (sales). `/ask` is an early taste (advisory/consult) | ⏳ (partial: `/ask`) |
| **M6** | Memory + handoff | Per-role knowledge stores (each agent its own context); inter-agent handoff + arbitration | ⏳ |

Dependency shape: **M1 is the spine.** M2 + M2.5 + M3 + M4 sit directly on it; M5
+ M6 are the deep end. M2.5 is a cross-cutting capability — it touches the
runtime LLM contract once, then any downstream role can opt into a different
model without further framework changes.

## Milestone detail

### M1 — Live crew daemon ✅
`python -m solo_founder_crew.app`. Slash commands; `DiscordHITL` gate with
Approve/Send back/Kill; SQLite checkpointer; channels auto-created under a
"<venture> crew" category; one webhook per role channel for distinct
identity. Local-first; portable to a VM by config alone. Docs:
`docs/running-the-crew.md`. Happy path + restart-durability +
stale-gate cleanup all verified live on real Discord; on_ready emits
phase logs (registry path, command sync, channel ensure, respawn
count) so any future startup issue is visible in stdout.

### M1.5 — Restart-durable Author Flow ✅

A run paused at a HITL gate must survive a process restart and still
complete when the founder eventually approves. The LangGraph
checkpointer already preserved *graph state*; M1.5 adds the
operational machinery to *bring that state back online* after a
restart.

Two pieces:

- **`Crew.resume(thread_id, role)`** (in `src/solo_founder_crew/crew.py`):
  re-enters the same interrupt-driving loop as ``author_flow``, but
  starts from the existing checkpointed state instead of fresh
  initial state. Shares the loop body via the new
  ``Crew._drive_interrupt_loop`` helper. Raises ``KeyError`` if the
  checkpointer has no state for the given ``thread_id``; returns the
  saved terminal state idempotently if the run already shipped /
  killed / exhausted.

- **`RunsRegistry`** (`src/solo_founder_crew/runs_registry.py`): a
  file-backed map (``data/runs.json``, atomic-rewrite on every
  mutation) from ``thread_id`` to ``{role, task, revisions,
  logical_channel, status}``. This is the operational metadata the
  LangGraph checkpoint does not carry. The daemon writes it on every
  ``/draft`` and on every status transition; reads it on startup to
  discover which runs were in flight when the previous process died.

The daemon's ``on_ready`` calls ``_respawn_pending_runs`` (in
``app.py``) which, for each ``running`` record in the registry,
spawns an ``asyncio.create_task(crew.resume(...))``. That task posts
a *fresh* HITL gate message in the role's channel; the button click
on the new message routes back into the new process's Future and
drives the run to terminal.

**Stale-button cleanup (M1.6, ✅ landed):** the registry now
persists the latest gate's ``(channel_id, message_id)`` via a
``DiscordHITL.on_posted`` hook the daemon installs. On respawn,
``_respawn_pending_runs`` edits the stale message to read
"🔄 Run resumed — see the latest gate above" and strips its
buttons before the resumed flow posts a fresh gate — so the
founder cannot tap a dead button. The edit is best-effort
(missing message / deleted channel / no perms is logged and
swallowed; the resume continues either way).

Tests:

- ``tests/test_crew_resume.py`` (6 tests) — cancellation + resume
  completes; multi-turn resume (reject → revise → approve);
  idempotent on terminal state; ``KeyError`` on unknown thread;
  ``RuntimeError`` without checkpointer; and an end-to-end
  through ``DiscordHITL + InMemoryTransport`` that proves the exact
  contract the daemon uses.
- ``tests/test_runs_registry.py`` (15 tests) — schema, pending
  filter, atomic write, robustness to malformed input.

### M2 — Real outbound tools 🔨
Behind `ToolRegistry`, real actions still gated by `DecisionRights`. Default
new/expensive actions to `must_escalate`. This is what makes Approve real.
- **Phase 1 (done):** `publisher_tool` posts the approved artifact to a
  `#published` Discord channel (`make_discord_publisher` in `app.py`). No new
  credentials. Approving a `/draft` now actually publishes.
- **Phase 2 — open-PR (done):** `pr_tool` opens a **draft** PR on a
  configured GitHub repository with the engineering role's approved
  proposal as the PR body and a corresponding `docs/proposals/<slug>.md`
  file. Lives in `src/solo_founder_crew/adapters/github_pr.py`;
  Protocol-driven (`GitHubAPI`) with `RealGitHubAPI` (httpx + GITHUB_TOKEN)
  and `FakeGitHubAPI` (in-memory for tests). End-to-end example at
  `examples/engineering_pr.py` (mock by default; `--live` opens a real
  draft PR). Drafts are never auto-mergeable; the founder promotes +
  merges on GitHub. The existing `pr-review-notify` workflow posts the PR
  to Discord when CI passes (Dev Flow's notify-only merge gate; see
  `docs/dev-flow.md`).
- **Phase 2 — send-email (done):** `email_tool` sends the marketing
  role's approved artefact as a real email via Resend. Lives in
  `src/solo_founder_crew/adapters/email.py`; same Protocol-with-fake
  shape as the PR tool (`EmailAPI` + `ResendEmailAPI` + `FakeEmailAPI`).
  The Marketing role now holds both `publisher_tool` and `email_tool`
  in its allowlist; `crew.author_flow(publish_tool="email_tool")`
  selects the email path. Subject is derived from the artefact's
  first line; body is rendered as both plain text and HTML. End-to-end
  example at `examples/marketing_email.py` (mock by default; `--live`
  sends through Resend). Sandbox sender `onboarding@resend.dev`
  needs no domain verification — perfect for the thesis demo.
- **Next:** update-a-sheet (Google Sheets) — the niche-but-useful
  finance/sales surface. Heavier API ceremony (service-account JSON)
  than Resend; defer until a concrete Finance flow needs it.

### M2.5 — Per-role model routing ✅

Each `Role` can be backed by a *different* model. The framework's
`LLMClient` Protocol is substrate-neutral by design; `Crew` now
exposes that as a per-role routing map:

```python
crew = Crew(
    brief=brief, roles=[marketing, engineering],
    llm=AnthropicLLM(model="claude-haiku-4-5"),      # default
    role_llms={"engineering": AnthropicLLM(model="claude-opus-4-7")},
    hitl=hitl, tools=tools,
)
```

The runtime resolves the LLM at node-construction time
(`Crew._llm_for(role)`); no node, no graph, and no checkpointer code
knows about tiers. Verified end-to-end by `examples/per_role_models.py`
(marketing on Haiku, engineering on Opus, distinct adapter call logs).

**Multi-vendor (OpenAI, Gemini) is deferred** until a concrete use case
demands it. The Protocol is one method (`complete(system, user) ->
LLMResponse`); adding a vendor is one file + one credential + one
`__post_init__` validation. The seam is open; we walk through it when
needed.

Open follow-ups (out of scope for M2.5 itself):
- **Multi-stage within a role.** Engineering's "Opus for architecture,
  Sonnet for implementation" is two *actions* with different LLMs,
  not one role with a pipeline. Cleanest model is sub-roles
  (`engineering_architect`, `engineering_implementer`) with distinct
  `DecisionRights`. Lands when the live engineering Dev Flow needs it.
- **Cost telemetry.** Each `AnthropicLLM.calls[*]` already records
  token usage; aggregating per-role per-run cost is a small
  observability win for M3 (scheduled work) where budgets matter.

### M3 — Scheduled work
A scheduler (cron) fires flows proactively; results post to the role channel
for async review. Cheap once M1 exists.

### M4 — Event-driven work
Inbound ingestion (email/webhook/Discord read — note: reading channel
messages needs the Message Content privileged intent) → route to a flow.

### M5 — Flow library
Each function gets a flow shaped like its real job, sharing primitives.
`/ask` (consult) already exists as the simplest one.

### M6 — Memory + handoff
Per-role memory namespace (read/write across runs) + agents passing work to
each other and to the founder; the "arbitration/coordination" layer.

## Passly go-live track (post-submission)

The capability ladder above turns the crew into a *living company*. This track
turns **Passly** into a *live venture* — a first real Greek SMB onboarded,
real wallet passes issued, a real campaign sent. It lives in a **separate
`passly` repo** (not yet created) that consumes `solo-founder-crew` as a
dependency; only B3/B4 touch this repo. Scope, scale, and honesty up front:
this is a startup buildout measured in **months, not weeks**, and it starts in
earnest *after* the thesis is submitted (2026-09-30). The framework spine is
not rewritten — B4 walks through seams that are already open.

| # | Phase | What it adds | Where | Status |
|---|-------|--------------|-------|--------|
| **B0** | Product repo bootstrap | New `passly` repo; depends on `solo-founder-crew`; CI; `.env`/secrets; deploy target chosen | `passly` | ⏳ |
| **B1** | Wallet pass issuance | The product core: Apple Wallet (PassKit, `.pkpass` signing, Apple Developer cert) + Google Wallet API. Issue, update, revoke a pass | `passly` | ⏳ |
| **B2** | SMB onboarding surface | SMB sign-up; brand config; define a pass (loyalty card / coupon); QR + link distribution to end-customers | `passly` | ⏳ |
| **B3** | AI marketing layer | Crew marketing role → real campaigns; pass-update pushes on campaign events. Email already real (`email_tool`, Resend) | both | ⏳ (email ✅) |
| **B4** | Crew M3–M5 | Proactive (scheduled campaign/reports), event-driven (SMB signup → onboarding flow; end-customer msg → support triage), flow library | `solo-founder-crew` | ⏳ (= M3/M4/M5) |
| **B5** | Compliance + ops | GDPR for **real** end-customer PII in passes; DPA with each SMB; billing (Stripe); hosting (VM + `postgresql://`); monitoring/budgets | `passly` | ⏳ |
| **B6** | First SMB pilot | Onboard one real Greek SMB end-to-end; real passes + real campaign; iterate to product-market signal | both | ⏳ |

Dependency shape: **B0 → B1 → B2** is the product spine and is independent of
the crew. **B3/B4** are where `solo-founder-crew` plugs in (B4 *is* M3–M5 from
the ladder above, now load-bearing rather than optional). **B5** is the
go-live gate — real PII and money mean it cannot be skipped. **B6** is the
proof. Nothing here is on the thesis critical path; the thesis evaluation
stays sandbox/synthetic by design.

## Ch.4 Passly demo (in-thesis, due 2026-09-30)

Decided 2026-06-27: a **thin slice** of the go-live track is pulled *into* the
thesis as the **Ch.4 Passly application** — a working demo of the platform as
a shop owner sees it when **creating a wallet pass ("πάσο") for a (demo)
shop**. This is B0+B1+B2 (+ a web HITL surface) at demo grade, on synthetic
data; full go-live (B3–B6, real customers/PII/billing) stays post-submission.
It lives in a **new `passly` repo** that consumes this one as a dependency.

**Build decisions:**
- **Real signed `.pkpass` (Apple Wallet)** — passes that actually add to
  Apple Wallet, not a visual mock. Requires an **Apple Developer Program
  cert (~$99/yr)** — external long pole; enrolment is the first action and
  gates P1 (needs Pass Type ID, signing `.p12`, Team ID).
- **AI crew integrated + web approval** — `solo-founder-crew`'s marketing
  crew drafts the pass copy + launch campaign; the founder approves/edits in
  the web UI via a new **`WebHITL` adapter**. This is a *second* adapter on
  the HITL seam alongside `DiscordHITL` — the strongest empirical evidence
  for the §3.8 substitutability claim, and Passly-live step B2.

**Architecture:** `Next.js UI → FastAPI → solo-founder-crew`. The FastAPI
service imports the framework; the framework repo stays clean.

| # | Phase | What | Status |
|---|-------|------|--------|
| **P0** | Scaffold | `passly` repo; Next.js `web/` + FastAPI `api/` (hexagonal, ports & adapters) importing `solo-founder-crew`; GitHub Actions CI | ✅ done (#1, #2) |
| **P1** | Pass issuance | shop design → `.pkpass` (pass.json + icons + manifest + signature) behind a `PassIssuer` port → "Add to Apple Wallet" | ✅ **done** (#5, #8) — **real Apple-signed** `.pkpass`; the Dion cert is in place (`pass.com.passly`, team `AVN9H8BY3X`) and the signature verifies against Apple WWDR |
| **P2** | Shop + designer UI | create shop (name/logo/colours/offer) + live pass preview — the "create a pass" flow | ✅ done (#1) |
| **P3** | Crew + WebHITL | FastAPI drives the crew to draft the campaign; founder approves/edits in web (`WebHITL`, the 2nd HITL adapter → §3.8 evidence) | ✅ done (#3, #4) |
| **P4** | Demo polish | real demo-shop data; end-to-end open → create shop → crew drafts → approve → real `.pkpass`; UI polish | ✅ done (#6) — **Chunky Cookie Bar** (real logo, with permission), end-to-end |

Progress note (2026-08-11): **P0–P4 all shipped.** The demo runs end to end with
**real Apple-signed passes** (Dion cert in place) and the AI crew, on the Chunky
Cookie Bar shop. Beyond P4, the following also landed (all behind the hexagonal
ports, framework-free CI green throughout):

- **SQLite persistence** — shops + members survive restarts (`PASSLY_DB`).
- **Member model** — each customer is a record with a unique pass serial; email
  is the identity (one pass per email per shop, idempotent enrolment).
- **Loyalty stamp counting** — member-identifying QR, a stamps goal, and
  reward + auto-reset at the goal; a shop-side "+1 stamp" console.
- **Pass re-download** — welcome-back join page + an emailed pass link on every
  enrolment (Resend when a key is set, else a no-op sender; logged).
- **Platform-neutral issuance** — a `PassIssuer` port + `ApplePassIssuer`; a
  Google Wallet issuer is a drop-in sibling.

Remaining for a real go-live (deferred): over-the-air pass updates (Apple APNs
push + pass web service) so a customer's wallet card auto-refreshes its stamp
count without re-downloading; a verified email domain; billing; real-PII GDPR.

**Synergy with Ch.5 eval:** the demo's shop scenarios double as the eval
harness scenarios — authored once, used for both Ch.4 (application) and Ch.5
(evaluation).

## Ch.5 evaluation harness (in-thesis, ✅ complete)

`evaluation/` in this repo — the machinery for the Chapter 5 comparison. The
instrument itself (dimensions, anchors, scoring procedure, validity threats) is
the pre-registered rubric in the thesis repo, frozen 2026-08-17 at v1.0 before
any run; this is only what runs it. Docs: `evaluation/README.md`.

| # | Item | Status |
|---|------|--------|
| **E-H1** | Scenario set S1–S10 defined once, read by both conditions | ✅ (#22) |
| **E-H2** | Condition F — Author Flow driven with the role taken from the Role Library, so Component 2 is exercised as shipped. `RecordingHITL` is a **third** `HITLContract` implementation, written without touching `Crew`, `Role` or tool code — §3.8 substitutability evidence | ✅ (#22) |
| **E-H3** | Condition B — a bare chat loop that **imports nothing from `solo_founder_crew`**. Same model, same `max_tokens`, so a difference cannot be attributed to the model | ✅ (#22) |
| **E-H4** | `run_condition_b.py` — scripted replay of the baseline protocol, third-party re-runnable | ✅ (#23) |
| **E-H5** | Operator guards + 48 protocol tests; `interaction_count` (M1) written into the log at schema v2 | ✅ (#24, #25) |

**47/47 runs complete**, across `F_mock_e4a`, `F_live_scored`, `F_live_e4b`,
`B_live_scored`, `B_live_e4b`. Panel B is read where §8 permits; Panel A scoring
(thesis Part 14) is the remaining thesis work and is **not** engineering.

Two things worth carrying forward, because they are framework findings rather
than harness details:

- **A third HITL adapter, for free.** `RecordingHITL` joins `DiscordHITL` and
  `WebHITL` on the same seam. Three independent implementations, none of which
  required a runtime change, is the strongest form the §3.8 claim takes.
- **The baseline shares no code, only data.** Both conditions read the same
  brief JSON and the same scenario definitions and nothing else. If the baseline
  imported the framework, "no framework" would be a claim the code contradicts —
  a test asserts it over parsed imports.

## Decisions log

- **Ch.4 = a real Passly demo, not a mockup (2026-06-27).** The thesis Ch.4
  application is a working demo: create a real signed `.pkpass` for a demo
  shop, with the AI crew drafting copy/campaign and the founder approving via
  a web `WebHITL` adapter. Chosen over a visual-mock UI because (a) a 2nd
  HITL adapter is the strongest evidence for §3.8 substitutability, and (b)
  it is a reusable thin slice of Passly-live (B1/B2). New `passly` repo,
  `Next.js → FastAPI → solo-founder-crew`. Apple Developer cert is the long
  pole — enrol first.
- **Thesis and Passly-live decoupled; thesis first (2026-06-27).** The
  διπλωματική submits on the sandbox/synthetic demo (defensible as-is); the
  Passly go-live track (B0–B6) runs post-submission so a fuzzy product goal
  never threatens the hard 2026-09-30 deadline. "Live" is defined as a first
  real Greek SMB onboarded.
- **Bot identity = per-role webhooks (Option A), not N separate bots.** One
  token/process; roles post under their own name via channel webhooks. The
  HITL approval gate stays on the main bot (embed labels the role). N real
  bot apps was rejected for the 6× setup/connection cost. (M1.)
- **Per-role "knowledge" deferred to M6** — it's a separate axis from
  identity. Skillset is already per-role (decision rights + tools).
- **PR review = notify-only.** CI-pass → Discord notification; founder
  reviews/merges on GitHub. Interactive "Approve & merge from Discord" (a
  serverless function or always-on bot) is specced but not built — needs a
  host + a GitHub merge token.
- **Local-first, VM-portable.** Outbound gateway (no inbound port);
  `sqlite:///` now → `postgresql://` later; `.env`/`tmux` → secret-manager/
  systemd later. Migration is config, not code.
- **Branch protection deferred** — private repo needs GitHub Pro or going
  public; running on soft convention (CI visible, ping-on-green) for now.

## Cross-cutting

- **Cost / autonomy guardrails:** proactive agents (M3/M4) make LLM calls +
  take actions — needs budgets/rate limits. `must_escalate` is the safety net.
- **Hosting:** local (Mac, `tmux`) for the thesis; VM later, no code change.
- **Observability:** the `RunTrace` already logs every step.
