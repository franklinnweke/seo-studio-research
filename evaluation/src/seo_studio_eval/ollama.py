import json
from http.client import RemoteDisconnected
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaHTTPError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"Ollama HTTP {status_code}: {detail}")
        self.status_code = status_code


class OllamaConnectionError(RuntimeError):
    pass


class OllamaTransport:
    def __init__(self, base_url: str, timeout_seconds: float = 240.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def version(self) -> str:
        payload = self._request("/api/version", method="GET")
        version = payload.get("version")
        if not isinstance(version, str) or not version:
            raise ValueError("Ollama version response is missing version")
        return version

    def tags(self) -> dict[str, Any]:
        return self._request("/api/tags", method="GET")

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._request("/api/generate", payload=request)

    def _request(
        self,
        path: str,
        payload: dict[str, Any] | None = None,
        method: str = "POST",
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                decoded = json.loads(response.read())
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise OllamaHTTPError(exc.code, detail) from exc
        except URLError as exc:
            raise OllamaConnectionError(f"Ollama connection failed: {exc.reason}") from exc
        except (ConnectionError, RemoteDisconnected, TimeoutError) as exc:
            raise OllamaConnectionError(f"Ollama connection failed: {exc}") from exc
        if not isinstance(decoded, dict):
            raise ValueError("Ollama response must be a JSON object")
        return decoded
