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
    assert len(data) == 2
    part_types = {t["part_type"] for t in data}
    assert part_types == {"tube_rack", "gel_comb"}


def test_legacy_design_endpoint() -> None:
    response = client.post(
        "/design",
        json={"prompt": "Create a 4 x 6 tube rack with 11 mm diameter, 15 mm spacing, and 50 mm height"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["part_request"]["part_type"] == "tube_rack"


def test_auth_me_requires_token() -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
