from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, Query, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.config import Settings, get_settings
from app.schemas.responses import (
    AiCropSuggestionRequest,
    BrandContextResponse,
    CropReviewResponse,
    ImageCompressionResponse,
    ImageCompressionSettings,
    ImageJobCreateResponse,
    ImageMetadataListResponse,
    ImageMetadataResult,
    JobFileListResponse,
    JobStatusResponse,
    ResizeInstructionRequest,
    ResizeInstructionResponse,
)
from app.services.ai_metadata_service import AiMetadataService
from app.services.brand_context_service import BrandContextService
from app.services.image_processor import ImageProcessor
from app.services.image_upload_service import ImageUploadService


router = APIRouter()


def get_image_upload_service(settings: Annotated[Settings, Depends(get_settings)]) -> ImageUploadService:
    return ImageUploadService(settings)


def get_image_processor(settings: Annotated[Settings, Depends(get_settings)]) -> ImageProcessor:
    return ImageProcessor(settings)


def get_ai_metadata_service(settings: Annotated[Settings, Depends(get_settings)]) -> AiMetadataService:
    return AiMetadataService(settings)


def get_brand_context_service(settings: Annotated[Settings, Depends(get_settings)]) -> BrandContextService:
    return BrandContextService(settings)


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


@router.get(
    "/{job_id}/brand-context",
    response_model=BrandContextResponse,
    summary="Read brand context documents",
    description=(
        "Returns brand context documents attached to an image job and the extracted "
        "plain text that will be included in AI image metadata prompts. Empty "
        "documents and text are returned when no brand context has been uploaded."
    ),
    responses={404: {"description": "Job not found."}},
)
def read_brand_context(
    job_id: str,
    service: Annotated[BrandContextService, Depends(get_brand_context_service)],
) -> BrandContextResponse:
    return service.get_brand_context(job_id)


@router.post(
    "/{job_id}/brand-context",
    response_model=BrandContextResponse,
    summary="Upload brand context documents",
    description=(
        "Attaches one or more brand context documents to an image job. Supports "
        "`.txt`, `.docx`, and `.pdf` files. The backend stores the original "
        "documents under the job folder, extracts plain text, truncates the "
        "combined context to the configured prompt limit, and persists it in "
        "`storage/uploads/{job_id}/job.json` for later AI metadata generation."
    ),
    responses={
        400: {"description": "The upload is empty, unsupported, too large, or has no extractable text."},
        404: {"description": "Job not found."},
    },
)
async def upload_brand_context(
    job_id: str,
    service: Annotated[BrandContextService, Depends(get_brand_context_service)],
    files: Annotated[
        list[UploadFile],
        File(description="One or more brand context documents. Supported extensions: .txt, .docx, .pdf."),
    ],
) -> BrandContextResponse:
    return await service.upload_brand_context(job_id, files)


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


@router.post(
    "/{job_id}/resize-instructions",
    response_model=ResizeInstructionResponse,
    summary="Parse image resize instructions",
    description=(
        "Converts a natural-language resize request into editable image processing "
        "settings. The POC parser recognizes common dimensions such as `600 x 400`, "
        "output formats like WebP/JPG/PNG, lossless mode, quality values, and fit-inside "
        "language. This endpoint does not call the AI model; subject-aware AI crop suggestions "
        "are requested separately through the AI crop endpoint so parsing stays responsive."
    ),
    responses={404: {"description": "Job not found."}},
)
def parse_resize_instructions(
    job_id: str,
    request: Annotated[
        ResizeInstructionRequest,
        Body(description="Natural-language resize request to interpret for the image job."),
    ],
    processor: Annotated[ImageProcessor, Depends(get_image_processor)],
) -> ResizeInstructionResponse:
    processor.upload_service.read_job(job_id)
    return processor.parse_resize_instruction(job_id, request.instruction)


@router.post(
    "/{job_id}/resize-review",
    response_model=CropReviewResponse,
    summary="Review crop requirements",
    description=(
        "Inspects uploaded images against exact resize settings and returns per-image "
        "crop review suggestions. Images whose aspect ratio does not match the target "
        "ratio are marked for review before final processing. Suggestions include "
        "normalized crop focus coordinates and optional AI crop boxes that can be "
        "reviewed in the UI before final processing."
    ),
    responses={
        400: {"description": "Exact target width and height are required."},
        404: {"description": "Job or uploaded source file not found."},
    },
)
def review_image_crops(
    job_id: str,
    settings: Annotated[
        ImageCompressionSettings,
        Body(description="Resize settings used to determine crop review requirements."),
    ],
    processor: Annotated[ImageProcessor, Depends(get_image_processor)],
) -> CropReviewResponse:
    return processor.crop_review(job_id, settings)


