from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

JobType = Literal["image", "website"]
JobStatus = Literal["pending", "processing", "processed", "needs_review", "accepted", "failed"]
ImagePurpose = Literal["informative", "decorative", "functional", "text", "complex", "redundant", "unknown"]
PurposeSource = Literal["unconfirmed", "human_confirmed", "ai_suggested"]
MetadataGenerationMode = Literal["dual_stage", "direct"]
MetadataContextMode = Literal["none", "brand_only", "page_only", "brand_and_page"]
VISUAL_FACTS_SCHEMA_VERSION = "visual-facts-v1"
CONTEXTUAL_METADATA_SCHEMA_VERSION = "contextual-metadata-v1"


class HealthResponse(BaseModel):
    status: Literal["ok"] = Field(description="API health status.")
    app: str = Field(description="Application identifier.")


class ApiErrorResponse(BaseModel):
    code: str = Field(description="Stable machine-readable error category.")
    message: str = Field(description="Safe human-readable error message.")
    field: str | None = Field(default=None, description="Related request or persisted field when applicable.")
    retryable: bool = Field(description="Whether repeating the same operation may succeed without changing input.")
    request_id: str = Field(description="Correlation identifier returned in the response header and body.")


AiHealthStatus = Literal["ready", "degraded", "unavailable"]


class AiModelReadiness(BaseModel):
    role: Literal["vision", "language"] = Field(description="Model role in the metadata pipeline.")
    model: str = Field(description="Configured model label; no inference host details are exposed.")
    ready: bool = Field(description="Whether the configured model is present in the Ollama inventory.")


class AiHealthResponse(BaseModel):
    status: AiHealthStatus = Field(description="Sanitized AI subsystem readiness state.")
    provider: str = Field(description="Configured AI provider.")
    inference_reachable: bool = Field(description="Whether the backend can reach the inference API.")
    models_ready: bool = Field(description="Whether every required configured model is installed.")
    version: str | None = Field(default=None, description="Inference runtime version when reachable.")
    models: list[AiModelReadiness] = Field(
        default_factory=list,
        description="Readiness of configured model roles without host, path, or credential details.",
    )
    issue_code: Literal["unsupported_provider", "inference_unreachable", "required_models_missing"] | None = Field(
        default=None,
        description="Stable sanitized reason when the subsystem is not ready.",
    )


class AuthUserResponse(BaseModel):
    id: str = Field(description="Supabase authenticated user identifier.")
    email: str | None = Field(default=None, description="Authenticated user's email address.")


class PageContextUpdateRequest(BaseModel):
    page_title: str = Field(default="", max_length=300, description="Title of the page containing the image.")
    section_heading: str = Field(default="", max_length=300, description="Nearest relevant section heading.")
    nearby_text: str = Field(default="", max_length=4000, description="Relevant surrounding page copy.")
    page_url: str = Field(default="", max_length=2000, description="Optional public page URL.")
    audience: str = Field(default="", max_length=500, description="Intended audience for the page.")
    language: str = Field(default="en-CA", min_length=2, max_length=35, description="BCP 47-style content language.")


class PageContext(PageContextUpdateRequest):
    updated_at: datetime | None = Field(default=None, description="UTC timestamp of the most recent human update.")


class PageContextResponse(BaseModel):
    job_id: str = Field(description="Image job identifier.")
    schema_version: Literal[2] = Field(default=2, description="Persisted job context schema version.")
    page_context: PageContext = Field(description="Page-level evidence available to metadata generation.")


class ImageContextUpdateRequest(BaseModel):
    purpose: ImagePurpose = Field(default="unknown", description="Human-selected role of the image on the page.")
    purpose_confirmed: bool = Field(default=False, description="Whether a human explicitly confirmed the purpose.")
    suggested_purpose: ImagePurpose | None = Field(default=None, description="Optional AI suggestion retained for review.")
    purpose_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional confidence attached to an AI purpose suggestion.",
    )
    purpose_suggestion_rationale: str = Field(
        default="",
        max_length=1000,
        description="Short model rationale retained as suggestion evidence, never as human confirmation.",
    )
    link_destination: str = Field(default="", max_length=2000, description="Link destination for a functional image.")
    functional_action: str = Field(default="", max_length=500, description="Action performed by a functional image.")
    long_description_available: bool = Field(
        default=False,
        description="Whether an equivalent long description is available for a complex image.",
    )
    complex_description_acknowledged: bool = Field(
        default=False,
        description="Whether a reviewer acknowledged the complex-image description requirement.",
    )
    notes: str = Field(default="", max_length=2000, description="Human review notes about image purpose or context.")


class ImageContext(ImageContextUpdateRequest):
    purpose_source: PurposeSource = Field(default="unconfirmed", description="Source of the current purpose decision.")
    updated_at: datetime | None = Field(default=None, description="UTC timestamp of the most recent update.")


class ImageContextResponse(BaseModel):
    job_id: str = Field(description="Image job identifier.")
    image_id: str = Field(description="Uploaded image identifier.")
    schema_version: Literal[2] = Field(default=2, description="Persisted job context schema version.")
    image_context: ImageContext = Field(description="Per-image purpose and review context.")


