from fastapi.testclient import TestClient

from labsmith.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_design_endpoint_returns_plan_for_supported_prompt() -> None:
    response = client.post(
        "/design",
        json={
            "prompt": "Create a tissue microarray mold with 96 wells, 1 mm diameter, 2 mm spacing"
        },
    )

    body = response.json()

    assert response.status_code == 200
    assert body["part_request"]["part_type"] == "tma_mold"
    assert body["validation"] == []
    assert body["estimated_dimensions"]["width_mm"] > 20
    assert {export["format"] for export in body["exports"]} == {"stl", "step"}


def test_design_endpoint_rejects_unknown_part() -> None:
    response = client.post("/design", json={"prompt": "Make a camera bracket"})

    assert response.status_code == 422
