"""Tests for the M5 agent abstraction.

Verifies:
- The registry returns the right agent class for each session_type.
- The chat dispatcher routes to the correct agent based on session.session_type.
- Onboarding sessions emit the M9 v0 onboarding catalog and no design events.
- session_type defaults to "part_design" on creation.
- session_type is rejected by PATCH /sessions/{id} (it's set-once).
- The schema response includes session_type.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from app.auth.clerk import get_current_user
from app.database import async_session_factory, engine
from app.main import app
from app.models.design_session import SessionType
from app.models.user import User
from app.services.agents import get_agent_for_session
from app.services.agents.onboarding import OnboardingAgent
from app.services.agents.part_design import PartDesignAgent
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def dispose_engine_after_test() -> AsyncGenerator[None, None]:
    yield
    await engine.dispose()


# ---------------------------------------------------------------------------
# Registry — pure function, no DB needed
# ---------------------------------------------------------------------------


async def test_registry_returns_part_design_agent_for_part_design_type() -> None:
    fake = _fake_session_with_type(SessionType.PART_DESIGN)
    assert isinstance(get_agent_for_session(fake), PartDesignAgent)


async def test_registry_returns_onboarding_agent_for_onboarding_type() -> None:
    fake = _fake_session_with_type(SessionType.ONBOARDING)
    assert isinstance(get_agent_for_session(fake), OnboardingAgent)


# ---------------------------------------------------------------------------
# End-to-end through the chat router (uses DB)
# ---------------------------------------------------------------------------


async def test_creating_session_defaults_to_part_design_type() -> None:
    await _require_database()
    user = await _create_user("default_type")

    async with _client_as(user) as client:
        session = await _create_session(client, lab_name="Default Type Lab", session_type=None)
        assert session["session_type"] == "part_design"


async def test_creating_session_with_onboarding_type_persists() -> None:
    await _require_database()
    user = await _create_user("onboarding_create")

    async with _client_as(user) as client:
        session = await _create_session(
            client, lab_name="Onboarding Lab", session_type="onboarding"
        )
        assert session["session_type"] == "onboarding"

        # Re-fetch to confirm round-trip
        fetched = await client.get(f"/api/v1/sessions/{session['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["session_type"] == "onboarding"


async def test_session_type_is_immutable_on_patch() -> None:
    """The PATCH schema does not include session_type — extra fields should
    be ignored by Pydantic, leaving the type unchanged."""
    await _require_database()
    user = await _create_user("immutable")

    async with _client_as(user) as client:
        session = await _create_session(
            client, lab_name="Immutable Lab", session_type="part_design"
        )

        # Try to flip it via PATCH. The field isn't in the schema, so it's
        # silently dropped — and the stored type stays put.
        patch_response = await client.patch(
            f"/api/v1/sessions/{session['id']}",
            json={"session_type": "onboarding", "title": "Renamed"},
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["session_type"] == "part_design"
        assert patch_response.json()["title"] == "Renamed"


async def test_part_design_chat_emits_full_event_sequence() -> None:
    """Behavioral regression — part_design agent must keep emitting the M3
    event catalog (text_delta → spec_parsed → generation_started →
    generation_complete → message_complete)."""
    await _require_database()
    user = await _create_user("part_chat")

    async with _client_as(user) as client:
        session = await _create_session(
            client, lab_name="Part Chat Lab", session_type="part_design"
        )

        events = await _post_chat(
            client,
            session["id"],
            "Create a tube rack 4x6 with 11mm diameter, 15mm spacing, and 50mm height",
        )
        types = [e["event"] for e in events]

        assert "text_delta" in types
        assert "spec_parsed" in types
        assert "generation_started" in types
        assert "generation_complete" in types
        assert types[-1] == "message_complete"


async def test_onboarding_chat_emits_v0_catalog_without_design_events() -> None:
    """Onboarding agent emits M9 onboarding events, but no design-only events."""
    await _require_database()
    user = await _create_user("onboarding_chat")

    async with _client_as(user) as client:
        session = await _create_session(
            client, lab_name="Onboarding Chat Lab", session_type="onboarding"
        )

        events = await _post_chat(
            client,
            session["id"],
            "Where is the centrifuge and who owns it?",
        )
        types = [e["event"] for e in events]

        assert types[0] == "topic_suggested"
        topic_event = events[0]
        assert topic_event["data"]["topic"] == "equipment"
        assert "Equipment" in topic_event["data"]["label"]
        assert types.count("checklist_step") == 3
        assert "text_delta" in types
        assert types[-1] == "message_complete"
        complete = events[-1]["data"]["content"]
        assert "Onboarding Chat Lab / Agent project" in complete
        assert "I do not have uploaded lab documents connected yet" in complete
        assert "equipment and locations" in complete.lower()

        # The design-only events MUST NOT appear for onboarding sessions
        assert "spec_parsed" not in types
        assert "generation_started" not in types
        assert "generation_complete" not in types

        messages_response = await client.get(f"/api/v1/sessions/{session['id']}/messages")
        assert messages_response.status_code == 200
        messages = messages_response.json()
        assistant = messages[-1]
        assert assistant["role"] == "assistant"
        assert assistant["metadata"]["agent"] == "onboarding"
        assert assistant["metadata"]["version"] == "v0"
        assert assistant["metadata"]["topic"] == "equipment"
        assert assistant["metadata"]["doc_backed"] is False

        # Onboarding agent does not produce artifacts
        artifacts_response = await client.get(
            f"/api/v1/sessions/{session['id']}/artifacts"
        )
        assert artifacts_response.status_code == 200
        assert artifacts_response.json() == []


async def test_onboarding_mentions_available_lab_documents() -> None:
    await _require_database()
    user = await _create_user("onboarding_docs")

    async with _client_as(user) as client:
        session = await _create_session(
            client, lab_name="Onboarding Docs Lab", session_type="onboarding"
        )
        upload_response = await client.post(
            f"/api/v1/labs/{session['lab_id']}/documents",
            json={
                "title": "Microscope SOP",
                "source_filename": "microscope-sop.txt",
                "content": "Ask for training before use.",
            },
        )
        assert upload_response.status_code == 201

        events = await _post_chat(client, session["id"], "What protocol should I use?")
        complete = events[-1]["data"]["content"]

        assert "uploaded lab document records" in complete
        assert "Microscope SOP" in complete
        assert "semantic search and citations are not connected yet" in complete
        assert "generation_complete" not in [event["event"] for event in events]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_session_with_type(session_type: SessionType):
    """Minimal duck-typed session for registry tests — registry only reads
    `.session_type`, so we don't need a full DB row."""

    class _Fake:
        pass

    fake = _Fake()
    fake.session_type = session_type
    return fake


