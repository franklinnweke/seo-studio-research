import json
from datetime import datetime, timezone
from pathlib import Path
import random
import re
import tomllib
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from .accounting import effective_error_category, resolve_attempt_records
from .config import ModelEntry, load_study, resolve_under_root
from .dataset import load_manifest
from .hashing import sha256_file
from .ollama import OllamaTransport
from .pilot import (
    _execute_vision_attempt,
    _existing_attempts,
    _is_recoverable_transport,
    _verify_live_digests,
)
from .records import attempt_record_paths, write_attempt_record
from .schemas import RunRecord, VisualFactsPayload
from .smoke import _git_state


class RepairTransport(Protocol):
    def version(self) -> str: ...

    def tags(self) -> dict[str, Any]: ...

    def generate(self, request: dict[str, Any]) -> dict[str, Any]: ...


class TruncationRepairCriteria(BaseModel):
    schema_version: Literal[1]
    criteria_id: str
    purpose: str
    source_done_reason: Literal["length"]
    source_output_token_limit: int = Field(gt=0)
    recovery_output_token_limit: int = Field(gt=0)
    expected_repairs: int = Field(gt=0)
    required_repairs_by_model: dict[str, int]
    per_attempt_timeout_seconds: float = Field(gt=0)
    hidden_retries_allowed: Literal[0]
    explicit_repair_attempts_per_truncation: Literal[1]
    abort_on_transport_error: Literal[True]
    max_transport_attempts_per_item: int = Field(ge=1)
    temperature: float
    seed: int
    thinking_mode: Literal["disabled"]
    context_window: int | None = Field(default=None, gt=0)
    warmup_manifest: Path
    warmup_image_id: str
    keep_alive: str


class RepairModelResult(BaseModel):
    planned: int = Field(ge=0)
    observed: int = Field(ge=0)
    valid: int = Field(ge=0)
    failed: int = Field(ge=0)


class TruncationRepairSummary(BaseModel):
    status: Literal["running", "paused", "complete", "incomplete"]
    experiment_id: str
    protocol_version: str
    criteria_id: str
    run_id: str
    ollama_version: str
    started_at: datetime
    updated_at: datetime
    git_commit: str
    dirty_worktree: bool
    system_snapshot_ref: str
    study_config_sha256: str
    models_config_sha256: str
    criteria_sha256: str
    randomization_seed: int
    source_output_token_limit: int
    recovery_output_token_limit: int
    timeout_seconds: float
    model_order: list[str]
    repair_order_by_model: dict[str, list[str]]
    expected_repairs: int = Field(ge=0)
    observed_repairs: int = Field(ge=0)
    valid_repairs: int = Field(ge=0)
    failed_repairs: int = Field(ge=0)
    raw_measured_records: int = Field(ge=0)
    superseded_transport_records: int = Field(ge=0)
    warmup_records: int = Field(ge=0)
    all_truncations_repaired: bool
    aborted_on_transport_error: bool
    abort_attempt_id: str = ""
    max_new_attempts: int | None = None
    new_attempts_this_session: int = Field(ge=0)
    by_model: dict[str, RepairModelResult]


def load_truncation_repair_criteria(path: Path) -> TruncationRepairCriteria:
    return TruncationRepairCriteria.model_validate(tomllib.loads(path.resolve().read_text()))


