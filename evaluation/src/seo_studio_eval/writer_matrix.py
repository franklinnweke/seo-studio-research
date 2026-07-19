import json
import random
from dataclasses import dataclass
from pathlib import Path
import tomllib
from typing import Any, Callable, Literal, Protocol

from pydantic import BaseModel, Field, model_validator

from .accounting import effective_error_category, resolve_attempt_records
from .config import ModelEntry, load_study, resolve_under_root
from .dataset import DatasetItem, load_manifest
from .hashing import sha256_file, sha256_text
from .ollama import OllamaTransport
from .pilot import _verify_live_digests
from .records import attempt_record_paths, read_attempt_record, write_attempt_record
from .runner import AttemptSpec, execute_attempt
from .schemas import (
    ContextualMetadataPayload,
    InputEvidence,
    ModelIdentity,
    PromptEvidence,
    RunRecord,
)
from .smoke import _git_state
from .writer_compatibility import _validate_purpose, _writer_prompt


class WriterMatrixTransport(Protocol):
    def version(self) -> str: ...

    def tags(self) -> dict[str, Any]: ...

    def generate(self, request: dict[str, Any]) -> dict[str, Any]: ...


class WriterMatrixCriteria(BaseModel):
    schema_version: Literal[1]
    criteria_id: str
    experiment_id: str
    protocol_version: str
    source_run_id: str
    repair_run_id: str
    source_model_ids: list[str] = Field(min_length=1)
    writer_model_id: str
    prompt_id: str
    temperature: float
    seed: int
    thinking_mode: Literal["disabled"]
    context_window: int = Field(gt=0)
    output_token_limit: int = Field(gt=0)
    per_attempt_timeout_seconds: float = Field(gt=0)
    keep_alive: str
    hidden_retries_allowed: Literal[0]
    max_transport_attempts_per_cell: int = Field(ge=1)
    expected_source_cells: int = Field(gt=0)
    expected_writer_calls: int = Field(gt=0)
    expected_upstream_failures: int = Field(ge=0)
    pixels_sent_to_writer: Literal[False]
    validation_retries_allowed: Literal[0]

    @model_validator(mode="after")
    def validate_population(self) -> "WriterMatrixCriteria":
        if len(self.source_model_ids) != len(set(self.source_model_ids)):
            raise ValueError("source_model_ids must be unique")
        if self.expected_writer_calls + self.expected_upstream_failures != self.expected_source_cells:
            raise ValueError("writer calls plus upstream failures must equal source cells")
        return self


@dataclass(frozen=True)
class EffectiveFactCell:
    source: RunRecord
    effective: RunRecord
    repair_attempt_id: str = ""

    @property
    def key(self) -> str:
        return writer_cell_key(self.source.model.id, self.source.input.image_id, self.source.repeat)


class WriterMatrixConditionSummary(BaseModel):
    source_cells: int = Field(ge=0)
    upstream_valid_facts: int = Field(ge=0)
    upstream_failures: int = Field(ge=0)
    writer_outcomes: int = Field(ge=0)
    writer_valid: int = Field(ge=0)
    writer_failed: int = Field(ge=0)


class WriterMatrixSummary(BaseModel):
    status: Literal["complete", "paused", "incomplete"]
    criteria_id: str
    run_id: str
    source_run_id: str
    repair_run_id: str
    writer_model_id: str
    writer_digest: str
    ollama_version: str
    expected_source_cells: int
    observed_source_cells: int
    expected_writer_calls: int
    observed_writer_outcomes: int
    valid_writer_outcomes: int
    failed_writer_outcomes: int
    upstream_failures: int
    raw_writer_records: int
    superseded_transport_records: int
    pending_writer_calls: int
    pixels_sent_to_writer: bool
    comparative_quality_inspected: Literal[False] = False
    git_commits: list[str]
    study_config_sha256: str
    models_config_sha256: str
    criteria_sha256: str
    prompt_template_sha256: str
    schema_sha256: str
    by_source_model: dict[str, WriterMatrixConditionSummary]


def load_writer_matrix_criteria(path: Path) -> WriterMatrixCriteria:
    return WriterMatrixCriteria.model_validate(tomllib.loads(path.resolve().read_text()))