async def _post_chat(
    client: AsyncClient,
    session_id: str,
    content: str,
) -> list[dict]:
    events: list[dict] = []
    async with client.stream(
        "POST",
        f"/api/v1/sessions/{session_id}/chat",
        json={"content": content},
    ) as response:
        assert response.status_code == 200
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
            event_type = line[len("event: "):]
        elif line.startswith("data: "):
            data_line = line[len("data: "):]
    if event_type is None or data_line is None:
        return None
    return {"event": event_type, "data": json.loads(data_line)}


async def _create_session(
    client: AsyncClient,
    *,
    lab_name: str,
    session_type: str | None,
) -> dict:
    lab_response = await client.post("/api/v1/labs", json={"name": lab_name})
    assert lab_response.status_code == 201
    lab_id = lab_response.json()["id"]

    project_response = await client.post(
        f"/api/v1/labs/{lab_id}/projects",
        json={"name": "Agent project"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    body: dict = {"title": "Agent session"}
    if session_type is not None:
        body["session_type"] = session_type
    session_response = await client.post(
        f"/api/v1/projects/{project_id}/sessions", json=body
    )
    assert session_response.status_code == 201
    session = session_response.json()
    session["lab_id"] = lab_id
    session["project_id"] = project_id
    return session


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
            email=f"agent-{label}-{unique_id}@example.com",
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
        pytest.skip(f"Database is not available for agent tests: {exc}")
