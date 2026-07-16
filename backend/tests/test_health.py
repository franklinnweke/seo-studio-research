from fastapi.testclient import TestClient

from app.config import get_cors_origins, get_settings
from app.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "seo-studio"}
    assert response.headers["x-request-id"].startswith("req_")


def test_valid_request_id_is_echoed_and_invalid_value_is_replaced() -> None:
    client = TestClient(app)

    echoed = client.get("/health", headers={"X-Request-ID": "request.test-123"})
    replaced = client.get("/health", headers={"X-Request-ID": "unsafe request id"})

    assert echoed.headers["x-request-id"] == "request.test-123"
    assert replaced.headers["x-request-id"].startswith("req_")
    assert replaced.headers["x-request-id"] != "unsafe request id"


def test_cors_allows_configured_frontend_origins() -> None:
    client = TestClient(app)
    settings = get_settings()
    origins = get_cors_origins(settings)

    for origin in origins[:2]:
        response = client.get("/health", headers={"Origin": origin})

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin


def test_cors_allows_context_put_and_request_id_header() -> None:
    client = TestClient(app)
    origin = get_cors_origins(get_settings())[0]
    response = client.options(
        "/api/jobs/job_test/page-context",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "Content-Type,X-Request-ID",
        },
    )

    assert response.status_code == 200
    assert "PUT" in response.headers["access-control-allow-methods"]
    assert "X-Request-ID" in response.headers["access-control-allow-headers"]
