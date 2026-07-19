import json
from pathlib import Path
from typing import Any, Literal
import unicodedata

from pydantic import BaseModel, Field

from .accounting import effective_error_category, resolve_attempt_records
from .schemas import RunRecord


class NormalizedRecord(BaseModel):
    normalization_version: Literal["normalization-v1", "normalization-v2"] = "normalization-v2"
    experiment_id: str
    attempt_id: str
    source_attempt_id: str = ""
    effective_attempt_id: str = ""
    repair_attempt_id: str = ""
    writer_attempt_id: str = ""
    pipeline_stage: Literal[
        "one_shot",
        "protocol_2_2_repair",
        "fixed_writer",
        "upstream_failure",
    ] = "one_shot"
    image_id: str
    repeat: int = Field(ge=1)
    model_id: str
    model_name: str
    valid: bool
    validation_errors: list[str] = Field(default_factory=list)
    error_category: str = ""
    output: dict[str, Any] | None = None


class NormalizationSummary(BaseModel):
    status: Literal["normalized", "invalid"]
    records_checked: int = Field(ge=0)
    records_written: int = Field(ge=0)
    source_outcomes_selected: int = Field(default=0, ge=0)
    repairs_applied: int = Field(default=0, ge=0)
    valid_pipeline_outcomes: int = Field(default=0, ge=0)
    invalid_pipeline_outcomes: int = Field(default=0, ge=0)
    superseded_transport_records: int = Field(default=0, ge=0)
    writer_outcomes_applied: int = Field(default=0, ge=0)
    writer_valid_outcomes: int = Field(default=0, ge=0)
    writer_failed_outcomes: int = Field(default=0, ge=0)
    upstream_failures_preserved: int = Field(default=0, ge=0)
    selected_models: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


def normalize_run_directory(run_dir: Path, output_dir: Path) -> tuple[NormalizationSummary, Path]:
    return normalize_run_directories([run_dir], output_dir)


