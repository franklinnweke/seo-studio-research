import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .config import load_study
from .dataset import load_manifest
from .records import attempt_record_paths, read_attempt_record
from .schemas import RunRecord


class RunAccountingSummary(BaseModel):
    status: Literal["complete", "incomplete"]
    expected_attempts: int = Field(ge=0)
    observed_attempts: int = Field(ge=0)
    raw_attempts: int = Field(ge=0)
    valid_attempts: int = Field(ge=0)
    failed_attempts: int = Field(ge=0)
    superseded_transport_attempts: int = Field(ge=0)
    implementation_deviation_attempts: int = Field(ge=0)
    missing_attempts: list[str] = Field(default_factory=list)
    duplicate_attempts: list[str] = Field(default_factory=list)
    unexpected_attempts: list[str] = Field(default_factory=list)
    by_model: dict[str, dict[str, int]] = Field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedAttemptSet:
    selected: dict[str, RunRecord]
    all_records: list[RunRecord]
    superseded_transport_attempts: int
    implementation_deviation_attempts: int
    duplicate_keys: list[str]


def build_run_accounting(
    config_path: Path,
    run_dirs: Path | list[Path],
    output_path: Path,
    model_ids: list[str] | None = None,
    image_ids: list[str] | None = None,
) -> RunAccountingSummary:
    study = load_study(config_path)
    manifest = load_manifest(study.root, study.config.dataset_manifest)
    selected_models = model_ids or study.config.model_ids
    selected_images = image_ids or [item.id for item in manifest]
    unknown_models = sorted(set(selected_models) - set(study.config.model_ids))
    unknown_images = sorted(set(selected_images) - {item.id for item in manifest})
    if unknown_models:
        raise ValueError(f"Accounting references unselected models: {', '.join(unknown_models)}")
    if unknown_images:
        raise ValueError(f"Accounting references unknown images: {', '.join(unknown_images)}")
    if len(selected_models) != len(set(selected_models)) or len(selected_images) != len(set(selected_images)):
        raise ValueError("Accounting model and image filters must be unique")
    expected = {
        _key(model_id, item.id, repeat)
        for model_id in selected_models
        for item in manifest
        if item.id in selected_images
        for repeat in range(1, study.config.repeats + 1)
    }
    resolution = resolve_attempt_records(run_dirs)
    by_model: dict[str, dict[str, int]] = {}
    valid_attempts = 0
    failed_attempts = 0
    for record in resolution.selected.values():
        counts = by_model.setdefault(record.model.id, {"observed": 0, "valid": 0, "failed": 0})
        counts["observed"] += 1
        if record.validation.valid:
            valid_attempts += 1
            counts["valid"] += 1
        else:
            failed_attempts += 1
            counts["failed"] += 1

    observed = set(resolution.selected)
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    duplicates = resolution.duplicate_keys
    status = "complete" if not missing and not unexpected and not duplicates else "incomplete"
    summary = RunAccountingSummary(
        status=status,
        expected_attempts=len(expected),
        observed_attempts=len(resolution.selected),
        raw_attempts=len(resolution.all_records),
        valid_attempts=valid_attempts,
        failed_attempts=failed_attempts,
        superseded_transport_attempts=resolution.superseded_transport_attempts,
        implementation_deviation_attempts=resolution.implementation_deviation_attempts,
        missing_attempts=missing,
        duplicate_attempts=duplicates,
        unexpected_attempts=unexpected,
        by_model=dict(sorted(by_model.items())),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary.model_dump(), indent=2, sort_keys=True) + "\n")
    return summary


def resolve_attempt_records(run_dirs: Path | list[Path]) -> ResolvedAttemptSet:
    directories = [run_dirs] if isinstance(run_dirs, Path) else run_dirs
    all_records = [
        read_attempt_record(path)
        for run_dir in directories
        for path in attempt_record_paths(run_dir)
    ]
    grouped: dict[str, list[RunRecord]] = {}
    for record in all_records:
        grouped.setdefault(
            _key(record.model.id, record.input.image_id, record.repeat), []
        ).append(record)

    selected: dict[str, RunRecord] = {}
    duplicate_keys: list[str] = []
    superseded_transport_attempts = 0
    implementation_deviation_attempts = 0
    for key, records in grouped.items():
        records.sort(key=lambda item: (item.collection_attempt, item.started_at, item.attempt_id))
        recoverable = [record for record in records if _is_recoverable_transport(record)]
        outcomes = [record for record in records if not _is_recoverable_transport(record)]
        collection_attempts = [record.collection_attempt for record in records]
        if len(collection_attempts) != len(set(collection_attempts)):
            duplicate_keys.append(key)
        if outcomes:
            if len(outcomes) > 1:
                if all(_is_timeout_record(record) for record in outcomes):
                    implementation_deviation_attempts += len(outcomes) - 1
                else:
                    duplicate_keys.append(key)
            selected[key] = outcomes[0]
            superseded_transport_attempts += len(recoverable)
        elif recoverable:
            selected[key] = recoverable[-1]

    return ResolvedAttemptSet(
        selected=selected,
        all_records=all_records,
        superseded_transport_attempts=superseded_transport_attempts,
        implementation_deviation_attempts=implementation_deviation_attempts,
        duplicate_keys=sorted(set(duplicate_keys)),
    )


def effective_error_category(record: RunRecord) -> str:
    if record.validation.valid:
        return "valid"
    if _is_timeout_record(record):
        return "inference_timeout"
    if record.error is not None:
        return record.error.category
    return "schema_invalid"


def _is_timeout_record(record: RunRecord) -> bool:
    return record.error is not None and (
        record.error.category == "inference_timeout"
        or "timed out" in record.error.message.lower()
    )


def _is_recoverable_transport(record: RunRecord) -> bool:
    return (
        record.error is not None
        and record.error.category == "transport_error"
        and not _is_timeout_record(record)
    )


def _key(model_id: str, image_id: str, repeat: int) -> str:
    return f"{model_id}|{image_id}|r{repeat}"
