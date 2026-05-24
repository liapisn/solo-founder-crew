# Spike evidence

Real-LLM outputs from the Part 7 framework spike, preserved here so the
thesis (Ch.3 framework and Ch.5 evaluation) can quote them without
relying on whatever happens to be in each spike's `out/` directory at
the time.

All three were produced by the same model (`claude-haiku-4-5`) against
the same [Venture Brief](../../scenarios/fixtures/passly_brief.json)
and the same [scripted founder feedback](../../scenarios/fixtures/founder_responses.json).
Run on 2026-05-23 with `python spikes/<candidate>/run.py --real-llm`.

| File | Candidate framework | Notes |
|---|---|---|
| [`custom_haiku.txt`](custom_haiku.txt) | Custom asyncio | Raw `anthropic.Anthropic().messages.create()`. Warm English with Greek tagline. |
| [`crewai_haiku.txt`](crewai_haiku.txt) | CrewAI | Via `litellm` + Agent backstory framing. Punchy English, agent-personality voice. |
| [`langgraph_haiku.txt`](langgraph_haiku.txt) | LangGraph | Via `langchain-anthropic` (`ChatAnthropic`). Fully Greek, tightest word count. |

The three outputs differ noticeably in register despite identical
model, brief, and founder feedback. That qualitative observation feeds
the Ch.5 discussion of *framework-induced register drift* — how each
candidate's default scaffolding around the LLM call shapes the model's
voice independent of explicit prompting.
