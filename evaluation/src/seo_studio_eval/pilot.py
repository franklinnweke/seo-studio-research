import base64
from collections.abc import Callable
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import tomllib
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from .config import ModelEntry, load_study, resolve_under_root
from .dataset import DatasetItem, load_manifest
from .hashing import sha256_file
from .ollama import OllamaTransport
from .records import attempt_record_paths, read_attempt_record, write_attempt_record
from .runner import AttemptSpec, execute_attempt
from .schemas import InputEvidence, ModelIdentity, PromptEvidence, RunRecord, VisualFactsPayload
from .smoke import _git_state


class PilotTransport(Protocol):
    def version(self) -> str: ...

    def tags(self) -> dict[str, Any]: ...

    def generate(self, request: dict[str, Any]) -> dict[str, Any]: ...


class CompatibilityCriteria(BaseModel):
    schema_version: Literal[1]
    criteria_id: str
    purpose: str
    pilot_items: int = Field(ge=1)
    warmup_manifest: Path
    warmup_image_id: str
    minimum_schema_valid_rate: float = Field(gt=0, le=1)
    per_attempt_timeout_seconds: float = Field(gt=0)
    hidden_retries_allowed: Literal[0]
    abort_on_transport_error: Literal[True]
    temperature: float
    seed: int
    thinking_mode: Literal["disabled"]
    output_token_limit: int = Field(gt=0)
    cold_smoke_keep_alive: int
    pilot_keep_alive: str
    pilot_warm_up_attempts_per_model: Literal[1]
    required_input_modalities: list[str]
    required_evidence: list[str]
    incompatible_replacement_reasons: list[str]
    replacement_quality_inspection_allowed: Literal[False]
    advancement: dict[str, Any]


class ModelPilotResult(BaseModel):
    observed: int = Field(ge=0)
    valid: int = Field(ge=0)
    failed: int = Field(ge=0)
    schema_valid_rate: float = Field(ge=0, le=1)
    threshold_met: bool


class PilotRunSummary(BaseModel):
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
    timeout_seconds: float
    keep_alive: str
    model_order: list[str]
    image_order_by_model: dict[str, list[str]]
    expected_attempts: int = Field(ge=0)
    observed_attempts: int = Field(ge=0)
    valid_attempts: int = Field(ge=0)
    failed_attempts: int = Field(ge=0)
    warmup_records: int = Field(ge=0)
    all_models_meet_threshold: bool
    aborted_on_transport_error: bool
    abort_attempt_id: str = ""
    max_new_attempts: int | None = None
    new_attempts_this_session: int = Field(ge=0)
    by_model: dict[str, ModelPilotResult]


ProgressCallback = Callable[[dict[str, Any]], None]


def load_compatibility_criteria(path: Path) -> CompatibilityCriteria:
    return CompatibilityCriteria.model_validate(tomllib.loads(path.resolve().read_text()))


