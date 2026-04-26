"""Tests for the M11 experiment runner — planner fallback, duration formulas,
device-type filter on the scheduler, and end-to-end agent execution.

Demo-safety contract these tests defend:
- The templated planner ALWAYS returns a valid protocol (never raises).
- `propose_protocol_safe` falls back to templated on any planner exception.
- Per-type sim durations are clamped to [MIN, MAX] and never NaN.
- Scheduler with `device_type` filter ignores devices of other types.
- The agent emits a terminal event (complete OR failed) on every run.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from app.auth.clerk import get_current_user
from app.database import async_session_factory, engine
from app.main import app
from app.models.lab_device import DeviceType, LabDevice
from app.models.user import User
from app.services import devices as device_service
from app.services.experiment_planner import (
    OpenAIPlanner,
    TemplatedPlanner,
    propose_protocol_safe,
)
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text


# ---------------------------------------------------------------------------
# duration calculators
# ---------------------------------------------------------------------------


def test_payload_duration_centrifuge_uses_seconds() -> None:
    """Result is the payload `seconds` after the demo speed factor + clamps.
    A 90s spin lands at ~36s with the current 0.4 multiplier."""
    expected = max(
        device_service._MIN_DURATION_SECONDS,
        min(device_service._MAX_DURATION_SECONDS, 90.0 * device_service._NON_PRINTER_SPEED_FACTOR),
    )
    assert (
        device_service.compute_payload_duration(
            device_type=DeviceType.CENTRIFUGE, payload={"rpm": 1000, "seconds": 90}
        )
        == pytest.approx(expected)
    )


def test_payload_duration_clamps_to_min_for_zero_seconds() -> None:
    duration = device_service.compute_payload_duration(
        device_type=DeviceType.CENTRIFUGE, payload={"rpm": 1000, "seconds": 0}
    )
    assert duration == device_service._MIN_DURATION_SECONDS


def test_payload_duration_clamps_to_max_for_huge_payloads() -> None:
    duration = device_service.compute_payload_duration(
        device_type=DeviceType.AUTOCLAVE, payload={"seconds": 99999}
    )
    assert duration == device_service._MAX_DURATION_SECONDS


def test_payload_duration_falls_back_for_garbage_payload() -> None:
    """A malformed payload must never crash — silently use the default."""
    duration = device_service.compute_payload_duration(
        device_type=DeviceType.THERMOCYCLER,
        payload={"cycles": "lots", "steps": "not a list"},
    )
    assert device_service._MIN_DURATION_SECONDS <= duration <= device_service._MAX_DURATION_SECONDS


def test_payload_duration_thermocycler_scales_with_cycles() -> None:
    short = device_service.compute_payload_duration(
        device_type=DeviceType.THERMOCYCLER,
        payload={
            "cycles": 5,
            "steps": [
                {"label": "denature", "temperature_c": 95, "seconds": 30},
                {"label": "anneal", "temperature_c": 60, "seconds": 30},
            ],
        },
    )
    longer = device_service.compute_payload_duration(
        device_type=DeviceType.THERMOCYCLER,
        payload={
            "cycles": 30,
            "steps": [
                {"label": "denature", "temperature_c": 95, "seconds": 30},
                {"label": "anneal", "temperature_c": 60, "seconds": 30},
            ],
        },
    )
    assert longer >= short


# ---------------------------------------------------------------------------
# Templated planner — must never raise
# ---------------------------------------------------------------------------


pytestmark = pytest.mark.asyncio


async def test_templated_planner_returns_valid_protocol_with_no_devices() -> None:
    planner = TemplatedPlanner()
    protocol = await planner.propose(
        user_content="amplify these samples", available_devices=[]
    )
    assert len(protocol.steps) >= 1
    # With zero devices it falls back to a fabricate placeholder.
    assert protocol.steps[0].kind == "fabricate"


async def test_templated_planner_uses_only_present_device_types() -> None:
    planner = TemplatedPlanner()
    devices = [
        LabDevice(
            id=uuid.uuid4(),
            laboratory_id=uuid.uuid4(),
            name="Cent #1",
            device_type=DeviceType.CENTRIFUGE,
            mean_seconds_per_cm3=12.0,
            simulated=True,
        )
    ]
    protocol = await planner.propose(
        user_content="spin these samples", available_devices=devices
    )
    # Centrifuge step present, no thermocycler/plate_reader since they're missing.
    types_used = {
        s.device_type for s in protocol.steps if s.kind == "device_job"
    }
    assert DeviceType.CENTRIFUGE in types_used
    assert DeviceType.THERMOCYCLER not in types_used
    assert DeviceType.PLATE_READER not in types_used


async def test_propose_protocol_safe_uses_templated_when_planner_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken planner must NOT bubble — propose_protocol_safe always
    returns a protocol, with `fallback_reason` set so the agent can mention
    why."""

    class FailingPlanner:
        async def propose(self, **_: object):
            raise RuntimeError("simulated openai outage")

    monkeypatch.setattr(
        "app.services.experiment_planner.get_experiment_planner", lambda: FailingPlanner()
    )

    protocol, reason = await propose_protocol_safe(
        user_content="test", available_devices=[]
    )
    assert protocol is not None and len(protocol.steps) >= 1
    assert reason is not None and "RuntimeError" in reason


