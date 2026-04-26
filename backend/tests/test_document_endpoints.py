from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from app.auth.clerk import get_current_user
from app.config import settings
from app.database import async_session_factory, engine
from app.main import app
from app.models.user import User
from app.services.storage import reset_storage_for_testing
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def isolated_storage(tmp_path: Path) -> AsyncGenerator[None, None]:
    original_storage_dir = settings.storage_dir
    original_max_bytes = settings.lab_document_max_bytes
    settings.storage_dir = str(tmp_path)
    reset_storage_for_testing()
    yield
    reset_storage_for_testing()
    settings.storage_dir = original_storage_dir
    settings.lab_document_max_bytes = original_max_bytes
    await engine.dispose()


async def test_member_can_upload_list_and_download_lab_document() -> None:
    await _require_database()
    user = await _create_user("docs-owner")

    async with _client_as(user) as client:
        lab_id = await _create_lab(client, name="Docs Lab")

        create_response = await client.post(
            f"/api/v1/labs/{lab_id}/documents",
            json={
                "title": "Centrifuge SOP",
                "source_filename": "centrifuge-sop.txt",
                "content_type": "text/plain",
                "content": "Balance tubes before starting the run.",
            },
        )
        assert create_response.status_code == 201
        document = create_response.json()
        assert document["title"] == "Centrifuge SOP"
        assert document["file_size_bytes"] == len("Balance tubes before starting the run.")
        assert document["download_url"] == f"/api/v1/documents/{document['id']}/download"
        assert "file_path" not in document

        list_response = await client.get(f"/api/v1/labs/{lab_id}/documents")
        assert list_response.status_code == 200
        assert [item["id"] for item in list_response.json()] == [document["id"]]

        download_response = await client.get(document["download_url"])
        assert download_response.status_code == 200
        assert download_response.text == "Balance tubes before starting the run."
        assert download_response.headers["content-type"].startswith("text/plain")
        assert "centrifuge-sop.txt" in download_response.headers["content-disposition"]


async def test_viewer_can_list_and_download_but_cannot_upload_documents() -> None:
    await _require_database()
    owner = await _create_user("docs-owner")
    viewer = await _create_user("docs-viewer")

    async with _client_as(owner) as owner_client:
        lab_id = await _create_lab(owner_client, name="Viewer Docs Lab")
        add_member_response = await owner_client.post(
            f"/api/v1/labs/{lab_id}/members",
            json={"email": viewer.email, "role": "viewer"},
        )
        assert add_member_response.status_code == 201
        document = await _create_document(owner_client, lab_id=lab_id)

    async with _client_as(viewer) as viewer_client:
        list_response = await viewer_client.get(f"/api/v1/labs/{lab_id}/documents")
        assert list_response.status_code == 200
        assert [item["id"] for item in list_response.json()] == [document["id"]]

        download_response = await viewer_client.get(document["download_url"])
        assert download_response.status_code == 200

        upload_response = await viewer_client.post(
            f"/api/v1/labs/{lab_id}/documents",
            json={"title": "Nope", "content": "viewer upload"},
        )
        assert upload_response.status_code == 403


async def test_non_member_cannot_read_known_document_id() -> None:
    await _require_database()
    owner = await _create_user("docs-owner")
    outsider = await _create_user("docs-outsider")

    async with _client_as(owner) as owner_client:
        lab_id = await _create_lab(owner_client, name="Private Docs Lab")
        document = await _create_document(owner_client, lab_id=lab_id)

    async with _client_as(outsider) as outsider_client:
        list_response = await outsider_client.get(f"/api/v1/labs/{lab_id}/documents")
        assert list_response.status_code == 404

        download_response = await outsider_client.get(document["download_url"])
        assert download_response.status_code == 404


async def test_document_upload_rejects_oversized_content() -> None:
    await _require_database()
    settings.lab_document_max_bytes = 4
    user = await _create_user("docs-limit")

    async with _client_as(user) as client:
        lab_id = await _create_lab(client, name="Limit Docs Lab")
        response = await client.post(
            f"/api/v1/labs/{lab_id}/documents",
            json={"title": "Too large", "content": "12345"},
        )
        assert response.status_code == 413


async def _create_document(client: AsyncClient, *, lab_id: str) -> dict:
    response = await client.post(
        f"/api/v1/labs/{lab_id}/documents",
        json={"title": "Lab Map", "source_filename": "map.txt", "content": "Bench A"},
    )
    assert response.status_code == 201
    return response.json()


async def _create_lab(client: AsyncClient, *, name: str) -> str:
    response = await client.post("/api/v1/labs", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


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
            email=f"doc-{label}-{unique_id}@example.com",
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
        pytest.skip(f"Database is not available for document endpoint tests: {exc}")
