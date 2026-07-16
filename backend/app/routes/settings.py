from fastapi import APIRouter

from app.config import get_cors_origins, get_settings
from app.schemas.responses import SettingsResponse


router = APIRouter()


@router.get(
    "",
    response_model=SettingsResponse,
    summary="Read runtime settings",
    description=(
        "Returns sanitized runtime settings used by the frontend. Private inference "
        "endpoints and backend storage paths are intentionally excluded."
    ),
)
def read_settings() -> SettingsResponse:
    settings = get_settings()
    return SettingsResponse(
        ai_provider=settings.ai_provider,
        ollama_model=settings.ollama_model,
        vision_model=settings.vision_model,
        language_model=settings.language_model,
        ollama_timeout_seconds=settings.ollama_timeout_seconds,
        ai_language_timeout_seconds=settings.ai_language_timeout_seconds,
        ai_crop_timeout_seconds=settings.ai_crop_timeout_seconds,
        ai_preview_max_width=settings.ai_preview_max_width,
        frontend_origin=", ".join(get_cors_origins(settings)),
    )
