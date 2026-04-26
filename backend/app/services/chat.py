"""Chat dispatcher — preflight + per-session-type agent routing.

After M5 this module is intentionally small. The actual chat behavior lives
in `app/services/agents/`, one class per `SessionType`. This file only:

1. `prepare_chat_turn()` runs the synchronous preflight (auth, archived
   check, persist user message) so HTTP errors return as proper 4xx codes
   before the SSE response starts streaming.
2. `stream_chat_turn()` looks up the agent for the session and forwards
   its events. It also wraps the agent in a try/except so any unhandled
   exception turns into a single `error` event instead of a mid-stream
   exception (which the SSE response can't recover from).

The agent registry, event catalogs, and per-type behavior are documented
in `docs/M5_CONTRACT.md`.
"""
from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.design_session import DesignSession, SessionStatus
from app.models.lab_membership import LabRole
from app.models.message import Message, MessageRole
from app.models.user import User
from app.services.access import get_session_with_membership
from app.services.agents import get_agent_for_session

logger = logging.getLogger(__name__)


async def prepare_chat_turn(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    user: User,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> tuple[DesignSession, Message]:
    """Run all preflight checks and persist the user message.

    Returns the (session, user_message) tuple. Raises HTTPException for any
    auth/state problem. This MUST be called before constructing a
    StreamingResponse so that errors (404/403/409) come back as proper HTTP
    errors instead of being raised mid-stream after headers ship.
    """
    design_session, _membership = await get_session_with_membership(
        db, session_id=session_id, user=user, minimum_role=LabRole.MEMBER
    )

    if design_session.status == SessionStatus.ARCHIVED:
        raise HTTPException(status_code=409, detail="Session is archived")

    user_msg = Message(
        session_id=design_session.id,
        role=MessageRole.USER,
        content=content,
        metadata_=metadata,
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)
    return design_session, user_msg


async def stream_chat_turn(
    db: AsyncSession,
    *,
    design_session: DesignSession,
    user: User,
    user_content: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """Look up the agent for the session and forward its events.

    Yields `{"event": "<type>", "data": {<payload>}}` dicts. The router
    encodes each as SSE wire format. Errors are converted into a single
    `error` event so the SSE response can close cleanly instead of raising
    mid-stream.

    Caller MUST have called `prepare_chat_turn()` first.
    """
    agent = get_agent_for_session(design_session)

    try:
        async for event in agent.run_turn(
            db=db,
            session=design_session,
            user=user,
            user_content=user_content,
        ):
            yield event
    except Exception as exc:  # noqa: BLE001 — convert to error event
        logger.exception(
            "Agent %s failed on session %s: %s",
            type(agent).__name__,
            design_session.id,
            exc,
        )
        yield {
            "event": "error",
            "data": {"code": "internal_error", "detail": str(exc)},
        }
