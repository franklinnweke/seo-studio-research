from fastapi import APIRouter

from app.schemas.responses import ExportPlaceholderResponse


router = APIRouter()


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
