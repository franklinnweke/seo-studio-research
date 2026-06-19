from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "seo-studio"}


def test_cors_allows_configured_frontend_origins() -> None:
    client = TestClient(app)

    for origin in ("http://localhost:11501", "https://seo-studio2.axivaq.com"):
        response = client.get("/health", headers={"Origin": origin})

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
