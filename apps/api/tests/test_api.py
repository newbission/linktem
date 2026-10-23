import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "")
    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body and "time" in body


def test_analyze_without_db_returns_503(client: TestClient) -> None:
    resp = client.post("/api/analyze", json={"url": "https://youtu.be/dQw4w9WgXcQ"})
    assert resp.status_code == 503
    assert "detail" in resp.json()


def test_analyze_validates_body(client: TestClient) -> None:
    assert client.post("/api/analyze", json={}).status_code == 422


def test_feedback_validates_type(client: TestClient) -> None:
    resp = client.post("/api/feedback", json={"item_id": "x", "feedback_type": "MAYBE"})
    assert resp.status_code == 422


def test_admin_cleanup_requires_token(client: TestClient) -> None:
    assert client.post("/api/admin/cleanup").status_code == 401


def test_rate_limit(client: TestClient) -> None:
    statuses = [
        client.post("/api/analyze", json={"url": "https://youtu.be/dQw4w9WgXcQ"}).status_code for _ in range(8)
    ]
    assert 429 in statuses
