"""Maps `SessionType` → agent instance.

Hardcoded for now (M5). If we ever need plugin loading we'd swap this for
something config-driven, but the indirection isn't worth it yet.

Adding a new session type:
1. Add the value to `SessionType` in `app/models/design_session.py` + an
   Alembic migration that extends the Postgres enum.
2. Write a class implementing `SessionAgent`.
3. Register it here.
4. Document the event catalog in the M5 contract.
"""
from __future__ import annotations

from app.models.design_session import DesignSession, SessionType
from app.services.agents.base import SessionAgent
from app.services.agents.onboarding import OnboardingAgent
from app.services.agents.part_design import PartDesignAgent

_REGISTRY: dict[SessionType, SessionAgent] = {
    SessionType.PART_DESIGN: PartDesignAgent(),
    SessionType.ONBOARDING: OnboardingAgent(),
}


def get_agent_for_session(session: DesignSession) -> SessionAgent:
    """Look up the agent that handles chat turns for this session.

    Every `SessionType` value MUST be in the registry — adding a new value
    without registering an agent is a programming error, not a runtime
    condition we recover from. We raise loudly so the gap is obvious in
    development.
    """
    try:
        return _REGISTRY[session.session_type]
    except KeyError as exc:
        raise RuntimeError(
            f"No agent registered for session_type={session.session_type!r}. "
            "Add an entry to app/services/agents/registry.py."
        ) from exc