def resolve_effective_fact_cells(
    source_run_dirs: list[Path],
    repair_run_dirs: list[Path],
    source_model_ids: list[str],
) -> list[EffectiveFactCell]:
    source_resolution = resolve_attempt_records(source_run_dirs)
    if source_resolution.duplicate_keys:
        raise ValueError(
            "Source runs contain unresolved duplicate outcomes: "
            + ", ".join(source_resolution.duplicate_keys)
        )
    selected_sources = [
        record
        for record in source_resolution.selected.values()
        if record.model.id in source_model_ids
    ]
    observed_models = {record.model.id for record in selected_sources}
    missing_models = sorted(set(source_model_ids) - observed_models)
    if missing_models:
        raise ValueError("Source outcomes are missing models: " + ", ".join(missing_models))

    source_by_attempt_id = {record.attempt_id: record for record in selected_sources}
    repairs_by_source_id: dict[str, RunRecord] = {}
    if repair_run_dirs:
        repair_resolution = resolve_attempt_records(repair_run_dirs)
        if repair_resolution.duplicate_keys:
            raise ValueError(
                "Repair runs contain unresolved duplicate outcomes: "
                + ", ".join(repair_resolution.duplicate_keys)
            )
        for repair in repair_resolution.selected.values():
            if repair.model.id not in source_model_ids:
                continue
            source_id = repair.sanitized_request.get("repair_source_attempt_id")
            if not isinstance(source_id, str) or source_id not in source_by_attempt_id:
                raise ValueError(f"Repair has invalid source linkage: {repair.attempt_id}")
            source = source_by_attempt_id[source_id]
            if source.validation.valid or source.done_reason != "length":
                raise ValueError(f"Repair source is not a length-truncated outcome: {repair.attempt_id}")
            if (
                repair.model.id != source.model.id
                or repair.input.image_id != source.input.image_id
                or repair.repeat != source.repeat
            ):
                raise ValueError(f"Repair does not preserve source identity: {repair.attempt_id}")
            if source_id in repairs_by_source_id:
                raise ValueError(f"Multiple repairs reference source attempt: {source_id}")
            repairs_by_source_id[source_id] = repair

    cells = [
        EffectiveFactCell(
            source=source,
            effective=repairs_by_source_id.get(source.attempt_id, source),
            repair_attempt_id=(
                repairs_by_source_id[source.attempt_id].attempt_id
                if source.attempt_id in repairs_by_source_id
                else ""
            ),
        )
        for source in selected_sources
    ]
    keys = [cell.key for cell in cells]
    if len(keys) != len(set(keys)):
        raise ValueError("Effective fact population contains duplicate condition/image/repeat cells")
    return sorted(cells, key=lambda cell: cell.key)


def resolve_writer_matrix_records(
    output_dir: Path,
    criteria: WriterMatrixCriteria,
    run_id: str,
) -> dict[str, list[RunRecord]]:
    grouped: dict[str, list[RunRecord]] = {}
    for path in attempt_record_paths(output_dir):
        record = read_attempt_record(path)
        if record.experiment_id != criteria.experiment_id or record.run_id != run_id:
            raise ValueError(f"Writer matrix directory mixes experiment identities: {path.name}")
        source_model_id = record.sanitized_request.get("source_vision_model_id")
        source_image_id = record.sanitized_request.get("source_image_id")
        source_repeat = record.sanitized_request.get("source_repeat")
        if source_model_id not in criteria.source_model_ids:
            raise ValueError(f"Writer record has unknown source model: {path.name}")
        if source_image_id != record.input.image_id or source_repeat != record.repeat:
            raise ValueError(f"Writer record does not preserve source cell identity: {path.name}")
        key = writer_cell_key(str(source_model_id), str(source_image_id), int(source_repeat))
        grouped.setdefault(key, []).append(record)
    for key, records in grouped.items():
        records.sort(key=lambda record: (record.collection_attempt, record.started_at))
        if len({record.collection_attempt for record in records}) != len(records):
            raise ValueError(f"Writer cell repeats a collection attempt: {key}")
        outcomes = [record for record in records if not is_recoverable_transport(record)]
        if len(outcomes) > 1:
            raise ValueError(f"Writer cell contains multiple final outcomes: {key}")
    return grouped


