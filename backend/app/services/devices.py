"""LabSmith Device Protocol — scheduler, sim engine, and CRUD service.

The simulation deliberately stores no live progress in the DB. Each running job
records `started_at + simulated_duration_seconds`; progress is derived from
wall-clock time on every read. Two consequences:

1. Restarting the backend doesn't lose state — jobs continue ticking from when
   they started.
2. Job advancement (queued → running → complete) happens lazily inside
   `tick_lab_devices()`, which the router calls on every read endpoint. There
   is no background worker, no Redis, no Celery. Postgres is the queue.

The scheduler currently picks the idle device first, falling back to the
shortest-queue device. Round-robin tiebreaker by `created_at`.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.artifact import Artifact
from app.models.design_session import DesignSession
from app.models.lab_device import DeviceJob, DeviceStatus, DeviceType, JobStatus, LabDevice
from app.models.lab_membership import LabRole
from app.models.project import Project
from app.models.user import User
from app.schemas.devices import (
    DeviceJobResponse,
    LabDeviceCreate,
    LabDeviceResponse,
    LabDeviceUpdate,
)
from app.services.access import require_lab_role
from app.services.device_results import generate_result

# ---------------------------------------------------------------------------
# Sim duration
# ---------------------------------------------------------------------------

_DEFAULT_VOLUME_CM3 = 12.0
"""Used when an artifact has no spec_snapshot we can size from. Roughly a small
gel comb — keeps the demo bar moving in a reasonable amount of time."""

_MIN_DURATION_SECONDS = 20.0
_MAX_DURATION_SECONDS = 60 * 30  # 30 min cap so demos don't drag


def estimate_volume_cm3(spec_snapshot: dict | None) -> float:
    """Best-effort volume estimate from an artifact's spec snapshot.

    Looks for common dimensional fields (`well_count`, `dimensions`, etc.) and
    falls back to `_DEFAULT_VOLUME_CM3`. The numbers don't need to be physically
    accurate — they just need to feel believable across our part templates so
    one print isn't 10x the duration of another for no visible reason.
    """
    if not spec_snapshot or not isinstance(spec_snapshot, dict):
        return _DEFAULT_VOLUME_CM3

    dims = spec_snapshot.get("dimensions") or {}
    if isinstance(dims, dict):
        # Convert mm³ → cm³
        x = float(dims.get("x_mm") or dims.get("length_mm") or 0)
        y = float(dims.get("y_mm") or dims.get("width_mm") or 0)
        z = float(dims.get("z_mm") or dims.get("height_mm") or 0)
        if x and y and z:
            return max(_DEFAULT_VOLUME_CM3, (x * y * z) / 1000.0)

    well_count = spec_snapshot.get("well_count") or spec_snapshot.get("count")
    if isinstance(well_count, (int, float)) and well_count > 0:
        return _DEFAULT_VOLUME_CM3 + 0.5 * float(well_count)

    return _DEFAULT_VOLUME_CM3


def compute_simulated_duration(
    *, spec_snapshot: dict | None, mean_seconds_per_cm3: float
) -> float:
    """Printer-specific duration: volume × per-cm³ rate, clamped."""
    volume = estimate_volume_cm3(spec_snapshot)
    raw = volume * mean_seconds_per_cm3
    return max(_MIN_DURATION_SECONDS, min(_MAX_DURATION_SECONDS, raw))


# Per-non-printer-type duration: derive from the job's payload. Each branch
# extracts its known fields and falls back to a sensible default if the
# payload is missing or malformed — we never want a misformed payload to
# block a demo, so calculators always return SOMETHING in [MIN, MAX].
_DEFAULT_NON_PRINTER_DURATIONS: dict[DeviceType, float] = {
    DeviceType.LIQUID_HANDLER: 240.0,
    DeviceType.CENTRIFUGE: 60.0,
    DeviceType.THERMOCYCLER: 600.0,
    DeviceType.PLATE_READER: 90.0,
    DeviceType.AUTOCLAVE: 1200.0,
}


def compute_payload_duration(
    *, device_type: DeviceType, payload: dict | None
) -> float:
    """Duration for a non-printer device job, clamped to [MIN, MAX]."""
    seconds = _DEFAULT_NON_PRINTER_DURATIONS.get(device_type, _MIN_DURATION_SECONDS)
    payload = payload or {}

    try:
        if device_type == DeviceType.CENTRIFUGE:
            seconds = float(payload.get("seconds", seconds))
        elif device_type == DeviceType.THERMOCYCLER:
            cycles = int(payload.get("cycles", 1))
            steps = payload.get("steps") or []
            per_cycle = sum(float(s.get("seconds", 30)) for s in steps if isinstance(s, dict))
            if cycles > 0 and per_cycle > 0:
                # Sim scaling for demo: real PCR is ~30-60 min, but we
                # compress aggressively so a 25-cycle program lands ~30s.
                # Adjust the divisor if you want longer/shorter steps.
                seconds = max(20.0, (cycles * per_cycle) / 30.0)
        elif device_type == DeviceType.PLATE_READER:
            wells = int(payload.get("wells", 96))
            seconds = max(60.0, wells * 0.6)
        elif device_type == DeviceType.LIQUID_HANDLER:
            seconds = float(payload.get("estimated_seconds", seconds))
        elif device_type == DeviceType.AUTOCLAVE:
            seconds = float(payload.get("seconds", seconds))
    except (TypeError, ValueError):
        # Bad payload — silently fall back to default, never crash.
        seconds = _DEFAULT_NON_PRINTER_DURATIONS.get(device_type, _MIN_DURATION_SECONDS)

    return max(_MIN_DURATION_SECONDS, min(_MAX_DURATION_SECONDS, float(seconds)))


# ---------------------------------------------------------------------------
# Tick: advance queued/running jobs based on wall-clock time
# ---------------------------------------------------------------------------


async def tick_lab_devices(db: AsyncSession, *, lab_id: uuid.UUID) -> None:
    """Advance any running jobs that have hit their end time, and start the
    next queued job on each idle device. Idempotent; cheap to call on every
    read.
    """
    now = datetime.now(timezone.utc)

    devices = await _load_devices_with_jobs(db, lab_id=lab_id)

    dirty = False
    for device in devices:
        live_jobs = [
            j for j in device.jobs if j.status in (JobStatus.QUEUED, JobStatus.RUNNING)
        ]

        # Mark any running job that has finished as complete.
        for job in list(live_jobs):
            if (
                job.status == JobStatus.RUNNING
                and job.started_at is not None
                and (now - job.started_at).total_seconds() >= job.simulated_duration_seconds
            ):
                job.status = JobStatus.COMPLETE
                job.completed_at = now
                job.queue_position = -1
                # Generate the simulated post-completion report. Safe to run
                # even for printer jobs — generate_result returns a stub
                # for unknown types.
                if job.result is None:
                    job.result = generate_result(
                        device_type=device.device_type,
                        job_id=job.id,
                        payload=job.payload,
                    )
                live_jobs.remove(job)
                dirty = True

        # Re-number the still-live queue, starting from 0.
        live_jobs.sort(
            key=lambda j: (j.queue_position if j.queue_position >= 0 else 999, j.created_at)
        )
        for index, job in enumerate(live_jobs):
            if job.queue_position != index:
                job.queue_position = index
                dirty = True

        # If nothing is running and there's a queued job at position 0, start it.
        running = next((j for j in live_jobs if j.status == JobStatus.RUNNING), None)
        if running is None and live_jobs:
            head = live_jobs[0]
            head.status = JobStatus.RUNNING
            head.started_at = now
            running = head
            dirty = True

        new_status = (
            DeviceStatus.OFFLINE
            if device.status == DeviceStatus.OFFLINE
            else DeviceStatus.BUSY
            if running is not None
            else DeviceStatus.IDLE
        )
        if device.status != new_status:
            device.status = new_status
            dirty = True

    if dirty:
        await db.commit()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def list_lab_devices(
    db: AsyncSession, *, lab_id: uuid.UUID, user: User
) -> list[LabDeviceResponse]:
    await require_lab_role(db, lab_id=lab_id, user=user, minimum_role=LabRole.VIEWER)
    await tick_lab_devices(db, lab_id=lab_id)
    devices = await _load_devices_with_jobs(db, lab_id=lab_id)
    return [serialize_device(device) for device in devices]


async def create_lab_device(
    db: AsyncSession,
    *,
    lab_id: uuid.UUID,
    user: User,
    data: LabDeviceCreate,
) -> LabDeviceResponse:
    await require_lab_role(db, lab_id=lab_id, user=user, minimum_role=LabRole.ADMIN)
    device = LabDevice(
        laboratory_id=lab_id,
        name=data.name.strip(),
        device_type=data.device_type,
        capabilities=data.capabilities,
        mean_seconds_per_cm3=data.mean_seconds_per_cm3,
        simulated=True,
        status=DeviceStatus.IDLE,
    )
    db.add(device)
    await db.commit()
    await db.refresh(device, attribute_names=["jobs"])
    return serialize_device(device)


async def update_lab_device(
    db: AsyncSession,
    *,
    device_id: uuid.UUID,
    user: User,
    data: LabDeviceUpdate,
) -> LabDeviceResponse:
    device = await _load_device_or_404(db, device_id=device_id)
    await require_lab_role(
        db, lab_id=device.laboratory_id, user=user, minimum_role=LabRole.ADMIN
    )
    if data.name is not None:
        device.name = data.name.strip()
    if data.status is not None:
        device.status = data.status
    if data.capabilities is not None:
        device.capabilities = data.capabilities
    if data.mean_seconds_per_cm3 is not None:
        device.mean_seconds_per_cm3 = data.mean_seconds_per_cm3
    await db.commit()
    await db.refresh(device, attribute_names=["jobs"])
    return serialize_device(device)


async def delete_lab_device(
    db: AsyncSession, *, device_id: uuid.UUID, user: User
) -> None:
    device = await _load_device_or_404(db, device_id=device_id)
    await require_lab_role(
        db, lab_id=device.laboratory_id, user=user, minimum_role=LabRole.ADMIN
    )
    await db.delete(device)
    await db.commit()


# ---------------------------------------------------------------------------
# Submit a print job
# ---------------------------------------------------------------------------


async def submit_print_job(
    db: AsyncSession,
    *,
    lab_id: uuid.UUID,
    user: User,
    artifact_id: uuid.UUID,
    device_id: uuid.UUID | None = None,
    copies: int = 1,
) -> list[DeviceJobResponse]:
    """Create one or more `DeviceJob` rows, dispatching them via the scheduler.

    Cross-lab safeguard: the artifact's session's project's lab_id must match
    `lab_id`. Otherwise the user has no business sending it to this lab's
    printers.
    """
    await require_lab_role(db, lab_id=lab_id, user=user, minimum_role=LabRole.MEMBER)

    artifact = await _load_artifact_with_lab_check(
        db, artifact_id=artifact_id, expected_lab_id=lab_id
    )

    await tick_lab_devices(db, lab_id=lab_id)

    jobs: list[DeviceJob] = []
    for _ in range(copies):
        # Lock to PRINTER_3D explicitly so multi-copy print jobs never
        # spill over onto centrifuges, plate readers, etc. when printers
        # are busy. Without the filter, the shortest-queue scheduler
        # would happily route a print to any device with capacity.
        device = await _select_device(
            db,
            lab_id=lab_id,
            preferred_id=device_id,
            device_type=DeviceType.PRINTER_3D,
        )
        if device is None:
            raise HTTPException(
                status_code=409,
                detail="No printers available in this lab. Add one in Lab Settings → Devices.",
            )
        duration = compute_simulated_duration(
            spec_snapshot=artifact.spec_snapshot,
            mean_seconds_per_cm3=device.mean_seconds_per_cm3,
        )
        job = DeviceJob(
            device_id=device.id,
            artifact_id=artifact.id,
            submitted_by=user.id,
            simulated_duration_seconds=duration,
            label=_label_for_artifact(artifact),
            queue_position=_next_queue_position(device),
            status=JobStatus.QUEUED,
        )
        db.add(job)
        device.jobs.append(job)
        jobs.append(job)

    await db.commit()

    # Run the tick AFTER committing the new rows so the head job starts
    # immediately (no need to wait for the next read).
    await tick_lab_devices(db, lab_id=lab_id)

    # Re-load to surface the now-running state.
    refreshed = []
    for job in jobs:
        await db.refresh(job)
        refreshed.append(job)
    return [serialize_job(job) for job in refreshed]


async def submit_device_job(
    db: AsyncSession,
    *,
    lab_id: uuid.UUID,
    user: User,
    device_type: DeviceType,
    payload: dict,
    label: str,
) -> DeviceJobResponse:
    """Dispatch a non-print job to the next-available device of `device_type`.

    Used by the M11 experiment runner. Always creates exactly one job —
    multi-copy semantics only make sense for printers and live in
    `submit_print_job`. The artifact_id is null; per-type sim duration is
    derived from `payload` via `compute_payload_duration`.

    Raises HTTPException(409) if no device of the requested type exists in
    the lab — the experiment runner translates that to a friendly
    "you need to add an X" message.
    """
    await require_lab_role(db, lab_id=lab_id, user=user, minimum_role=LabRole.MEMBER)
    await tick_lab_devices(db, lab_id=lab_id)

    device = await _select_device(
        db, lab_id=lab_id, preferred_id=None, device_type=device_type
    )
    if device is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"No {device_type.value} available in this lab. "
                "Add one in Lab Settings → Devices."
            ),
        )

    duration = compute_payload_duration(device_type=device_type, payload=payload)
    job = DeviceJob(
        device_id=device.id,
        artifact_id=None,
        submitted_by=user.id,
        simulated_duration_seconds=duration,
        label=label[:160] or device_type.value,
        payload=payload,
        queue_position=_next_queue_position(device),
        status=JobStatus.QUEUED,
    )
    db.add(job)
    device.jobs.append(job)
    await db.commit()
    await tick_lab_devices(db, lab_id=lab_id)
    await db.refresh(job)
    return serialize_job(job)


async def _select_device(
    db: AsyncSession,
    *,
    lab_id: uuid.UUID,
    preferred_id: uuid.UUID | None,
    device_type: DeviceType | None = None,
) -> LabDevice | None:
    """Pick the best device in the lab.

    When `device_type` is set, only devices of that type are eligible —
    used by the experiment runner to route a centrifuge step to a
    centrifuge, etc. When unset (the M10 print path), any device type
    qualifies.
    """
    devices = await _load_devices_with_jobs(db, lab_id=lab_id)
    eligible = [
        d for d in devices
        if d.status != DeviceStatus.OFFLINE
        and d.status != DeviceStatus.ERROR
        and (device_type is None or d.device_type == device_type)
    ]
    if not eligible:
        return None

    if preferred_id is not None:
        chosen = next((d for d in eligible if d.id == preferred_id), None)
        if chosen is None:
            raise HTTPException(
                status_code=404, detail="Selected device not found in this lab"
            )
        return chosen

    # Idle first, then shortest-queue, then oldest device.
    def queue_len(device: LabDevice) -> int:
        return sum(
            1 for j in device.jobs
            if j.status in (JobStatus.QUEUED, JobStatus.RUNNING)
        )

    eligible.sort(key=lambda d: (queue_len(d), d.created_at))
    return eligible[0]


def _next_queue_position(device: LabDevice) -> int:
    live = [
        j.queue_position
        for j in device.jobs
        if j.status in (JobStatus.QUEUED, JobStatus.RUNNING)
    ]
    if not live:
        return 0
    return max(live) + 1


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def serialize_job(job: DeviceJob) -> DeviceJobResponse:
    progress, eta_seconds = _progress_and_eta(job)
    return DeviceJobResponse(
        id=job.id,
        device_id=job.device_id,
        artifact_id=job.artifact_id,
        submitted_by=job.submitted_by,
        label=job.label,
        status=job.status,
        queue_position=job.queue_position,
        simulated_duration_seconds=job.simulated_duration_seconds,
        started_at=job.started_at,
        completed_at=job.completed_at,
        submitted_at=job.created_at,
        progress=progress,
        eta_seconds=eta_seconds,
        payload=job.payload,
        result=job.result,
    )


def serialize_device(device: LabDevice) -> LabDeviceResponse:
    live = [
        j for j in device.jobs
        if j.status in (JobStatus.QUEUED, JobStatus.RUNNING)
    ]
    live.sort(key=lambda j: (j.queue_position, j.created_at))
    current = next((j for j in live if j.status == JobStatus.RUNNING), None)
    queue = [j for j in live if j is not current]

    return LabDeviceResponse(
        id=device.id,
        laboratory_id=device.laboratory_id,
        name=device.name,
        device_type=device.device_type,
        status=device.status,
        capabilities=device.capabilities,
        simulated=device.simulated,
        mean_seconds_per_cm3=device.mean_seconds_per_cm3,
        created_at=device.created_at,
        current_job=serialize_job(current) if current else None,
        queue=[serialize_job(j) for j in queue],
        queue_depth=len(queue),
    )


def _progress_and_eta(job: DeviceJob) -> tuple[float, float | None]:
    if job.status == JobStatus.COMPLETE:
        return 1.0, 0.0
    if job.status in (JobStatus.QUEUED, JobStatus.CANCELLED, JobStatus.FAILED):
        return 0.0, None
    if job.started_at is None or job.simulated_duration_seconds <= 0:
        return 0.0, None

    elapsed = (datetime.now(timezone.utc) - job.started_at).total_seconds()
    raw = elapsed / job.simulated_duration_seconds
    progress = max(0.0, min(0.999, raw))  # cap shy of 1 until tick promotes it
    eta = max(0.0, job.simulated_duration_seconds - elapsed)
    if math.isnan(progress):
        return 0.0, None
    return progress, eta


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------


async def _load_devices_with_jobs(
    db: AsyncSession, *, lab_id: uuid.UUID
) -> list[LabDevice]:
    result = await db.execute(
        select(LabDevice)
        .where(LabDevice.laboratory_id == lab_id)
        .options(selectinload(LabDevice.jobs))
        .order_by(LabDevice.created_at)
    )
    return list(result.scalars().all())


async def _load_device_or_404(
    db: AsyncSession, *, device_id: uuid.UUID
) -> LabDevice:
    result = await db.execute(
        select(LabDevice)
        .where(LabDevice.id == device_id)
        .options(selectinload(LabDevice.jobs))
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


async def _load_artifact_with_lab_check(
    db: AsyncSession, *, artifact_id: uuid.UUID, expected_lab_id: uuid.UUID
) -> Artifact:
    result = await db.execute(
        select(Artifact, Project.laboratory_id)
        .join(DesignSession, DesignSession.id == Artifact.session_id)
        .join(Project, Project.id == DesignSession.project_id)
        .where(Artifact.id == artifact_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    artifact, lab_id = row
    if lab_id != expected_lab_id:
        # Don't reveal cross-lab existence — 404 like the artifact doesn't
        # exist for this user.
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


def _label_for_artifact(artifact: Artifact) -> str:
    spec = artifact.spec_snapshot or {}
    part_type = spec.get("part_type") or artifact.artifact_type.value
    return f"{part_type} · v{artifact.version}"
