import base64
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field


class OllamaGenerationResult(BaseModel):
    model: str
    response: str
    thinking: str = ""
    done_reason: str = ""
    total_duration_ns: int = Field(default=0, ge=0)
    load_duration_ns: int = Field(default=0, ge=0)
    prompt_eval_count: int = Field(default=0, ge=0)
    prompt_eval_duration_ns: int = Field(default=0, ge=0)
    eval_count: int = Field(default=0, ge=0)
    eval_duration_ns: int = Field(default=0, ge=0)
    wall_duration_ms: float = Field(ge=0)
    request_id: str


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._client = http_client or httpx.Client(base_url=self.base_url, timeout=timeout_seconds)
        self._owns_client = http_client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def generate_vision(
        self,
        image_path: Path,
        prompt: str,
        *,
        model: str | None = None,
        response_schema: dict[str, object] | str | None = None,
        options: dict[str, object] | None = None,
        keep_alive: str | int | None = None,
        request_id: str | None = None,
        timeout_seconds: float | None = None,
    ) -> OllamaGenerationResult:
        image_base64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return self._generate(
            prompt,
            model=model,
            images=[image_base64],
            response_schema=response_schema,
            options=options,
            keep_alive=keep_alive,
            request_id=request_id,
            timeout_seconds=timeout_seconds,
        )

    def generate_text_result(
        self,
        prompt: str,
        *,
        model: str | None = None,
        response_schema: dict[str, object] | str | None = None,
        options: dict[str, object] | None = None,
        keep_alive: str | int | None = None,
        request_id: str | None = None,
        timeout_seconds: float | None = None,
    ) -> OllamaGenerationResult:
        return self._generate(
            prompt,
            model=model,
            response_schema=response_schema,
            options=options,
            keep_alive=keep_alive,
            request_id=request_id,
            timeout_seconds=timeout_seconds,
        )

    def generate_image_metadata(
        self,
        image_path: Path,
        prompt: str,
        timeout_seconds: float | None = None,
        options: dict[str, object] | None = None,
    ) -> str:
        return self.generate_vision(
            image_path,
            prompt,
            options=options,
            timeout_seconds=timeout_seconds,
        ).response

    def generate_text(
        self,
        prompt: str,
        timeout_seconds: float | None = None,
        options: dict[str, object] | None = None,
    ) -> str:
        return self.generate_text_result(
            prompt,
            options=options,
            timeout_seconds=timeout_seconds,
        ).response

    def _generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        images: list[str] | None = None,
        response_schema: dict[str, object] | str | None = None,
        options: dict[str, object] | None = None,
        keep_alive: str | int | None = None,
        request_id: str | None = None,
        timeout_seconds: float | None = None,
    ) -> OllamaGenerationResult:
        resolved_request_id = request_id or str(uuid4())
        request_options: dict[str, object] = {"temperature": 0}
        if options:
            request_options.update(options)

        payload: dict[str, object] = {
            "model": model or self.model,
            "prompt": prompt,
            "stream": False,
            "options": request_options,
        }
        if images:
            payload["images"] = images
        if response_schema is not None:
            payload["format"] = response_schema
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive

        started_at = perf_counter()
        response = self._client.post(
            "/api/generate",
            json=payload,
            headers={"X-Request-ID": resolved_request_id},
            timeout=timeout_seconds if timeout_seconds is not None else self.timeout_seconds,
        )
        wall_duration_ms = (perf_counter() - started_at) * 1000
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Ollama returned a non-object generation response.")

        content = data.get("response")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Ollama returned an empty generation response.")

        return OllamaGenerationResult(
            model=self._string_value(data.get("model")) or str(payload["model"]),
            response=content,
            thinking=self._string_value(data.get("thinking")),
            done_reason=self._string_value(data.get("done_reason")),
            total_duration_ns=self._nonnegative_int(data.get("total_duration")),
            load_duration_ns=self._nonnegative_int(data.get("load_duration")),
            prompt_eval_count=self._nonnegative_int(data.get("prompt_eval_count")),
            prompt_eval_duration_ns=self._nonnegative_int(data.get("prompt_eval_duration")),
            eval_count=self._nonnegative_int(data.get("eval_count")),
            eval_duration_ns=self._nonnegative_int(data.get("eval_duration")),
            wall_duration_ms=wall_duration_ms,
            request_id=resolved_request_id,
        )

    @staticmethod
    def _string_value(value: object) -> str:
        return value if isinstance(value, str) else ""

    @staticmethod
    def _nonnegative_int(value: object) -> int:
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0
