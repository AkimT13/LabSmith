"""Per-session-type chat agents.

Each `SessionType` value is handled by exactly one `SessionAgent` registered
in `registry.py`. The chat router calls the registry to look up the right
agent for a session, then streams events from `agent.run_turn(...)` over SSE.

Adding a new session kind is additive: write a new agent class implementing
`SessionAgent`, declare its event catalog in the M5 contract, and register it.
Nothing else in the chat pipeline needs to change.
"""
from app.services.agents.base import AgentEvent, SessionAgent
from app.services.agents.registry import get_agent_for_session

__all__ = ["AgentEvent", "SessionAgent", "get_agent_for_session"]
