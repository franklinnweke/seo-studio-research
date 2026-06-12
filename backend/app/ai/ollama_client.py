import base64
from pathlib import Path

import httpx


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout_seconds: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate_image_metadata(self, image_path: Path, prompt: str, timeout_seconds: float | None = None) -> str:
        image_base64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        response = httpx.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "images": [image_base64],
                "stream": False,
                "options": {"temperature": 0},
            },
            timeout=timeout_seconds if timeout_seconds is not None else self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("response")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Ollama returned an empty metadata response.")
        return content

    def generate_text(self, prompt: str, timeout_seconds: float | None = None) -> str:
        response = httpx.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0},
            },
            timeout=timeout_seconds if timeout_seconds is not None else self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("response")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Ollama returned an empty text response.")
        return content
