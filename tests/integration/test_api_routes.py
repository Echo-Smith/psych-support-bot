from fastapi.testclient import TestClient

from psych_support_bot.app import app


client = TestClient(app)


def test_health_route() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_assessment_route() -> None:
    response = client.post(
        "/v1/assessments",
        json={"user_id": "u-api", "assessment_type": "gad7", "score": 12},
    )
    assert response.status_code == 200
    assert response.json()["severity_band"] == "moderate"


def test_plans_route() -> None:
    response = client.get("/v1/plans")
    assert response.status_code == 200
    assert "anxiety_14d" in response.json()
