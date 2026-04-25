from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lab_membership import LabRole
from app.models.project import Project
from app.models.user import User
from app.schemas.projects import ProjectCreate, ProjectUpdate
from app.services.access import get_project_with_membership, require_lab_role


async def list_projects(
    db: AsyncSession,
    *,
    lab_id: uuid.UUID,
    user: User,
) -> list[Project]:
    await require_lab_role(db, lab_id=lab_id, user=user, minimum_role=LabRole.VIEWER)
    result = await db.execute(
        select(Project)
        .where(Project.laboratory_id == lab_id)
        .order_by(Project.created_at.desc(), Project.name)
    )
    return list(result.scalars().all())


async def create_project(
    db: AsyncSession,
    *,
    lab_id: uuid.UUID,
    user: User,
    data: ProjectCreate,
) -> Project:
    await require_lab_role(db, lab_id=lab_id, user=user, minimum_role=LabRole.MEMBER)
    project = Project(
        laboratory_id=lab_id,
        name=data.name.strip(),
        description=data.description,
        created_by=user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def get_project(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    user: User,
) -> Project:
    project, _membership = await get_project_with_membership(
        db, project_id=project_id, user=user
    )
    return project


async def update_project(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    user: User,
    data: ProjectUpdate,
) -> Project:
    project, _membership = await get_project_with_membership(
        db, project_id=project_id, user=user, minimum_role=LabRole.MEMBER
    )
    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] is not None:
        project.name = update_data["name"].strip()
    if "description" in update_data:
        project.description = update_data["description"]

    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    user: User,
) -> None:
    project, _membership = await get_project_with_membership(
        db, project_id=project_id, user=user, minimum_role=LabRole.ADMIN
    )
    await db.delete(project)
    await db.commit()
