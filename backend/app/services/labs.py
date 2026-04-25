from __future__ import annotations

import re
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lab_membership import LabMembership, LabRole
from app.models.laboratory import Laboratory
from app.models.user import User
from app.schemas.labs import (
    LabCreate,
    LabMemberCreate,
    LabMembershipResponse,
    LabResponse,
    LabUpdate,
)
from app.services.access import get_lab_with_membership, require_lab_role


async def list_labs(db: AsyncSession, *, user: User) -> list[LabResponse]:
    result = await db.execute(
        select(Laboratory, LabMembership)
        .join(LabMembership, LabMembership.laboratory_id == Laboratory.id)
        .where(LabMembership.user_id == user.id)
        .order_by(Laboratory.name)
    )
    return [_lab_response(lab, membership) for lab, membership in result.all()]


async def create_lab(db: AsyncSession, *, user: User, data: LabCreate) -> LabResponse:
    lab = Laboratory(
        name=data.name.strip(),
        slug=await _unique_lab_slug(db, data.name),
        description=data.description,
        created_by=user.id,
    )
    db.add(lab)
    await db.flush()

    membership = LabMembership(user_id=user.id, laboratory_id=lab.id, role=LabRole.OWNER)
    db.add(membership)

    await db.commit()
    await db.refresh(lab)
    await db.refresh(membership)
    return _lab_response(lab, membership)


async def get_lab(db: AsyncSession, *, lab_id: uuid.UUID, user: User) -> LabResponse:
    lab, membership = await get_lab_with_membership(db, lab_id=lab_id, user=user)
    return _lab_response(lab, membership)


async def update_lab(
    db: AsyncSession,
    *,
    lab_id: uuid.UUID,
    user: User,
    data: LabUpdate,
) -> LabResponse:
    lab, membership = await get_lab_with_membership(
        db, lab_id=lab_id, user=user, minimum_role=LabRole.ADMIN
    )
    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] is not None:
        lab.name = update_data["name"].strip()
    if "description" in update_data:
        lab.description = update_data["description"]

    await db.commit()
    await db.refresh(lab)
    return _lab_response(lab, membership)


async def delete_lab(db: AsyncSession, *, lab_id: uuid.UUID, user: User) -> None:
    lab, _membership = await get_lab_with_membership(
        db, lab_id=lab_id, user=user, minimum_role=LabRole.OWNER
    )
    await db.delete(lab)
    await db.commit()


async def list_lab_members(
    db: AsyncSession,
    *,
    lab_id: uuid.UUID,
    user: User,
) -> list[LabMembershipResponse]:
    await require_lab_role(db, lab_id=lab_id, user=user, minimum_role=LabRole.VIEWER)
    result = await db.execute(
        select(LabMembership, User)
        .join(User, User.id == LabMembership.user_id)
        .where(LabMembership.laboratory_id == lab_id)
        .order_by(User.email)
    )
    return [
        _membership_response(membership, member_user)
        for membership, member_user in result.all()
    ]


async def add_lab_member(
    db: AsyncSession,
    *,
    lab_id: uuid.UUID,
    user: User,
    data: LabMemberCreate,
) -> LabMembershipResponse:
    await require_lab_role(db, lab_id=lab_id, user=user, minimum_role=LabRole.ADMIN)

    member_user = await _get_user_by_email(db, data.email)
    existing = await db.execute(
        select(LabMembership).where(
            LabMembership.laboratory_id == lab_id,
            LabMembership.user_id == member_user.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="User is already a lab member")

    membership = LabMembership(
        laboratory_id=lab_id,
        user_id=member_user.id,
        role=data.role,
        invited_by=user.id,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return _membership_response(membership, member_user)


async def update_lab_member(
    db: AsyncSession,
    *,
    lab_id: uuid.UUID,
    membership_id: uuid.UUID,
    user: User,
    role: LabRole,
) -> LabMembershipResponse:
    await require_lab_role(db, lab_id=lab_id, user=user, minimum_role=LabRole.ADMIN)
    membership, member_user = await _get_membership_with_user(db, lab_id, membership_id)

    if membership.role == LabRole.OWNER and role != LabRole.OWNER:
        await _ensure_another_owner_exists(db, lab_id, excluding_membership_id=membership.id)

    membership.role = role
    await db.commit()
    await db.refresh(membership)
    return _membership_response(membership, member_user)


async def remove_lab_member(
    db: AsyncSession,
    *,
    lab_id: uuid.UUID,
    membership_id: uuid.UUID,
    user: User,
) -> None:
    await require_lab_role(db, lab_id=lab_id, user=user, minimum_role=LabRole.ADMIN)
    membership, _member_user = await _get_membership_with_user(db, lab_id, membership_id)

    if membership.role == LabRole.OWNER:
        await _ensure_another_owner_exists(db, lab_id, excluding_membership_id=membership.id)

    await db.execute(delete(LabMembership).where(LabMembership.id == membership.id))
    await db.commit()


async def _unique_lab_slug(db: AsyncSession, name: str) -> str:
    base = _slugify(name) or "lab"
    slug = base
    suffix = 2
    while await _slug_exists(db, slug):
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


async def _slug_exists(db: AsyncSession, slug: str) -> bool:
    result = await db.execute(select(Laboratory.id).where(Laboratory.slug == slug))
    return result.scalar_one_or_none() is not None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return re.sub(r"-+", "-", slug)


async def _get_user_by_email(db: AsyncSession, email: str) -> User:
    result = await db.execute(select(User).where(User.email == email.strip().lower()))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def _get_membership_with_user(
    db: AsyncSession,
    lab_id: uuid.UUID,
    membership_id: uuid.UUID,
) -> tuple[LabMembership, User]:
    result = await db.execute(
        select(LabMembership, User)
        .join(User, User.id == LabMembership.user_id)
        .where(LabMembership.id == membership_id, LabMembership.laboratory_id == lab_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Lab member not found")
    return row


async def _ensure_another_owner_exists(
    db: AsyncSession,
    lab_id: uuid.UUID,
    *,
    excluding_membership_id: uuid.UUID,
) -> None:
    result = await db.execute(
        select(func.count(LabMembership.id)).where(
            LabMembership.laboratory_id == lab_id,
            LabMembership.role == LabRole.OWNER,
            LabMembership.id != excluding_membership_id,
        )
    )
    if result.scalar_one() == 0:
        raise HTTPException(status_code=400, detail="A lab must have at least one owner")


def _lab_response(lab: Laboratory, membership: LabMembership) -> LabResponse:
    response = LabResponse.model_validate(lab)
    response.role = membership.role
    return response


def _membership_response(
    membership: LabMembership,
    user: User,
) -> LabMembershipResponse:
    return LabMembershipResponse(
        id=membership.id,
        laboratory_id=membership.laboratory_id,
        user_id=membership.user_id,
        role=membership.role,
        invited_by=membership.invited_by,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        created_at=membership.created_at,
        updated_at=membership.updated_at,
    )
