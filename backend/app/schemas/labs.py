from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.lab_membership import LabRole


class LabCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    description: str | None = None


class LabUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None


class LabResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    role: LabRole | None = None


class LabMemberCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    role: LabRole = LabRole.MEMBER


class LabMemberUpdate(BaseModel):
    role: LabRole


class LabMembershipResponse(BaseModel):
    id: uuid.UUID
    laboratory_id: uuid.UUID
    user_id: uuid.UUID
    role: LabRole
    invited_by: uuid.UUID | None
    email: str
    display_name: str | None
    avatar_url: str | None
    created_at: datetime
    updated_at: datetime
