"""LabSmith Device Protocol — HTTP routes for devices and print jobs (M10)."""
from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.clerk import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.devices import (
    LabDeviceCreate,
    LabDeviceResponse,
    LabDeviceUpdate,
    SubmitPrintJobRequest,
    SubmitPrintJobResponse,
)
from app.services import devices as device_service
from app.services.access import require_lab_role
from app.models.lab_membership import LabRole

router = APIRouter(prefix="/api/v1", tags=["devices"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Devices CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/labs/{lab_id}/devices",
    response_model=list[LabDeviceResponse],
)
async def list_devices(
    lab_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> list[LabDeviceResponse]:
    return await device_service.list_lab_devices(db, lab_id=lab_id, user=current_user)


@router.post(
    "/labs/{lab_id}/devices",
    response_model=LabDeviceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_device(
    lab_id: uuid.UUID,
    data: LabDeviceCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> LabDeviceResponse:
    return await device_service.create_lab_device(
        db, lab_id=lab_id, user=current_user, data=data
    )


@router.patch(
    "/devices/{device_id}",
    response_model=LabDeviceResponse,
)
async def update_device(
    device_id: uuid.UUID,
    data: LabDeviceUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> LabDeviceResponse:
    return await device_service.update_lab_device(
        db, device_id=device_id, user=current_user, data=data
    )


@router.delete(
    "/devices/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_device(
    device_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> Response:
    await device_service.delete_lab_device(
        db, device_id=device_id, user=current_user
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Submit print job
# ---------------------------------------------------------------------------


@router.post(
    "/labs/{lab_id}/devices/print",
    response_model=SubmitPrintJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_print(
    lab_id: uuid.UUID,
    data: SubmitPrintJobRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> SubmitPrintJobResponse:
    jobs = await device_service.submit_print_job(
        db,
        lab_id=lab_id,
        user=current_user,
        artifact_id=data.artifact_id,
        device_id=data.device_id,
        copies=data.copies,
    )
    return SubmitPrintJobResponse(jobs=jobs)


# ---------------------------------------------------------------------------
# Live stream
# ---------------------------------------------------------------------------


@router.get("/labs/{lab_id}/devices/stream")
async def stream_devices(
    lab_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> StreamingResponse:
    """SSE stream emitting the lab's full devices+jobs snapshot every ~2s.

    The frontend uses this to animate progress bars without polling. We send a
    full snapshot rather than diffs so the client is stateless — easier to
    debug, trivial to reconnect.
    """
    # Membership check up-front so we 401/404 before opening the stream.
    await require_lab_role(
        db, lab_id=lab_id, user=current_user, minimum_role=LabRole.VIEWER
    )

    async def gen() -> AsyncGenerator[bytes, None]:
        while True:
            try:
                snapshot = await device_service.list_lab_devices(
                    db, lab_id=lab_id, user=current_user
                )
            except Exception:  # noqa: BLE001 — never crash the long-lived stream
                yield b": stream-error\n\n"
                await asyncio.sleep(5)
                continue

            payload = json.dumps(
                [d.model_dump(mode="json") for d in snapshot],
                default=str,
            )
            yield f"event: snapshot\ndata: {payload}\n\n".encode()
            await asyncio.sleep(2.0)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
