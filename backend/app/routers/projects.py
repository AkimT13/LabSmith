from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.clerk import get_current_user
from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.schemas.projects import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services import projects as project_service

router = APIRouter(prefix="/api/v1", tags=["projects"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/labs/{lab_id}/projects", response_model=list[ProjectResponse])
async def list_projects(
    lab_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[Project]:
    return await project_service.list_projects(db, lab_id=lab_id, user=current_user)


@router.post(
    "/labs/{lab_id}/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    lab_id: uuid.UUID,
    data: ProjectCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> Project:
    return await project_service.create_project(db, lab_id=lab_id, user=current_user, data=data)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> Project:
    return await project_service.get_project(db, project_id=project_id, user=current_user)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> Project:
    return await project_service.update_project(
        db,
        project_id=project_id,
        user=current_user,
        data=data,
    )


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
    await project_service.delete_project(db, project_id=project_id, user=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
