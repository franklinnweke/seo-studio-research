from typing import Literal

from pydantic import BaseModel, Field

JobType = Literal["image", "website"]
JobStatus = Literal["pending", "processing", "processed", "needs_review", "accepted", "failed"]


class HealthResponse(BaseModel):
    status: Literal["ok"] = Field(description="API health status.")
    app: str = Field(description="Application identifier.")


class SettingsResponse(BaseModel):
    ai_provider: str = Field(description="Configured AI provider for metadata workflows.")
    ollama_base_url: str = Field(description="Base URL for the local Ollama runtime.")
    ollama_model: str = Field(description="Default Ollama model used by AI workflows.")
    vision_model: str = Field(description="Ollama vision model used for image inspection and crop targeting.")
    language_model: str = Field(description="Ollama language model used for SEO metadata writing.")
    ollama_timeout_seconds: float = Field(description="Timeout in seconds for each Ollama request.")
    ai_crop_timeout_seconds: float = Field(description="Timeout in seconds for AI crop targeting requests.")
    ai_preview_max_width: int = Field(description="Maximum preview width sent to AI models.")
    frontend_origin: str = Field(description="Allowed frontend origin for local CORS.")
    storage_root: str = Field(description="Backend local storage root.")


class JobStatusResponse(BaseModel):
    id: str = Field(description="Unique job identifier.")
    type: JobType = Field(description="Job workflow type.")
    status: JobStatus = Field(description="Current job status.")
    file_count: int = Field(description="Number of uploaded image files associated with the job.")


class ImageUploadFileRecord(BaseModel):
    id: str = Field(description="Unique uploaded image file identifier.")
    original_filename: str = Field(description="Original filename provided by the user or ZIP entry.")
    stored_filename: str = Field(description="Sanitized filename stored under the job upload folder.")
    relative_path: str = Field(description="Path relative to the job upload folder.")
    content_type: str = Field(description="Detected or provided content type.")
    size_bytes: int = Field(description="Stored image size in bytes.")
    source: Literal["upload", "zip"] = Field(description="Whether the file came directly or from a ZIP.")
    source_archive: str | None = Field(
        default=None,
        description="Original ZIP filename when the image came from an archive.",
    )


class ImageJobCreateResponse(BaseModel):
    id: str = Field(description="Unique image job identifier.")
    type: Literal["image"] = Field(description="Job workflow type.")
    status: JobStatus = Field(description="Current job status after upload.")
    accepted_extensions: list[str] = Field(description="File extensions accepted by the upload endpoint.")
    files: list[ImageUploadFileRecord] = Field(description="Validated uploaded image files.")


class JobFileListResponse(BaseModel):
    job_id: str = Field(description="Unique job identifier.")
    files: list[ImageUploadFileRecord] = Field(
        default_factory=list,
        description="Uploaded image files associated with the job.",
    )


class BrandContextDocument(BaseModel):
    id: str = Field(description="Unique brand context document identifier.")
    original_filename: str = Field(description="Original brand document filename.")
    stored_filename: str = Field(description="Sanitized filename stored under the job folder.")
    content_type: str = Field(description="Detected or provided content type.")
    size_bytes: int = Field(description="Stored document size in bytes.")
    extracted_chars: int = Field(description="Number of extracted text characters used for AI context.")


class BrandContextResponse(BaseModel):
    job_id: str = Field(description="Image job identifier.")
    documents: list[BrandContextDocument] = Field(
        default_factory=list,
        description="Uploaded brand context documents attached to the image job.",
    )
    combined_text: str = Field(
        default="",
        description="Combined extracted brand context text passed to AI metadata generation.",
    )
    max_chars: int = Field(description="Maximum combined text characters retained for AI prompts.")


CompressionMode = Literal["lossy", "lossless"]
ResizeMode = Literal["none", "max_1920", "max_1200", "custom", "exact", "fit_inside"]
OutputFormat = Literal["keep_original", "webp", "jpg", "png"]


