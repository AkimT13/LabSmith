"""Artifact list, download, and preview routes.

The contract for download/preview is in `docs/M4_CONTRACT.md`. Both routes
reuse `_resolve_artifact()` to enforce lab-membership auth — only members of
the artifact's session's lab can read or download bytes.
"""
from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.clerk import get_current_user
from app.database import get_db
from app.models.artifact import Artifact, ArtifactType
from app.models.design_session import DesignSession
from app.models.user import User
from app.schemas.artifacts import ArtifactResponse
from app.services.access import get_session_with_membership
from app.services.storage import CONTENT_TYPE_BY_EXTENSION, get_storage

router = APIRouter(prefix="/api/v1", tags=["artifacts"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


_EXTENSION_BY_TYPE: dict[ArtifactType, str] = {
    ArtifactType.STL: "stl",
    ArtifactType.STEP: "step",
    ArtifactType.SPEC_JSON: "json",
    ArtifactType.VALIDATION_JSON: "json",
}


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
) -> Response:
    """Return artifact bytes as an attachment (browser triggers a save dialog)."""
    artifact, design_session = await _resolve_artifact_and_session(
        db, artifact_id=artifact_id, user=current_user
    )
    data, content_type = await _read_artifact_bytes(artifact)
    filename = _build_download_filename(design_session, artifact)
    return FastAPIResponse(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": _content_disposition_attachment(filename),
            "Content-Length": str(len(data)),
            "Cache-Control": "private, no-cache",
        },
    )


@router.get("/artifacts/{artifact_id}/preview")
async def preview_artifact(
    artifact_id: uuid.UUID,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
    """Return artifact bytes inline, with an ETag the browser can use to skip re-fetches."""
    artifact, _design_session = await _resolve_artifact_and_session(
        db, artifact_id=artifact_id, user=current_user
    )
    if artifact.artifact_type != ArtifactType.STL:
        raise HTTPException(status_code=415, detail="Artifact preview only supports STL")

    etag = _etag_for(artifact)

    # Honor If-None-Match so the browser doesn't re-download bytes that haven't
    # changed (artifact ID + version uniquely identify the byte payload).
    if request.headers.get("if-none-match") == etag:
        return FastAPIResponse(status_code=304, headers={"ETag": etag})

    data, content_type = await _read_artifact_bytes(artifact)
    return FastAPIResponse(
        content=data,
        media_type=content_type,
        headers={
            "Content-Length": str(len(data)),
            "Cache-Control": "private, max-age=300",
            "ETag": etag,
        },
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _resolve_artifact_and_session(
    db: AsyncSession,
    *,
    artifact_id: uuid.UUID,
    user: User,
) -> tuple[Artifact, DesignSession]:
    """Look up the artifact and verify the caller is a lab member of its session.

    Returns the session too so the download filename helper can build a nice
    name without an extra query.
    """
    result = await db.execute(select(Artifact).where(Artifact.id == artifact_id))
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    design_session, _membership = await get_session_with_membership(
        db, session_id=artifact.session_id, user=user
    )
    return artifact, design_session


async def _read_artifact_bytes(artifact: Artifact) -> tuple[bytes, str]:
    """Read the artifact bytes from storage.

    404 if the row has no file_path or the bytes are missing on disk — both
    indicate the artifact has no downloadable content (generation failure,
    manual cleanup, etc.).
    """
    if artifact.file_path is None:
        raise HTTPException(status_code=404, detail="Artifact has no stored bytes")

    storage = get_storage()
    try:
        data = await storage.read(artifact.file_path)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Artifact bytes not found in storage"
        ) from exc

    extension = _EXTENSION_BY_TYPE.get(artifact.artifact_type, "bin")
    content_type = CONTENT_TYPE_BY_EXTENSION.get(extension, "application/octet-stream")
    return data, content_type


def _etag_for(artifact: Artifact) -> str:
    """Stable ETag built from artifact id + version. Quoted per RFC 7232."""
    return f'"{artifact.id}:v{artifact.version}"'


def _build_download_filename(design_session: DesignSession, artifact: Artifact) -> str:
    """Build a human-friendly filename for the Content-Disposition header.

    Pattern: `<slugified session title>-v<version>.<ext>`. Falls back to
    `artifact-<id>` if the title slugifies to empty (e.g., all unicode).
    """
    slug = _slugify(design_session.title) or f"artifact-{artifact.id}"
    extension = _EXTENSION_BY_TYPE.get(artifact.artifact_type, "bin")
    return f"{slug}-v{artifact.version}.{extension}"


def _slugify(value: str) -> str:
    """ASCII-safe slug. Lowercases, collapses non-alnum to single hyphens."""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug[:80]


def _content_disposition_attachment(filename: str) -> str:
    """Build a Content-Disposition header that survives non-ASCII filenames.

    `filename=` is the ASCII fallback (already slugified by `_slugify`).
    `filename*=UTF-8''...` is RFC 5987 for clients that support it.
    """
    quoted = quote(filename, safe="")
    return f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quoted}'
