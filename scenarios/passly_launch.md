# Scenario: Passly Launch Announcement

**Purpose:** Test bench for the Part 7 framework spike. Same scenario implemented in CrewAI, LangGraph, and a custom asyncio runtime.

## Narrative

A solo founder wants to publish a launch announcement for **Passly** (digital wallet passes + AI marketing for Greek SMBs). They have a Venture Brief on file. Rather than draft it themselves, they hand the job to a single-role **Marketing** agent. Before anything is published, the founder must approve. The founder may approve, reject with feedback (triggering a revision), or kill the task.

## Flow

```
1. Load Venture Brief (passly.json)
       │
       ▼
2. Crew Generator → assemble crew = [Marketing role]
       │
       ▼
3. Marketing.draft(brief) → draft_v1
       │
       ▼
4. HITL gate: founder review of draft_v1
       │
       ├── approve  → 6
       ├── reject(feedback) → 5
       └── kill     → END
       │
       ▼
5. Marketing.revise(draft_v1, feedback) → draft_v2
       │
       ▼  (HITL gate again on draft_v2; max 1 revision for the spike)
       │
       ▼
6. publisher_tool.publish(approved_draft) → STUB: prints "shipped"
       │
       ▼
7. END
```

## Inputs

- **Venture Brief**: [`scenarios/fixtures/passly_brief.json`](fixtures/passly_brief.json) (conforms to [`schemas/venture_brief.schema.json`](../schemas/venture_brief.schema.json)).
- **Founder response (scripted for spike runs)**: a small JSON like `{"action": "reject", "feedback": "Tone too formal — make it warmer and add a Greek tagline."}` for turn 1, then `{"action": "approve"}` for turn 2.

The spike does NOT use a live interactive prompt — founder responses are scripted from a fixture so runs are deterministic and the rubric criterion "HITL ergonomics" can be scored on *how easy it is to wire the gate in*, not on UI polish.

## Outputs

For each implementation, the run must produce:

1. `final_announcement.txt` — the approved draft text
2. `run_trace.json` — a structured trace of: (role, action, input, output, founder_decision, timestamps)

These are what the scorer inspects for the "Observability" criterion.

## Constraints

- One LLM call per role action (draft, revise). The spike caps at 4 LLM calls per run.
- All three implementations use the **same model** (e.g., `claude-haiku-4-5`) to keep cost and quality variation flat across candidates.
- Each implementation must be **<300 LOC** (excluding tests and the shared schema/fixture files).
- No network calls beyond the LLM API. Publisher tool is a stub.

## Role definition (Marketing)

For the spike, the Marketing role carries:

```yaml
name: marketing
goal: Draft customer-facing announcements that match the venture's voice and constraints
decision_rights:
  can: [draft_content, revise_content]
  must_escalate: [final_approval_before_publish]
tools: [publisher_tool]  # but cannot invoke it until founder approves
```

The point of writing it this way is to see how each candidate framework lets us *express* this. CrewAI has its own Agent abstraction; LangGraph has none built-in; custom is whatever we design. Scoring criterion: how naturally does the candidate let us express decision rights and the "must escalate before tool use" rule?
