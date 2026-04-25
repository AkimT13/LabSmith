from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.clerk import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.labs import (
    LabCreate,
    LabMemberCreate,
    LabMembershipResponse,
    LabMemberUpdate,
    LabResponse,
    LabUpdate,
)
from app.services import labs as lab_service

router = APIRouter(prefix="/api/v1/labs", tags=["labs"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=list[LabResponse])
async def list_labs(db: DbSession, current_user: CurrentUser) -> list[LabResponse]:
    return await lab_service.list_labs(db, user=current_user)


@router.post("", response_model=LabResponse, status_code=status.HTTP_201_CREATED)
async def create_lab(
    data: LabCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> LabResponse:
    return await lab_service.create_lab(db, user=current_user, data=data)


@router.get("/{lab_id}", response_model=LabResponse)
async def get_lab(
    lab_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> LabResponse:
    return await lab_service.get_lab(db, lab_id=lab_id, user=current_user)


@router.patch("/{lab_id}", response_model=LabResponse)
async def update_lab(
    lab_id: uuid.UUID,
    data: LabUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> LabResponse:
    return await lab_service.update_lab(db, lab_id=lab_id, user=current_user, data=data)


@router.delete("/{lab_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lab(
    lab_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
    await lab_service.delete_lab(db, lab_id=lab_id, user=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{lab_id}/members", response_model=list[LabMembershipResponse])
async def list_lab_members(
    lab_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[LabMembershipResponse]:
    return await lab_service.list_lab_members(db, lab_id=lab_id, user=current_user)


@router.post(
    "/{lab_id}/members",
    response_model=LabMembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_lab_member(
    lab_id: uuid.UUID,
    data: LabMemberCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> LabMembershipResponse:
    return await lab_service.add_lab_member(db, lab_id=lab_id, user=current_user, data=data)


@router.patch("/{lab_id}/members/{membership_id}", response_model=LabMembershipResponse)
async def update_lab_member(
    lab_id: uuid.UUID,
    membership_id: uuid.UUID,
    data: LabMemberUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> LabMembershipResponse:
    return await lab_service.update_lab_member(
        db,
        lab_id=lab_id,
        membership_id=membership_id,
        user=current_user,
        role=data.role,
    )


@router.delete("/{lab_id}/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_lab_member(
    lab_id: uuid.UUID,
    membership_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
    await lab_service.remove_lab_member(
        db,
        lab_id=lab_id,
        membership_id=membership_id,
        user=current_user,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
