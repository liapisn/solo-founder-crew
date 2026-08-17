# Dev Flow — the engineering role and the PR-review gate

This documents how the framework treats software change as crew work, and
how the founder's authority over what ships is rendered through the same
Human-in-the-Loop Contract used everywhere else (Ch.3 §3.8). It is the "dev"
counterpart to the Author Flow (Ch.3 §3.7).

## The idea in one line

A dev agent (the **engineering** role) branches and opens a pull request on
its own; CI validates it unattended; only the **merge to main** requires the
founder — and that gate is delivered to a Discord channel for review.

## Why this is just another HITL gate

Nothing new is invented. The engineering role's decision rights
(`roles_library.make_engineering`) encode the split:

| May do alone (`can`)                                   | Must escalate (`must_escalate`)               |
|--------------------------------------------------------|-----------------------------------------------|
| `draft_content`, `revise_content`, `propose_change`, `open_pull_request` | `merge_to_main`, `dependency_change`, `schema_or_data_migration` |

Opening a PR is safe — it does not touch production — so the agent does it
autonomously. Merging is the consequential act, so it is a founder gate. That
gate is a `HITLRequest` like any other:

| `HITLRequest` field | Value for a merge gate                          |
|---------------------|-------------------------------------------------|
| `role`              | `engineering`                                   |
| `channel`           | `dev`                                            |
| `action`            | `merge_to_main`                                  |
| `artifact`          | PR title + summary (+ diff/CI status as context) |
| `options`           | Approve & merge / Request changes / Close        |

The contract is unchanged; only the surface and the gated action differ from
the Author Flow's `final_approval_before_publish`.

## Ordering: how Dev Flow differs from Author Flow

Author Flow is `draft → review → publish`. Dev Flow inserts an automated
validation step *before* the human gate, because code can be checked before a
human looks at it:

```
draft change → open PR → [CI runs, unattended] → founder review (merge gate) → merge
```

The CI step is a precondition on the gate: the founder is only asked once the
change is green. In this repo that precondition is enforced GitHub-natively
(see below) rather than inside a LangGraph graph — the runtime stays the
generic Author Flow; the CI-before-review ordering lives in CI config. A fully
executable Dev Flow graph (with CI status as a graph edge) is a possible
extension, not required for the gate semantics.

## What is wired up in this repo

0. **The engineering role writes the code** — see "The agent writes the code"
   below; `pr_tool` opens a draft PR containing a real diff.
1. **`.github/workflows/ci.yml`** — runs ruff + pytest on every push and PR.
2. **`.github/workflows/pr-review-notify.yml`** — when CI succeeds on a PR,
   posts the PR (title, author, branch, diffstat, link) to Discord with
   "✅ CI passed — ready for your review." The founder reviews and merges on
   GitHub. This is the *notify-only* rendering of the merge gate.

### Setup (one secret)

1. In Discord: target channel (e.g. `#dev`) → **Edit Channel → Integrations →
   Webhooks → New Webhook** → **Copy Webhook URL**.
2. In GitHub: repo **Settings → Secrets and variables → Actions → New
   repository secret**, name `DISCORD_WEBHOOK_URL`, paste the URL.

That's it. If the secret is absent the notify job no-ops, so the workflow is
safe to merge before the secret exists.

## Notify-only vs. interactive (deliberate scope)

This step ships **notify-only**: the founder reviews and merges on GitHub,
where the full diff and review tooling live. The *interactive* variant — tap
**Approve & merge** in Discord and have a bot merge via the GitHub API —
reuses `DiscordHITL` directly but needs an always-on hosted bot and a token
with merge rights. It is the natural next step once there is somewhere to host
the bot; the framework side (the merge gate as a `HITLRequest`) is already in
place.

## The agent writes the code (M2 Phase 3)

Phase 2 shipped a `pr_tool` that committed the *proposal* as a markdown file:
the change the founder reviewed was a design note, not code. That was a tooling
limit, not a decision-rights one — `open_pull_request` has always been in the
engineering role's `can` list.

Phase 3 closes it. On approval, `ImplementedPRTool` hands the proposal to an
`Implementer`:

```
Implementer (Protocol)
├── ClaudeCodeImplementer   headless `claude -p` in a throwaway git worktree,
│                           then commit + push from outside the agent
└── FakeImplementer         deterministic — what CI and the suite use
```

Three outcomes, and only one of them opens a PR:

| Outcome | Result |
|---------|--------|
| Diff touches a dependency manifest or a migration | **No PR.** `dependency_change` / `schema_or_data_migration` are in `must_escalate`, so the founder is told what needs separate approval. The branch is still pushed, so the work is not lost. |
| Agent changed nothing | **No PR.** |
| Clean change | **Draft PR** carrying the real diff, the approved proposal as its body, and the run's turns / wall-clock / cost. |

