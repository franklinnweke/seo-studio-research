from fastapi import APIRouter

from app.config import get_cors_origins, get_settings
from app.schemas.responses import SettingsResponse


router = APIRouter()


@router.get(
    "",
    response_model=SettingsResponse,
    summary="Read runtime settings",
    description=(
        "Returns local runtime settings used by the frontend, including the Ollama "
        "endpoint, default model, CORS origin, and backend storage root."
    ),
)
def read_settings() -> SettingsResponse:
    settings = get_settings()
    return SettingsResponse(
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        frontend_origin=", ".join(get_cors_origins(settings)),
        storage_root=str(settings.storage_root),
    )
