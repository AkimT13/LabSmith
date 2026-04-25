from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.design_session import DesignSession
from app.models.lab_membership import LabMembership, LabRole
from app.models.laboratory import Laboratory
from app.models.project import Project
from app.models.user import User

ROLE_RANK: dict[LabRole, int] = {
    LabRole.VIEWER: 1,
    LabRole.MEMBER: 2,
    LabRole.ADMIN: 3,
    LabRole.OWNER: 4,
}


def assert_lab_role(membership: LabMembership, minimum_role: LabRole) -> None:
    if ROLE_RANK[membership.role] < ROLE_RANK[minimum_role]:
        raise HTTPException(status_code=403, detail="Insufficient lab permissions")


async def get_lab_membership(
    db: AsyncSession,
    *,
    lab_id: uuid.UUID,
    user_id: uuid.UUID,
) -> LabMembership:
    result = await db.execute(
        select(LabMembership).where(
            LabMembership.laboratory_id == lab_id,
            LabMembership.user_id == user_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=404, detail="Laboratory not found")
    return membership


async def require_lab_role(
    db: AsyncSession,
    *,
    lab_id: uuid.UUID,
    user: User,
    minimum_role: LabRole,
) -> LabMembership:
    membership = await get_lab_membership(db, lab_id=lab_id, user_id=user.id)
    assert_lab_role(membership, minimum_role)
    return membership


async def get_lab_with_membership(
    db: AsyncSession,
    *,
    lab_id: uuid.UUID,
    user: User,
    minimum_role: LabRole = LabRole.VIEWER,
) -> tuple[Laboratory, LabMembership]:
    result = await db.execute(
        select(Laboratory, LabMembership)
        .join(LabMembership, LabMembership.laboratory_id == Laboratory.id)
        .where(Laboratory.id == lab_id, LabMembership.user_id == user.id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Laboratory not found")

    lab, membership = row
    assert_lab_role(membership, minimum_role)
    return lab, membership


async def get_project_with_membership(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    user: User,
    minimum_role: LabRole = LabRole.VIEWER,
) -> tuple[Project, LabMembership]:
    result = await db.execute(
        select(Project, LabMembership)
        .join(LabMembership, LabMembership.laboratory_id == Project.laboratory_id)
        .where(Project.id == project_id, LabMembership.user_id == user.id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Project not found")

    project, membership = row
    assert_lab_role(membership, minimum_role)
    return project, membership


async def get_session_with_membership(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    user: User,
    minimum_role: LabRole = LabRole.VIEWER,
) -> tuple[DesignSession, LabMembership]:
    result = await db.execute(
        select(DesignSession, LabMembership)
        .join(Project, Project.id == DesignSession.project_id)
        .join(LabMembership, LabMembership.laboratory_id == Project.laboratory_id)
        .where(DesignSession.id == session_id, LabMembership.user_id == user.id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    design_session, membership = row
    assert_lab_role(membership, minimum_role)
    return design_session, membership
