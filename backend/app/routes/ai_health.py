from typing import Annotated

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.schemas.responses import AiHealthResponse
from app.services.ai_health_service import AiHealthService


router = APIRouter()


def get_ai_health_service(settings: Annotated[Settings, Depends(get_settings)]) -> AiHealthService:
    return AiHealthService(settings)


@router.get(
    "/health",
    response_model=AiHealthResponse,
    summary="Check AI subsystem readiness",
    description=(
        "Checks inference reachability and required model availability using a bounded timeout. "
        "The response intentionally excludes inference URLs, storage paths, and credentials."
    ),
)
def read_ai_health(service: Annotated[AiHealthService, Depends(get_ai_health_service)]) -> AiHealthResponse:
    return service.check()
