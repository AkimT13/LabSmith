from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db


async def get_session(db: AsyncSession = Depends(get_db)) -> AsyncGenerator[AsyncSession, None]:
    """Alias for get_db — use in route signatures."""
    yield db