def run_writer_matrix(
    config_path: Path,
    criteria_path: Path,
    source_run_dirs: list[Path],
    repair_run_dirs: list[Path],
    base_url: str,
    output_dir: Path,
    run_id: str,
    system_snapshot_ref: str,
    *,
    transport: WriterMatrixTransport | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
    max_new_attempts: int | None = None,
) -> tuple[WriterMatrixSummary, Path]:
    study = load_study(config_path)
    criteria = load_writer_matrix_criteria(criteria_path)
    if max_new_attempts is not None and max_new_attempts < 1:
        raise ValueError("max_new_attempts must be at least one")
    source_summary = json.loads((source_run_dirs[0] / "pilot-summary.json").read_text())
    if source_summary.get("status") != "complete" or source_summary.get("run_id") != criteria.source_run_id:
        raise ValueError("Writer matrix requires the declared complete source pilot")
    repair_summary = json.loads((repair_run_dirs[0] / "truncation-repair-summary.json").read_text())
    if (
        repair_summary.get("status") != "complete"
        or repair_summary.get("run_id") != criteria.repair_run_id
    ):
        raise ValueError("Writer matrix requires the declared truncation-repair run")

    configured = {model.id: model for model in study.models.models}
    unknown = sorted(set(criteria.source_model_ids + [criteria.writer_model_id]) - set(configured))
    if unknown:
        raise ValueError("Writer criteria references unknown models: " + ", ".join(unknown))
    writer = configured[criteria.writer_model_id]
    if not writer.expected_digest:
        raise ValueError("Writer model requires a configured immutable digest")
    cells = resolve_effective_fact_cells(source_run_dirs, repair_run_dirs, criteria.source_model_ids)
    upstream_valid = [cell for cell in cells if cell.effective.validation.valid]
    upstream_failed = [cell for cell in cells if not cell.effective.validation.valid]
    if len(cells) != criteria.expected_source_cells:
        raise ValueError(f"Expected {criteria.expected_source_cells} source cells, found {len(cells)}")
    if len(upstream_valid) != criteria.expected_writer_calls:
        raise ValueError(f"Expected {criteria.expected_writer_calls} writer calls, found {len(upstream_valid)}")
    if len(upstream_failed) != criteria.expected_upstream_failures:
        raise ValueError(
            f"Expected {criteria.expected_upstream_failures} upstream failures, found {len(upstream_failed)}"
        )
    manifest = {item.id: item for item in load_manifest(study.root, study.config.dataset_manifest)}
    missing_images = sorted({cell.source.input.image_id for cell in cells} - set(manifest))
    if missing_images:
        raise ValueError("Writer source cells reference unknown images: " + ", ".join(missing_images))

    active_transport = transport or OllamaTransport(
        base_url, timeout_seconds=criteria.per_attempt_timeout_seconds
    )
    ollama_version = active_transport.version()
    _verify_live_digests([writer], active_transport.tags())
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "writer-matrix-summary.json"
    existing = resolve_writer_matrix_records(output_dir, criteria, run_id)
    ordered = upstream_valid.copy()
    random.Random(criteria.seed).shuffle(ordered)
    prompt_path = study.root / "prompts" / "context-writer-v1.txt"
    schema_path = study.root / "schemas" / "metadata.schema.json"
    schema = ContextualMetadataPayload.model_json_schema()
    options = {
        "temperature": criteria.temperature,
        "seed": criteria.seed,
        "num_ctx": criteria.context_window,
        "num_predict": criteria.output_token_limit,
    }
    commit, dirty = _git_state(study.root.parent)
    new_attempts = 0

    for ordinal, cell in enumerate(ordered, start=1):
        prior = existing.get(cell.key, [])
        if any(not is_recoverable_transport(record) for record in prior):
            continue
        transports = [record for record in prior if is_recoverable_transport(record)]
        if len(transports) >= criteria.max_transport_attempts_per_cell:
            raise ValueError(f"Writer transport-attempt limit reached: {cell.key}")
        if max_new_attempts is not None and new_attempts >= max_new_attempts:
            break
        collection_attempt = len(transports) + 1
        attempt_id = (
            f"{run_id}-{ordinal:03d}-{cell.source.model.id}-"
            f"{cell.source.input.image_id}-r{cell.source.repeat}-c{collection_attempt}"
        )
        pending_after_this = sum(
            not any(not is_recoverable_transport(record) for record in existing.get(other.key, []))
            for other in ordered[ordinal:]
        )
        keep_alive: str | int = 0 if pending_after_this == 0 else criteria.keep_alive
        record = _execute_writer_matrix_attempt(
            study.root,
            criteria,
            run_id,
            attempt_id,
            cell,
            manifest[cell.source.input.image_id],
            writer,
            commit,
            dirty,
            ollama_version,
            system_snapshot_ref,
            sha256_file(study.config_path),
            sha256_file(resolve_under_root(study.root, study.config.models_config)),
            sha256_file(criteria_path.resolve()),
            prompt_path,
            schema_path,
            schema,
            options,
            keep_alive,
            active_transport,
            collection_attempt,
            transports[-1].attempt_id if transports else "",
        )
        write_attempt_record(output_dir, record)
        existing.setdefault(cell.key, []).append(record)
        new_attempts += 1
        summary = _build_writer_matrix_summary(
            criteria, run_id, writer, ollama_version, cells, existing,
            sha256_file(study.config_path),
            sha256_file(resolve_under_root(study.root, study.config.models_config)),
            sha256_file(criteria_path.resolve()), sha256_file(prompt_path), sha256_file(schema_path),
        )
        _write_summary(summary_path, summary)
        if progress is not None:
            progress({
                "event": "writer_cell_complete",
                "ordinal": ordinal,
                "source_cells": len(cells),
                "writer_calls_expected": criteria.expected_writer_calls,
                "writer_outcomes_observed": summary.observed_writer_outcomes,
                "pending_writer_calls": summary.pending_writer_calls,
                "valid": record.validation.valid,
                "failure_category": (
                    "" if record.validation.valid else effective_error_category(record)
                ),
            })
        if is_recoverable_transport(record):
            summary = summary.model_copy(update={"status": "paused"})
            _write_summary(summary_path, summary)
            return summary, summary_path

    summary = _build_writer_matrix_summary(
        criteria, run_id, writer, ollama_version, cells, existing,
        sha256_file(study.config_path),
        sha256_file(resolve_under_root(study.root, study.config.models_config)),
        sha256_file(criteria_path.resolve()), sha256_file(prompt_path), sha256_file(schema_path),
    )
    if summary.pending_writer_calls and max_new_attempts is not None:
        summary = summary.model_copy(update={"status": "paused"})
    _write_summary(summary_path, summary)
    return summary, summary_path