def normalize_run_directories(
    run_dirs: list[Path],
    output_dir: Path,
    *,
    model_ids: list[str] | None = None,
    repair_run_dirs: list[Path] | None = None,
) -> tuple[NormalizationSummary, Path]:
    errors: list[str] = []
    normalized: list[NormalizedRecord] = []
    if not run_dirs:
        raise ValueError("At least one run directory is required")
    if model_ids is not None and len(model_ids) != len(set(model_ids)):
        raise ValueError("Normalization model filters must be unique")

    source_resolution = resolve_attempt_records(run_dirs)
    if not source_resolution.all_records:
        errors.append("No attempt records found")
    if source_resolution.duplicate_keys:
        errors.append(
            "Source runs contain unresolved duplicate outcomes: "
            + ", ".join(source_resolution.duplicate_keys)
        )
    available_models = sorted({record.model.id for record in source_resolution.selected.values()})
    selected_models = model_ids or available_models
    unknown_models = sorted(set(selected_models) - set(available_models))
    if unknown_models:
        errors.append(f"Selected models are absent from source outcomes: {', '.join(unknown_models)}")

    selected_sources = [
        record
        for record in source_resolution.selected.values()
        if record.model.id in selected_models
    ]
    source_by_attempt_id = {record.attempt_id: record for record in selected_sources}
    repairs_by_source_id: dict[str, RunRecord] = {}
    repair_resolution = None
    if repair_run_dirs:
        repair_resolution = resolve_attempt_records(repair_run_dirs)
        if repair_resolution.duplicate_keys:
            errors.append(
                "Repair runs contain unresolved duplicate outcomes: "
                + ", ".join(repair_resolution.duplicate_keys)
            )
        for repair in repair_resolution.selected.values():
            if repair.model.id not in selected_models:
                continue
            source_id = repair.sanitized_request.get("repair_source_attempt_id")
            if not isinstance(source_id, str) or not source_id:
                errors.append(f"Repair lacks source linkage: {repair.attempt_id}")
                continue
            source = source_by_attempt_id.get(source_id)
            if source is None:
                errors.append(f"Repair references an unselected source: {repair.attempt_id}")
                continue
            if source.validation.valid or source.done_reason != "length":
                errors.append(f"Repair source is not a length-truncated outcome: {repair.attempt_id}")
                continue
            if (
                repair.model.id != source.model.id
                or repair.input.image_id != source.input.image_id
                or repair.repeat != source.repeat
            ):
                errors.append(f"Repair does not preserve source identity: {repair.attempt_id}")
                continue
            if source_id in repairs_by_source_id:
                errors.append(f"Multiple repairs reference source attempt: {source_id}")
                continue
            repairs_by_source_id[source_id] = repair

    for source in sorted(
        selected_sources,
        key=lambda record: (record.model.id, record.input.image_id, record.repeat),
    ):
        try:
            effective = repairs_by_source_id.get(source.attempt_id, source)
            repair_applied = effective is not source
            normalized.append(
                NormalizedRecord(
                    experiment_id=source.experiment_id,
                    attempt_id=effective.attempt_id,
                    source_attempt_id=source.attempt_id,
                    effective_attempt_id=effective.attempt_id,
                    repair_attempt_id=effective.attempt_id if repair_applied else "",
                    pipeline_stage="protocol_2_2_repair" if repair_applied else "one_shot",
                    image_id=source.input.image_id,
                    repeat=source.repeat,
                    model_id=source.model.id,
                    model_name=source.model.ollama_name,
                    valid=effective.validation.valid,
                    validation_errors=effective.validation.errors,
                    error_category=(
                        "" if effective.validation.valid else effective_error_category(effective)
                    ),
                    output=_normalize_value(effective.parsed_payload),
                )
            )
        except (OSError, ValueError) as exc:
            errors.append(f"{source.attempt_id}: {exc}")

    attempt_ids = [record.attempt_id for record in normalized]
    duplicates = sorted({attempt_id for attempt_id in attempt_ids if attempt_ids.count(attempt_id) > 1})
    if duplicates:
        errors.append(f"Duplicate attempt ids: {', '.join(duplicates)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "records.normalization-v2.jsonl"
    with output_path.open("w", encoding="utf-8") as output:
        for record in normalized:
            output.write(json.dumps(record.model_dump(mode="json"), sort_keys=True) + "\n")

    summary = NormalizationSummary(
        status="normalized" if not errors else "invalid",
        records_checked=(
            len(source_resolution.all_records)
            + (len(repair_resolution.all_records) if repair_resolution is not None else 0)
        ),
        records_written=len(normalized),
        source_outcomes_selected=len(selected_sources),
        repairs_applied=len(repairs_by_source_id),
        valid_pipeline_outcomes=sum(record.valid for record in normalized),
        invalid_pipeline_outcomes=sum(not record.valid for record in normalized),
        superseded_transport_records=(
            source_resolution.superseded_transport_attempts
            + (repair_resolution.superseded_transport_attempts if repair_resolution is not None else 0)
        ),
        selected_models=list(selected_models),
        errors=errors,
    )
    (output_dir / "normalization-summary.json").write_text(
        json.dumps(summary.model_dump(), indent=2, sort_keys=True) + "\n"
    )
    return summary, output_path


def normalize_metadata_pipeline(
    source_run_dirs: list[Path],
    repair_run_dirs: list[Path],
    writer_run_dir: Path,
    output_dir: Path,
    *,
    model_ids: list[str],
    writer_criteria_path: Path,
    writer_run_id: str,
) -> tuple[NormalizationSummary, Path]:
    from .writer_matrix import (
        is_recoverable_transport,
        load_writer_matrix_criteria,
        resolve_effective_fact_cells,
        resolve_writer_matrix_records,
    )

    if len(model_ids) != len(set(model_ids)):
        raise ValueError("Metadata normalization model filters must be unique")
    criteria = load_writer_matrix_criteria(writer_criteria_path)
    if model_ids != criteria.source_model_ids:
        raise ValueError("Metadata normalization models must match the frozen writer criteria order")
    cells = resolve_effective_fact_cells(source_run_dirs, repair_run_dirs, model_ids)
    writer_records = resolve_writer_matrix_records(writer_run_dir, criteria, writer_run_id)
    errors: list[str] = []
    normalized: list[NormalizedRecord] = []
    writer_outcomes = 0
    writer_valid = 0
    writer_failed = 0
    upstream_failures = 0
    superseded_transport = 0

    for cell in cells:
        if not cell.effective.validation.valid:
            upstream_failures += 1
            normalized.append(
                NormalizedRecord(
                    experiment_id=criteria.experiment_id,
                    attempt_id=cell.source.attempt_id,
                    source_attempt_id=cell.source.attempt_id,
                    effective_attempt_id=cell.effective.attempt_id,
                    repair_attempt_id=cell.repair_attempt_id,
                    pipeline_stage="upstream_failure",
                    image_id=cell.source.input.image_id,
                    repeat=cell.source.repeat,
                    model_id=cell.source.model.id,
                    model_name=cell.source.model.ollama_name,
                    valid=False,
                    validation_errors=cell.effective.validation.errors,
                    error_category=f"upstream_{effective_error_category(cell.effective)}",
                    output=None,
                )
            )
            continue

        records = writer_records.get(cell.key, [])
        finals = [record for record in records if not is_recoverable_transport(record)]
        superseded_transport += sum(is_recoverable_transport(record) for record in records)
        if len(finals) != 1:
            errors.append(f"Writer cell requires exactly one final outcome: {cell.key}")
            continue
        writer = finals[0]
        if writer.sanitized_request.get("source_fact_attempt_id") != cell.effective.attempt_id:
            errors.append(f"Writer cell references the wrong effective fact attempt: {cell.key}")
            continue
        writer_outcomes += 1
        writer_valid += int(writer.validation.valid)
        writer_failed += int(not writer.validation.valid)
        normalized.append(
            NormalizedRecord(
                experiment_id=criteria.experiment_id,
                attempt_id=writer.attempt_id,
                source_attempt_id=cell.source.attempt_id,
                effective_attempt_id=cell.effective.attempt_id,
                repair_attempt_id=cell.repair_attempt_id,
                writer_attempt_id=writer.attempt_id,
                pipeline_stage="fixed_writer",
                image_id=cell.source.input.image_id,
                repeat=cell.source.repeat,
                model_id=cell.source.model.id,
                model_name=cell.source.model.ollama_name,
                valid=writer.validation.valid,
                validation_errors=writer.validation.errors,
                error_category="" if writer.validation.valid else effective_error_category(writer),
                output=_normalize_value(writer.parsed_payload),
            )
        )

    expected_keys = {cell.key for cell in cells if cell.effective.validation.valid}
    unexpected_writer_keys = sorted(set(writer_records) - expected_keys)
    if unexpected_writer_keys:
        errors.append("Writer run contains unexpected cells: " + ", ".join(unexpected_writer_keys))
    if len(normalized) != len(cells):
        errors.append(f"Expected {len(cells)} normalized pipeline cells, wrote {len(normalized)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "records.metadata-normalization-v2.jsonl"
    with output_path.open("w", encoding="utf-8") as output:
        for record in sorted(
            normalized, key=lambda record: (record.model_id, record.image_id, record.repeat)
        ):
            output.write(json.dumps(record.model_dump(mode="json"), sort_keys=True) + "\n")
    summary = NormalizationSummary(
        status="normalized" if not errors else "invalid",
        records_checked=len(cells) + sum(len(records) for records in writer_records.values()),
        records_written=len(normalized),
        source_outcomes_selected=len(cells),
        repairs_applied=sum(bool(cell.repair_attempt_id) for cell in cells),
        valid_pipeline_outcomes=sum(record.valid for record in normalized),
        invalid_pipeline_outcomes=sum(not record.valid for record in normalized),
        superseded_transport_records=superseded_transport,
        writer_outcomes_applied=writer_outcomes,
        writer_valid_outcomes=writer_valid,
        writer_failed_outcomes=writer_failed,
        upstream_failures_preserved=upstream_failures,
        selected_models=model_ids,
        errors=errors,
    )
    (output_dir / "metadata-normalization-summary.json").write_text(
        json.dumps(summary.model_dump(), indent=2, sort_keys=True) + "\n"
    )
    return summary, output_path


def read_normalized_records(path: Path) -> list[NormalizedRecord]:
    records: list[NormalizedRecord] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(NormalizedRecord.model_validate_json(line))
        except ValueError as exc:
            raise ValueError(f"Invalid normalized record line {line_number}: {exc}") from exc
    if not records:
        raise ValueError("Normalized record file is empty")
    return records


def _normalize_value(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(unicodedata.normalize("NFC", value).split())
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_value(value[key]) for key in sorted(value)}
    return value
