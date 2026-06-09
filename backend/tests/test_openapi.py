from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_docs_routes_are_available() -> None:
    docs_response = client.get("/docs")
    redoc_response = client.get("/redoc")
    schema_response = client.get("/openapi.json")

    assert docs_response.status_code == 200
    assert redoc_response.status_code == 200
    assert schema_response.status_code == 200


def test_openapi_has_expected_metadata() -> None:
    schema = client.get("/openapi.json").json()

    assert schema["info"]["title"] == "seo-studio API"
    assert schema["info"]["version"] == "0.1.0"
    assert "image optimization" in schema["info"]["description"]


def test_current_routes_are_documented() -> None:
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]

    expected_routes = [
        ("/health", "get"),
        ("/api/settings", "get"),
        ("/api/jobs/{job_id}", "get"),
        ("/api/jobs/{job_id}/process", "post"),
        ("/api/jobs/{job_id}/resize-instructions", "post"),
        ("/api/jobs/{job_id}/resize-ai-crop", "post"),
        ("/api/jobs/{job_id}/resize-review", "post"),
        ("/api/jobs/{job_id}/processed/{filename}", "get"),
        ("/api/jobs/{job_id}/files", "get"),
        ("/api/jobs/{job_id}/pages", "get"),
        ("/api/jobs/{job_id}/links", "get"),
        ("/api/jobs/{job_id}/broken-links", "get"),
        ("/api/jobs/{job_id}/export.{export_format}", "get"),
    ]

    for path, method in expected_routes:
        operation = paths[path][method]
        assert operation["summary"]
        assert operation["description"]
        success_response = operation["responses"]["200"]
        if "content" in success_response:
            assert success_response["content"]
        else:
            assert path == "/api/jobs/{job_id}/processed/{filename}"


def test_openapi_tags_are_grouped() -> None:
    schema = client.get("/openapi.json").json()
    tags = {tag["name"]: tag["description"] for tag in schema["tags"]}

    assert "health" in tags
    assert "settings" in tags
    assert "image jobs" in tags
    assert "website jobs" in tags
    assert "exports" in tags