def select_truncation_sources(
    source_run_dirs: list[Path],
    configured: dict[str, ModelEntry],
    criteria: TruncationRepairCriteria,
) -> dict[str, RunRecord]:
    resolution = resolve_attempt_records(source_run_dirs)
    if resolution.duplicate_keys:
        raise ValueError("Source runs contain unresolved duplicate outcome keys")
    selected: dict[str, RunRecord] = {}
    for key, record in resolution.selected.items():
        if record.model.id not in configured:
            continue
        if record.validation.valid or record.done_reason != criteria.source_done_reason:
            continue
        if record.error is not None:
            raise ValueError(f"Truncation source unexpectedly contains an error object: {record.attempt_id}")
        if record.generation_options.get("num_predict") != criteria.source_output_token_limit:
            raise ValueError(f"Truncation source has the wrong output limit: {record.attempt_id}")
        if (
            criteria.context_window is not None
            and record.generation_options.get("num_ctx") != criteria.context_window
        ):
            raise ValueError(f"Truncation source has the wrong context window: {record.attempt_id}")
        model = configured[record.model.id]
        if record.model.digest != model.expected_digest:
            raise ValueError(f"Truncation source digest mismatch: {record.attempt_id}")
        selected[key] = record

    counts = {
        model_id: sum(record.model.id == model_id for record in selected.values())
        for model_id in configured
    }
    if counts != criteria.required_repairs_by_model:
        raise ValueError(
            "Truncation repair population changed: "
            + json.dumps({"expected": criteria.required_repairs_by_model, "observed": counts}, sort_keys=True)
        )
    if len(selected) != criteria.expected_repairs:
        raise ValueError(
            f"Expected {criteria.expected_repairs} truncation repairs; found {len(selected)}"
        )
    return selected


