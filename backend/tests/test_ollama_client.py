import base64
import json
from pathlib import Path

import httpx
import pytest

from app.ai.ollama_client import OllamaClient


def test_generate_vision_returns_native_telemetry(tmp_path: Path) -> None:
    image_path = tmp_path / "fixture.png"
    image_path.write_bytes(b"safe-public-fixture")
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "qwen3.5:latest",
                "response": '{"alt_text":"A test fixture."}',
                "thinking": "hidden reasoning",
                "done_reason": "stop",
                "total_duration": 100,
                "load_duration": 20,
                "prompt_eval_count": 10,
                "prompt_eval_duration": 30,
                "eval_count": 8,
                "eval_duration": 40,
            },
        )

    http_client = httpx.Client(base_url="http://ollama.test", transport=httpx.MockTransport(handler))
    client = OllamaClient("http://private.example:11434", "fallback", http_client=http_client)
    try:
        result = client.generate_vision(
            image_path,
            "Describe the image.",
            model="qwen3.5:latest",
            response_schema={"type": "object"},
            options={"seed": 42, "temperature": 0},
            keep_alive="5m",
            request_id="request-123",
        )
    finally:
        http_client.close()

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "qwen3.5:latest"
    assert payload["format"] == {"type": "object"}
    assert payload["keep_alive"] == "5m"
    assert payload["options"] == {"temperature": 0, "seed": 42}
    assert payload["images"] == [base64.b64encode(b"safe-public-fixture").decode("ascii")]
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["x-request-id"] == "request-123"
    assert result.model == "qwen3.5:latest"
    assert result.response == '{"alt_text":"A test fixture."}'
    assert result.thinking == "hidden reasoning"
    assert result.total_duration_ns == 100
    assert result.eval_count == 8
    assert result.wall_duration_ms >= 0
    assert result.request_id == "request-123"


def test_legacy_text_method_returns_response_string() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": "writer", "response": "metadata"})

    http_client = httpx.Client(base_url="http://ollama.test", transport=httpx.MockTransport(handler))
    client = OllamaClient("http://private.example:11434", "writer", http_client=http_client)
    try:
        assert client.generate_text("Write metadata.") == "metadata"
    finally:
        http_client.close()


def test_empty_generation_response_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": "writer", "response": "  "})

    http_client = httpx.Client(base_url="http://ollama.test", transport=httpx.MockTransport(handler))
    client = OllamaClient("http://private.example:11434", "writer", http_client=http_client)
    try:
        with pytest.raises(ValueError, match="empty generation response"):
            client.generate_text_result("Write metadata.")
    finally:
        http_client.close()
