"""Tests for the M3 chat endpoint and SSE event ordering."""
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


async def test_chat_emits_full_event_sequence_for_valid_prompt() -> None:
    await _require_database()
    user = await _create_user("chatter")

    async with _client_as(user) as client:
        session_id = await _create_session(client, lab_name="Chat Lab")

        events = await _post_chat(
            client,
            session_id,
            "Create a tissue microarray mold with 96 wells, 1 mm diameter, 2 mm spacing",
        )

        event_types = [e["event"] for e in events]
        # Expect at least one text_delta, then spec_parsed, generation_started,
        # generation_complete, message_complete (in that order).
        assert "text_delta" in event_types
        assert event_types.index("spec_parsed") > event_types.index("text_delta")
        assert event_types.index("generation_started") > event_types.index("spec_parsed")
        assert (
            event_types.index("generation_complete")
            > event_types.index("generation_started")
        )
        assert event_types[-1] == "message_complete"

        # spec_parsed payload includes a part_request.
        spec_event = next(e for e in events if e["event"] == "spec_parsed")
        assert spec_event["data"]["part_request"]["part_type"] == "tma_mold"

        # generation_complete payload includes an artifact_id.
        gen_event = next(e for e in events if e["event"] == "generation_complete")
        artifact_id = gen_event["data"]["artifact_id"]
        assert artifact_id

        # Both user and assistant messages should be persisted now.
        messages_response = await client.get(f"/api/v1/sessions/{session_id}/messages")
        assert messages_response.status_code == 200
        messages = messages_response.json()
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

        # The artifact should appear in the session's artifact list.
        artifacts_response = await client.get(f"/api/v1/sessions/{session_id}/artifacts")
        assert artifacts_response.status_code == 200
        artifacts = artifacts_response.json()
        assert len(artifacts) == 1
        assert artifacts[0]["id"] == artifact_id
        assert artifacts[0]["version"] == 1
        # M4: mock generation now writes a placeholder STL via the storage backend.
        # file_path + file_size_bytes should be populated and download/preview URLs surfaced.
        assert artifacts[0]["file_path"] is not None
        assert artifacts[0]["file_size_bytes"] == len(get_placeholder_stl_bytes())
        assert artifacts[0]["download_url"] == f"/api/v1/artifacts/{artifact_id}/download"
        assert artifacts[0]["preview_url"] == f"/api/v1/artifacts/{artifact_id}/preview"


async def test_chat_increments_artifact_version_on_re_run() -> None:
    await _require_database()
    user = await _create_user("repeat")

    async with _client_as(user) as client:
        session_id = await _create_session(client, lab_name="Repeat Lab")
        prompt = "tube rack 4x6 with 11mm diameter and 15mm spacing"

        await _post_chat(client, session_id, prompt)
        await _post_chat(client, session_id, prompt)

        artifacts = (await client.get(f"/api/v1/sessions/{session_id}/artifacts")).json()
        assert len(artifacts) == 2
        # newest first → version 2 then version 1
        assert {a["version"] for a in artifacts} == {1, 2}


async def test_chat_returns_message_complete_only_for_unparseable_prompt() -> None:
    await _require_database()
    user = await _create_user("unparse")

    async with _client_as(user) as client:
        session_id = await _create_session(client, lab_name="Unparse Lab")

        events = await _post_chat(client, session_id, "make me a camera bracket")
        event_types = [e["event"] for e in events]

        assert "spec_parsed" not in event_types
        assert "generation_started" not in event_types
        assert event_types[-1] == "message_complete"


async def test_chat_rejects_archived_session() -> None:
    await _require_database()
    user = await _create_user("archived")

    async with _client_as(user) as client:
        session_id = await _create_session(client, lab_name="Archived Lab")

        archive_response = await client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"status": "archived"},
        )
        assert archive_response.status_code == 200

        chat_response = await client.post(
            f"/api/v1/sessions/{session_id}/chat",
            json={"content": "anything"},
        )
        assert chat_response.status_code == 409


async def test_chat_rejects_empty_content() -> None:
    await _require_database()
    user = await _create_user("empty")

    async with _client_as(user) as client:
        session_id = await _create_session(client, lab_name="Empty Lab")

        chat_response = await client.post(
            f"/api/v1/sessions/{session_id}/chat",
            json={"content": ""},
        )
        assert chat_response.status_code == 422


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _post_chat(
    client: AsyncClient,
    session_id: str,
    content: str,
) -> list[dict]:
    """POST to the chat endpoint and parse the SSE stream into a list of event dicts."""
    events: list[dict] = []
    async with client.stream(
        "POST",
        f"/api/v1/sessions/{session_id}/chat",
        json={"content": content},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        buffer = ""
        async for chunk in response.aiter_text():
            buffer += chunk
            while "\n\n" in buffer:
                block, buffer = buffer.split("\n\n", 1)
                event = _parse_sse_block(block)
                if event:
                    events.append(event)
    return events


def _parse_sse_block(block: str) -> dict | None:
    event_type: str | None = None
    data_line: str | None = None
    for line in block.splitlines():
        if line.startswith("event: "):
            event_type = line[len("event: ") :]
        elif line.startswith("data: "):
            data_line = line[len("data: ") :]
    if event_type is None or data_line is None:
        return None
    return {"event": event_type, "data": json.loads(data_line)}


async def _create_session(client: AsyncClient, *, lab_name: str) -> str:
    lab_response = await client.post("/api/v1/labs", json={"name": lab_name})
    assert lab_response.status_code == 201
    lab_id = lab_response.json()["id"]

    project_response = await client.post(
        f"/api/v1/labs/{lab_id}/projects",
        json={"name": "Chat project"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    session_response = await client.post(
        f"/api/v1/projects/{project_id}/sessions",
        json={"title": "Chat session"},
    )
    assert session_response.status_code == 201
    return session_response.json()["id"]


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
            email=f"chat-{label}-{unique_id}@example.com",
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
        pytest.skip(f"Database is not available for chat API tests: {exc}")