def _execute_writer_matrix_attempt(
    root: Path,
    criteria: WriterMatrixCriteria,
    run_id: str,
    attempt_id: str,
    cell: EffectiveFactCell,
    item: DatasetItem,
    writer: ModelEntry,
    commit: str,
    dirty: bool,
    ollama_version: str,
    system_snapshot_ref: str,
    study_config_sha256: str,
    models_config_sha256: str,
    criteria_sha256: str,
    prompt_path: Path,
    schema_path: Path,
    schema: dict[str, Any],
    options: dict[str, Any],
    keep_alive: str | int,
    transport: WriterMatrixTransport,
    collection_attempt: int,
    supersedes_attempt_id: str,
) -> RunRecord:
    page_context = json.loads(resolve_under_root(root, item.page_context_path).read_text())
    brand_context = json.loads(resolve_under_root(root, item.brand_profile_path).read_text())
    confirmed_purpose = {"purpose": item.purpose, "purpose_confirmed": True}
    prompt = _writer_prompt(
        prompt_path.read_text().strip(),
        cell.effective.parsed_payload or {},
        page_context,
        brand_context,
        confirmed_purpose,
    )
    request_payload = {
        "model": writer.ollama_name,
        "prompt": prompt,
        "stream": False,
        "format": schema,
        "think": False,
        "keep_alive": keep_alive,
        "options": options,
    }
    spec = AttemptSpec(
        experiment_id=criteria.experiment_id,
        protocol_version=criteria.protocol_version,
        run_id=run_id,
        attempt_id=attempt_id,
        repeat=cell.source.repeat,
        randomization_block=f"facts-source-{cell.source.model.id}",
        git_commit=commit,
        dirty_worktree=dirty,
        ollama_version=ollama_version,
        system_snapshot_ref=system_snapshot_ref,
        model=ModelIdentity(
            id=writer.id,
            ollama_name=writer.ollama_name,
            digest=writer.expected_digest,
            family=writer.family,
            parameters=writer.parameters,
            quantization=writer.quantization,
            license=writer.license,
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
            prompt_id=criteria.prompt_id,
            prompt_sha256=sha256_text(prompt),
            schema_sha256=sha256_file(schema_path),
            system_prompt_sha256=sha256_text(""),
        ),
        generation_options=options,
        thinking_mode="disabled",
        sanitized_request={
            "model": writer.ollama_name,
            "source_vision_model_id": cell.source.model.id,
            "source_image_id": item.id,
            "source_repeat": cell.source.repeat,
            "source_one_shot_attempt_id": cell.source.attempt_id,
            "source_fact_attempt_id": cell.effective.attempt_id,
            "source_repair_attempt_id": cell.repair_attempt_id,
            "source_fact_digest": cell.effective.model.digest,
            "prompt_sha256": sha256_text(prompt),
            "page_context_sha256": item.page_context_sha256,
            "brand_profile_sha256": item.brand_profile_sha256,
            "purpose": item.purpose,
            "pixels_sent_to_writer": False,
            "stream": False,
            "think": False,
            "keep_alive": keep_alive,
            "options": options,
        },
        study_config_sha256=study_config_sha256,
        models_config_sha256=models_config_sha256,
        criteria_sha256=criteria_sha256,
        collection_attempt=collection_attempt,
        supersedes_attempt_id=supersedes_attempt_id,
    )
    return _validate_purpose(
        execute_attempt(
            spec,
            transport,
            request_payload=request_payload,
            response_model=ContextualMetadataPayload,
        ),
        item.purpose,
    )


