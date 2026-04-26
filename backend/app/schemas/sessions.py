from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.design_session import SessionStatus, SessionType


class DesignSessionCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=220)
    session_type: SessionType = SessionType.PART_DESIGN
    part_type: str | None = Field(default=None, max_length=120)
    current_spec: dict[str, Any] | None = None


class DesignSessionUpdate(BaseModel):
    """Update payload for a session.

    `session_type` is intentionally NOT updatable — switching the type after
    creation would invalidate the existing message history (it was generated
    under different rules) and conflate event catalogs from different agents.
    Users who want a different type create a new session.
    """

    title: str | None = Field(default=None, min_length=1, max_length=220)
    status: SessionStatus | None = None
    part_type: str | None = Field(default=None, max_length=120)
    current_spec: dict[str, Any] | None = None


class DesignSessionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    status: SessionStatus
    session_type: SessionType
    part_type: str | None
    current_spec: dict[str, Any] | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
