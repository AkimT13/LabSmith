"""Artifact list + download/preview shells.

The list endpoint is fully wired in M3 so the frontend can render the artifact
list. The download/preview endpoints are reserved here but only return 501 in
M3 — real bytes land in M4 (storage service + 3D viewer) and M5 (real CadQuery
output).
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.clerk import get_current_user
from app.database import get_db
from app.models.artifact import Artifact
from app.models.user import User
from app.schemas.artifacts import ArtifactResponse
from app.services.access import get_session_with_membership

router = APIRouter(prefix="/api/v1", tags=["artifacts"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/sessions/{session_id}/artifacts", response_model=list[ArtifactResponse])
async def list_session_artifacts(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[Artifact]:
    design_session, _membership = await get_session_with_membership(
        db, session_id=session_id, user=current_user
    )
    result = await db.execute(
        select(Artifact)
        .where(Artifact.session_id == design_session.id)
        .order_by(desc(Artifact.created_at))
    )
    return list(result.scalars().all())


@router.get("/artifacts/{artifact_id}/download")
async def download_artifact(
    artifact_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """M4 will return the artifact bytes with Content-Disposition: attachment."""
    await _resolve_artifact(db, artifact_id=artifact_id, user=current_user)
    raise HTTPException(status_code=501, detail="Artifact download lands in M4")


@router.get("/artifacts/{artifact_id}/preview")
async def preview_artifact(
    artifact_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """M4 will stream raw STL bytes for the React Three Fiber viewer."""
    await _resolve_artifact(db, artifact_id=artifact_id, user=current_user)
    raise HTTPException(status_code=501, detail="Artifact preview lands in M4")


async def _resolve_artifact(
    db: AsyncSession,
    *,
    artifact_id: uuid.UUID,
    user: User,
) -> Artifact:
    result = await db.execute(select(Artifact).where(Artifact.id == artifact_id))
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    # Authorization: must be a lab member of the session's lab.
    await get_session_with_membership(db, session_id=artifact.session_id, user=user)
    return artifact
