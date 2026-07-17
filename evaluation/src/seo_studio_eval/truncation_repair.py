import json
from datetime import datetime, timezone
from pathlib import Path
import random
import re
import tomllib
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from .accounting import resolve_attempt_records
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