def run_compatibility_pilot(
    config_path: Path,
    criteria_path: Path,
    base_url: str,
    output_dir: Path,
    run_id: str,
    system_snapshot_ref: str,
    *,
    transport: PilotTransport | None = None,
    progress: ProgressCallback | None = None,
    max_new_attempts: int | None = None,
) -> tuple[PilotRunSummary, Path]:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", run_id):
        raise ValueError("run id must contain only lowercase letters, digits, and hyphens")
    if max_new_attempts is not None and max_new_attempts < 1:
        raise ValueError("max new attempts must be at least one")
    study = load_study(config_path)
    criteria = load_compatibility_criteria(criteria_path)
    if study.config.repeats != 1:
        raise ValueError("The compatibility pilot requires exactly one measured repeat per item")
    manifest = load_manifest(study.root, study.config.dataset_manifest)
    if len(manifest) != criteria.pilot_items:
        raise ValueError(
            f"Compatibility criteria require {criteria.pilot_items} items; manifest contains {len(manifest)}"
        )
    if criteria.seed != study.config.seed:
        raise ValueError("Compatibility and study seeds must match")
    warmup_items = {
        item.id: item for item in load_manifest(study.root, criteria.warmup_manifest)
    }
    if criteria.warmup_image_id not in warmup_items:
        raise ValueError(f"Unknown compatibility warm-up image: {criteria.warmup_image_id}")
    warmup_item = warmup_items[criteria.warmup_image_id]

    configured = {model.id: model for model in study.models.models}
    models = [configured[model_id] for model_id in study.config.model_ids]
    for model in models:
        if not model.expected_digest:
            raise ValueError(f"{model.id}: immutable digest is required before pilot execution")

    active_transport = transport or OllamaTransport(
        base_url,
        timeout_seconds=criteria.per_attempt_timeout_seconds,
    )
    ollama_version = active_transport.version()
    _verify_live_digests(models, active_transport.tags())

    output_dir.mkdir(parents=True, exist_ok=True)
    warmup_dir = output_dir / "warmups"
    summary_path = output_dir / "pilot-summary.json"
    commit, dirty = _git_state(study.root.parent)
    study_config_sha256 = sha256_file(study.config_path)
    models_config_sha256 = sha256_file(resolve_under_root(study.root, study.config.models_config))
    criteria_sha256 = sha256_file(criteria_path.resolve())
    started_at = datetime.now(timezone.utc)
    session_id = started_at.strftime("%Y%m%dT%H%M%S%fZ").lower()
    model_order = [model.id for model in models]
    random.Random(criteria.seed).shuffle(model_order)
    image_order_by_model = {
        model_id: _shuffled_image_ids(manifest, criteria.seed, model_id)
        for model_id in model_order
    }
    existing = _existing_attempts(output_dir, study.config.experiment_id, run_id)
    expected_keys = {
        _attempt_key(model_id, image_id, repeat)
        for model_id in model_order
        for image_id in image_order_by_model[model_id]
        for repeat in range(1, study.config.repeats + 1)
    }
    unexpected = sorted(set(existing) - expected_keys)
    if unexpected:
        raise ValueError(f"Run directory contains unexpected attempts: {', '.join(unexpected[:5])}")

    schema_path = study.root / "schemas" / "visual-facts.schema.json"
    prompt_path = study.root / "prompts" / "vision-facts-v1.txt"
    schema = VisualFactsPayload.model_json_schema()
    prompt_text = prompt_path.read_text().strip()
    options = {
        "temperature": criteria.temperature,
        "seed": criteria.seed,
        "num_predict": criteria.output_token_limit,
    }

    summary = _build_summary(
        study.config.experiment_id,
        study.config.protocol_version,
        criteria,
        run_id,
        ollama_version,
        started_at,
        commit,
        dirty,
        system_snapshot_ref,
        study_config_sha256,
        models_config_sha256,
        criteria_sha256,
        model_order,
        image_order_by_model,
        existing,
        warmup_dir,
        status="running",
        abort_attempt_id="",
        max_new_attempts=max_new_attempts,
        new_attempts_this_session=0,
    )
    _write_summary(summary_path, summary)

    abort_attempt_id = ""
    new_attempts_this_session = 0
    paused = False
    for block_index, model_id in enumerate(model_order, start=1):
        model = configured[model_id]
        pending = [
            (image_id, repeat)
            for repeat in range(1, study.config.repeats + 1)
            for image_id in image_order_by_model[model_id]
            if _attempt_key(model_id, image_id, repeat) not in existing
        ]
        if not pending:
            continue

        warmup_id = f"{run_id}-warmup-{model_id}-{session_id}"
        warmup_record = _execute_vision_attempt(
            study.root,
            study.config.experiment_id,
            study.config.protocol_version,
            run_id,
            warmup_id,
            1,
            f"model-block-{block_index:02d}-warmup",
            commit,
            dirty,
            ollama_version,
            system_snapshot_ref,
            study_config_sha256,
            models_config_sha256,
            criteria_sha256,
            model,
            warmup_item,
            prompt_path,
            prompt_text,
            schema_path,
            schema,
            options,
            criteria.pilot_keep_alive,
            active_transport,
        )
        warmup_path = write_attempt_record(warmup_dir, warmup_record)
        _emit(
            progress,
            {
                "event": "warmup_complete",
                "model_id": model_id,
                "valid": warmup_record.validation.valid,
                "record_path": str(warmup_path),
            },
        )
        if warmup_record.error is not None and warmup_record.error.category == "transport_error":
            abort_attempt_id = warmup_record.attempt_id
            break

        for pending_index, (image_id, repeat) in enumerate(pending, start=1):
            item = next(item for item in manifest if item.id == image_id)
            attempt_id = f"{run_id}-{block_index:02d}-{pending_index:03d}-{model_id}-{image_id}-r{repeat}"
            keep_alive: str | int = (
                0 if pending_index == len(pending) else criteria.pilot_keep_alive
            )
            record = _execute_vision_attempt(
                study.root,
                study.config.experiment_id,
                study.config.protocol_version,
                run_id,
                attempt_id,
                repeat,
                f"model-block-{block_index:02d}",
                commit,
                dirty,
                ollama_version,
                system_snapshot_ref,
                study_config_sha256,
                models_config_sha256,
                criteria_sha256,
                model,
                item,
                prompt_path,
                prompt_text,
                schema_path,
                schema,
                options,
                keep_alive,
                active_transport,
            )
            record_path = write_attempt_record(output_dir, record)
            existing[_attempt_key(model_id, image_id, repeat)] = record
            new_attempts_this_session += 1
            summary = _build_summary(
                study.config.experiment_id,
                study.config.protocol_version,
                criteria,
                run_id,
                ollama_version,
                started_at,
                commit,
                dirty,
                system_snapshot_ref,
                study_config_sha256,
                models_config_sha256,
                criteria_sha256,
                model_order,
                image_order_by_model,
                existing,
                warmup_dir,
                status="running",
                abort_attempt_id=(
                    record.attempt_id
                    if record.error is not None and record.error.category == "transport_error"
                    else ""
                ),
                max_new_attempts=max_new_attempts,
                new_attempts_this_session=new_attempts_this_session,
            )
            _write_summary(summary_path, summary)
            _emit(
                progress,
                {
                    "event": "attempt_complete",
                    "model_id": model_id,
                    "image_id": image_id,
                    "repeat": repeat,
                    "valid": record.validation.valid,
                    "observed_attempts": summary.observed_attempts,
                    "expected_attempts": summary.expected_attempts,
                    "wall_duration_ms": record.telemetry.wall_duration_ms,
                    "record_path": str(record_path),
                },
            )
            if record.error is not None and record.error.category == "transport_error":
                abort_attempt_id = record.attempt_id
                break
            if (
                max_new_attempts is not None
                and new_attempts_this_session >= max_new_attempts
                and len(existing) < len(expected_keys)
            ):
                paused = True
                break
        if abort_attempt_id or paused:
            break

    final_status: Literal["paused", "complete", "incomplete"]
    if len(existing) == len(expected_keys) and not abort_attempt_id:
        final_status = "complete"
    elif paused and not abort_attempt_id:
        final_status = "paused"
    else:
        final_status = "incomplete"
    summary = _build_summary(
        study.config.experiment_id,
        study.config.protocol_version,
        criteria,
        run_id,
        ollama_version,
        started_at,
        commit,
        dirty,
        system_snapshot_ref,
        study_config_sha256,
        models_config_sha256,
        criteria_sha256,
        model_order,
        image_order_by_model,
        existing,
        warmup_dir,
        status=final_status,
        abort_attempt_id=abort_attempt_id,
        max_new_attempts=max_new_attempts,
        new_attempts_this_session=new_attempts_this_session,
    )
    _write_summary(summary_path, summary)
    return summary, summary_path


