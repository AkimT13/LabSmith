"""Tests for the app.main entry point."""

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_scaffold_routes_are_not_exposed() -> None:
    assert client.get("/templates").status_code == 404
    assert client.post("/parse", json={"prompt": "Create a tube rack"}).status_code == 404
    assert client.post("/design", json={"prompt": "Create a tube rack"}).status_code == 404


def test_auth_me_requires_token() -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_openapi_docs_include_v1_tag_metadata() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    tags = {tag["name"]: tag["description"] for tag in schema["tags"]}
    assert "Server-Sent Events chat turns" in tags["chat"]
    assert "Authenticated artifact listing" in tags["artifacts"]
    assert "Lab-scoped onboarding documents" in tags["documents"]
    assert "legacy" not in tags
    assert "/api/v1/sessions/{session_id}/chat" in schema["paths"]
    assert "/api/v1/artifacts/{artifact_id}/download" in schema["paths"]
    assert "/api/v1/labs/{lab_id}/documents" in schema["paths"]
    assert "/templates" not in schema["paths"]
    assert "/parse" not in schema["paths"]
    assert "/design" not in schema["paths"]
