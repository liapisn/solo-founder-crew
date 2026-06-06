# Live Discord HITL surface — setup

This runs the framework's Human-in-the-Loop gate (Ch.3 §3.8.6) through a real
Discord channel: the founder approves / sends back / kills a draft by tapping
a button, from their phone, no terminal. ~10 minutes to set up.

> Scope note (thesis): this is a *demonstration* surface for §3.8.6, exercised
> against synthetic Passly scenarios. It is not a live customer deployment —
> consistent with the sandbox evaluation posture.

## 1. Install the optional extra

```bash
cd solo-founder-crew
.venv/bin/pip install -e ".[discord]"
```

## 2. Create a Discord application + bot

1. Go to <https://discord.com/developers/applications> → **New Application**.
2. Open **Bot** → **Add Bot** → **Reset Token** → copy the token.
   - Leave the privileged intents (Presence / Server Members / Message
     Content) **off** — the gate uses interaction buttons, which don't need
     them.
3. Open **OAuth2 → URL Generator**:
   - Scopes: **bot**
   - Bot permissions: **Send Messages**, **Embed Links**, **Read Message
     History** (in the target channel).
   - Copy the generated URL, open it, and invite the bot to your server.

## 3. Get the channel id

In Discord: **User Settings → Advanced → Developer Mode** (on). Then
right-click the target channel → **Copy Channel ID**.

Tip: name channels to match the framework's logical channels —
`#marketing` (or `#ads-report`), `#customer-support`, `#dev`. The demo maps
the `marketing` role to one channel; multi-channel routing is the same
pattern with more `channel_map` entries.

## 4. Configure `.env`

In the repo root `.env`:

```
DISCORD_BOT_TOKEN=your-bot-token
DISCORD_MARKETING_CHANNEL_ID=123456789012345678
# only needed with --real-llm:
ANTHROPIC_API_KEY=sk-ant-...
```

`.env` is gitignored — do not commit the token.

## 5. Run

```bash
.venv/bin/python examples/passly_discord.py            # mock LLM (free, deterministic)
.venv/bin/python examples/passly_discord.py --real-llm # Anthropic Haiku
```

The bot connects, posts the draft to the marketing channel with
**[Approve] [Send back] [Kill run]** buttons, and waits for your tap.
- **Approve** → publishes; the script prints `status = shipped`.
- **Send back** → opens a modal for notes; the role revises and re-posts
  (up to `max_revisions`).
- **Kill run** → aborts; `status = killed`.

Outputs land in `examples/out/` (`final_announcement_discord.txt`,
`run_trace_discord.json`).

## How it maps to the framework

| Discord element | Framework source |
|---|---|
| Which channel the message lands in | `HITLRequest.channel` → `channel_map` |
| Embed title / author identity | `HITLRequest.role_display_name` |
| The buttons | `HITLRequest.options` (`ReviewOption`) |
| The "Send back" modal | `ReviewOption.requires_feedback` |
| Button tap → resume the run | `DiscordHITL.submit_response` resolves the parked `Future` |
| Survives the founder taking their time | LangGraph checkpointer + `thread_id` |

The bot holds **no orchestration state** — it only renders a `HITLRequest`
and returns a `FounderResponse`. All run state lives in the runtime/
checkpointer (the state-vs-view discipline argued in §3.8.6).

## Troubleshooting

- **Bot connects but no message appears:** check the channel id and that the
  bot can Send Messages in that specific channel.
- **`SystemExit: Set DISCORD_BOT_TOKEN…`:** `.env` not found or keys unset.
- **Buttons do nothing:** the script must stay running; the bot's event loop
  is what receives the tap. Don't background it.
- **Want pause-across-restart:** swap the default in-memory checkpointer for
  a `SqliteSaver` when constructing the `Crew` (`checkpointer=…`) and pass
  the same `thread_id` on the next run. (Demonstrated separately.)