@router.post(
    "/{job_id}/resize-ai-crop",
    response_model=ResizeInstructionResponse,
    summary="Suggest AI crop boxes",
    description=(
        "Requests AI vision crop suggestions for an exact resize instruction. This endpoint "
        "is intentionally separate from resize instruction parsing because model calls can be "
        "slow or fail. The response returns updated processing settings with optional crop "
        "boxes, plus notes or warnings that the UI can show before crop review."
    ),
    responses={
        400: {"description": "Exact target width and height are required."},
        404: {"description": "Job or uploaded source file not found."},
        502: {"description": "Configured AI provider request failed or returned invalid crop JSON."},
    },
)
def suggest_ai_crop(
    job_id: str,
    request: Annotated[
        AiCropSuggestionRequest,
        Body(description="Subject-aware crop request and current resize settings."),
    ],
    processor: Annotated[ImageProcessor, Depends(get_image_processor)],
) -> ResizeInstructionResponse:
    processor.upload_service.read_job(job_id)
    return processor.suggest_ai_crop(job_id, request.instruction, request.settings)


@router.get(
    "/{job_id}/images/metadata",
    response_model=ImageMetadataListResponse,
    summary="List AI image metadata",
    description=(
        "Returns generated AI metadata for an image job. Empty results are returned "
        "when metadata has not been generated yet."
    ),
    responses={404: {"description": "Job not found."}},
)
def list_image_metadata(
    job_id: str,
    service: Annotated[AiMetadataService, Depends(get_ai_metadata_service)],
) -> ImageMetadataListResponse:
    return service.list_image_metadata(job_id)


@router.get(
    "/{job_id}/images/metadata.csv",
    response_class=Response,
    summary="Export AI image metadata CSV",
    description=(
        "Exports one CSV row per uploaded image in a job. Optional repeated `fields` "
        "query values control which SEO and file columns are included. The export joins "
        "uploaded image records, generated AI metadata when available, and processed "
        "image filenames when the job has been optimized."
    ),
    responses={
        400: {"description": "One or more requested CSV fields are not supported."},
        404: {"description": "Job not found."},
    },
)
def export_image_metadata_csv(
    job_id: str,
    service: Annotated[AiMetadataService, Depends(get_ai_metadata_service)],
    fields: Annotated[
        list[str] | None,
        Query(description="CSV fields to include. Repeat this query value for multiple columns."),
    ] = None,
) -> Response:
    csv_content = service.export_image_metadata_csv(job_id, fields)
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{job_id}-image-metadata.csv"'},
    )


@router.post(
    "/{job_id}/images/metadata",
    response_model=ImageMetadataListResponse,
    summary="Generate AI metadata for all image files",
    description=(
        "Generates filename suggestions, alt text, captions, and confidence scores "
        "for every image in a job. Images are processed sequentially through the "
        "configured AI provider. Failed rows are returned with failed status while "
        "successful rows are persisted for review."
    ),
    responses={404: {"description": "Job not found."}},
)
def generate_all_image_metadata(
    job_id: str,
    service: Annotated[AiMetadataService, Depends(get_ai_metadata_service)],
) -> ImageMetadataListResponse:
    return service.generate_all_image_metadata(job_id)


@router.post(
    "/{job_id}/images/{image_id}/metadata",
    response_model=ImageMetadataResult,
    summary="Regenerate AI metadata for one image",
    description=(
        "Regenerates filename suggestion, alt text, caption, and confidence score "
        "for one uploaded image in an image job."
    ),
    responses={
        404: {"description": "Job or image file not found."},
        502: {"description": "Configured AI provider request failed."},
    },
)
def generate_single_image_metadata(
    job_id: str,
    image_id: str,
    service: Annotated[AiMetadataService, Depends(get_ai_metadata_service)],
) -> ImageMetadataResult:
    return service.generate_single_image_metadata(job_id, image_id)


@router.get(
    "/{job_id}/images/{image_id}/download",
    response_class=FileResponse,
    summary="Download image with SEO filename",
    description=(
        "Downloads the processed image for an uploaded image id when processed output exists. "
        "If the job has not been processed, downloads the original uploaded image instead. "
        "The attachment filename uses the provided filename query value, generated AI filename, "
        "or stored filename while preserving the actual downloaded file extension."
    ),
    responses={
        404: {"description": "Job, image, processed file, or original upload not found."},
    },
)
def download_image_with_metadata_filename(
    job_id: str,
    image_id: str,
    processor: Annotated[ImageProcessor, Depends(get_image_processor)],
    filename: Annotated[
        str | None,
        Query(description="Optional extension-free filename to use for the attachment."),
    ] = None,
) -> FileResponse:
    path, download_filename = processor.image_download(job_id, image_id, filename)
    return FileResponse(path=path, filename=download_filename)


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
