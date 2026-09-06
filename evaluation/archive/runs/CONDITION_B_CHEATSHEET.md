# Condition B at the REPL — one card

**The REPL is not a conversation. It is a script being executed.** The scripted
decisions printed at the top of each run are the control; anything you say that
is not on the script contaminates the run. Do not answer the model's questions,
do not add context, do not steer. It will ask. Ignore it.

## Every run, same five moves

1. `/brief`
2. Paste the task line the REPL printed. **On its own, after the brief comes back**
   — pasting both at once makes the second line get eaten by the next prompt.
3. Model drafts.
4. Work the scripted decisions **in order**:
   - `reject` → paste that Greek feedback string verbatim as a normal line
   - `approve` → `/approve`
   - `kill` → `/kill`
5. Done. The log writes itself.

## Per scenario

| Scenario | After the task, in order |
|---|---|
| S1 | feedback 1 → `/approve` |
| S2, S5, S7 | `/approve` |
| S3 | feedback 1 → feedback 2 → `/approve` |
| S4, S6, S9 | feedback 1 → `/approve` |
| S8 | `/kill` |
| S10 | feedback 1 → feedback 2 → feedback 3 → `/stop` |

**S10 is the one to get right.** Type only the first three feedback strings. The
fourth scripted rejection is the founder giving up — *"Ας το αφήσουμε, θα το
γράψω μόνος μου"* — so it is `/stop`, not a typed line. Typing it would produce a
fifth draft and exceed the cap Condition F enforces. Three typed, then `/stop`,
gives four drafts in both conditions.

## If you mistype a command

A typo like `/bried` is not a command, so it goes to the model as a prompt and
**counts as an interaction** — inflating M1 for the baseline. `/undo` drops the
last exchange and removes the interaction. Use it immediately.

## Commands

```
/brief    send the Venture Brief prose (1 interaction)
/approve  terminal — you would ship this
/kill     terminal — you would not ship this at all
/stop     terminal — you gave up revising (the exhausted analogue)
/undo     drop the last exchange (mistyped; not a founder decision)
```

## Run numbering

The ten scored runs use the default rep. Only the E4b re-runs on S2, S3 and S8
use `--rep 2`, `--rep 3`, `--rep 4`.

```bash
cd /Users/nikolasliapis/Development/University/mba/Diplomatic/solo-founder-crew

# the ten scored runs — S1 … S10
.venv/bin/python -m evaluation.baseline_repl --scenario S1 \
  --out ../Diplomatic/05_Drafts/Ch5_Eval_Runs/B_live_scored

# E4b re-runs — S2, S3, S8 × rep 2,3,4
.venv/bin/python -m evaluation.baseline_repl --scenario S2 --rep 2 \
  --out ../Diplomatic/05_Drafts/Ch5_Eval_Runs/B_live_e4b
```

## Ctrl-C is safe

An aborted run writes no log. Nothing to clean up — just start that scenario
again. Better an aborted run than an off-script one.
