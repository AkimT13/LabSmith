"""SessionAgent protocol — the seam between the chat pipeline and per-type behavior.

Each session type has exactly one agent class. The chat router never knows
about specific agents; it just calls `get_agent_for_session(session)` and
streams whatever events come back. This keeps adding new session types
purely additive — no changes to the router, the SSE encoder, or the
persistence helpers.

Events emitted by an agent are plain dicts with shape
`{"event": "<type>", "data": {<json-serializable payload>}}`. The chat
router serializes them to SSE wire format. Each agent owns the event
catalog for its session type — see the M5 contract for the canonical list
per agent.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any, Protocol, TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.design_session import DesignSession, SessionType
from app.models.user import User


class AgentEvent(TypedDict):
    """Wire shape for events yielded by an agent."""

    event: str
    data: dict[str, Any]


class SessionAgent(Protocol):
    """One agent per `SessionType`. Owns its system prompt, toolchain, and
    event catalog.

    Agents are stateless singletons — instances live for the lifetime of the
    process. Per-session state (history, current_spec, etc.) is read from
    `session` and from the database; never stash state on the agent itself.
    """

    session_type: SessionType

    async def run_turn(
        self,
        *,
        db: AsyncSession,
        session: DesignSession,
        user: User,
        user_content: str,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Run a single chat turn and yield events.

        Caller guarantees:
        - The user message has already been persisted (by `prepare_chat_turn`).
        - The session is not archived.
        - The caller is at least a `member` of the session's lab.

        The agent is responsible for:
        - Persisting the assistant Message row(s).
        - Persisting any artifacts it generates.
        - Committing on success. On exception the dispatcher will roll back
          and emit an `error` event; the agent should not catch generic
          exceptions itself.
        """
        ...
