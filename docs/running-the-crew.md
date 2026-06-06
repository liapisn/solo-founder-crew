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
  Webhooks** (Manage Channels lets the daemon auto-create the role channels;
  Manage Webhooks lets each role post under its own name) → open the URL, add
  it to your server.
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
- **`/draft role:marketing task:"launch announcement for the wallet pass"`** —
  runs Author Flow; the draft appears in `#marketing` with buttons. Tap
  **Approve** to publish (stubbed), **Send back** to revise with notes, or
  **Kill run** to abort.
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
