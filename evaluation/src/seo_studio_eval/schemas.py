from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VisualFactsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    people: list[str] = Field(default_factory=list)
    objects: list[str] = Field(default_factory=list)
    setting: str = ""
    visible_text: list[str] = Field(default_factory=list)
    uncertain_facts: list[str] = Field(default_factory=list)
    forbidden_inferences_observed: list[str] = Field(default_factory=list)


class ContextualMetadataPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str
    alt_text: str
    caption: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
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
    study_config_sha256: str = ""
    models_config_sha256: str = ""
    criteria_sha256: str = ""
    collection_attempt: int = Field(default=1, ge=1)
    supersedes_attempt_id: str = ""


class ClaimAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1)
    claim_text: str = Field(min_length=1)
    label: Literal["supported", "unsupported", "contradicted", "not_verifiable_from_permitted_evidence"]
    evidence_note: str = ""


class AnnotationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rubric_version: Literal["rubric-v1"] = "rubric-v1"
    record_type: Literal["individual", "adjudicated"] = "individual"
    item_id: str
    review_item_id: str
    blinded_condition_id: str
    reviewer_alias: str
    repeat: Literal[1] = 1
    calibration_item: bool = False
    claims: list[ClaimAnnotation] = Field(default_factory=list)
    factual_grounding_score: int = Field(ge=1, le=5)
    salient_coverage_score: int = Field(ge=1, le=5)
    contextual_usefulness_score: int = Field(ge=1, le=5)
    redundancy_control_score: int | None = Field(default=None, ge=1, le=5)
    purpose_appropriateness_score: int = Field(ge=1, le=5)
    brand_alignment_score: int | None = Field(default=None, ge=1, le=5)
    safety_score: int = Field(ge=1, le=5)
    concision_fluency_score: int = Field(ge=1, le=5)
    disposition: Literal["accept_unchanged", "minor_edit", "major_edit", "reject"]
    notes: str = ""

    @model_validator(mode="after")
    def validate_claim_ids(self) -> "AnnotationRecord":
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim ids must be unique within an annotation record")
        return self


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
