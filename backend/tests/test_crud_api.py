from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from app.auth.clerk import get_current_user
from app.database import async_session_factory, engine
from app.main import app
from app.models.user import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def dispose_engine_after_test() -> AsyncGenerator[None, None]:
    yield
    await engine.dispose()


async def test_lab_project_session_crud_flow() -> None:
    await _require_database()
    owner = await _create_user("owner")

    async with _client_as(owner) as client:
        lab_response = await client.post(
            "/api/v1/labs",
            json={"name": "Genome Tools", "description": "Custom fixtures"},
        )
        assert lab_response.status_code == 201
        lab = lab_response.json()
        assert lab["slug"].startswith("genome-tools")
        assert lab["role"] == "owner"

        lab_id = lab["id"]
        list_labs_response = await client.get("/api/v1/labs")
        assert list_labs_response.status_code == 200
        assert lab_id in {item["id"] for item in list_labs_response.json()}

        update_lab_response = await client.patch(
            f"/api/v1/labs/{lab_id}",
            json={"description": "Shared fixture work"},
        )
        assert update_lab_response.status_code == 200
        assert update_lab_response.json()["description"] == "Shared fixture work"

        project_response = await client.post(
            f"/api/v1/labs/{lab_id}/projects",
            json={"name": "Ice bucket rack", "description": "Rack sizing work"},
        )
        assert project_response.status_code == 201
        project = project_response.json()
        project_id = project["id"]

        session_response = await client.post(
            f"/api/v1/projects/{project_id}/sessions",
            json={
                "title": "Initial rack design",
                "part_type": "tube_rack",
                "current_spec": {"rows": 4, "cols": 6},
            },
        )
        assert session_response.status_code == 201
        design_session = session_response.json()
        session_id = design_session["id"]
        assert design_session["status"] == "active"

        update_session_response = await client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"status": "completed", "current_spec": {"rows": 5, "cols": 6}},
        )
        assert update_session_response.status_code == 200
        assert update_session_response.json()["status"] == "completed"
        assert update_session_response.json()["current_spec"] == {"rows": 5, "cols": 6}

        list_sessions_response = await client.get(f"/api/v1/projects/{project_id}/sessions")
        assert list_sessions_response.status_code == 200
        assert session_id in {item["id"] for item in list_sessions_response.json()}

        assert (await client.delete(f"/api/v1/sessions/{session_id}")).status_code == 204
        assert (await client.delete(f"/api/v1/projects/{project_id}")).status_code == 204
        assert (await client.delete(f"/api/v1/labs/{lab_id}")).status_code == 204


async def test_viewer_can_read_but_cannot_create_projects() -> None:
    await _require_database()
    owner = await _create_user("owner")
    viewer = await _create_user("viewer")

    async with _client_as(owner) as owner_client:
        lab_response = await owner_client.post("/api/v1/labs", json={"name": "Viewer Lab"})
        assert lab_response.status_code == 201
        lab_id = lab_response.json()["id"]

        add_member_response = await owner_client.post(
            f"/api/v1/labs/{lab_id}/members",
            json={"email": viewer.email, "role": "viewer"},
        )
        assert add_member_response.status_code == 201

    async with _client_as(viewer) as viewer_client:
        assert (await viewer_client.get(f"/api/v1/labs/{lab_id}")).status_code == 200

        create_project_response = await viewer_client.post(
            f"/api/v1/labs/{lab_id}/projects",
            json={"name": "Unauthorized project"},
        )
        assert create_project_response.status_code == 403

        update_lab_response = await viewer_client.patch(
            f"/api/v1/labs/{lab_id}",
            json={"name": "Renamed by viewer"},
        )
        assert update_lab_response.status_code == 403

    async with _client_as(owner) as owner_client:
        assert (await owner_client.delete(f"/api/v1/labs/{lab_id}")).status_code == 204


async def test_non_member_cannot_read_known_workspace_ids() -> None:
    await _require_database()
    owner = await _create_user("owner")
    outsider = await _create_user("outsider")

    async with _client_as(owner) as owner_client:
        lab_response = await owner_client.post("/api/v1/labs", json={"name": "IDOR Lab"})
        assert lab_response.status_code == 201
        lab_id = lab_response.json()["id"]

        project_response = await owner_client.post(
            f"/api/v1/labs/{lab_id}/projects",
            json={"name": "Private project"},
        )
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        session_response = await owner_client.post(
            f"/api/v1/projects/{project_id}/sessions",
            json={"title": "Private session"},
        )
        assert session_response.status_code == 201
        session_id = session_response.json()["id"]

    async with _client_as(outsider) as outsider_client:
        assert (await outsider_client.get(f"/api/v1/labs/{lab_id}")).status_code == 404
        assert (
            await outsider_client.get(f"/api/v1/labs/{lab_id}/projects")
        ).status_code == 404
        assert (
            await outsider_client.get(f"/api/v1/projects/{project_id}")
        ).status_code == 404
        assert (
            await outsider_client.get(f"/api/v1/projects/{project_id}/sessions")
        ).status_code == 404
        assert (
            await outsider_client.get(f"/api/v1/sessions/{session_id}")
        ).status_code == 404
        assert (
            await outsider_client.get(f"/api/v1/sessions/{session_id}/messages")
        ).status_code == 404

    async with _client_as(owner) as owner_client:
        assert (await owner_client.delete(f"/api/v1/labs/{lab_id}")).status_code == 204


async def test_member_management_preserves_at_least_one_owner() -> None:
    await _require_database()
    owner = await _create_user("owner")

    async with _client_as(owner) as client:
        lab_response = await client.post("/api/v1/labs", json={"name": "Owner Lab"})
        assert lab_response.status_code == 201
        lab_id = lab_response.json()["id"]

        members_response = await client.get(f"/api/v1/labs/{lab_id}/members")
        assert members_response.status_code == 200
        owner_membership_id = members_response.json()[0]["id"]

        demote_response = await client.patch(
            f"/api/v1/labs/{lab_id}/members/{owner_membership_id}",
            json={"role": "member"},
        )
        assert demote_response.status_code == 400

        delete_member_response = await client.delete(
            f"/api/v1/labs/{lab_id}/members/{owner_membership_id}"
        )
        assert delete_member_response.status_code == 400

        assert (await client.delete(f"/api/v1/labs/{lab_id}")).status_code == 204


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
            email=f"crud-{label}-{unique_id}@example.com",
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
        pytest.skip(f"Database is not available for CRUD API tests: {exc}")
