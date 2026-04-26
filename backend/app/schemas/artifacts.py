from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, computed_field

from app.models.artifact import ArtifactType


class ArtifactResponse(BaseModel):
    """Response shape for a single artifact.

    `download_url` and `preview_url` are derived server-side rather than built
    on the frontend. When the artifact has no on-disk bytes (no `file_path`),
    both URLs are null and the frontend cleanly degrades to an empty state.
    `preview_url` is also null for non-STL artifacts since the 3D viewer can
    only render STL today.
    """

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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def download_url(self) -> str | None:
        if self.file_path is None:
            return None
        return f"/api/v1/artifacts/{self.id}/download"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def preview_url(self) -> str | None:
        if self.file_path is None:
            return None
        if self.artifact_type != ArtifactType.STL:
            return None
        return f"/api/v1/artifacts/{self.id}/preview"