def _execute_vision_attempt(
    root: Path,
    experiment_id: str,
    protocol_version: str,
    run_id: str,
    attempt_id: str,
    repeat: int,
    randomization_block: str,
    commit: str,
    dirty: bool,
    ollama_version: str,
    system_snapshot_ref: str,
    study_config_sha256: str,
    models_config_sha256: str,
    criteria_sha256: str,
    model: ModelEntry,
    item: DatasetItem,
    prompt_path: Path,
    prompt_text: str,
    schema_path: Path,
    schema: dict[str, Any],
    options: dict[str, Any],
    keep_alive: str | int,
    transport: PilotTransport,
) -> RunRecord:
    image_path = resolve_under_root(root, item.image_path)
    image_base64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    request_payload = {
        "model": model.ollama_name,
        "prompt": prompt_text,
        "images": [image_base64],
        "stream": False,
        "format": schema,
        "think": False,
        "keep_alive": keep_alive,
        "options": options,
    }
    sanitized_request = {
        "model": model.ollama_name,
        "prompt_sha256": sha256_file(prompt_path),
        "image_sha256": item.sha256,
        "format_schema_sha256": sha256_file(schema_path),
        "stream": False,
        "think": False,
        "keep_alive": keep_alive,
        "options": options,
    }
    spec = AttemptSpec(
        experiment_id=experiment_id,
        protocol_version=protocol_version,
        run_id=run_id,
        attempt_id=attempt_id,
        repeat=repeat,
        randomization_block=randomization_block,
        git_commit=commit,
        dirty_worktree=dirty,
        ollama_version=ollama_version,
        system_snapshot_ref=system_snapshot_ref,
        model=ModelIdentity(
            id=model.id,
            ollama_name=model.ollama_name,
            digest=model.expected_digest,
            family=model.family,
            parameters=model.parameters,
            quantization=model.quantization,
            license=model.license,
        ),
        input=InputEvidence(
            image_id=item.id,
            image_sha256=item.sha256,
            dataset_stratum=item.domain,
            purpose=item.purpose,
            page_context_sha256=item.page_context_sha256,
            brand_profile_sha256=item.brand_profile_sha256,
        ),
        prompt=PromptEvidence(
            prompt_id="vision-facts-v1",
            prompt_sha256=sha256_file(prompt_path),
            schema_sha256=sha256_file(schema_path),
            system_prompt_sha256=sha256_file(prompt_path),
        ),
        generation_options=options,
        thinking_mode="disabled",
        sanitized_request=sanitized_request,
        study_config_sha256=study_config_sha256,
        models_config_sha256=models_config_sha256,
        criteria_sha256=criteria_sha256,
    )
    return execute_attempt(
        spec,
        transport,
        request_payload=request_payload,
        response_model=VisualFactsPayload,
    )


