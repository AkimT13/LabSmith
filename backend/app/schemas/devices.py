"""Pydantic schemas for the LabSmith Device Protocol (M10)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.lab_device import DeviceStatus, DeviceType, JobStatus


class LabDeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    device_type: DeviceType = DeviceType.PRINTER_3D
    capabilities: dict | None = None
    mean_seconds_per_cm3: float = Field(default=12.0, gt=0, le=600)


class LabDeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    status: DeviceStatus | None = None
    capabilities: dict | None = None
    mean_seconds_per_cm3: float | None = Field(default=None, gt=0, le=600)


class DeviceJobResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    device_id: uuid.UUID
    artifact_id: uuid.UUID | None
    """Set for printer jobs; null for non-printer device jobs (centrifuge,
    plate reader, etc.) which describe their work via `payload` instead."""

    submitted_by: uuid.UUID
    label: str | None
    status: JobStatus
    queue_position: int
    simulated_duration_seconds: float
    started_at: datetime | None
    completed_at: datetime | None
    submitted_at: datetime
    progress: float = Field(ge=0.0, le=1.0)
    """Live progress fraction (0–1) computed from started_at + duration."""

    eta_seconds: float | None
    """Seconds remaining if running, None if queued or already done."""

    payload: dict | None = None
    """Per-device-type job parameters (e.g. centrifuge rpm/seconds). Null
    for printer jobs."""

    result: dict | None = None
    """Simulated post-completion report (Tier-2 demo polish). Populated when
    the job transitions to COMPLETE; null while queued/running. Shape is
    per-device-type — see backend `app/services/device_results.py`."""


class LabDeviceResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    laboratory_id: uuid.UUID
    name: str
    device_type: DeviceType
    status: DeviceStatus
    capabilities: dict | None
    simulated: bool
    mean_seconds_per_cm3: float
    created_at: datetime

    current_job: DeviceJobResponse | None = None
    queue: list[DeviceJobResponse] = []
    queue_depth: int = 0


class SubmitPrintJobRequest(BaseModel):
    artifact_id: uuid.UUID
    device_id: uuid.UUID | None = None
    """If omitted, the scheduler picks the device with the shortest queue."""
    copies: int = Field(default=1, ge=1, le=10)


class SubmitPrintJobResponse(BaseModel):
    jobs: list[DeviceJobResponse]
