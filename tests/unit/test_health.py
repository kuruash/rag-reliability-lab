from fastapi.testclient import TestClient

from rag_lab.main import app


def test_liveness_endpoint() -> None:
    response = TestClient(app).get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
