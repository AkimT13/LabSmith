"""LabSmith Device Protocol — endpoint and scheduler tests (M10).

The simulation derives progress from `started_at + duration` on read, so we
manipulate `started_at` directly to fast-forward the clock instead of waiting
in real time.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest
from app.auth.clerk import get_current_user
from app.database import async_session_factory, engine
from app.main import app
from app.models.artifact import Artifact
from app.models.lab_device import DeviceJob, JobStatus, LabDevice
from app.models.user import User
from app.services import devices as device_service
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text


_PROMPT = "Create a 4 x 6 tube rack with 11 mm diameter, 15 mm spacing, and 50 mm height"


# ---------------------------------------------------------------------------
# sim duration formula (sync, no DB)
# ---------------------------------------------------------------------------


def test_estimate_volume_falls_back_to_default_for_empty_spec() -> None:
    assert device_service.estimate_volume_cm3(None) == device_service._DEFAULT_VOLUME_CM3
    assert device_service.estimate_volume_cm3({}) == device_service._DEFAULT_VOLUME_CM3


def test_estimate_volume_uses_dimensions_when_present() -> None:
    spec = {"dimensions": {"x_mm": 100, "y_mm": 50, "z_mm": 20}}
    # 100 * 50 * 20 mm³ = 100,000 mm³ = 100 cm³
    assert device_service.estimate_volume_cm3(spec) == pytest.approx(100.0)


def test_compute_simulated_duration_clamps_to_min() -> None:
    # 0.5 cm³ × 1 sec = 0.5 sec → clamped to 30
    duration = device_service.compute_simulated_duration(
        spec_snapshot={"dimensions": {"x_mm": 5, "y_mm": 5, "z_mm": 20}},
        mean_seconds_per_cm3=1.0,
    )
    assert duration == pytest.approx(device_service._MIN_DURATION_SECONDS)


def test_compute_simulated_duration_clamps_to_max() -> None:
    duration = device_service.compute_simulated_duration(
        spec_snapshot={"dimensions": {"x_mm": 1000, "y_mm": 1000, "z_mm": 1000}},
        mean_seconds_per_cm3=999.0,
    )
    assert duration == pytest.approx(device_service._MAX_DURATION_SECONDS)


# ---------------------------------------------------------------------------
# print intent parser
# ---------------------------------------------------------------------------


from app.services.agents.part_design import _parse_print_intent  # noqa: E402


def test_parse_print_intent_returns_none_for_design_prompts() -> None:
    assert _parse_print_intent("create a 6x8 tube rack with 11mm holes") is None
    assert _parse_print_intent("make the wells deeper") is None
    assert _parse_print_intent("") is None
    # Looks vaguely related but isn't a print verb
    assert _parse_print_intent("describe the print process") is None


def test_parse_print_intent_simple_phrases() -> None:
    intent = _parse_print_intent("print this")
    assert intent is not None and intent.copies == 1 and intent.version is None

    intent = _parse_print_intent("send to printer")
    assert intent is not None and intent.copies == 1 and intent.version is None


def test_parse_print_intent_with_digit_count() -> None:
    intent = _parse_print_intent("print 5")
    assert intent is not None and intent.copies == 5 and intent.version is None

    intent = _parse_print_intent("print 3 of these")
    assert intent is not None and intent.copies == 3 and intent.version is None


def test_parse_print_intent_with_word_count() -> None:
    intent = _parse_print_intent("print three of these")
    assert intent is not None and intent.copies == 3 and intent.version is None

    intent = _parse_print_intent("queue this two times")
    assert intent is not None and intent.copies == 2


def test_parse_print_intent_with_version_only() -> None:
    intent = _parse_print_intent("print v2")
    assert intent is not None and intent.copies == 1 and intent.version == 2


def test_parse_print_intent_with_count_and_version() -> None:
    intent = _parse_print_intent("print 5 of v1")
    assert intent is not None and intent.copies == 5 and intent.version == 1

    intent = _parse_print_intent("send 3 copies of version 2 to the printer")
    assert intent is not None and intent.copies == 3 and intent.version == 2


def test_parse_print_intent_clamps_copies_to_ten() -> None:
    intent = _parse_print_intent("print 99 of these")
    assert intent is not None and intent.copies == 10


# Async tests below
pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# end-to-end via HTTP
# ---------------------------------------------------------------------------


async def test_member_can_create_device_and_dispatch_print() -> None:
    await _require_database()
    user = await _create_user("printer-owner")

    async with _client_as(user) as client:
        lab_id = await _create_lab(client, name="Print Lab")

        device_response = await client.post(
            f"/api/v1/labs/{lab_id}/devices",
            json={"name": "Bench MK4", "mean_seconds_per_cm3": 6},
        )
        assert device_response.status_code == 201
        device = device_response.json()
        assert device["status"] == "idle"
        assert device["queue_depth"] == 0

        artifact = await _generate_artifact(client, lab_id=lab_id)

        print_response = await client.post(
            f"/api/v1/labs/{lab_id}/devices/print",
            json={"artifact_id": artifact["id"]},
        )
        assert print_response.status_code == 201
        jobs = print_response.json()["jobs"]
        assert len(jobs) == 1
        assert jobs[0]["status"] == "running"
        assert jobs[0]["queue_position"] == 0
        assert jobs[0]["device_id"] == device["id"]


async def test_scheduler_balances_across_two_printers() -> None:
    await _require_database()
    user = await _create_user("balancer")

    async with _client_as(user) as client:
        lab_id = await _create_lab(client, name="Balance Lab")

        first = (await client.post(
            f"/api/v1/labs/{lab_id}/devices",
            json={"name": "MK4 #1"},
        )).json()
        second = (await client.post(
            f"/api/v1/labs/{lab_id}/devices",
            json={"name": "MK4 #2"},
        )).json()

        artifact = await _generate_artifact(client, lab_id=lab_id)

        first_job = (await client.post(
            f"/api/v1/labs/{lab_id}/devices/print",
            json={"artifact_id": artifact["id"]},
        )).json()["jobs"][0]
        second_job = (await client.post(
            f"/api/v1/labs/{lab_id}/devices/print",
            json={"artifact_id": artifact["id"]},
        )).json()["jobs"][0]

        # The two jobs should land on DIFFERENT printers — each printer is
        # idle when the other is mid-run, so shortest-queue picks the empty
        # one second.
        assert {first_job["device_id"], second_job["device_id"]} == {
            first["id"],
            second["id"],
        }


async def test_third_job_queues_when_both_printers_busy() -> None:
    await _require_database()
    user = await _create_user("queue-builder")

    async with _client_as(user) as client:
        lab_id = await _create_lab(client, name="Queue Lab")
        await client.post(f"/api/v1/labs/{lab_id}/devices", json={"name": "MK4 #1"})
        await client.post(f"/api/v1/labs/{lab_id}/devices", json={"name": "MK4 #2"})

        artifact = await _generate_artifact(client, lab_id=lab_id)

        for _ in range(2):
            await client.post(
                f"/api/v1/labs/{lab_id}/devices/print",
                json={"artifact_id": artifact["id"]},
            )

        third = (await client.post(
            f"/api/v1/labs/{lab_id}/devices/print",
            json={"artifact_id": artifact["id"]},
        )).json()["jobs"][0]

        # Both printers are busy — third job has to wait.
        assert third["status"] == "queued"
        assert third["queue_position"] == 1


async def test_tick_promotes_completed_run_and_starts_next() -> None:
    """Manipulate `started_at` to fast-forward past the duration, then assert
    that `tick_lab_devices` promotes the running job to complete and starts
    the next queued one."""
    await _require_database()
    user = await _create_user("tick")

    async with _client_as(user) as client:
        lab_id = await _create_lab(client, name="Tick Lab")
        await client.post(f"/api/v1/labs/{lab_id}/devices", json={"name": "MK4"})
        artifact = await _generate_artifact(client, lab_id=lab_id)

        for _ in range(2):
            await client.post(
                f"/api/v1/labs/{lab_id}/devices/print",
                json={"artifact_id": artifact["id"]},
            )

    # Backdate the running job's started_at so the next read marks it complete.
    async with async_session_factory() as db:
        result = await db.execute(
            select(DeviceJob).where(DeviceJob.status == JobStatus.RUNNING)
        )
        running = result.scalar_one()
        running.started_at = datetime.now(timezone.utc) - timedelta(
            seconds=running.simulated_duration_seconds + 5
        )
        await db.commit()

        await device_service.tick_lab_devices(db, lab_id=uuid.UUID(lab_id))

        # The previously-running job is now complete; the second job is now running.
        result = await db.execute(
            select(DeviceJob).order_by(DeviceJob.created_at)
        )
        rows = list(result.scalars().all())
        assert rows[0].status == JobStatus.COMPLETE
        assert rows[1].status == JobStatus.RUNNING
        assert rows[1].queue_position == 0


async def test_dispatch_rejects_artifact_from_other_lab() -> None:
    await _require_database()
    user = await _create_user("cross-lab")

    async with _client_as(user) as client:
        lab_a = await _create_lab(client, name="Lab A")
        lab_b = await _create_lab(client, name="Lab B")
        await client.post(f"/api/v1/labs/{lab_b}/devices", json={"name": "MK4"})

        artifact_in_a = await _generate_artifact(client, lab_id=lab_a)

        # Try to print Lab A's artifact on Lab B's printer — should 404.
        response = await client.post(
            f"/api/v1/labs/{lab_b}/devices/print",
            json={"artifact_id": artifact_in_a["id"]},
        )
        assert response.status_code == 404


async def test_dispatch_409_when_no_devices() -> None:
    await _require_database()
    user = await _create_user("empty")

    async with _client_as(user) as client:
        lab_id = await _create_lab(client, name="Empty Lab")
        artifact = await _generate_artifact(client, lab_id=lab_id)

        response = await client.post(
            f"/api/v1/labs/{lab_id}/devices/print",
            json={"artifact_id": artifact["id"]},
        )
        assert response.status_code == 409


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _create_lab(client: AsyncClient, *, name: str) -> str:
    response = await client.post("/api/v1/labs", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


async def _generate_artifact(client: AsyncClient, *, lab_id: str) -> dict:
    project_response = await client.post(
        f"/api/v1/labs/{lab_id}/projects",
        json={"name": "Print project"},
    )
    project_id = project_response.json()["id"]
    session_response = await client.post(
        f"/api/v1/projects/{project_id}/sessions",
        json={"title": "Print session"},
    )
    session_id = session_response.json()["id"]

    async with client.stream(
        "POST",
        f"/api/v1/sessions/{session_id}/chat",
        json={"content": _PROMPT},
    ) as response:
        assert response.status_code == 200
        async for _ in response.aiter_text():
            pass

    artifacts_response = await client.get(f"/api/v1/sessions/{session_id}/artifacts")
    assert artifacts_response.status_code == 200
    return artifacts_response.json()[0]


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
            email=f"dev-{label}-{unique_id}@example.com",
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
        pytest.skip(f"Database is not available for device tests: {exc}")
