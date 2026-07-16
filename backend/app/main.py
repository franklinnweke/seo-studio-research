from collections.abc import Awaitable, Callable
import logging
from pathlib import Path
import re
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.auth import require_authenticated_user
from app.config import get_cors_origins, get_settings
from app.errors import ApiError
from app.routes import ai_health, auth, exports, image_jobs, settings, website_jobs
from app.schemas.responses import HealthResponse


OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Operational checks for local development and smoke testing.",
    },
    {
        "name": "AI health",
        "description": "Sanitized inference and required-model readiness checks.",
    },
    {
        "name": "settings",
        "description": "Runtime configuration exposed to the frontend.",
    },
    {
        "name": "auth",
        "description": "Supabase JWT-backed authentication checks for dashboard sessions.",
    },
    {
        "name": "image jobs",
        "description": "Image upload, processing, metadata review, and image result endpoints.",
    },
    {
        "name": "website jobs",
        "description": "Website crawling, page extraction, broken link, and SEO metadata endpoints.",
    },
    {
        "name": "exports",
        "description": "CSV, JSON, XLSX, and ZIP export endpoints for completed jobs.",
    },
]

API_DESCRIPTION = """
The seo-studio API powers the local proof-of-concept workflow for image optimization,
website crawling, AI metadata generation, and exports.

The POC uses local file storage, a separate local Ollama runtime, and Supabase
Auth for dashboard access. Long-running worker queues and persistent job
databases are intentionally deferred until beta readiness.
"""

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def ensure_storage_dirs(storage_root: Path) -> None:
    for name in ("uploads", "processed", "exports", "temp"):
        (storage_root / name).mkdir(parents=True, exist_ok=True)


def create_app() -> FastAPI:
    configure_logging()
    app_settings = get_settings()
    ensure_storage_dirs(app_settings.storage_root)

    app = FastAPI(
        title="seo-studio API",
        summary="Local API for the seo-studio optimization POC.",
        description=API_DESCRIPTION,
        version="0.1.0",
        contact={"name": "seo-studio maintainers"},
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(app_settings),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Accept", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def add_request_id(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        supplied_request_id = request.headers.get("X-Request-ID", "")
        request_id = (
            supplied_request_id
            if REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
            else f"req_{uuid4().hex}"
        )
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", f"req_{uuid4().hex}")
        return JSONResponse(status_code=exc.status_code, content=exc.response_body(request_id))

    @app.get(
        "/health",
        tags=["health"],
        response_model=HealthResponse,
        summary="Check API health",
        description="Returns a small response confirming the FastAPI service is running.",
    )
    def health() -> HealthResponse:
        return HealthResponse(status="ok", app=app_settings.app_name)

    auth_dependency = [Depends(require_authenticated_user)]
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(image_jobs.router, prefix="/api/jobs", tags=["image jobs"], dependencies=auth_dependency)
    app.include_router(website_jobs.router, prefix="/api/jobs", tags=["website jobs"], dependencies=auth_dependency)
    app.include_router(exports.router, prefix="/api/jobs", tags=["exports"], dependencies=auth_dependency)
    app.include_router(settings.router, prefix="/api/settings", tags=["settings"], dependencies=auth_dependency)
    app.include_router(ai_health.router, prefix="/api/ai", tags=["AI health"], dependencies=auth_dependency)

    return app


app = create_app()
