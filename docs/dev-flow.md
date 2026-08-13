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

### Turning it on

Set both `SFC_PR_REPO` and `SFC_PR_REPO_PATH` (see `.env.example`). With either
missing the daemon keeps the stub `pr_tool`, so a fresh clone never points a
coding agent at a real repository by accident.
