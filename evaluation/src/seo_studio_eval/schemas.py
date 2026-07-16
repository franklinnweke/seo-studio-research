from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class VisualFactsPayload(BaseModel):
    summary: str
    people: list[str] = Field(default_factory=list)
    objects: list[str] = Field(default_factory=list)
    setting: str = ""
    visible_text: list[str] = Field(default_factory=list)
    uncertain_facts: list[str] = Field(default_factory=list)
    forbidden_inferences_observed: list[str] = Field(default_factory=list)


class ContextualMetadataPayload(BaseModel):
    filename: str
    alt_text: str
    caption: str
    purpose_rationale: str
    warnings: list[str] = Field(default_factory=list)


class ModelIdentity(BaseModel):
    id: str
    ollama_name: str
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    family: str
    parameters: str
    quantization: str
    license: str


class InputEvidence(BaseModel):
    image_id: str
    image_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_stratum: str
    purpose: str
    page_context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    brand_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PromptEvidence(BaseModel):
    prompt_id: str
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    system_prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ValidationEvidence(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)


class ErrorEvidence(BaseModel):
    category: str
    message: str
    retryable: bool = False


class TelemetryEvidence(BaseModel):
    wall_duration_ms: float = Field(ge=0)
    total_duration_ns: int = Field(default=0, ge=0)
    load_duration_ns: int = Field(default=0, ge=0)
    prompt_eval_count: int = Field(default=0, ge=0)
    prompt_eval_duration_ns: int = Field(default=0, ge=0)
    eval_count: int = Field(default=0, ge=0)
    eval_duration_ns: int = Field(default=0, ge=0)


class RunRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    record_version: Literal[1] = 1
    experiment_id: str
    protocol_version: str
    run_id: str
    attempt_id: str
    repeat: int = Field(ge=1)
    randomization_block: str
    started_at: datetime
    ended_at: datetime
    git_commit: str
    dirty_worktree: bool
    ollama_version: str
    system_snapshot_ref: str
    model: ModelIdentity
    input: InputEvidence
    prompt: PromptEvidence
    generation_options: dict[str, Any]
    thinking_mode: Literal["disabled", "enabled"]
    sanitized_request: dict[str, Any]
    raw_response: dict[str, Any]
    parsed_payload: dict[str, Any] | None = None
    validation: ValidationEvidence
    http_status: int | None = None
    error: ErrorEvidence | None = None
    retry_count: Literal[0] = 0
    done_reason: str = ""
    telemetry: TelemetryEvidence
    parser_version: str
    normalization_version: str


class AnnotationRecord(BaseModel):
    item_id: str
    blinded_condition_id: str
    reviewer_alias: str
    supported_claims: int = Field(ge=0)
    unsupported_claims: int = Field(ge=0)
    completeness_score: int = Field(ge=1, le=5)
    contextual_usefulness_score: int = Field(ge=1, le=5)
    notes: str = ""


SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "visual-facts.schema.json": VisualFactsPayload,
    "metadata.schema.json": ContextualMetadataPayload,
    "run-record.schema.json": RunRecord,
    "annotation.schema.json": AnnotationRecord,
}


def export_schemas(output_dir: Path) -> None:
    import json

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, model in SCHEMA_MODELS.items():
        (output_dir / filename).write_text(
            json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
        )
