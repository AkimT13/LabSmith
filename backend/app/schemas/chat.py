from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000)
    metadata: dict[str, Any] | None = None
