from typing import Literal

from pydantic import BaseModel, Field

JobType = Literal["image", "website"]
JobStatus = Literal["pending", "processing", "processed", "needs_review", "accepted", "failed"]


class HealthResponse(BaseModel):
    status: Literal["ok"] = Field(description="API health status.")
    app: str = Field(description="Application identifier.")


class SettingsResponse(BaseModel):
    ollama_base_url: str = Field(description="Base URL for the local Ollama runtime.")
    ollama_model: str = Field(description="Default Ollama model used by AI workflows.")
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


CompressionMode = Literal["lossy", "lossless"]
ResizeMode = Literal["none", "max_1920", "max_1200", "custom"]
OutputFormat = Literal["keep_original", "webp", "jpg", "png"]


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
    strip_metadata: bool = Field(default=True, description="Whether to remove image metadata.")
    filename_overrides: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Optional per-image filename overrides keyed by uploaded image file id. "
            "Values may include an extension, but the processed extension is determined "
            "by output_format or the source format."
        ),
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