Escalations are detected from the files the agent actually changed, not from
what the prompt asked for: the decision-rights model is checked against the
artefact rather than trusted to the system prompt.

### Isolation

The worktree is created from `origin/<base>` under `SFC_WORKTREE_ROOT`, so the
founder's working tree is never touched and an in-flight run cannot collide
with local edits. It also carries no gitignored files, which is why the agent
never sees `api/.env` or the credentials in it.

The agent runs with full bash (`--permission-mode bypassPermissions`) and a
real `HOME`, so it *can* read the user's home directory and reach the network.
What it cannot do is push or merge: its environment is built from an allowlist
that excludes every repository and venture credential, `gh` is pointed at an
empty config directory, and git's global/system config is blanked so no
credential helper is reachable. The adapter pushes afterwards, outside the
agent. Every result lands as a reviewable diff, and `merge_to_main` stays the
founder's.

The Claude Code CLI exposes no turn cap, so `SFC_IMPLEMENT_TIMEOUT`
(wall-clock) is the only bound on a run.

### Cost

A run is a full agentic coding session, so the tier it runs at is the single
biggest lever on what the crew costs. `claude -p` with no `--model` inherits
whatever the founder's *interactive* CLI defaults to — and the child
environment allowlist strips `ANTHROPIC_MODEL`, so the flag is the only way in.
The adapter therefore names the tier explicitly:

| Var | Default | Applies to |
|-----|---------|-----------|
| `SFC_IMPLEMENT_MODEL` | `sonnet` | writing an approved proposal |
| `SFC_IMPLEMENT_EFFORT` | `high` | writing an approved proposal |
| `SFC_FIX_MODEL` | `sonnet` | `/fix` on a red build |
| `SFC_FIX_EFFORT` | `medium` | `/fix` on a red build |

The two jobs are tiered separately because they are not the same size:
implementing a proposal is open-ended work from a prose brief, while a CI fix
is a named failure with a known smallest change that the founder can ask for
repeatedly. `effort` matters at least as much as `model` — it governs thinking
depth *and* how many tool calls a run makes.

These are starting points, not findings. Every run already reports its turns,
wall-clock and cost to `#crew-logs`, so move the defaults on that evidence:
raise the tier if a diff comes back unusable, lower it if the same PR arrives
either way.

### Turning it on

Set both `SFC_PR_REPO` and `SFC_PR_REPO_PATH` (see `.env.example`). With either
missing the daemon keeps the stub `pr_tool`, so a fresh clone never points a
coding agent at a real repository by accident.

## When CI goes red (M2 Phase 4)

Phase 3 ended at the push. Nothing in the crew observed what CI then said, and
`pr-review-notify.yml` only spoke on success — so a red build was *silent*,
indistinguishable from one still running. The agent could not learn it had
shipped something broken, and neither could the founder.

The loop closes in two halves, and the seam between them is deliberate:

```
CI fails
   │
   ├─ pr-review-notify.yml  ──▶  #crew-logs: ❌ which job, which step, /fix <pr>
   │                                   │
   │                          the founder decides           ◀── the retry bound
   │                                   │
   └─ /fix 22  ──▶  CIFixFlow  ──▶  Implementer(existing=True)  ──▶  same branch
                         │                                             │
                    reads the failing job's log            PR updates, CI re-runs
```

**The founder is the retry bound.** There is no polling loop, no automatic
re-iteration and no `max_attempts` to tune. Each attempt costs one human
decision, which is the cheapest available guard against an agent burning spend
against a failure it cannot fix — a flaky fetch, or something already broken on
`main`. It also keeps the framework's claim honest: the crew acts, the founder
decides.

### What `/fix` does

1. Reads the PR (`ChecksAPI`, a read-only three-method Protocol — the PR tool
   writes, this reads, neither carries the other's surface).
2. Finds the failed Actions jobs on the head commit and pulls each log, tail
   first and capped: the error is at the end and a whole Actions log will not
   fit in a prompt.
3. Hands that report to the same `Implementer`, with `existing=True` — the
   worktree starts at `origin/<pr branch>` instead of the base, so the commit
   lands on the branch the pull request already points at and CI re-runs
   against it.

Four refusals, before any agent is spawned:

| Case | Why |
|------|-----|
| PR closed or merged | No branch left in play. |
| Head branch is not the crew's (`engineering/`) | A mistyped number must not point a coding agent at hand-written work. |
| No failed job on the head commit | CI is green, or still running. |
| Agent changed nothing | Reported as the flake case, not as a fix. |

The agent's brief for a fix is not the proposal brief: it is told to keep the
branch's behaviour, and that deleting or skipping a failing test is not a fix.
An agent asked only to make CI pass can always satisfy that by reverting the
work.

Escalations are unchanged — `detect_escalations` still inspects what the fix
actually touched, so a "fix" that reaches for a new dependency stops and asks.
The PR stays a draft. `merge_to_main` is still yours.
