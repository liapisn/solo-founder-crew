"""Optional HITL surface adapters.

Adapters render the :class:`~solo_founder_crew.hitl_request.HITLRequest`
through a concrete channel and return a ``FounderDecision``. They satisfy
the HITL Contract (Component 5) without the core package depending on any
surface's libraries — import an adapter only when you use it.

Currently:
    - ``discord_hitl.DiscordHITL`` — Discord channel + interaction buttons.
"""