def build_truncation_repair_plan(
    config_path: Path,
    criteria_path: Path,
    source_run_dirs: list[Path],
    output_path: Path,
) -> dict[str, Any]:
    study = load_study(config_path)
    criteria = load_truncation_repair_criteria(criteria_path)
    all_models = {model.id: model for model in study.models.models}
    configured = {model_id: all_models[model_id] for model_id in study.config.model_ids}
    sources = select_truncation_sources(source_run_dirs, configured, criteria)
    model_order = list(study.config.model_ids)
    random.Random(criteria.seed).shuffle(model_order)
    repair_order_by_model: dict[str, list[str]] = {}
    source_by_pair = {
        (record.model.id, record.input.image_id): record for record in sources.values()
    }
    for model_id in model_order:
        image_ids = sorted(
            record.input.image_id for record in sources.values() if record.model.id == model_id
        )
        random.Random(f"{criteria.seed}:{model_id}:truncation-repair").shuffle(image_ids)
        repair_order_by_model[model_id] = image_ids
    plan = _plan_payload(criteria, model_order, repair_order_by_model, source_by_pair)
    plan.update(
        {
            "experiment_id": study.config.experiment_id,
            "protocol_version": study.config.protocol_version,
            "study_config_sha256": sha256_file(study.config_path),
            "models_config_sha256": sha256_file(
                resolve_under_root(study.root, study.config.models_config)
            ),
            "criteria_sha256": sha256_file(criteria_path.resolve()),
            "source_run_ids": sorted({record.run_id for record in sources.values()}),
        }
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    return plan


def run_truncation_repair(
    config_path: Path,
    criteria_path: Path,
    source_run_dirs: list[Path],
    base_url: str,
    output_dir: Path,
    run_id: str,
    system_snapshot_ref: str,
    *,
    transport: RepairTransport | None = None,
    progress: Any | None = None,
    max_new_attempts: int | None = None,
) -> tuple[TruncationRepairSummary, Path]:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", run_id):
        raise ValueError("run id must contain only lowercase letters, digits, and hyphens")
    if max_new_attempts is not None and max_new_attempts < 1:
        raise ValueError("max new attempts must be at least one")
    study = load_study(config_path)
    criteria = load_truncation_repair_criteria(criteria_path)
    if study.config.repeats != 1 or study.config.seed != criteria.seed:
        raise ValueError("Truncation repair requires one repeat and the frozen study seed")
    manifest = load_manifest(study.root, study.config.dataset_manifest)
    items = {item.id: item for item in manifest}
    warmup_items = {
        item.id: item for item in load_manifest(study.root, criteria.warmup_manifest)
    }
    if criteria.warmup_image_id not in warmup_items:
        raise ValueError(f"Unknown truncation-repair warm-up image: {criteria.warmup_image_id}")

    all_models = {model.id: model for model in study.models.models}
    configured = {model_id: all_models[model_id] for model_id in study.config.model_ids}
    for model in configured.values():
        if not model.expected_digest:
            raise ValueError(f"{model.id}: immutable digest is required")
    sources = select_truncation_sources(source_run_dirs, configured, criteria)
    source_by_pair = {
        (record.model.id, record.input.image_id): record for record in sources.values()
    }
    missing_images = sorted({record.input.image_id for record in sources.values()} - set(items))
    if missing_images:
        raise ValueError(f"Repair sources reference unknown images: {', '.join(missing_images)}")

    active_transport = transport or OllamaTransport(
        base_url, timeout_seconds=criteria.per_attempt_timeout_seconds
    )
    ollama_version = active_transport.version()
    _verify_live_digests(list(configured.values()), active_transport.tags())

    output_dir.mkdir(parents=True, exist_ok=True)
    warmup_dir = output_dir / "warmups"
    summary_path = output_dir / "truncation-repair-summary.json"
    commit, dirty = _git_state(study.root.parent)
    study_sha = sha256_file(study.config_path)
    models_sha = sha256_file(resolve_under_root(study.root, study.config.models_config))
    criteria_sha = sha256_file(criteria_path.resolve())
    session_started = datetime.now(timezone.utc)
    session_id = session_started.strftime("%Y%m%dT%H%M%S%fZ").lower()

    model_order = list(study.config.model_ids)
    random.Random(criteria.seed).shuffle(model_order)
    repair_order_by_model: dict[str, list[str]] = {}
    for model_id in model_order:
        image_ids = sorted(
            record.input.image_id for record in sources.values() if record.model.id == model_id
        )
        random.Random(f"{criteria.seed}:{model_id}:truncation-repair").shuffle(image_ids)
        repair_order_by_model[model_id] = image_ids

    existing, completed, transports = _existing_attempts(
        output_dir,
        study.config.experiment_id,
        run_id,
        criteria.max_transport_attempts_per_item,
    )
    expected_keys = {
        _key(model_id, image_id)
        for model_id, image_ids in repair_order_by_model.items()
        for image_id in image_ids
    }
    unexpected = sorted(set(existing) - expected_keys)
    if unexpected:
        raise ValueError(f"Repair directory contains unexpected attempts: {', '.join(unexpected[:5])}")
    prior_records = list(existing.values()) + [record for values in transports.values() for record in values]
    started_at = min((record.started_at for record in prior_records), default=session_started)

    schema_path = study.root / "schemas" / "visual-facts.schema.json"
    prompt_path = study.root / "prompts" / "vision-facts-v1.txt"
    schema = VisualFactsPayload.model_json_schema()
    prompt_text = prompt_path.read_text().strip()
    options = {
        "temperature": criteria.temperature,
        "seed": criteria.seed,
        "num_predict": criteria.recovery_output_token_limit,
    }
    if criteria.context_window is not None:
        options["num_ctx"] = criteria.context_window
    _write_plan(output_dir, criteria, model_order, repair_order_by_model, source_by_pair)
    summary = _build_summary(
        study.config.experiment_id, study.config.protocol_version, criteria, run_id,
        ollama_version, started_at, commit, dirty, system_snapshot_ref, study_sha,
        models_sha, criteria_sha, model_order, repair_order_by_model, existing, transports,
        warmup_dir, "running", "", max_new_attempts, 0,
    )
    _write_summary(summary_path, summary)

    abort_attempt_id = ""
    paused = False
    new_attempts = 0
    for block_index, model_id in enumerate(model_order, start=1):
        pending = [
            image_id for image_id in repair_order_by_model[model_id]
            if _key(model_id, image_id) not in completed
        ]
        if not pending:
            continue
        model = configured[model_id]
        warmup = _execute_vision_attempt(
            study.root, study.config.experiment_id, study.config.protocol_version, run_id,
            f"{run_id}-warmup-{model_id}-{session_id}", 1,
            f"repair-block-{block_index:02d}-warmup", commit, dirty, ollama_version,
            system_snapshot_ref, study_sha, models_sha, criteria_sha, model,
            warmup_items[criteria.warmup_image_id], prompt_path, prompt_text, schema_path,
            schema, options, criteria.keep_alive, active_transport,
        )
        warmup_path = write_attempt_record(warmup_dir, warmup)
        _emit(progress, {"event": "warmup_complete", "model_id": model_id,
                         "valid": warmup.validation.valid, "record_path": str(warmup_path)})
        if _is_recoverable_transport(warmup):
            abort_attempt_id = warmup.attempt_id
            break

        for pending_index, image_id in enumerate(pending, start=1):
            key = _key(model_id, image_id)
            prior_transport = transports.get(key, [])
            if len(prior_transport) >= criteria.max_transport_attempts_per_item:
                raise ValueError(f"Transport-attempt limit reached for {key}")
            collection_attempt = len(prior_transport) + 1
            source = source_by_pair[(model_id, image_id)]
            record = _execute_vision_attempt(
                study.root, study.config.experiment_id, study.config.protocol_version, run_id,
                f"{run_id}-{block_index:02d}-{pending_index:03d}-{model_id}-{image_id}-r1-c{collection_attempt}",
                1, f"repair-block-{block_index:02d}", commit, dirty, ollama_version,
                system_snapshot_ref, study_sha, models_sha, criteria_sha, model, items[image_id],
                prompt_path, prompt_text, schema_path, schema, options,
                0 if pending_index == len(pending) else criteria.keep_alive,
                active_transport, collection_attempt=collection_attempt,
                supersedes_attempt_id=(prior_transport[-1].attempt_id if prior_transport else source.attempt_id),
            )
            record = record.model_copy(
                update={
                    "sanitized_request": {
                        **record.sanitized_request,
                        "repair_source_attempt_id": source.attempt_id,
                        "repair_trigger": "done_reason_length",
                    }
                }
            )
            record_path = write_attempt_record(output_dir, record)
            existing[key] = record
            if _is_recoverable_transport(record):
                transports.setdefault(key, []).append(record)
            else:
                completed.add(key)
            new_attempts += 1
            _emit(progress, {"event": "repair_complete", "model_id": model_id,
                             "image_id": image_id, "valid": record.validation.valid,
                             "observed_repairs": len(completed),
                             "expected_repairs": len(expected_keys),
                             "wall_duration_ms": record.telemetry.wall_duration_ms,
                             "record_path": str(record_path)})
            if _is_recoverable_transport(record):
                abort_attempt_id = record.attempt_id
                break
            if max_new_attempts is not None and new_attempts >= max_new_attempts and len(completed) < len(expected_keys):
                paused = True
                break
        if abort_attempt_id or paused:
            break

    status: Literal["paused", "complete", "incomplete"]
    if len(completed) == len(expected_keys) and not abort_attempt_id:
        status = "complete"
    elif paused and not abort_attempt_id:
        status = "paused"
    else:
        status = "incomplete"
    summary = _build_summary(
        study.config.experiment_id, study.config.protocol_version, criteria, run_id,
        ollama_version, started_at, commit, dirty, system_snapshot_ref, study_sha,
        models_sha, criteria_sha, model_order, repair_order_by_model, existing, transports,
        warmup_dir, status, abort_attempt_id, max_new_attempts, new_attempts,
    )
    _write_summary(summary_path, summary)
    return summary, summary_path


def build_truncation_repair_report(
    source_config_paths: list[Path],
    source_run_dirs: list[Path],
    repair_run_dir: Path,
    criteria_path: Path,
    evidence_path: Path,
    report_path: Path,
) -> tuple[Path, Path]:
    criteria = load_truncation_repair_criteria(criteria_path)
    summary = TruncationRepairSummary.model_validate_json(
        (repair_run_dir / "truncation-repair-summary.json").read_text()
    )
    if summary.status != "complete" or summary.expected_repairs != criteria.expected_repairs:
        raise ValueError("Truncation-repair report requires the complete frozen repair population")
    source_resolution = resolve_attempt_records(source_run_dirs)
    repair_resolution = resolve_attempt_records(repair_run_dir)
    if source_resolution.duplicate_keys or repair_resolution.duplicate_keys:
        raise ValueError("Cannot report unresolved duplicate outcome keys")
    if len(repair_resolution.selected) != criteria.expected_repairs:
        raise ValueError("Repair run does not contain the frozen number of outcomes")

    model_order: list[str] = []
    configured: dict[str, ModelEntry] = {}
    for config_path in source_config_paths:
        study = load_study(config_path)
        models = {model.id: model for model in study.models.models}
        for model_id in study.config.model_ids:
            if model_id in configured:
                raise ValueError(f"Source configs repeat model id: {model_id}")
            configured[model_id] = models[model_id]
            model_order.append(model_id)

    repair_by_source_id: dict[str, RunRecord] = {}
    for record in repair_resolution.selected.values():
        source_id = record.sanitized_request.get("repair_source_attempt_id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError(f"Repair record lacks source linkage: {record.attempt_id}")
        if source_id in repair_by_source_id:
            raise ValueError(f"Multiple repairs link to source attempt: {source_id}")
        repair_by_source_id[source_id] = record

    repair_configured = {
        model_id: configured[model_id] for model_id in criteria.required_repairs_by_model
    }
    expected_sources = select_truncation_sources(source_run_dirs, repair_configured, criteria)
    source_by_attempt_id = {record.attempt_id: record for record in expected_sources.values()}
    if set(repair_by_source_id) != set(source_by_attempt_id):
        raise ValueError("Repair records do not match the frozen source-linked population")
    for source_id, repair in repair_by_source_id.items():
        source = source_by_attempt_id[source_id]
        if (
            repair.model.id != source.model.id
            or repair.input.image_id != source.input.image_id
            or repair.generation_options.get("num_predict") != criteria.recovery_output_token_limit
        ):
            raise ValueError(f"Repair record does not preserve its frozen source contract: {repair.attempt_id}")
    if (
        summary.observed_repairs != len(repair_resolution.selected)
        or summary.valid_repairs
        != sum(record.validation.valid for record in repair_resolution.selected.values())
    ):
        raise ValueError("Repair summary accounting does not match immutable records")

    model_results: list[dict[str, Any]] = []
    eligible_challengers: list[str] = []
    for model_id in model_order:
        source_records = [
            record for record in source_resolution.selected.values() if record.model.id == model_id
        ]
        if len(source_records) != 20:
            raise ValueError(f"Expected 20 source outcomes for {model_id}; found {len(source_records)}")
        one_shot_valid = sum(record.validation.valid for record in source_records)
        repaired_sources = [
            record for record in source_records if record.attempt_id in repair_by_source_id
        ]
        successful_repairs = sum(
            repair_by_source_id[record.attempt_id].validation.valid for record in repaired_sources
        )
        pipeline_valid = one_shot_valid + successful_repairs
        pipeline_failures: dict[str, int] = {}
        for source in source_records:
            if source.validation.valid:
                continue
            effective = repair_by_source_id.get(source.attempt_id, source)
            if effective.validation.valid:
                continue
            category = effective_error_category(effective)
            pipeline_failures[category] = pipeline_failures.get(category, 0) + 1
        threshold_met = pipeline_valid / len(source_records) >= 0.95
        if threshold_met and model_id != "qwen25vl-3b-baseline":
            eligible_challengers.append(model_id)
        model = configured[model_id]
        model_results.append(
            {
                "model_id": model_id,
                "ollama_name": model.ollama_name,
                "digest": model.expected_digest,
                "one_shot_valid": one_shot_valid,
                "one_shot_rate": one_shot_valid / len(source_records),
                "planned_truncation_repairs": len(repaired_sources),
                "successful_truncation_repairs": successful_repairs,
                "pipeline_valid": pipeline_valid,
                "pipeline_rate": pipeline_valid / len(source_records),
                "pipeline_threshold_met": threshold_met,
                "pipeline_failure_categories": dict(sorted(pipeline_failures.items())),
            }
        )

    repair_records = list(repair_resolution.selected.values())
    started_at = min(record.started_at for record in repair_records)
    ended_at = max(record.ended_at for record in repair_records)
    baseline_reference = "qwen25vl-3b-baseline"
    quality_screening_set = [baseline_reference, *eligible_challengers]
    evidence = {
        "evidence_version": 1,
        "stage": "Protocol 2.2 explicit output-truncation repair",
        "quality_ranking_permitted": False,
        "one_shot_evidence_preserved": True,
        "repair_run_id": summary.run_id,
        "protocol_version": summary.protocol_version,
        "criteria_id": summary.criteria_id,
        "source_run_ids": sorted({record.run_id for record in source_resolution.all_records}),
        "collection_window": {
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
            "elapsed_hours_including_operational_pauses": round(
                (ended_at - started_at).total_seconds() / 3600, 3
            ),
            "analyzed_repair_wall_hours": round(
                sum(record.telemetry.wall_duration_ms for record in repair_records) / 3_600_000,
                3,
            ),
        },
        "runtime": {
            "ollama_version": summary.ollama_version,
            "system_snapshot_ref": summary.system_snapshot_ref,
            "git_commit": summary.git_commit,
            "tracked_worktree_clean": not summary.dirty_worktree,
            "access_authority": "$davneet-dgx-access",
            "temporary_collection_path": "localhost-only SSH tunnel; public licensed images and fictional contexts only",
        },
        "frozen_repair_contract": {
            "trigger": "invalid source outcome with done_reason=length at 384 tokens",
            "source_output_token_limit": criteria.source_output_token_limit,
            "recovery_output_token_limit": criteria.recovery_output_token_limit,
            "explicit_repair_attempts_per_truncation": criteria.explicit_repair_attempts_per_truncation,
            "timeout_seconds": criteria.per_attempt_timeout_seconds,
            "temperature": criteria.temperature,
            "seed": criteria.seed,
            "thinking_mode": criteria.thinking_mode,
            "context_window": criteria.context_window,
            "quality_retry_permitted": False,
            "timeout_repair_permitted": False,
            "minimum_pipeline_valid_rate": 0.95,
            "criteria_sha256": sha256_file(criteria_path.resolve()),
        },
        "repair_accounting": {
            "expected_repairs": criteria.expected_repairs,
            "observed_repairs": len(repair_records),
            "valid_repairs": sum(record.validation.valid for record in repair_records),
            "failed_repairs": sum(not record.validation.valid for record in repair_records),
            "raw_measured_records": len(repair_resolution.all_records),
            "superseded_transport_records": repair_resolution.superseded_transport_attempts,
            "missing_repairs": 0,
            "unexpected_repairs": 0,
        },
        "results_in_original_then_amendment_order": model_results,
        "advancement": {
            "baseline_reference": baseline_reference,
            "eligible_non_baseline_challengers": eligible_challengers,
            "eligible_challenger_count": len(eligible_challengers),
            "required_eligible_challengers": 2,
            "quality_screening_set": quality_screening_set if len(eligible_challengers) >= 2 else [],
            "status": (
                "ready_for_quality_screening_after_supervisor_acknowledgement"
                if len(eligible_challengers) >= 2
                else "protocol_reassessment_required"
            ),
        },
        "limitations": [
            "Pipeline validity is a system-level outcome and must not be presented as one-shot model validity.",
            (
                "The repair policy was predeclared before isolated collection; the exact repair population was frozen after one-shot failure classification and before any repair call."
                if criteria.context_window is not None
                else "The repair policy was introduced after pilot failure-taxonomy review and before final protocol freeze; both stages must be disclosed."
            ),
            "Compatibility outcomes do not measure factual quality or rank the eligible challengers.",
            "Reviewer-time calibration and supervisor acknowledgement remain required before final protocol freeze.",
        ],
    }
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_render_repair_report(evidence))
    return evidence_path, report_path


def _render_repair_report(evidence: dict[str, Any]) -> str:
    lines = [
        "# Protocol 2.2 truncation-repair report",
        "",
        "This report evaluates explicit system-level truncation handling. It does not rank factual quality, and it preserves the one-shot results separately.",
        "",
        f"- Repairs: `{evidence['repair_accounting']['observed_repairs']}` / `{evidence['repair_accounting']['expected_repairs']}`",
        f"- Valid repairs: `{evidence['repair_accounting']['valid_repairs']}`",
        f"- Hidden, quality, or timeout retries: `0`",
        f"- Pipeline-validity gate: `{evidence['frozen_repair_contract']['minimum_pipeline_valid_rate']:.0%}`",
        "",
        "| Model condition | One-shot | Repairs valid | Pipeline valid | Gate | Remaining failures |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for result in evidence["results_in_original_then_amendment_order"]:
        failures = ", ".join(
            f"{key}: {value}" for key, value in result["pipeline_failure_categories"].items()
        ) or "none"
        lines.append(
            f"| `{result['model_id']}` | {result['one_shot_valid']}/20 | "
            f"{result['successful_truncation_repairs']}/{result['planned_truncation_repairs']} | "
            f"{result['pipeline_valid']}/20 | "
            f"{'pass' if result['pipeline_threshold_met'] else 'fail'} | {failures} |"
        )
    challengers = ", ".join(evidence["advancement"]["eligible_non_baseline_challengers"])
    screening = ", ".join(evidence["advancement"]["quality_screening_set"])
    advancement_ready = (
        evidence["advancement"]["eligible_challenger_count"]
        >= evidence["advancement"]["required_eligible_challengers"]
    )
    if advancement_ready:
        consequence = (
            f"Eligible non-baseline challengers: `{challengers}`. The required count is met. "
            f"The compatibility-screening set is `{screening}`: the baseline reference plus the two eligible challengers. "
            "This set may enter blinded quality screening only after supervisor acknowledgement; no quality winner has been selected."
        )
    else:
        consequence = (
            f"Eligible non-baseline challengers: `{challengers or 'none'}`. The required count is not met, "
            "so no quality-screening set is formed and the protocol requires reassessment before comparative inspection."
        )
    lines.extend(
        [
            "",
            "## Advancement consequence",
            "",
            consequence,
            "",
            "## Limitations",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in evidence["limitations"])
    return "\n".join(lines) + "\n"


def _key(model_id: str, image_id: str) -> str:
    return f"{model_id}|{image_id}|r1"


def _build_summary(
    experiment_id: str, protocol_version: str, criteria: TruncationRepairCriteria,
    run_id: str, ollama_version: str, started_at: datetime, commit: str, dirty: bool,
    system_snapshot_ref: str, study_sha: str, models_sha: str, criteria_sha: str,
    model_order: list[str], repair_order_by_model: dict[str, list[str]],
    records: dict[str, RunRecord], transports: dict[str, list[RunRecord]],
    warmup_dir: Path, status: Literal["running", "paused", "complete", "incomplete"],
    abort_attempt_id: str, max_new_attempts: int | None, new_attempts: int,
) -> TruncationRepairSummary:
    by_model: dict[str, RepairModelResult] = {}
    for model_id in model_order:
        model_records = [record for record in records.values() if record.model.id == model_id]
        valid = sum(record.validation.valid for record in model_records)
        by_model[model_id] = RepairModelResult(
            planned=len(repair_order_by_model[model_id]), observed=len(model_records),
            valid=valid, failed=len(model_records) - valid,
        )
    valid_total = sum(record.validation.valid for record in records.values())
    expected = sum(len(image_ids) for image_ids in repair_order_by_model.values())
    return TruncationRepairSummary(
        status=status, experiment_id=experiment_id, protocol_version=protocol_version,
        criteria_id=criteria.criteria_id, run_id=run_id, ollama_version=ollama_version,
        started_at=started_at, updated_at=datetime.now(timezone.utc), git_commit=commit,
        dirty_worktree=dirty, system_snapshot_ref=system_snapshot_ref,
        study_config_sha256=study_sha, models_config_sha256=models_sha,
        criteria_sha256=criteria_sha, randomization_seed=criteria.seed,
        source_output_token_limit=criteria.source_output_token_limit,
        recovery_output_token_limit=criteria.recovery_output_token_limit,
        timeout_seconds=criteria.per_attempt_timeout_seconds, model_order=model_order,
        repair_order_by_model=repair_order_by_model, expected_repairs=expected,
        observed_repairs=len(records), valid_repairs=valid_total,
        failed_repairs=len(records) - valid_total,
        raw_measured_records=len(attempt_record_paths(warmup_dir.parent)),
        superseded_transport_records=sum(len(values) for values in transports.values()),
        warmup_records=len(attempt_record_paths(warmup_dir)),
        all_truncations_repaired=len(records) == expected and valid_total == expected,
        aborted_on_transport_error=bool(abort_attempt_id),
        abort_attempt_id=abort_attempt_id, max_new_attempts=max_new_attempts,
        new_attempts_this_session=new_attempts, by_model=by_model,
    )


def _write_plan(
    output_dir: Path, criteria: TruncationRepairCriteria, model_order: list[str],
    repair_order_by_model: dict[str, list[str]], source_by_pair: dict[tuple[str, str], RunRecord],
) -> None:
    plan = _plan_payload(criteria, model_order, repair_order_by_model, source_by_pair)
    path = output_dir / "plans" / "truncation-repair-plan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text() != serialized:
        raise ValueError("Existing truncation-repair plan does not match the frozen source population")
    if not path.exists():
        path.write_text(serialized)


def _plan_payload(
    criteria: TruncationRepairCriteria, model_order: list[str],
    repair_order_by_model: dict[str, list[str]], source_by_pair: dict[tuple[str, str], RunRecord],
) -> dict[str, Any]:
    return {
        "plan_version": 1,
        "criteria_id": criteria.criteria_id,
        "trigger": "invalid source outcome with done_reason=length and num_predict=384",
        "quality_retry_permitted": False,
        "timeout_repair_permitted": False,
        "explicit_repair_attempts_per_truncation": 1,
        "source_output_token_limit": criteria.source_output_token_limit,
        "recovery_output_token_limit": criteria.recovery_output_token_limit,
        "timeout_seconds": criteria.per_attempt_timeout_seconds,
        "temperature": criteria.temperature,
        "seed": criteria.seed,
        "thinking_mode": criteria.thinking_mode,
        "expected_repairs": criteria.expected_repairs,
        "required_repairs_by_model": criteria.required_repairs_by_model,
        "model_order": model_order,
        "repairs": [
            {
                "model_id": model_id,
                "image_id": image_id,
                "source_attempt_id": source_by_pair[(model_id, image_id)].attempt_id,
                "source_experiment_id": source_by_pair[(model_id, image_id)].experiment_id,
                "source_run_id": source_by_pair[(model_id, image_id)].run_id,
                "model_digest": source_by_pair[(model_id, image_id)].model.digest,
            }
            for model_id in model_order for image_id in repair_order_by_model[model_id]
        ],
    }


def _write_summary(path: Path, summary: TruncationRepairSummary) -> None:
    path.write_text(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")


def _emit(progress: Any | None, payload: dict[str, Any]) -> None:
    if progress is not None:
        progress(payload)