class CropBox(BaseModel):
    x: float = Field(ge=0.0, le=1.0, description="Normalized left edge of the crop or subject box.")
    y: float = Field(ge=0.0, le=1.0, description="Normalized top edge of the crop or subject box.")
    width: float = Field(ge=0.0, le=1.0, description="Normalized box width.")
    height: float = Field(ge=0.0, le=1.0, description="Normalized box height.")


class ImageCompressionSettings(BaseModel):
    mode: CompressionMode = Field(default="lossy", description="Compression mode.")
    quality: int = Field(default=80, ge=1, le=100, description="Lossy compression quality.")
    resize_mode: ResizeMode = Field(default="none", description="Optional max-width resize mode.")
    output_format: OutputFormat = Field(
        default="keep_original",
        description="Output image format. keep_original preserves each source extension.",
    )
    custom_max_width: int | None = Field(
        default=None,
        ge=1,
        le=10000,
        description="Custom max width used only when resize_mode is custom.",
    )
    target_width: int | None = Field(
        default=None,
        ge=1,
        le=10000,
        description="Target output width used by exact crop and fit-inside resize modes.",
    )
    target_height: int | None = Field(
        default=None,
        ge=1,
        le=10000,
        description="Target output height used by exact crop and fit-inside resize modes.",
    )
    prevent_upscaling: bool = Field(
        default=True,
        description="Whether exact and fit-inside resize modes should avoid enlarging smaller source images.",
    )
    crop_focus_x: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Normalized horizontal crop focus from 0 left to 1 right.",
    )
    crop_focus_y: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Normalized vertical crop focus from 0 top to 1 bottom.",
    )
    pad_color: str = Field(
        default="#ffffff",
        pattern=r"^#[0-9a-fA-F]{6}$",
        description="Canvas background color used by fit-inside resize mode.",
    )
    strip_metadata: bool = Field(default=True, description="Whether to remove image metadata.")
    filename_overrides: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Optional per-image filename overrides keyed by uploaded image file id. "
            "Values may include an extension, but the processed extension is determined "
            "by output_format or the source format."
        ),
    )
    crop_boxes: dict[str, CropBox] = Field(
        default_factory=dict,
        description=(
            "Optional normalized crop boxes keyed by uploaded image file id. "
            "Used by AI-assisted exact crop workflows when a subject should stay in frame."
        ),
    )
    crop_subjects: dict[str, str] = Field(
        default_factory=dict,
        description="Optional AI-detected crop subjects keyed by uploaded image file id.",
    )
    crop_reasons: dict[str, str] = Field(
        default_factory=dict,
        description="Optional AI crop explanations keyed by uploaded image file id.",
    )
    crop_confidences: dict[str, float] = Field(
        default_factory=dict,
        description="Optional AI crop confidence scores keyed by uploaded image file id.",
    )


class ImageCompressionResult(BaseModel):
    id: str = Field(description="Uploaded image file identifier.")
    original_filename: str = Field(description="Original filename from upload.")
    stored_filename: str = Field(description="Original stored upload filename.")
    processed_filename: str = Field(description="Processed filename saved under processed storage.")
    relative_path: str = Field(description="Processed file path relative to the processed job folder.")
    original_format: str = Field(description="Original file format extension.")
    new_format: str = Field(description="Processed file format extension.")
    original_size_bytes: int = Field(description="Original uploaded file size in bytes.")
    processed_size_bytes: int = Field(description="Processed file size in bytes.")
    reduction_percent: float = Field(description="Percent size reduction after compression.")
    width: int = Field(description="Processed image width in pixels.")
    height: int = Field(description="Processed image height in pixels.")
    status: Literal["processed"] = Field(description="Processing status for this image.")


class ImageCompressionResponse(BaseModel):
    job_id: str = Field(description="Image job identifier.")
    status: Literal["processed"] = Field(description="Image compression job status.")
    settings: ImageCompressionSettings = Field(description="Compression settings applied.")
    results: list[ImageCompressionResult] = Field(description="Per-image compression results.")


