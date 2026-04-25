from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.artifact import ArtifactType


class ArtifactResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    session_id: uuid.UUID
    message_id: uuid.UUID | None
    artifact_type: ArtifactType
    file_path: str | None
    file_size_bytes: int | None
    spec_snapshot: dict[str, Any] | None
    validation: dict[str, Any] | None
    version: int
    created_at: datetime
