from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, computed_field


class LabDocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    source_filename: str | None = Field(default=None, max_length=255)
    content_type: str = Field(default="text/plain", max_length=255)


class LabDocumentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    laboratory_id: uuid.UUID
    title: str
    source_filename: str | None
    content_type: str
    file_size_bytes: int
    uploaded_by: uuid.UUID
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def download_url(self) -> str:
        return f"/api/v1/documents/{self.id}/download"
