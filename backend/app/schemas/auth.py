from __future__ import annotations

import uuid

from pydantic import BaseModel


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    clerk_user_id: str
    email: str
    display_name: str | None = None
    avatar_url: str | None = None