class SettingsResponse(BaseModel):
    ai_provider: str = Field(description="Configured AI provider for metadata workflows.")
    context_metadata_enabled: bool = Field(description="Whether the context-aware metadata workflow is enabled.")
    purpose_suggestion_enabled: bool = Field(description="Whether AI purpose suggestions are enabled.")
    ollama_model: str = Field(description="Default Ollama model used by AI workflows.")
    vision_model: str = Field(description="Ollama vision model used for image inspection and crop targeting.")
    language_model: str = Field(description="Ollama language model used for SEO metadata writing.")
    ollama_timeout_seconds: float = Field(description="Timeout in seconds for each Ollama request.")
    ai_language_timeout_seconds: float = Field(description="Timeout in seconds for AI metadata language requests.")
    ai_crop_timeout_seconds: float = Field(description="Timeout in seconds for AI crop targeting requests.")
    ai_preview_max_width: int = Field(description="Maximum preview width sent to AI models.")
    frontend_origin: str = Field(description="Allowed frontend origin for local CORS.")


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
    schema_version: Literal[2] = Field(default=2, description="Version of the persisted image-job schema.")
    id: str = Field(description="Unique image job identifier.")
    type: Literal["image"] = Field(description="Job workflow type.")
    status: JobStatus = Field(description="Current job status after upload.")
    accepted_extensions: list[str] = Field(description="File extensions accepted by the upload endpoint.")
    files: list[ImageUploadFileRecord] = Field(description="Validated uploaded image files.")
    page_context: PageContext = Field(default_factory=PageContext, description="Page-level metadata context.")
    image_contexts: dict[str, ImageContext] = Field(
        default_factory=dict,
        description="Per-image purpose contexts keyed by uploaded image id.",
    )


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
    status: Literal["needs_review", "accepted", "failed"] = Field(
        description="Metadata generation or review status for this image."
    )
    error_message: str = Field(default="", description="Failure detail when status is failed.")
    purpose: ImagePurpose = Field(default="unknown", description="Confirmed page role used during generation.")
    purpose_rationale: str = Field(default="", description="Short rationale grounded in the permitted evidence.")
    warnings: list[str] = Field(default_factory=list, description="Model or validation warnings requiring review.")
    visual_facts: "VisualFactsPayload | None" = Field(
        default=None,
        description="Structured pixel-grounded facts produced only by the decomposed condition.",
    )
    provenance: "GenerationProvenance | None" = Field(
        default=None,
        description="Sanitized reproducibility evidence; never contains raw page or brand context.",
    )
    review_history: list["MetadataReviewEvent"] = Field(
        default_factory=list,
        description="Append-only generation, edit, and acceptance events.",
    )


class VisualFactsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1000)
    people: list[str] = Field(default_factory=list)
    objects: list[str] = Field(default_factory=list)
    setting: str = Field(default="", max_length=500)
    visible_text: list[str] = Field(default_factory=list)
    uncertain_facts: list[str] = Field(default_factory=list)
    forbidden_inferences_observed: list[str] = Field(default_factory=list)


class ContextualMetadataPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=120)
    alt_text: str = Field(default="", max_length=500)
    caption: str = Field(min_length=1, max_length=500)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    purpose_rationale: str = Field(default="", max_length=1000)
    warnings: list[str] = Field(default_factory=list)


class PurposeSuggestionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: ImagePurpose
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1, max_length=1000)


class GenerationStageEvidence(BaseModel):
    request_id: str = ""
    model: str = ""
    wall_duration_ms: float = Field(default=0.0, ge=0.0)
    total_duration_ns: int = Field(default=0, ge=0)
    prompt_eval_count: int = Field(default=0, ge=0)
    eval_count: int = Field(default=0, ge=0)


class GenerationProvenance(BaseModel):
    generation_id: str
    generation_mode: MetadataGenerationMode
    generated_at: datetime
    vision_model: str
    writer_model: str
    vision_model_digest: str = ""
    writer_model_digest: str = ""
    visual_facts_prompt_version: str = ""
    metadata_prompt_version: str
    visual_facts_schema_version: str = ""
    metadata_schema_version: str
    image_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    brand_context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    image_context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    system_prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    visual_facts_prompt_sha256: str = ""
    visual_facts_schema_sha256: str = ""
    generation_options: dict[str, object] = Field(default_factory=dict)
    image_preprocessing: dict[str, object] = Field(default_factory=dict)
    retry_count: int = Field(default=0, ge=0)
    vision_stage: GenerationStageEvidence | None = None
    writer_stage: GenerationStageEvidence | None = None


class MetadataReviewEvent(BaseModel):
    action: Literal["generated", "edited", "accepted"]
    at: datetime


class MetadataGenerationRequest(BaseModel):
    image_ids: list[str] | None = Field(
        default=None,
        description="Optional subset of image ids; omitted runs every image in the job.",
    )
    generation_mode: MetadataGenerationMode = "dual_stage"
    context_mode: MetadataContextMode = "brand_and_page"


class ImageMetadataListResponse(BaseModel):
    job_id: str = Field(description="Image job identifier.")
    provider: str = Field(description="AI provider used for metadata generation.")
    model: str = Field(description="AI model used for metadata generation.")
    vision_model: str = Field(default="", description="Vision model used to inspect image content.")
    language_model: str = Field(default="", description="Language model used to write metadata.")
    results: list[ImageMetadataResult] = Field(default_factory=list, description="Per-image metadata results.")


class ImageMetadataUpdateRequest(BaseModel):
    suggested_filename: str = Field(
        min_length=1,
        max_length=120,
        description="Reviewed extension-free filename to persist for this image.",
    )
    alt_text: str = Field(
        min_length=0,
        max_length=500,
        description="Reviewed alt text; empty is valid only for confirmed decorative or redundant images.",
    )
    caption: str = Field(
        min_length=1,
        max_length=500,
        description="Reviewed caption to persist for this image.",
    )
    status: Literal["needs_review", "accepted"] | None = Field(
        default=None,
        description="Optional explicit review status to apply with the metadata update.",
    )


class ImageMetadataBulkAcceptRequest(BaseModel):
    image_ids: list[str] = Field(
        min_length=1,
        description="One or more uploaded image file ids to mark as accepted.",
    )


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
