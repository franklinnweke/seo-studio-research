from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, UploadFile, status
from fastapi.responses import FileResponse

from app.config import Settings, get_settings
from app.schemas.responses import (
    ImageCompressionResponse,
    ImageCompressionSettings,
    ImageJobCreateResponse,
    JobFileListResponse,
    JobStatusResponse,
)
from app.services.image_processor import ImageProcessor
from app.services.image_upload_service import ImageUploadService


router = APIRouter()


def get_image_upload_service(settings: Annotated[Settings, Depends(get_settings)]) -> ImageUploadService:
    return ImageUploadService(settings)


def get_image_processor(settings: Annotated[Settings, Depends(get_settings)]) -> ImageProcessor:
    return ImageProcessor(settings)


@router.post(
    "/images",
    response_model=ImageJobCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create image upload job",
    description=(
        "Creates an image job from one or more uploaded files. Accepts direct "
        "`.jpg`, `.jpeg`, `.png`, and `.webp` images plus `.zip` archives that "
        "contain supported images. Direct image files and ZIP entries are limited "
        "to 5MB each. ZIP archives are safely inspected to prevent path traversal."
    ),
    responses={
        400: {
            "description": "The upload is empty, unsupported, too large, unsafe, or not a valid image.",
        }
    },
)
async def create_image_job(
    service: Annotated[ImageUploadService, Depends(get_image_upload_service)],
    files: Annotated[
        list[UploadFile],
        File(
            description=(
                "One or more image files or ZIP archives. Supported extensions: "
                ".jpg, .jpeg, .png, .webp, .zip."
            )
        ),
    ],
) -> ImageJobCreateResponse:
    return await service.create_job(files)


@router.post(
    "/{job_id}/process",
    response_model=ImageCompressionResponse,
    summary="Process uploaded image files",
    description=(
        "Processes every validated image in an image job using the provided compression, "
        "conversion, and filename cleanup settings. Defaults match the RFC: lossy mode, "
        "quality 80, no resize, metadata stripping enabled, and original output format. "
        "It can convert output format to WebP, JPG, PNG, or keep the original extension. "
        "Optional filename overrides are sanitized, lowercased, de-duplicated, and saved "
        "with the selected output extension. Processed files are written to "
        "`storage/processed/{job_id}/images`. Transparent images converted to JPG are "
        "flattened onto a white background."
    ),
    responses={
        400: {"description": "The job has no images or settings are invalid."},
        404: {"description": "Job or uploaded source file not found."},
    },
)
def process_image_job(
    job_id: str,
    settings: Annotated[
        ImageCompressionSettings,
        Body(
            description=(
                "Processing settings. Quality is most relevant for JPEG and WebP; "
                "PNG uses lossless optimization behavior. filename_overrides may be "
                "used to manually set cleaned output filenames by uploaded file id."
            )
        ),
    ],
    processor: Annotated[ImageProcessor, Depends(get_image_processor)],
) -> ImageCompressionResponse:
    return processor.compress_job(job_id, settings)


@router.get(
    "/{job_id}/processed/{filename}",
    response_class=FileResponse,
    summary="Download processed image",
    description=(
        "Downloads one processed image from `storage/processed/{job_id}/images`. "
        "The filename must be a direct processed filename returned by the compression result."
    ),
    responses={
        400: {"description": "Filename is invalid."},
        404: {"description": "Processed file not found."},
    },
)
def download_processed_image(
    job_id: str,
    filename: str,
    processor: Annotated[ImageProcessor, Depends(get_image_processor)],
) -> FileResponse:
    path = processor.processed_file_path(job_id, filename)
    return FileResponse(path=path, filename=filename)


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status",
    description=(
        "Returns status for an image job created by the upload endpoint, including "
        "the number of validated uploaded image files."
    ),
    responses={404: {"description": "Job not found."}},
)
def get_job(
    job_id: str,
    service: Annotated[ImageUploadService, Depends(get_image_upload_service)],
) -> JobStatusResponse:
    return service.get_job(job_id)


@router.get(
    "/{job_id}/files",
    response_model=JobFileListResponse,
    summary="List uploaded image job files",
    description=(
        "Returns validated direct image uploads and extracted ZIP image entries for "
        "an image job."
    ),
    responses={404: {"description": "Job not found."}},
)
def list_job_files(
    job_id: str,
    service: Annotated[ImageUploadService, Depends(get_image_upload_service)],
) -> JobFileListResponse:
    return JobFileListResponse(job_id=job_id, files=service.list_files(job_id))
