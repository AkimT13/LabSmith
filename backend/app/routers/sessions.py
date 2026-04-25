from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.clerk import get_current_user
from app.database import get_db
from app.models.design_session import DesignSession
from app.models.user import User
from app.schemas.sessions import (
    DesignSessionCreate,
    DesignSessionResponse,
    DesignSessionUpdate,
)
from app.services import sessions as session_service

router = APIRouter(prefix="/api/v1", tags=["sessions"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/projects/{project_id}/sessions", response_model=list[DesignSessionResponse])
async def list_sessions(
    project_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[DesignSession]:
    return await session_service.list_sessions(db, project_id=project_id, user=current_user)


@router.post(
    "/projects/{project_id}/sessions",
    response_model=DesignSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    project_id: uuid.UUID,
    data: DesignSessionCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> DesignSession:
    return await session_service.create_session(
        db,
        project_id=project_id,
        user=current_user,
        data=data,
    )


@router.get("/sessions/{session_id}", response_model=DesignSessionResponse)
async def get_session(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DesignSession:
    return await session_service.get_session(db, session_id=session_id, user=current_user)


@router.patch("/sessions/{session_id}", response_model=DesignSessionResponse)
async def update_session(
    session_id: uuid.UUID,
    data: DesignSessionUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> DesignSession:
    return await session_service.update_session(
        db,
        session_id=session_id,
        user=current_user,
        data=data,
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
    await session_service.delete_session(db, session_id=session_id, user=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
