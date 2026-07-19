import json
from collections import Counter
from math import ceil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from .hashing import sha256_file
from .dataset import load_manifest, verify_dataset_item


SHA256_PATTERN = r"^[0-9a-f]{64}$"


class ModelIdentity(BaseModel):
    model_id: str = Field(min_length=1)
    expected_digest: str = Field(pattern=SHA256_PATTERN)
    role: str = Field(min_length=1)
    identity_frozen: bool
    live_reverification_required: bool


class PromptIdentity(BaseModel):
    prompt_id: str = Field(min_length=1)
    path: Path
    sha256: str = Field(pattern=SHA256_PATTERN)


class DatasetPlan(BaseModel):
    pilot_disposition: Literal["excluded_from_primary_inference"]
    split: Literal["full"]
    manifest_path: Path
    provisional_items: int = Field(gt=0)
    final_items: int | None = Field(default=None, gt=0)
    primary_claim_images: int = Field(gt=0)
    production_metadata_images: int = Field(gt=0)
    context_ablation_images: int = Field(gt=0)
    domains: dict[str, int | None]
    sample_size_approved: bool
    analysis_intent: Literal["estimation_first"]
    sample_size_decision_path: Path
    sample_size_decision_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_populations(self) -> "DatasetPlan":
        domain_counts = list(self.domains.values())
        if (
            self.final_items is not None
            and all(count is not None for count in domain_counts)
            and sum(count for count in domain_counts if count is not None) != self.final_items
        ):
            raise ValueError("domain counts must sum to final_items")
        if self.final_items is not None and self.primary_claim_images > self.final_items:
            raise ValueError("primary_claim_images cannot exceed final_items")
        if self.final_items is not None and self.production_metadata_images > self.final_items:
            raise ValueError("production_metadata_images cannot exceed final_items")
        if self.context_ablation_images > self.production_metadata_images:
            raise ValueError("context_ablation_images cannot exceed production_metadata_images")
        return self


class ExecutionPlan(BaseModel):
    repeats: int = Field(ge=1)
    human_repeat: int = Field(ge=1)
    randomization_seed: int | None
    temperature: float
    thinking_mode: Literal["disabled"]
    context_window: int = Field(gt=0)
    facts_output_token_limit: int = Field(gt=0)
    metadata_output_token_limit: int = Field(gt=0)
    per_attempt_timeout_seconds: int = Field(gt=0)
    keep_alive: str = Field(min_length=1)
    hidden_retries_allowed: Literal[0]

    @model_validator(mode="after")
    def validate_human_repeat(self) -> "ExecutionPlan":
        if self.human_repeat > self.repeats:
            raise ValueError("human_repeat cannot exceed repeats")
        return self


class MeaningfulEffect(BaseModel):
    rq_id: Literal["RQ1", "RQ2", "RQ3"]
    metric: str = Field(min_length=1)
    threshold: float = Field(gt=0)
    unit: str = Field(min_length=1)
    approved: bool


class ApprovalState(BaseModel):
    private_supervisor_record_complete: bool
    authorship_credit_agreed: bool
    publication_route_confirmed: bool
    ethics_determination_recorded: bool
    data_and_network_policy_confirmed: bool
    reviewer_burden_approved: bool
    full_study_execution_approved: bool


class InfrastructureState(BaseModel):
    runtime_version: str = Field(min_length=1)
    runtime_reverified: bool
    approved_access_path: Literal["ssh_tunnel"]
    listener_binding: str = Field(min_length=1)
    listener_security_verified: bool
    dedicated_workspace_verified: bool
    telemetry_path_verified: bool
    telemetry_scope: list[str] = Field(min_length=1)
    telemetry_limitations: list[str] = Field(min_length=1)
    evidence_path: Path


class RunAccounting(BaseModel):
    provisional_final_images: int = Field(gt=0)
    primary_claim_images: int = Field(gt=0)
    production_metadata_images: int = Field(gt=0)
    context_ablation_images: int = Field(gt=0)
    finalist_models: int = Field(gt=0)
    repeats: int = Field(gt=0)
    vision_fact_calls: int = Field(gt=0)
    decomposed_writer_calls: int = Field(gt=0)
    direct_metadata_calls: int = Field(gt=0)
    incremental_context_calls: int = Field(gt=0)
    total_model_calls: int = Field(gt=0)
    unique_human_review_items: int = Field(gt=0)
    total_reviewer_assignments: int = Field(gt=0)
    reviewers: int = Field(gt=0)
    rq1_overlap_rate: float = Field(ge=0, le=1)
    metadata_overlap_rate: float = Field(ge=0, le=1)
    review_seconds_per_item: int = Field(gt=0)
    projected_minutes_per_reviewer: float = Field(gt=0)
    adjudication_minutes_included: bool


