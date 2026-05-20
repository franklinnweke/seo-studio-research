from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.config import Settings, get_settings
from app.schemas.responses import ExportPlaceholderResponse
from app.services.export_service import ExportService


router = APIRouter()


def get_export_service(settings: Annotated[Settings, Depends(get_settings)]) -> ExportService:
    return ExportService(settings)


@router.get(
    "/{job_id}/export.zip",
    response_class=FileResponse,
    summary="Download processed images ZIP",
    description=(
        "Creates and downloads a ZIP archive containing every processed image for an "
        "image job. The job must already be processed through the image optimizer. "
        "Images are stored inside the archive under the `images/` folder."
    ),
    responses={
        404: {"description": "Job or processed images were not found."},
    },
)
def export_processed_images_zip(
    job_id: str,
    service: Annotated[ExportService, Depends(get_export_service)],
) -> FileResponse:
    zip_path = service.create_processed_images_zip(job_id)
    return FileResponse(
        path=zip_path,
        filename=f"{job_id}-processed-images.zip",
        media_type="application/zip",
    )


@router.get(
    "/{job_id}/export.{export_format}",
    response_model=ExportPlaceholderResponse,
    summary="Export job results",
    description=(
        "Placeholder export endpoint for CSV, JSON, XLSX, and ZIP downloads. "
        "Phase 7 will return generated files with the correct media type."
    ),
)
def export_job(job_id: str, export_format: str) -> ExportPlaceholderResponse:
    return ExportPlaceholderResponse(
        job_id=job_id,
        format=export_format,
        status="not_implemented",
    )
