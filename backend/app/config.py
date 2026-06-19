from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_FRONTEND_ORIGINS = (
    "http://localhost:3000,http://127.0.0.1:3000,"
    "http://localhost:11501,http://127.0.0.1:11501,"
    "https://84.46.242.149:11501,http://84.46.242.149:11501,"
    "https://184.146.14.24:11501,http://184.146.14.24:11501,"
    "https://seo-studio2.axivaq.com,http://seo-studio2.axivaq.com,"
    "https://seo-studio.axivaq.com,http://seo-studio.axivaq.com"
)


class Settings(BaseSettings):
    app_name: str = "seo-studio"
    environment: str = "local"
    frontend_origin: str = "http://localhost:3000"
    frontend_origins: str = DEFAULT_FRONTEND_ORIGINS
    ai_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "moondream"
    vision_model: str = "qwen2.5vl:3b"
    language_model: str = "qwen3.5"
    ollama_timeout_seconds: float = 90.0
    ai_language_timeout_seconds: float = 120.0
    ai_crop_timeout_seconds: float = 45.0
    ai_preview_max_width: int = 1024
    storage_root: Path = Path(__file__).resolve().parent / "storage"
    max_upload_file_size_bytes: int = 5 * 1024 * 1024
    max_zip_file_size_bytes: int = 25 * 1024 * 1024
    max_files_per_image_job: int = 50
    max_brand_context_file_size_bytes: int = 5 * 1024 * 1024
    max_brand_context_chars: int = 8000

    model_config = SettingsConfigDict(env_prefix="SEO_STUDIO_", env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_cors_origins(settings: Settings) -> list[str]:
    origins = [origin.strip() for origin in settings.frontend_origins.split(",") if origin.strip()]
    if settings.frontend_origin not in origins:
        origins.append(settings.frontend_origin)
    return origins
