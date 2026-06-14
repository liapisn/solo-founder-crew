"""Optional adapters — HITL surfaces and outbound tools.

Adapters either:

- Render a :class:`~solo_founder_crew.hitl_request.HITLRequest` through a
  concrete channel and return a ``FounderDecision``. They satisfy the HITL
  Contract (Component 5) without the core package depending on any
  surface's libraries — import an adapter only when you use it.
- Or expose an outbound tool (publisher_tool, pr_tool, etc.) that is
  registered against a ``ToolRegistry`` and invoked by the runtime
  after founder approval. These satisfy the Tool contract; the
  framework's role/decision-rights enforcement still applies above them.

Currently:
    - ``discord_hitl.DiscordHITL`` — Discord channel + interaction buttons.
    - ``github_pr.GitHubPRTool`` — opens a draft PR on a configured
      repo with the engineering role's proposal artefact.
"""
