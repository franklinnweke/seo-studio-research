import json
from pathlib import Path
from typing import Any, Literal
import unicodedata

from pydantic import BaseModel, Field

from .records import attempt_record_paths, read_attempt_record


class NormalizedRecord(BaseModel):
    normalization_version: Literal["normalization-v1"] = "normalization-v1"
    experiment_id: str
    attempt_id: str
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
    errors: list[str] = Field(default_factory=list)


def normalize_run_directory(run_dir: Path, output_dir: Path) -> tuple[NormalizationSummary, Path]:
    return normalize_run_directories([run_dir], output_dir)


def normalize_run_directories(
    run_dirs: list[Path],
    output_dir: Path,
) -> tuple[NormalizationSummary, Path]:
    errors: list[str] = []
    normalized: list[NormalizedRecord] = []
    if not run_dirs:
        raise ValueError("At least one run directory is required")
    record_paths = [path for run_dir in run_dirs for path in attempt_record_paths(run_dir)]
    if not record_paths:
        errors.append("No attempt records found")

    for path in record_paths:
        try:
            record = read_attempt_record(path)
            normalized.append(
                NormalizedRecord(
                    experiment_id=record.experiment_id,
                    attempt_id=record.attempt_id,
                    image_id=record.input.image_id,
                    repeat=record.repeat,
                    model_id=record.model.id,
                    model_name=record.model.ollama_name,
                    valid=record.validation.valid,
                    validation_errors=record.validation.errors,
                    error_category=record.error.category if record.error else "",
                    output=_normalize_value(record.parsed_payload),
                )
            )
        except (OSError, ValueError) as exc:
            errors.append(f"{path.name}: {exc}")

    attempt_ids = [record.attempt_id for record in normalized]
    duplicates = sorted({attempt_id for attempt_id in attempt_ids if attempt_ids.count(attempt_id) > 1})
    if duplicates:
        errors.append(f"Duplicate attempt ids: {', '.join(duplicates)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "records.normalization-v1.jsonl"
    with output_path.open("w", encoding="utf-8") as output:
        for record in normalized:
            output.write(json.dumps(record.model_dump(mode="json"), sort_keys=True) + "\n")

    summary = NormalizationSummary(
        status="normalized" if not errors else "invalid",
        records_checked=len(record_paths),
        records_written=len(normalized),
        errors=errors,
    )
    (output_dir / "normalization-summary.json").write_text(
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
