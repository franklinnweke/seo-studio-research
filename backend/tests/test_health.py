from fastapi.testclient import TestClient

from app.config import get_cors_origins, get_settings
from app.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "seo-studio"}


def test_cors_allows_configured_frontend_origins() -> None:
    client = TestClient(app)
    settings = get_settings()
    origins = get_cors_origins(settings)

    for origin in origins[:2]:
        response = client.get("/health", headers={"Origin": origin})

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