def _verify_live_digests(models: list[ModelEntry], payload: dict[str, Any]) -> None:
    raw_models = payload.get("models")
    if not isinstance(raw_models, list):
        raise ValueError("Ollama tags response is missing models")
    live: dict[str, str] = {}
    for entry in raw_models:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name") or entry.get("model")
        digest = entry.get("digest")
        if isinstance(name, str) and isinstance(digest, str):
            live[name] = digest
    errors = [
        f"{model.id}: expected {model.expected_digest}, live {live.get(model.ollama_name, 'missing')}"
        for model in models
        if live.get(model.ollama_name) != model.expected_digest
    ]
    if errors:
        raise ValueError("Live model identity mismatch: " + "; ".join(errors))


def _existing_attempts(
    output_dir: Path,
    experiment_id: str,
    run_id: str,
) -> dict[str, RunRecord]:
    records: dict[str, RunRecord] = {}
    for path in attempt_record_paths(output_dir):
        record = read_attempt_record(path)
        if record.experiment_id != experiment_id or record.run_id != run_id:
            raise ValueError(f"Run directory mixes experiment identities: {path.name}")
        key = _attempt_key(record.model.id, record.input.image_id, record.repeat)
        if key in records:
            raise ValueError(f"Run directory contains duplicate attempt key: {key}")
        records[key] = record
    return records


def _build_summary(
    experiment_id: str,
    protocol_version: str,
    criteria: CompatibilityCriteria,
    run_id: str,
    ollama_version: str,
    started_at: datetime,
    commit: str,
    dirty: bool,
    system_snapshot_ref: str,
    study_config_sha256: str,
    models_config_sha256: str,
    criteria_sha256: str,
    model_order: list[str],
    image_order_by_model: dict[str, list[str]],
    records: dict[str, RunRecord],
    warmup_dir: Path,
    status: Literal["running", "paused", "complete", "incomplete"],
    abort_attempt_id: str,
    max_new_attempts: int | None,
    new_attempts_this_session: int,
) -> PilotRunSummary:
    by_model: dict[str, ModelPilotResult] = {}
    for model_id in model_order:
        model_records = [record for record in records.values() if record.model.id == model_id]
        valid = sum(record.validation.valid for record in model_records)
        observed = len(model_records)
        rate = valid / observed if observed else 0.0
        by_model[model_id] = ModelPilotResult(
            observed=observed,
            valid=valid,
            failed=observed - valid,
            schema_valid_rate=rate,
            threshold_met=(
                observed == criteria.pilot_items and rate >= criteria.minimum_schema_valid_rate
            ),
        )
    expected = criteria.pilot_items * len(model_order)
    valid_total = sum(record.validation.valid for record in records.values())
    return PilotRunSummary(
        status=status,
        experiment_id=experiment_id,
        protocol_version=protocol_version,
        criteria_id=criteria.criteria_id,
        run_id=run_id,
        ollama_version=ollama_version,
        started_at=started_at,
        updated_at=datetime.now(timezone.utc),
        git_commit=commit,
        dirty_worktree=dirty,
        system_snapshot_ref=system_snapshot_ref,
        study_config_sha256=study_config_sha256,
        models_config_sha256=models_config_sha256,
        criteria_sha256=criteria_sha256,
        randomization_seed=criteria.seed,
        timeout_seconds=criteria.per_attempt_timeout_seconds,
        keep_alive=criteria.pilot_keep_alive,
        model_order=model_order,
        image_order_by_model=image_order_by_model,
        expected_attempts=expected,
        observed_attempts=len(records),
        valid_attempts=valid_total,
        failed_attempts=len(records) - valid_total,
        warmup_records=len(attempt_record_paths(warmup_dir)),
        all_models_meet_threshold=all(result.threshold_met for result in by_model.values()),
        aborted_on_transport_error=bool(abort_attempt_id),
        abort_attempt_id=abort_attempt_id,
        max_new_attempts=max_new_attempts,
        new_attempts_this_session=new_attempts_this_session,
        by_model=by_model,
    )


def _write_summary(path: Path, summary: PilotRunSummary) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _shuffled_image_ids(items: list[DatasetItem], seed: int, model_id: str) -> list[str]:
    image_ids = [item.id for item in items]
    derived = int.from_bytes(
        hashlib.sha256(f"{seed}:{model_id}".encode()).digest()[:8],
        byteorder="big",
    )
    random.Random(derived).shuffle(image_ids)
    return image_ids


def _attempt_key(model_id: str, image_id: str, repeat: int) -> str:
    return f"{model_id}|{image_id}|r{repeat}"


def _emit(progress: ProgressCallback | None, payload: dict[str, Any]) -> None:
    if progress is not None:
        progress(payload)
