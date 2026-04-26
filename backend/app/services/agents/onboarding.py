"""Stub agent for `onboarding` sessions.

Real implementation lands in M8 (lab onboarding agent — RAG over lab docs,
checklist generation, etc.). M5 ships only this stub so:

1. The registry is plural — adding agent #3 later is purely additive.
2. Users can already create onboarding-typed sessions; the chat just
   returns a friendly "not implemented yet" message instead of crashing.
3. The frontend can route on `session_type` and show an appropriate empty
   state without depending on backend behavior that doesn't exist yet.

The event catalog here is intentionally minimal — just `text_delta` and
`message_complete` — so the frontend's existing `useChat` hook works against
this agent without any new event handlers. M8 will introduce richer events
(`doc_referenced`, `topic_suggested`, `checklist_step`, etc.).
"""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.design_session import DesignSession, SessionType
from app.models.message import Message, MessageRole
from app.models.user import User
from app.services.agents.base import AgentEvent

_PLACEHOLDER_REPLY = (
    "Onboarding sessions are coming in milestone 8. The agent will help new "
    "lab members find protocols, equipment, and the people who own each "
    "workflow. Until then, this is a placeholder — feel free to use the "
    "session to take notes."
)


class OnboardingAgent:
    session_type = SessionType.ONBOARDING

    async def run_turn(
        self,
        *,
        db: AsyncSession,
        session: DesignSession,
        user: User,
        user_content: str,
    ) -> AsyncGenerator[AgentEvent, None]:
        assistant_message_id = uuid.uuid4()

        assistant_msg = Message(
            id=assistant_message_id,
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content=_PLACEHOLDER_REPLY,
            metadata_={"placeholder": True},
        )
        db.add(assistant_msg)
        await db.flush()

        # Stream the placeholder in chunks so the frontend's text-delta
        # handler exercises the same code path it does for real agents.
        chunk_size = max(1, len(_PLACEHOLDER_REPLY) // 4)
        for i in range(0, len(_PLACEHOLDER_REPLY), chunk_size):
            chunk = _PLACEHOLDER_REPLY[i : i + chunk_size]
            yield {
                "event": "text_delta",
                "data": {
                    "message_id": str(assistant_message_id),
                    "delta": chunk,
                },
            }
            if settings.chat_mock:
                await asyncio.sleep(0.1)

        yield {
            "event": "message_complete",
            "data": {
                "message_id": str(assistant_message_id),
                "content": _PLACEHOLDER_REPLY,
            },
        }
        await db.commit()
