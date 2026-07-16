import httpx
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.routes.ai_health import get_ai_health_service
from app.schemas.responses import AiHealthResponse, AiModelReadiness
from app.services.ai_health_service import AiHealthService


def make_client(*, models: list[str], version: str = "0.24.0") -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": version})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": model} for model in models]})
        return httpx.Response(404)

    return httpx.Client(base_url="http://ollama.test", transport=httpx.MockTransport(handler))


def test_ai_health_reports_ready_without_exposing_topology() -> None:
    settings = get_settings().model_copy(
        update={"vision_model": "qwen2.5vl:3b", "language_model": "qwen3.5:latest"}
    )
    with make_client(models=["qwen2.5vl:3b", "qwen3.5:latest"]) as http_client:
        response = AiHealthService(settings, http_client=http_client).check()

    body = response.model_dump()
    assert body["status"] == "ready"
    assert body["version"] == "0.24.0"
    assert body["models_ready"] is True
    assert all(model["ready"] for model in body["models"])
    assert "ollama_base_url" not in body
    assert "storage_root" not in body


def test_ai_health_reports_missing_required_model() -> None:
    settings = get_settings().model_copy(
        update={"vision_model": "qwen2.5vl:3b", "language_model": "qwen3.5:latest"}
    )
    with make_client(models=["qwen2.5vl:3b"]) as http_client:
        response = AiHealthService(settings, http_client=http_client).check()

    assert response.status == "degraded"
    assert response.inference_reachable is True
    assert response.models_ready is False
    assert response.issue_code == "required_models_missing"
    assert response.models[1].ready is False


def test_ai_health_resolves_an_implicit_latest_tag() -> None:
    settings = get_settings().model_copy(
        update={"vision_model": "qwen2.5vl:3b", "language_model": "qwen3.5"}
    )
    with make_client(models=["qwen2.5vl:3b", "qwen3.5:latest"]) as http_client:
        response = AiHealthService(settings, http_client=http_client).check()

    assert response.status == "ready"
    assert response.models[1].model == "qwen3.5"
    assert response.models[1].ready is True


def test_ai_health_sanitizes_connection_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private-host.example:11434 refused connection", request=request)

    http_client = httpx.Client(base_url="http://ollama.test", transport=httpx.MockTransport(handler))
    try:
        response = AiHealthService(get_settings(), http_client=http_client).check()
    finally:
        http_client.close()

    assert response.model_dump() == {
        "status": "unavailable",
        "provider": "ollama",
        "inference_reachable": False,
        "models_ready": False,
        "version": None,
        "models": [],
        "issue_code": "inference_unreachable",
    }


def test_ai_health_route_uses_sanitized_response_contract() -> None:
    class StubHealthService:
        def check(self) -> AiHealthResponse:
            return AiHealthResponse(
                status="ready",
                provider="ollama",
                inference_reachable=True,
                models_ready=True,
                version="0.24.0",
                models=[
                    AiModelReadiness(role="vision", model="vision-model", ready=True),
                    AiModelReadiness(role="language", model="language-model", ready=True),
                ],
            )

    app.dependency_overrides[get_ai_health_service] = StubHealthService
    try:
        response = TestClient(app).get("/api/ai/health")
    finally:
        app.dependency_overrides.pop(get_ai_health_service, None)

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert "ollama_base_url" not in response.json()