async def test_openai_planner_rejects_empty_api_key() -> None:
    with pytest.raises(ValueError, match="LABSMITH_OPENAI_API_KEY"):
        OpenAIPlanner(api_key="", model="gpt-4o-mini")


# ---------------------------------------------------------------------------
# scheduler device_type filter
# ---------------------------------------------------------------------------


async def test_scheduler_with_type_filter_ignores_other_types() -> None:
    """When the experiment runner asks for a centrifuge, only centrifuges
    should be considered — even if there's an idle printer with shorter
    queue."""
    await _require_database()
    user = await _create_user("scheduler-filter")

    async with _client_as(user) as client:
        lab_id_str = (
            await client.post("/api/v1/labs", json={"name": "Filter Lab"})
        ).json()["id"]
        # One printer, one centrifuge — both idle.
        printer = (
            await client.post(
                f"/api/v1/labs/{lab_id_str}/devices",
                json={"name": "MK4", "device_type": "printer_3d"},
            )
        ).json()
        centrifuge = (
            await client.post(
                f"/api/v1/labs/{lab_id_str}/devices",
                json={"name": "Cent A", "device_type": "centrifuge"},
            )
        ).json()

    # Direct service call — no HTTP route for non-print device job dispatch.
    async with async_session_factory() as db:
        from app.models.user import User as UserModel
        from sqlalchemy import select

        loaded_user = (await db.execute(select(UserModel).where(UserModel.id == user.id))).scalar_one()

        job = await device_service.submit_device_job(
            db,
            lab_id=uuid.UUID(lab_id_str),
            user=loaded_user,
            device_type=DeviceType.CENTRIFUGE,
            payload={"rpm": 1000, "seconds": 60},
            label="test spin",
        )

    assert str(job.device_id) == centrifuge["id"]
    assert str(job.device_id) != printer["id"]


async def test_scheduler_409s_when_no_device_of_requested_type() -> None:
    await _require_database()
    user = await _create_user("scheduler-empty")

    async with _client_as(user) as client:
        lab_id_str = (
            await client.post("/api/v1/labs", json={"name": "No Cent Lab"})
        ).json()["id"]
        # Add a printer but NOT a centrifuge.
        await client.post(
            f"/api/v1/labs/{lab_id_str}/devices",
            json={"name": "MK4", "device_type": "printer_3d"},
        )

    async with async_session_factory() as db:
        from app.models.user import User as UserModel
        from fastapi import HTTPException
        from sqlalchemy import select

        loaded_user = (await db.execute(select(UserModel).where(UserModel.id == user.id))).scalar_one()

        with pytest.raises(HTTPException) as excinfo:
            await device_service.submit_device_job(
                db,
                lab_id=uuid.UUID(lab_id_str),
                user=loaded_user,
                device_type=DeviceType.CENTRIFUGE,
                payload={"rpm": 1000, "seconds": 60},
                label="test spin",
            )
        assert excinfo.value.status_code == 409


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _client_as(user: User) -> AsyncGenerator[AsyncClient, None]:
    async def override_current_user() -> User:
        return user

    app.dependency_overrides[get_current_user] = override_current_user
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def _create_user(label: str) -> User:
    unique_id = uuid.uuid4().hex
    async with async_session_factory() as db:
        user = User(
            clerk_user_id=f"test-{label}-{unique_id}",
            email=f"exp-{label}-{unique_id}@example.com",
            display_name=f"{label.title()} User",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def _require_database() -> None:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"Database is not available for experiment tests: {exc}")
