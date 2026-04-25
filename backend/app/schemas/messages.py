from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.message import MessageRole


class MessageResponse(BaseModel):
    """Response schema for a chat message.

    Note: the ORM uses `metadata_` as the Python attribute (DB column is still
    `metadata`) to avoid SQLAlchemy's reserved-name conflict. We expose it as
    `metadata` over the wire via `validation_alias` so the JSON shape stays
    clean and matches the M3 contract.
    """

    model_config = {"from_attributes": True, "populate_by_name": True}

    id: uuid.UUID
    session_id: uuid.UUID
    role: MessageRole
    content: str
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="metadata_")
    created_at: datetime
