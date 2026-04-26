"""Lab device + queued print job models for the LabSmith Device Protocol (M10).

A `LabDevice` is a lab-scoped, simulated piece of hardware (today: 3D printers).
A `DeviceJob` is one unit of work assigned to a device — currently a print of a
session-bound `Artifact`. Progress is *derived* from `started_at +
simulated_duration_seconds` rather than written to the row, so the simulation
survives server restarts and horizontal scaling without any background tasks.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.artifact import Artifact
    from app.models.laboratory import Laboratory
    from app.models.user import User


class DeviceType(str, enum.Enum):
    """The kind of device. Each value maps to a per-type sim duration
    formula in `app/services/devices.py` and a default capability schema
    surfaced to the UI when adding the device.

    Job semantics are uniform: submit → run → complete, with progress
    derived from `started_at + simulated_duration_seconds`. Different
    device types just compute that duration differently (printer uses
    artifact volume; centrifuge uses user-supplied seconds; etc.).
    """

    PRINTER_3D = "printer_3d"
    LIQUID_HANDLER = "liquid_handler"
    CENTRIFUGE = "centrifuge"
    THERMOCYCLER = "thermocycler"
    PLATE_READER = "plate_reader"
    AUTOCLAVE = "autoclave"


class DeviceStatus(str, enum.Enum):
    """High-level device state surfaced to the UI. `busy` means a job is
    actively running; `queued_only` means jobs are waiting but none has begun
    (rare — only happens between dispatch ticks)."""

    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LabDevice(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lab_devices"

    laboratory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("laboratories.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    device_type: Mapped[DeviceType] = mapped_column(
        Enum(
            DeviceType,
            name="device_type",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    status: Mapped[DeviceStatus] = mapped_column(
        Enum(
            DeviceStatus,
            name="device_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=DeviceStatus.IDLE,
    )
    capabilities: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    """Per-type config bag, e.g. for printer_3d: {build_volume_mm: {x,y,z},
    nozzle_diameter_mm: 0.4, materials: ["PLA", "PETG"]}."""

    simulated: Mapped[bool] = mapped_column(default=True, nullable=False)
    """True for the demo. False would mean a real device adapter is wired in."""

    mean_seconds_per_cm3: Mapped[float] = mapped_column(
        Float, nullable=False, default=12.0
    )
    """Tuning knob for the sim duration formula. Lower = faster printer."""

    laboratory: Mapped[Laboratory] = relationship(foreign_keys=[laboratory_id])
    jobs: Mapped[list[DeviceJob]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
        order_by="DeviceJob.queue_position",
    )

    def __repr__(self) -> str:
        return f"<LabDevice {self.name} ({self.device_type})>"


class DeviceJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "device_jobs"

    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lab_devices.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Print history is meaningless without the artifact it was printing.
    # Cascading the delete keeps project/session deletes simple. Nullable
    # because non-printer device types (centrifuge, plate reader, etc.)
    # don't reference an artifact — their inputs live in `payload` instead.
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        nullable=True,
    )
    submitted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Per-device-type job parameters. Printer jobs leave this null and rely
    # on the artifact spec; everyone else writes a small JSON dict here
    # (e.g. centrifuge: {"rpm": 1000, "seconds": 30}). The shape per type
    # is defined in `app/schemas/devices.py`.
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Simulated post-completion report (Tier-2 demo polish). Populated by
    # `tick_lab_devices` when a job transitions to COMPLETE; null while
    # queued/running. Shape is per-device-type; see
    # `app/services/device_results.py` for generators.
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[JobStatus] = mapped_column(
        Enum(
            JobStatus,
            name="device_job_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=JobStatus.QUEUED,
    )
    queue_position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    """0 = currently running (or about to start). Higher = further back in the
    line. Recomputed when jobs complete."""

    simulated_duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    """Set at submit time from the artifact's spec snapshot via the printer's
    mean_seconds_per_cm3. Used to derive live progress on read."""

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Short human label like 'TMA mold v3 · 6×8 wells'. Set at submit."""

    device: Mapped[LabDevice] = relationship(back_populates="jobs", foreign_keys=[device_id])
    artifact: Mapped[Artifact] = relationship(foreign_keys=[artifact_id])
    submitter: Mapped[User] = relationship(foreign_keys=[submitted_by])

    def __repr__(self) -> str:
        return f"<DeviceJob {self.label or self.id} status={self.status}>"
