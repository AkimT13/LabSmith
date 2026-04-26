"""Pydantic schemas for the M11 experiment runner.

A protocol is an ordered list of `ExperimentStep`s. Each step is one of:
- `fabricate` — generate a part from a CAD prompt (uses the existing CAD
  pipeline; produces an Artifact).
- `device_job` — submit a job to a specific device type (uses the M10
  scheduler; produces a DeviceJob).

The shape of `params` per device type is defined as a tagged union below.
The LLM only ever produces strings/numbers — we validate into typed models
at the agent boundary so a malformed protocol is rejected with a clear
error before any device is touched.
"""
from __future__ import annotations

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.models.lab_device import DeviceType


# ---------------------------------------------------------------------------
# Per-device job parameters
# ---------------------------------------------------------------------------


class CentrifugeParams(BaseModel):
    rpm: int = Field(ge=100, le=20000, description="Rotation speed in RPM.")
    seconds: int = Field(ge=10, le=3600, description="Spin time in seconds.")


class ThermocyclerStep(BaseModel):
    label: str = Field(default="step", max_length=40)
    temperature_c: float = Field(ge=4.0, le=99.0)
    seconds: int = Field(ge=1, le=600)


class ThermocyclerParams(BaseModel):
    cycles: int = Field(ge=1, le=60)
    steps: list[ThermocyclerStep] = Field(min_length=1, max_length=10)


class PlateReaderParams(BaseModel):
    mode: Literal["absorbance", "fluorescence", "luminescence"] = "absorbance"
    wavelength_nm: int | None = Field(default=None, ge=200, le=1000)
    wells: int = Field(default=96, ge=1, le=384)


class LiquidHandlerParams(BaseModel):
    protocol_label: str = Field(max_length=80, description="Short human label for the protocol.")
    plate_count: int = Field(default=1, ge=1, le=10)
    estimated_seconds: int = Field(default=240, ge=30, le=1800)


class AutoclaveParams(BaseModel):
    temperature_c: int = Field(default=121, ge=100, le=140)
    seconds: int = Field(default=1200, ge=300, le=3600)


# Tagged union over device types — each step's `params` must match the
# step's `device_type` or validation rejects the protocol.
DeviceParams = (
    CentrifugeParams
    | ThermocyclerParams
    | PlateReaderParams
    | LiquidHandlerParams
    | AutoclaveParams
)


# ---------------------------------------------------------------------------
# Step + Protocol
# ---------------------------------------------------------------------------


class FabricateStep(BaseModel):
    """A `fabricate` step generates a part using the existing CAD pipeline.
    The `prompt` is fed verbatim to the spec extractor — same path as
    `part_design` sessions."""

    kind: Literal["fabricate"] = "fabricate"
    label: str = Field(max_length=80)
    prompt: str = Field(min_length=4, max_length=400)


class DeviceJobStep(BaseModel):
    """A `device_job` step dispatches work to a specific device type via
    the M10 scheduler. The `params` must match the chosen device type."""

    kind: Literal["device_job"] = "device_job"
    label: str = Field(max_length=80)
    device_type: DeviceType
    params: dict = Field(
        default_factory=dict,
        description="Per-device-type parameters — see schemas above.",
    )


ExperimentStep = Annotated[
    FabricateStep | DeviceJobStep, Field(discriminator="kind")
]


class ExperimentProtocol(BaseModel):
    title: str = Field(max_length=120)
    summary: str = Field(default="", max_length=400)
    steps: list[ExperimentStep] = Field(min_length=1, max_length=12)


# ---------------------------------------------------------------------------
# Persistence shape — what's stored on `design_sessions.current_spec`
# ---------------------------------------------------------------------------


class StepRunState(BaseModel):
    """Per-step runtime state that gets updated as the agent executes the
    protocol. Persisted on the session alongside the protocol so a page
    refresh shows the right progress.

    `dispatched_id` is either an artifact id (fabricate) or a device job
    id (device_job). `error` is set on failure so the UI can render it.

    `result` holds the per-device-type post-completion report copied from
    the dispatched device job — embedding it on the step state means the
    timeline UI doesn't need to cross-reference the live device snapshot
    (which doesn't carry completed jobs).
    """

    status: Literal["pending", "running", "complete", "failed", "skipped"] = "pending"
    dispatched_id: uuid.UUID | None = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    result: dict | None = None


class ExperimentRunState(BaseModel):
    """Top-level wrapper persisted on `session.current_spec` for experiment
    sessions. The protocol is immutable once execution starts; step states
    update independently as work progresses."""

    protocol: ExperimentProtocol
    step_states: list[StepRunState]
    status: Literal["proposed", "running", "complete", "failed"] = "proposed"