class ProtocolFreezeContract(BaseModel):
    schema_version: Literal[1]
    protocol_id: str = Field(min_length=1)
    protocol_version: str = Field(min_length=1)
    status: Literal["draft", "frozen"]
    canonical_document: Path
    model_identities: list[ModelIdentity] = Field(min_length=1)
    prompts: list[PromptIdentity] = Field(min_length=1)
    dataset: DatasetPlan
    execution: ExecutionPlan
    meaningful_effects: list[MeaningfulEffect] = Field(min_length=3)
    approvals: ApprovalState
    infrastructure: InfrastructureState
    run_accounting: RunAccounting
    condition_ids: list[str] = Field(min_length=1)
    primary_outcomes: dict[str, str]

    @model_validator(mode="after")
    def validate_unique_contract_ids(self) -> "ProtocolFreezeContract":
        model_ids = [model.model_id for model in self.model_identities]
        prompt_ids = [prompt.prompt_id for prompt in self.prompts]
        if len(model_ids) != len(set(model_ids)):
            raise ValueError("model identities must be unique")
        if len(prompt_ids) != len(set(prompt_ids)):
            raise ValueError("prompt identities must be unique")
        if len(self.condition_ids) != len(set(self.condition_ids)):
            raise ValueError("condition ids must be unique")
        if set(self.primary_outcomes) != {"RQ1", "RQ2", "RQ3", "RQ4"}:
            raise ValueError("exactly one primary outcome is required for each RQ1-RQ4")
        if {effect.rq_id for effect in self.meaningful_effects} != {"RQ1", "RQ2", "RQ3"}:
            raise ValueError("meaningful effects are required for RQ1-RQ3")
        return self


class ProtocolAuditSummary(BaseModel):
    status: Literal["freeze_ready", "draft_blocked", "invalid"]
    protocol_id: str | None = None
    protocol_sha256: str | None = None
    blockers: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    verified_prompt_hashes: int = Field(ge=0, default=0)


