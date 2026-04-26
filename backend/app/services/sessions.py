from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.design_session import DesignSession, SessionStatus
from app.models.lab_membership import LabRole
from app.models.user import User
from app.schemas.sessions import DesignSessionCreate, DesignSessionUpdate
from app.services.access import get_project_with_membership, get_session_with_membership


async def list_sessions(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    user: User,
) -> list[DesignSession]:
    project, _membership = await get_project_with_membership(
        db, project_id=project_id, user=user, minimum_role=LabRole.VIEWER
    )
    result = await db.execute(
        select(DesignSession)
        .where(DesignSession.project_id == project.id)
        .order_by(DesignSession.created_at.desc(), DesignSession.title)
    )
    return list(result.scalars().all())


async def create_session(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    user: User,
    data: DesignSessionCreate,
) -> DesignSession:
    project, _membership = await get_project_with_membership(
        db, project_id=project_id, user=user, minimum_role=LabRole.MEMBER
    )
    design_session = DesignSession(
        project_id=project.id,
        title=data.title.strip(),
        status=SessionStatus.ACTIVE,
        session_type=data.session_type,
        part_type=data.part_type,
        current_spec=data.current_spec,
        created_by=user.id,
    )
    db.add(design_session)
    await db.commit()
    await db.refresh(design_session)
    return design_session


async def get_session(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    user: User,
) -> DesignSession:
    design_session, _membership = await get_session_with_membership(
        db, session_id=session_id, user=user
    )
    return design_session


async def update_session(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    user: User,
    data: DesignSessionUpdate,
) -> DesignSession:
    design_session, _membership = await get_session_with_membership(
        db, session_id=session_id, user=user, minimum_role=LabRole.MEMBER
    )
    update_data = data.model_dump(exclude_unset=True)

    if "title" in update_data and update_data["title"] is not None:
        design_session.title = update_data["title"].strip()
    if "status" in update_data and update_data["status"] is not None:
        design_session.status = update_data["status"]
    if "part_type" in update_data:
        design_session.part_type = update_data["part_type"]
    if "current_spec" in update_data:
        design_session.current_spec = update_data["current_spec"]

    await db.commit()
    await db.refresh(design_session)
    return design_session


async def delete_session(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    user: User,
) -> None:
    design_session, _membership = await get_session_with_membership(
        db, session_id=session_id, user=user, minimum_role=LabRole.MEMBER
    )
    await db.delete(design_session)
    await db.commit()
