from __future__ import annotations

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.clerk import get_current_user
from app.database import get_db
from app.models.lab_document import LabDocument
from app.models.user import User
from app.schemas.documents import LabDocumentCreate, LabDocumentResponse
from app.services import documents as document_service

router = APIRouter(prefix="/api/v1", tags=["documents"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/labs/{lab_id}/documents", response_model=list[LabDocumentResponse])
async def list_lab_documents(
    lab_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[LabDocument]:
    return await document_service.list_lab_documents(
        db,
        lab_id=lab_id,
        user=current_user,
    )


@router.post("/labs/{lab_id}/documents", response_model=LabDocumentResponse, status_code=201)
async def create_lab_document(
    lab_id: uuid.UUID,
    data: LabDocumentCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> LabDocument:
    return await document_service.create_lab_document(
        db,
        lab_id=lab_id,
        user=current_user,
        data=data,
    )


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> FastAPIResponse:
    document = await document_service.get_document_for_user(
        db,
        document_id=document_id,
        user=current_user,
    )
    data = await document_service.read_document_bytes(document)
    filename = document_service.build_document_filename(document)
    return FastAPIResponse(
        content=data,
        media_type=document.content_type,
        headers={
            "Content-Disposition": _content_disposition_attachment(filename),
            "Content-Length": str(len(data)),
            "Cache-Control": "private, no-cache",
        },
    )


def _content_disposition_attachment(filename: str) -> str:
    quoted = quote(filename, safe="")
    return f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quoted}'
