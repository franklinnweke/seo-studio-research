import httpx

from app.config import Settings
from app.schemas.responses import AiHealthResponse, AiModelReadiness


class AiHealthService:
    def __init__(self, settings: Settings, *, http_client: httpx.Client | None = None) -> None:
        self.settings = settings
        self._client = http_client

    def check(self) -> AiHealthResponse:
        if self.settings.ai_provider != "ollama":
            return AiHealthResponse(
                status="unavailable",
                provider=self.settings.ai_provider,
                inference_reachable=False,
                models_ready=False,
                issue_code="unsupported_provider",
            )

        if self._client is not None:
            return self._check_ollama(self._client)

        try:
            with httpx.Client(
                base_url=self.settings.ollama_base_url.rstrip("/"),
                timeout=self.settings.ai_health_timeout_seconds,
            ) as client:
                return self._check_ollama(client)
        except (httpx.HTTPError, ValueError):
            return self._unreachable_response()

    def _check_ollama(self, client: httpx.Client) -> AiHealthResponse:
        try:
            version_response = client.get("/api/version", timeout=self.settings.ai_health_timeout_seconds)
            version_response.raise_for_status()
            tags_response = client.get("/api/tags", timeout=self.settings.ai_health_timeout_seconds)
            tags_response.raise_for_status()

            version_data = version_response.json()
            tags_data = tags_response.json()
            if not isinstance(version_data, dict) or not isinstance(tags_data, dict):
                raise ValueError("Inference health response must be a JSON object.")

            installed = self._installed_model_names(tags_data.get("models"))
            models = [
                AiModelReadiness(
                    role="vision",
                    model=self.settings.vision_model,
                    ready=self._model_is_installed(self.settings.vision_model, installed),
                ),
                AiModelReadiness(
                    role="language",
                    model=self.settings.language_model,
                    ready=self._model_is_installed(self.settings.language_model, installed),
                ),
            ]
            models_ready = all(model.ready for model in models)
            version = version_data.get("version")

            return AiHealthResponse(
                status="ready" if models_ready else "degraded",
                provider=self.settings.ai_provider,
                inference_reachable=True,
                models_ready=models_ready,
                version=version if isinstance(version, str) else None,
                models=models,
                issue_code=None if models_ready else "required_models_missing",
            )
        except (httpx.HTTPError, ValueError):
            return self._unreachable_response()

    def _unreachable_response(self) -> AiHealthResponse:
        return AiHealthResponse(
            status="unavailable",
            provider=self.settings.ai_provider,
            inference_reachable=False,
            models_ready=False,
            issue_code="inference_unreachable",
        )

    @staticmethod
    def _installed_model_names(value: object) -> set[str]:
        if not isinstance(value, list):
            raise ValueError("Ollama model inventory must be a list.")

        installed: set[str] = set()
        for item in value:
            if not isinstance(item, dict):
                continue
            for key in ("name", "model"):
                name = item.get(key)
                if isinstance(name, str) and name:
                    installed.add(name)
        return installed

    @staticmethod
    def _model_is_installed(configured_model: str, installed: set[str]) -> bool:
        if configured_model in installed:
            return True
        return ":" not in configured_model and f"{configured_model}:latest" in installed
