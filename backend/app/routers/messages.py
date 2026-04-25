from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.clerk import get_current_user
from app.database import get_db
from app.models.message import Message
from app.models.user import User
from app.schemas.messages import MessageResponse
from app.services.access import get_session_with_membership

router = APIRouter(prefix="/api/v1", tags=["messages"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[Message]:
    """Return all messages for a session, oldest first.

    Used to hydrate the chat panel on initial load and after refresh.
    """
    design_session, _membership = await get_session_with_membership(
        db, session_id=session_id, user=current_user
    )
    result = await db.execute(
        select(Message)
        .where(Message.session_id == design_session.id)
        .order_by(Message.created_at.asc())
    )
    return list(result.scalars().all())