class ResizeInstructionRequest(BaseModel):
    instruction: str = Field(
        min_length=1,
        max_length=1000,
        description="Natural-language resize instruction to convert into editable processing settings.",
    )


class AiCropSuggestionRequest(BaseModel):
    instruction: str = Field(
        min_length=1,
        max_length=1000,
        description="Natural-language subject-aware crop instruction.",
    )
    settings: ImageCompressionSettings = Field(description="Current resize settings to augment with AI crop boxes.")


class ResizeInstructionResponse(BaseModel):
    instruction: str = Field(description="Original instruction provided by the user.")
    settings: ImageCompressionSettings = Field(description="Parsed resize and conversion settings.")
    notes: list[str] = Field(
        default_factory=list,
        description="Human-readable notes about how the instruction was interpreted.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Recoverable warnings raised while interpreting the instruction.",
    )


class CropReviewItem(BaseModel):
    id: str = Field(description="Uploaded image file identifier.")
    original_filename: str = Field(description="Original filename from upload.")
    width: int = Field(description="Original image width in pixels.")
    height: int = Field(description="Original image height in pixels.")
    target_width: int = Field(description="Requested target width in pixels.")
    target_height: int = Field(description="Requested target height in pixels.")
    needs_review: bool = Field(description="Whether source and target ratios differ enough to review cropping.")
    focus_x: float = Field(ge=0.0, le=1.0, description="Suggested normalized crop focus x coordinate.")
    focus_y: float = Field(ge=0.0, le=1.0, description="Suggested normalized crop focus y coordinate.")
    confidence: float = Field(ge=0.0, le=1.0, description="Suggestion confidence from 0 to 1.")
    source: Literal["center", "preset", "ai"] = Field(description="How the crop suggestion was produced.")
    crop_box: CropBox | None = Field(default=None, description="Optional normalized AI crop or subject box.")
    subject: str = Field(default="", description="Subject the AI crop suggestion is trying to preserve.")
    reason: str = Field(default="", description="Short explanation for the crop suggestion.")


class CropReviewResponse(BaseModel):
    job_id: str = Field(description="Image job identifier.")
    target_width: int = Field(description="Requested target width in pixels.")
    target_height: int = Field(description="Requested target height in pixels.")
    items: list[CropReviewItem] = Field(description="Per-image crop review suggestions.")


class ImageMetadataResult(BaseModel):
    id: str = Field(description="Uploaded image file identifier.")
    original_filename: str = Field(description="Original filename from upload.")
    suggested_filename: str = Field(description="AI-generated extension-free filename.")
    alt_text: str = Field(description="AI-generated image alt text.")
    caption: str = Field(description="AI-generated image caption.")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Model confidence from 0 to 1.")
    status: Literal["needs_review", "failed"] = Field(description="Metadata generation status for this image.")
    error_message: str = Field(default="", description="Failure detail when status is failed.")


class ImageMetadataListResponse(BaseModel):
    job_id: str = Field(description="Image job identifier.")
    provider: str = Field(description="AI provider used for metadata generation.")
    model: str = Field(description="AI model used for metadata generation.")
    vision_model: str = Field(default="", description="Vision model used to inspect image content.")
    language_model: str = Field(default="", description="Language model used to write metadata.")
    results: list[ImageMetadataResult] = Field(default_factory=list, description="Per-image metadata results.")


class PageListResponse(BaseModel):
    job_id: str = Field(description="Unique website job identifier.")
    pages: list[str] = Field(
        default_factory=list,
        description="Crawled page URLs. Empty until Phase 8 is implemented.",
    )


class LinkListResponse(BaseModel):
    job_id: str = Field(description="Unique website job identifier.")
    links: list[str] = Field(
        default_factory=list,
        description="Checked link URLs. Empty until Phase 9 is implemented.",
    )


class ExportPlaceholderResponse(BaseModel):
    job_id: str = Field(description="Unique job identifier.")
    format: str = Field(description="Requested export format.")
    status: Literal["not_implemented"] = Field(
        description="Placeholder status until export generation is implemented.",
    )