def audit_protocol_freeze(
    protocol_path: Path,
    output_path: Path,
) -> tuple[ProtocolAuditSummary, Path]:
    errors: list[str] = []
    blockers: list[str] = []
    protocol: ProtocolFreezeContract | None = None
    try:
        protocol = ProtocolFreezeContract.model_validate_json(protocol_path.read_text())
    except (OSError, ValidationError, ValueError) as exc:
        errors.append(str(exc))

    verified_prompt_hashes = 0
    if protocol is not None:
        root = protocol_path.resolve().parent.parent
        for prompt in protocol.prompts:
            prompt_path = (root / prompt.path).resolve()
            if root != prompt_path and root not in prompt_path.parents:
                errors.append(f"{prompt.prompt_id}: prompt path escapes evaluation root")
            elif not prompt_path.is_file():
                errors.append(f"{prompt.prompt_id}: prompt file is missing")
            elif sha256_file(prompt_path) != prompt.sha256:
                errors.append(f"{prompt.prompt_id}: prompt SHA-256 mismatch")
            else:
                verified_prompt_hashes += 1

        _validate_accounting(protocol, errors)
        _collect_blockers(protocol, root, blockers)
        _validate_decision_record(protocol, root, errors)
        _validate_manifest(protocol, root, errors)

    if errors:
        status = "invalid"
    elif blockers:
        status = "draft_blocked"
    else:
        status = "freeze_ready"

    summary = ProtocolAuditSummary(
        status=status,
        protocol_id=protocol.protocol_id if protocol else None,
        protocol_sha256=sha256_file(protocol_path) if protocol_path.is_file() else None,
        blockers=blockers,
        errors=errors,
        verified_prompt_hashes=verified_prompt_hashes,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
    return summary, output_path


def _collect_blockers(
    protocol: ProtocolFreezeContract,
    root: Path,
    blockers: list[str],
) -> None:
    if protocol.status != "frozen":
        blockers.append("protocol status is draft")
    if protocol.dataset.final_items is None:
        blockers.append("final dataset size is not set")
    if not protocol.dataset.sample_size_approved:
        blockers.append("sample-size justification is not approved")
    manifest_path = (root / protocol.dataset.manifest_path).resolve()
    if not manifest_path.is_file():
        blockers.append("full-study dataset manifest is not materialized")
    decision_path = (root / protocol.dataset.sample_size_decision_path).resolve()
    if not decision_path.is_file():
        blockers.append("sample-size decision record is not materialized")
    if any(count is None for count in protocol.dataset.domains.values()):
        blockers.append("final domain allocation is not set")
    if protocol.execution.randomization_seed is None:
        blockers.append("full-study randomization seed is not set")
    for model in protocol.model_identities:
        if not model.identity_frozen:
            blockers.append(f"{model.model_id}: model identity is not frozen")
        if model.live_reverification_required:
            blockers.append(f"{model.model_id}: live digest/runtime reverification is pending")
    for effect in protocol.meaningful_effects:
        if not effect.approved:
            blockers.append(f"{effect.rq_id}: minimum meaningful effect is not approved")
    for field_name, approved in protocol.approvals.model_dump().items():
        if not approved:
            blockers.append(field_name.replace("_", " ") + " is pending")
    infrastructure_checks = {
        "runtime reverification": protocol.infrastructure.runtime_reverified,
        "listener security verification": protocol.infrastructure.listener_security_verified,
        "dedicated project workspace verification": protocol.infrastructure.dedicated_workspace_verified,
        "supported telemetry path verification": protocol.infrastructure.telemetry_path_verified,
    }
    for label, complete in infrastructure_checks.items():
        if not complete:
            blockers.append(label + " is pending")


def _validate_accounting(protocol: ProtocolFreezeContract, errors: list[str]) -> None:
    accounting = protocol.run_accounting
    images = accounting.provisional_final_images
    finalists = accounting.finalist_models
    repeats = accounting.repeats
    expected_vision = images * finalists * repeats
    expected_writer = images * finalists * repeats
    expected_direct = images * repeats
    expected_incremental_context = accounting.context_ablation_images * 3 * repeats
    expected_total = expected_vision + expected_writer + expected_direct + expected_incremental_context
    rq1_items = accounting.primary_claim_images * finalists
    metadata_items = (
        accounting.primary_claim_images * 2
        + accounting.production_metadata_images * (finalists - 1)
        + accounting.context_ablation_images * 3
    )
    expected_human_items = rq1_items + metadata_items
    expected_assignments = (
        rq1_items
        + ceil(rq1_items * accounting.rq1_overlap_rate)
        + metadata_items
        + ceil(metadata_items * accounting.metadata_overlap_rate)
    )
    expected_minutes_per_reviewer = (
        expected_assignments
        * accounting.review_seconds_per_item
        / 60
        / accounting.reviewers
    )
    checks = {
        "provisional_final_images": (
            accounting.provisional_final_images,
            protocol.dataset.final_items,
        ),
        "primary_claim_images": (
            accounting.primary_claim_images,
            protocol.dataset.primary_claim_images,
        ),
        "production_metadata_images": (
            accounting.production_metadata_images,
            protocol.dataset.production_metadata_images,
        ),
        "context_ablation_images": (
            accounting.context_ablation_images,
            protocol.dataset.context_ablation_images,
        ),
        "repeats": (accounting.repeats, protocol.execution.repeats),
        "vision_fact_calls": (accounting.vision_fact_calls, expected_vision),
        "decomposed_writer_calls": (accounting.decomposed_writer_calls, expected_writer),
        "direct_metadata_calls": (accounting.direct_metadata_calls, expected_direct),
        "incremental_context_calls": (
            accounting.incremental_context_calls,
            expected_incremental_context,
        ),
        "total_model_calls": (accounting.total_model_calls, expected_total),
        "unique_human_review_items": (
            accounting.unique_human_review_items,
            expected_human_items,
        ),
        "total_reviewer_assignments": (
            accounting.total_reviewer_assignments,
            expected_assignments,
        ),
        "projected_minutes_per_reviewer": (
            accounting.projected_minutes_per_reviewer,
            expected_minutes_per_reviewer,
        ),
    }
    for field_name, (actual, expected) in checks.items():
        if actual != expected:
            errors.append(f"run accounting {field_name} is {actual}; expected {expected}")

    if protocol.dataset.provisional_items != images:
        errors.append("dataset provisional_items does not match run accounting")
    if protocol.dataset.primary_claim_images != accounting.primary_claim_images:
        errors.append("dataset primary_claim_images does not match run accounting")
    if protocol.dataset.production_metadata_images != accounting.production_metadata_images:
        errors.append("dataset production_metadata_images does not match run accounting")
    if protocol.dataset.context_ablation_images != accounting.context_ablation_images:
        errors.append("dataset context_ablation_images does not match run accounting")
    if protocol.execution.repeats != repeats:
        errors.append("execution repeats does not match run accounting")


def _validate_manifest(
    protocol: ProtocolFreezeContract,
    root: Path,
    errors: list[str],
) -> None:
    manifest_path = (root / protocol.dataset.manifest_path).resolve()
    if not manifest_path.is_file():
        return
    try:
        items = load_manifest(root, protocol.dataset.manifest_path)
    except (OSError, ValueError) as exc:
        errors.append(f"full-study dataset manifest is invalid: {exc}")
        return

    if protocol.dataset.final_items is not None and len(items) != protocol.dataset.final_items:
        errors.append(
            "full-study dataset item count is "
            f"{len(items)}; expected {protocol.dataset.final_items}"
        )
    wrong_split = [item.id for item in items if item.split != protocol.dataset.split]
    if wrong_split:
        errors.append("full-study dataset contains non-full items: " + ", ".join(wrong_split))
    actual_domains = dict(Counter(item.domain for item in items))
    expected_domains = {
        domain: count
        for domain, count in protocol.dataset.domains.items()
        if count is not None
    }
    if actual_domains != expected_domains:
        errors.append(
            f"full-study domain counts are {actual_domains}; expected {expected_domains}"
        )
    for item in items:
        errors.extend(verify_dataset_item(root, item))


def _validate_decision_record(
    protocol: ProtocolFreezeContract,
    root: Path,
    errors: list[str],
) -> None:
    decision_path = (root / protocol.dataset.sample_size_decision_path).resolve()
    if root != decision_path and root not in decision_path.parents:
        errors.append("sample-size decision path escapes evaluation root")
        return
    if not decision_path.is_file():
        return
    if sha256_file(decision_path) != protocol.dataset.sample_size_decision_sha256:
        errors.append("sample-size decision record SHA-256 mismatch")
