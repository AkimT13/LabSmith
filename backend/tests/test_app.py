"""Tests for the new app.main entry point (legacy routes preserved)."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_legacy_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_legacy_templates_endpoint() -> None:
    response = client.get("/templates")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    part_types = {t["part_type"] for t in data}
    assert part_types == {"tma_mold", "tube_rack", "gel_comb"}


def test_legacy_design_endpoint() -> None:
    response = client.post(
        "/design",
        json={"prompt": "Create a tissue microarray mold with 96 wells, 1 mm diameter, 2 mm spacing"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["part_request"]["part_type"] == "tma_mold"


def test_auth_me_requires_token() -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
