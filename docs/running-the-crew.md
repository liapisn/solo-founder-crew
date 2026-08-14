# Running the crew (live, local)

M1 of the "company in Discord" roadmap: run the crew as a long-lived local
process. The agents are **online** — you start a flow from Discord with a
slash command and approve / reject / kill it with buttons. Runs are **durable
across restarts** (SQLite checkpointer).

Built local-first; portable to a VM later by config alone (see the bottom).

## What M1 does (and doesn't)

- **Does:** crew online; `/draft` starts an Author Flow for a role; the draft
  lands in that role's channel with Approve / Send back / Kill buttons; state
  survives restarts.
- **Doesn't (yet):** scheduled work (M3), inbound events (M4), new flow types
  beyond Author Flow (M5), real publish tools (M2 — publishing is stubbed).

## Setup

### 1. Install the runtime extra

```bash
cd solo-founder-crew
.venv/bin/pip install -e ".[runtime]"
```

### 2. Discord bot

Create a bot and invite it (Developer Portal → your app):
- **Bot** tab → Reset Token → copy (this is `DISCORD_BOT_TOKEN`).
- **OAuth2 → URL Generator** → scopes **`bot`** AND **`applications.commands`**
  (both — the second is required for slash commands to register) → bot
  permissions: **Send Messages, Embed Links, Manage Channels, Manage
  Webhooks, Create Public Threads** (Manage Channels = auto-create role
  channels; Manage Webhooks = per-role identity; Create Public Threads =
  keep revision rounds in a thread) → open the URL, add it to your server.
  (Granting **Administrator** covers all of these.)
- No privileged intents needed (slash commands + buttons).

### 3. Config

**Channels are created for you.** On connect, the daemon ensures a channel
per role exists (`#marketing`, `#product`, `#engineering`, …) under a
"<venture> crew" category, creating any that are missing (needs the bot's
Manage Channels permission). So `crew.toml` is **optional** — copy
`crew.toml.example` → `crew.toml` only if you want to pin specific channels
(an explicit `[channels]` mapping always wins over auto-create) or change the
brief/model. To turn auto-create off, set `SFC_AUTO_CHANNELS=false` (then map
channels yourself).

**Each role posts under its own name.** The daemon also creates one webhook
per role channel (needs Manage Webhooks), so role messages — e.g. the
product role's `/ask` replies — appear from "Product", "Engineering", etc.,
like distinct teammates, while still being one bot under the hood. The HITL
approval gate (the draft + buttons) stays on the main bot, with the embed
labelling the role. If Manage Webhooks is absent, role posts just use the
bot's identity (still works).

Put secrets / infra in `.env` (gitignored):

```
DISCORD_BOT_TOKEN=your-bot-token
SFC_GUILD_ID=your-server-id
# SFC_MODEL=real            # uncomment for live drafting (needs the next line)
# ANTHROPIC_API_KEY=sk-ant-...
```

`model = "mock"` (the default) runs fully offline with a placeholder draft —
enough to see the wiring and the founder gate. Set `SFC_MODEL=real` for actual
Haiku drafting.

### 4. Run

```bash
.venv/bin/python -m solo_founder_crew.app
```

You'll see `Crew online as <bot> · venture=Passly · roles=[…]`.

### Keep it alive locally

For the thesis, a terminal or `tmux` session is enough:

```bash
tmux new -s crew '.venv/bin/python -m solo_founder_crew.app'
```

(Optional polish: a `launchd` plist to survive reboot — not required for M1.)

## Using it from Discord

- **`/crew`** — the roster + each role's decision rights.
- **`/draft role:marketing task:"…" [revisions:3]`** — runs Author Flow; the
  draft appears in `#marketing` with buttons. Tap **Approve** to publish
  (posts to **#published** — M2), **Send back** to revise with notes, or
  **Kill run** to abort. `revisions` (default 3) is how many send-backs you
  get before the run ends as **exhausted** (nothing published — just run
  `/draft` again). The channel gets a closing line when a run ends
  (✅ published / ⚠ exhausted / 🛑 killed). The first draft posts in the
  channel (and @mentions you); **revision rounds go into a thread** off that
  message, so the channel stays clean.
- **`/ask role:product question:"what's our roadmap?"`** — advisory; the role
  replies in its own channel under its own name.
- **`/status`** — in-flight runs and which ones await your tap.

Note: the gate's displayed action label is currently the generic
`final_approval_before_publish` even for the engineering role (whose true
gate is `merge_to_main`) — the gate works correctly; only the label is
generic. Per-role gate labels are a small runtime refinement, not M1.

## Local → VM later (config, not code)

| Concern | Local now | VM later |
|---|---|---|
| State | `SFC_CHECKPOINTER_URL=sqlite:///./data/state.db` | `SFC_CHECKPOINTER_URL=postgresql://…` (swap saver) |
| Secrets | `.env` | same var names via the host's secret manager |
| Process | `tmux` | `systemd` / Docker / Fly — same `python -m solo_founder_crew.app` |
| Networking | outbound gateway (nothing to open) | identical |

The daemon connects to Discord over an **outbound** WebSocket, so it works
behind home NAT with no port-forwarding — and the exact same on a VM.

## The activity log (`#crew-logs`)

The gate tells you when a *decision* is needed. It says nothing about anything
either side of it. `#crew-logs` carries that: which run started, that a draft is
waiting, what you decided, that a coding agent is working, what it cost, and
whether a pull request opened.

The channel is auto-created alongside the role channels and `#published`, so
there is nothing to configure. Without it the daemon runs exactly as before —
the sink is inert when no channel is bound.

A full engineering run reads like this:

```
▶️ engineering · started a run  run-1537
> In the passly wallet pass the Member field is empty — show the member's name

⏸️ engineering · waiting for your review (turn 1)  run-1537

🫵 engineering · you chose approve  run-1537

🛠️ engineering · implementing "Show the member's name on the wallet pass"
branch engineering/show-the-member-s-name-… — a coding agent is working in a worktree.

📦 engineering · 2 file(s) changed
11 turns · 94s · $0.8700

🔀 engineering · opened a draft PR
https://github.com/liapisn/passly/pull/9

✅ engineering · run finished — shipped  run-1537
```

Escalations and failures appear here too, which is the point: a run that dies
inside the coding agent used to be visible only in the daemon's stdout and the
checkpointer.

### How it is wired

`CrewEventSink` is a Protocol with the usual pair — `DiscordEventSink` for real
use, `RecordingEventSink` for tests — and `NullEventSink` as the default so
nothing is required.

Gate and decision events come from `LoggingHITL`, a **decorator** around any
`HITLContract`. Observability was not allowed to become a reason to edit the
contract itself (Ch.3 §3.8), and wrapping means any surface — Discord, web,
stdin — gains the same log for free.

For Ch.4, these events *are* the case-study measurements: gate latency,
revision counts, approve/reject ratios, escalation frequency and cost per
change, captured while the venture is built rather than reconstructed later.
