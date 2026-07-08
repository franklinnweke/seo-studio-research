import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_cors_origins, get_settings
from app.routes import exports, image_jobs, settings, website_jobs
from app.schemas.responses import HealthResponse


OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Operational checks for local development and smoke testing.",
    },
    {
        "name": "settings",
        "description": "Runtime configuration exposed to the frontend.",
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

The POC uses local file storage and a separate local Ollama runtime. Long-running
worker queues, authentication, and persistent databases are intentionally deferred
until beta readiness.
"""


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
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Accept"],
    )

    @app.get(
        "/health",
        tags=["health"],
        response_model=HealthResponse,
        summary="Check API health",
        description="Returns a small response confirming the FastAPI service is running.",
    )
    def health() -> HealthResponse:
        return HealthResponse(status="ok", app=app_settings.app_name)

    app.include_router(image_jobs.router, prefix="/api/jobs", tags=["image jobs"])
    app.include_router(website_jobs.router, prefix="/api/jobs", tags=["website jobs"])
    app.include_router(exports.router, prefix="/api/jobs", tags=["exports"])
    app.include_router(settings.router, prefix="/api/settings", tags=["settings"])

    return app


app = create_app()