def _build_writer_matrix_summary(
    criteria: WriterMatrixCriteria,
    run_id: str,
    writer: ModelEntry,
    ollama_version: str,
    cells: list[EffectiveFactCell],
    existing: dict[str, list[RunRecord]],
    study_config_sha256: str,
    models_config_sha256: str,
    criteria_sha256: str,
    prompt_template_sha256: str,
    schema_sha256: str,
) -> WriterMatrixSummary:
    outcomes: dict[str, RunRecord] = {}
    superseded = 0
    raw_records = [record for records in existing.values() for record in records]
    for key, records in existing.items():
        final = [record for record in records if not is_recoverable_transport(record)]
        if final:
            outcomes[key] = final[0]
            superseded += sum(is_recoverable_transport(record) for record in records)
    by_model: dict[str, WriterMatrixConditionSummary] = {}
    for model_id in criteria.source_model_ids:
        model_cells = [cell for cell in cells if cell.source.model.id == model_id]
        model_outcomes = [outcomes[cell.key] for cell in model_cells if cell.key in outcomes]
        by_model[model_id] = WriterMatrixConditionSummary(
            source_cells=len(model_cells),
            upstream_valid_facts=sum(cell.effective.validation.valid for cell in model_cells),
            upstream_failures=sum(not cell.effective.validation.valid for cell in model_cells),
            writer_outcomes=len(model_outcomes),
            writer_valid=sum(record.validation.valid for record in model_outcomes),
            writer_failed=sum(not record.validation.valid for record in model_outcomes),
        )
    observed = len(outcomes)
    pending = criteria.expected_writer_calls - observed
    return WriterMatrixSummary(
        status="complete" if pending == 0 else "incomplete",
        criteria_id=criteria.criteria_id,
        run_id=run_id,
        source_run_id=criteria.source_run_id,
        repair_run_id=criteria.repair_run_id,
        writer_model_id=writer.id,
        writer_digest=writer.expected_digest,
        ollama_version=ollama_version,
        expected_source_cells=criteria.expected_source_cells,
        observed_source_cells=len(cells),
        expected_writer_calls=criteria.expected_writer_calls,
        observed_writer_outcomes=observed,
        valid_writer_outcomes=sum(record.validation.valid for record in outcomes.values()),
        failed_writer_outcomes=sum(not record.validation.valid for record in outcomes.values()),
        upstream_failures=sum(not cell.effective.validation.valid for cell in cells),
        raw_writer_records=len(raw_records),
        superseded_transport_records=superseded,
        pending_writer_calls=pending,
        pixels_sent_to_writer=False,
        git_commits=sorted({record.git_commit for record in raw_records}),
        study_config_sha256=study_config_sha256,
        models_config_sha256=models_config_sha256,
        criteria_sha256=criteria_sha256,
        prompt_template_sha256=prompt_template_sha256,
        schema_sha256=schema_sha256,
        by_source_model=by_model,
    )


def is_recoverable_transport(record: RunRecord) -> bool:
    return effective_error_category(record) == "transport_error"


def writer_cell_key(model_id: str, image_id: str, repeat: int) -> str:
    return f"{model_id}|{image_id}|r{repeat}"


def _write_summary(path: Path, summary: WriterMatrixSummary) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
    temporary.replace(path)
