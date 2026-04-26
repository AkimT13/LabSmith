"""Tests for the M4 artifact download/preview endpoints."""
from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from app.auth.clerk import get_current_user
from app.database import async_session_factory, engine
from app.main import app
from app.models.user import User
from app.services.placeholder_stl import get_placeholder_stl_bytes
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def dispose_engine_after_test() -> AsyncGenerator[None, None]:
    yield
    await engine.dispose()


async def test_download_returns_placeholder_stl_with_correct_headers() -> None:
    await _require_database()
    user = await _create_user("downloader")

    async with _client_as(user) as client:
        artifact = await _generate_artifact(client, prompt=_TMA_PROMPT, lab_name="DL Lab")

        response = await client.get(f"/api/v1/artifacts/{artifact['id']}/download")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("model/stl")
        assert "attachment" in response.headers["content-disposition"].lower()
        # filename should incorporate the session title slug + version
        assert "v1" in response.headers["content-disposition"]
        assert response.content == get_placeholder_stl_bytes()


async def test_preview_returns_inline_bytes_with_etag() -> None:
    await _require_database()
    user = await _create_user("previewer")

    async with _client_as(user) as client:
        artifact = await _generate_artifact(client, prompt=_TMA_PROMPT, lab_name="PV Lab")

        response = await client.get(f"/api/v1/artifacts/{artifact['id']}/preview")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("model/stl")
        # No Content-Disposition for inline preview
        assert "content-disposition" not in {k.lower() for k in response.headers.keys()}
        # ETag is set so the browser can revalidate cheaply
        etag = response.headers["etag"]
        assert artifact["id"] in etag
        assert "v1" in etag
        assert response.content == get_placeholder_stl_bytes()


async def test_preview_returns_304_on_matching_if_none_match() -> None:
    await _require_database()
    user = await _create_user("etag")

    async with _client_as(user) as client:
        artifact = await _generate_artifact(client, prompt=_TMA_PROMPT, lab_name="ETag Lab")

        first = await client.get(f"/api/v1/artifacts/{artifact['id']}/preview")
        etag = first.headers["etag"]

        second = await client.get(
            f"/api/v1/artifacts/{artifact['id']}/preview",
            headers={"If-None-Match": etag},
        )

        assert second.status_code == 304
        assert second.content == b""
        assert second.headers["etag"] == etag


async def test_artifact_response_includes_download_and_preview_urls() -> None:
    await _require_database()
    user = await _create_user("urls")

    async with _client_as(user) as client:
        artifact = await _generate_artifact(client, prompt=_TMA_PROMPT, lab_name="URL Lab")

        assert artifact["download_url"] == f"/api/v1/artifacts/{artifact['id']}/download"
        assert artifact["preview_url"] == f"/api/v1/artifacts/{artifact['id']}/preview"
        assert artifact["file_path"] is not None
        assert artifact["file_size_bytes"] == len(get_placeholder_stl_bytes())


async def test_download_returns_404_for_unknown_artifact() -> None:
    await _require_database()
    user = await _create_user("missing")

    async with _client_as(user) as client:
        response = await client.get(f"/api/v1/artifacts/{uuid.uuid4()}/download")
        assert response.status_code == 404


async def test_download_returns_403_for_non_member() -> None:
    await _require_database()
    owner = await _create_user("owner")
    outsider = await _create_user("outsider")

    async with _client_as(owner) as owner_client:
        artifact = await _generate_artifact(
            owner_client, prompt=_TMA_PROMPT, lab_name="Private Lab"
        )

    async with _client_as(outsider) as outsider_client:
        # Outsider isn't a member of the lab. The session lookup raises 404
        # rather than 403 to avoid leaking the existence of artifacts they
        # don't have access to — we verify that surface.
        response = await outsider_client.get(
            f"/api/v1/artifacts/{artifact['id']}/download"
        )
        assert response.status_code in (403, 404)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


_TMA_PROMPT = "Create a tissue microarray mold with 96 wells, 1 mm diameter, 2 mm spacing"


async def _generate_artifact(
    client: AsyncClient,
    *,
    prompt: str,
    lab_name: str,
) -> dict:
    """Spin up a session, fire one chat turn, and return the resulting artifact dict."""
    lab_response = await client.post("/api/v1/labs", json={"name": lab_name})
    assert lab_response.status_code == 201
    lab_id = lab_response.json()["id"]

    project_response = await client.post(
        f"/api/v1/labs/{lab_id}/projects",
        json={"name": "Artifact project"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    session_response = await client.post(
        f"/api/v1/projects/{project_id}/sessions",
        json={"title": "Artifact session"},
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    # Run a chat turn to produce the artifact.
    async with client.stream(
        "POST",
        f"/api/v1/sessions/{session_id}/chat",
        json={"content": prompt},
    ) as response:
        assert response.status_code == 200
        # Drain the stream so persistence completes before we list artifacts.
        async for _ in response.aiter_text():
            pass

    artifacts_response = await client.get(f"/api/v1/sessions/{session_id}/artifacts")
    assert artifacts_response.status_code == 200
    artifacts = artifacts_response.json()
    assert len(artifacts) == 1
    return artifacts[0]


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
            email=f"art-{label}-{unique_id}@example.com",
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
        pytest.skip(f"Database is not available for artifact endpoint tests: {exc}")
