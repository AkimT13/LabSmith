from __future__ import annotations

import re
import unicodedata
import uuid
from pathlib import PurePath

from fastapi import HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.lab_document import LabDocument
from app.models.lab_membership import LabRole
from app.models.user import User
from app.schemas.documents import LabDocumentCreate
from app.services.access import get_lab_with_membership, require_lab_role
from app.services.storage import get_storage


async def list_lab_documents(
    db: AsyncSession,
    *,
    lab_id: uuid.UUID,
    user: User,
) -> list[LabDocument]:
    await require_lab_role(db, lab_id=lab_id, user=user, minimum_role=LabRole.VIEWER)
    result = await db.execute(
        select(LabDocument)
        .where(LabDocument.laboratory_id == lab_id)
        .order_by(desc(LabDocument.created_at))
    )
    return list(result.scalars().all())


async def create_lab_document(
    db: AsyncSession,
    *,
    lab_id: uuid.UUID,
    user: User,
    data: LabDocumentCreate,
) -> LabDocument:
    await require_lab_role(db, lab_id=lab_id, user=user, minimum_role=LabRole.MEMBER)

    content = data.content.encode("utf-8")
    if len(content) > settings.lab_document_max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Document exceeds {settings.lab_document_max_bytes} byte limit",
        )

    document = LabDocument(
        laboratory_id=lab_id,
        uploaded_by=user.id,
        title=data.title.strip(),
        source_filename=_clean_source_filename(data.source_filename),
        content_type=data.content_type.strip() or "text/plain",
        file_path="pending",
        file_size_bytes=0,
    )
    db.add(document)
    await db.flush()

    key = _lab_document_storage_key(
        lab_id=lab_id,
        document_id=document.id,
        filename=document.source_filename or document.title,
    )
    stored = await get_storage().save(key, content, content_type=document.content_type)
    document.file_path = stored.key
    document.file_size_bytes = stored.size_bytes

    await db.commit()
    await db.refresh(document)
    return document


async def get_document_for_user(
    db: AsyncSession,
    *,
    document_id: uuid.UUID,
    user: User,
    minimum_role: LabRole = LabRole.VIEWER,
) -> LabDocument:
    result = await db.execute(
        select(LabDocument).where(LabDocument.id == document_id)
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    await get_lab_with_membership(
        db,
        lab_id=document.laboratory_id,
        user=user,
        minimum_role=minimum_role,
    )
    return document


async def read_document_bytes(document: LabDocument) -> bytes:
    try:
        return await get_storage().read(document.file_path)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=404,
            detail="Document bytes not found in storage",
        ) from exc


async def delete_lab_document(
    db: AsyncSession,
    *,
    document_id: uuid.UUID,
    user: User,
) -> None:
    """Remove a lab document's row AND its bytes from storage.

    Mirrors the upload role gate (MEMBER+). The DB row is the source of
    truth for whether the document "exists" — we drop it first, then attempt
    the storage delete. Storage delete failures are swallowed so a transient
    storage hiccup doesn't leave a zombie row that can never be re-deleted.
    LocalFilesystemStorage's delete is already idempotent, so a missing file
    is fine.
    """
    document = await get_document_for_user(
        db,
        document_id=document_id,
        user=user,
        minimum_role=LabRole.MEMBER,
    )
    storage_key = document.file_path
    await db.delete(document)
    await db.commit()
    try:
        await get_storage().delete(storage_key)
    except Exception:  # noqa: BLE001 — storage hiccup shouldn't undo the row delete
        pass


def build_document_filename(document: LabDocument) -> str:
    source_name = document.source_filename or document.title
    path = PurePath(source_name)
    suffix = path.suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,10}", suffix or ""):
        suffix = ".txt"

    stem = path.stem if path.suffix else source_name
    slug = _slugify(stem) or f"document-{document.id}"
    return f"{slug[:80]}{suffix}"


def _lab_document_storage_key(
    *,
    lab_id: uuid.UUID,
    document_id: uuid.UUID,
    filename: str,
) -> str:
    return f"labs/{lab_id}/documents/{document_id}-{build_storage_filename(filename)}"


def build_storage_filename(filename: str) -> str:
    path = PurePath(filename)
    suffix = path.suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,10}", suffix or ""):
        suffix = ".txt"
    stem = path.stem if path.suffix else filename
    return f"{_slugify(stem) or 'document'}{suffix}"


def _clean_source_filename(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = PurePath(value.strip()).name
    return cleaned or None


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return re.sub(r"-+", "-", slug)
