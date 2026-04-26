"""SSE chat endpoint for design sessions (M3)."""
from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from contextlib import suppress
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.clerk import get_current_user
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.chat import ChatRequest
from app.services import chat as chat_service
from app.services.rate_limit import chat_rate_limiter

router = APIRouter(prefix="/api/v1", tags=["chat"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/sessions/{session_id}/chat")
async def chat(
    session_id: uuid.UUID,
    body: ChatRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> StreamingResponse:
    """Initiate a chat turn. Returns a Server-Sent Events stream.

    Event ordering and payload shapes are defined in `docs/M3_CONTRACT.md`.
    The session must not be archived; the caller must be at least a `member` of the lab.

    Preflight checks (auth, archived, persist user message) run synchronously and
    can raise 401/403/404/409. Once those succeed, the SSE stream begins.
    """
    retry_after = await chat_rate_limiter.retry_after_seconds(
        key=f"user:{current_user.id}",
        limit=settings.chat_rate_limit_requests,
        window_seconds=settings.chat_rate_limit_window_seconds,
    )
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many chat requests. Please try again shortly.",
            headers={"Retry-After": str(retry_after)},
        )

    design_session, _user_msg = await chat_service.prepare_chat_turn(
        db,
        session_id=session_id,
        user=current_user,
        content=body.content,
        metadata=body.metadata,
    )

    event_stream = chat_service.stream_chat_turn(
        db,
        design_session=design_session,
        user=current_user,
        user_content=body.content,
    )

    return StreamingResponse(
        _format_sse(event_stream),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # tell nginx not to buffer
            "Connection": "keep-alive",
        },
    )


async def _format_sse(events: AsyncGenerator[dict, None]) -> AsyncGenerator[bytes, None]:
    """Encode service-layer event dicts as SSE wire format."""
    keepalive_interval = settings.sse_keepalive_interval_seconds
    if keepalive_interval <= 0:
        async for event in events:
            yield _format_sse_event(event)
        return

    next_event = asyncio.create_task(events.__anext__())
    try:
        while True:
            done, _pending = await asyncio.wait({next_event}, timeout=keepalive_interval)
            if not done:
                yield b":keepalive\n\n"
                continue

            try:
                event = next_event.result()
            except StopAsyncIteration:
                break

            yield _format_sse_event(event)
            next_event = asyncio.create_task(events.__anext__())
    finally:
        if not next_event.done():
            next_event.cancel()
            with suppress(asyncio.CancelledError):
                await next_event


def _format_sse_event(event: dict) -> bytes:
    event_type = event.get("event", "message")
    data = event.get("data", {})
    payload = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n".encode()
