# Roadmap — the crew as a company in Discord

Tracking doc for turning the framework (a demonstrated artifact) into a
*living company* the solo founder runs from Discord: channels per function,
agents that act, the founder approving from their phone.

**Scope note.** This is **product**, not the διπλωματική. The thesis
contribution — the five-component framework, the HITL Contract as a
substitutable seam, the operating-model demonstration — is already done and
defensible (Ch.3). This roadmap is what the framework *enables*, built on top
of it. Most of it is post-thesis; the most it should touch the thesis is
enriching the Ch.4 Passly demonstration (still sandbox/synthetic).

## The reusable spine (already built)

- **Typed authority** — each `Role` has its own `DecisionRights` (`can` /
  `must_escalate`) + tool allowlist. The safety model is core, not bolted on.
- **HITL Contract + `HITLRequest` envelope** — transport-agnostic; routes by
  logical `channel`.
- **`DiscordHITL` + `DiscordPyTransport`** — the founder gate rendered to
  Discord (buttons).
- **Crew Generator, runtime (Author Flow), trace, checkpointer** — compose,
  run, observe, pause/resume.
- **Dev workflow** — CI (ruff+pytest) + CI→Discord PR notify + the
  `engineering` role / Dev Flow.

## Milestones

| # | Milestone | What it adds | Status |
|---|-----------|--------------|--------|
| **M1** | Live crew daemon | Crew online as a local process; `/draft` `/ask` `/crew` `/status`; founder approves with buttons; durable across restarts; auto-created channels; per-role identity via webhooks | ✅ **built** (live-verify the `/draft` button gate to fully close) |
| **M2** | Real outbound tools | Replace stub publish with real, escalation-gated actions. **Phase 1 done:** Approve posts the artifact to #published (Discord). **Next:** send-email, open-PR, update-a-sheet | 🔨 in progress |
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
`docs/running-the-crew.md`. **Open:** live-verify `/draft` → button → publish
(the suite proves the gate via `InMemoryTransport`; the Discord gateway
round-trip is only checkable by running it).

### M2 — Real outbound tools 🔨
Behind `ToolRegistry`, real actions still gated by `DecisionRights`. Default
new/expensive actions to `must_escalate`. This is what makes Approve real.
- **Phase 1 (done):** `publisher_tool` posts the approved artifact to a
  `#published` Discord channel (`make_discord_publisher` in `app.py`). No new
  credentials. Approving a `/draft` now actually publishes.
- **Next:** send-email (SMTP/Resend), open-PR (GitHub token — wires
  `pr_tool` for the engineering role), update-a-sheet (Google Sheets). Each
  is a new tool behind the same seam; each needs its own credential.

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

## Decisions log

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
