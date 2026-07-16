import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .config import load_study
from .dataset import load_manifest
from .records import attempt_record_paths, read_attempt_record


class RunAccountingSummary(BaseModel):
    status: Literal["complete", "incomplete"]
    expected_attempts: int = Field(ge=0)
    observed_attempts: int = Field(ge=0)
    valid_attempts: int = Field(ge=0)
    failed_attempts: int = Field(ge=0)
    missing_attempts: list[str] = Field(default_factory=list)
    duplicate_attempts: list[str] = Field(default_factory=list)
    unexpected_attempts: list[str] = Field(default_factory=list)
    by_model: dict[str, dict[str, int]] = Field(default_factory=dict)


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
    observed_counts: dict[str, int] = {}
    by_model: dict[str, dict[str, int]] = {}
    valid_attempts = 0
    failed_attempts = 0
    directories = [run_dirs] if isinstance(run_dirs, Path) else run_dirs
    for path in [path for run_dir in directories for path in attempt_record_paths(run_dir)]:
        record = read_attempt_record(path)
        key = _key(record.model.id, record.input.image_id, record.repeat)
        observed_counts[key] = observed_counts.get(key, 0) + 1
        counts = by_model.setdefault(record.model.id, {"observed": 0, "valid": 0, "failed": 0})
        counts["observed"] += 1
        if record.validation.valid:
            valid_attempts += 1
            counts["valid"] += 1
        else:
            failed_attempts += 1
            counts["failed"] += 1

    observed = set(observed_counts)
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    duplicates = sorted(key for key, count in observed_counts.items() if count > 1)
    status = "complete" if not missing and not unexpected and not duplicates else "incomplete"
    summary = RunAccountingSummary(
        status=status,
        expected_attempts=len(expected),
        observed_attempts=sum(observed_counts.values()),
        valid_attempts=valid_attempts,
        failed_attempts=failed_attempts,
        missing_attempts=missing,
        duplicate_attempts=duplicates,
        unexpected_attempts=unexpected,
        by_model=dict(sorted(by_model.items())),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary.model_dump(), indent=2, sort_keys=True) + "\n")
    return summary


def _key(model_id: str, image_id: str, repeat: int) -> str:
    return f"{model_id}|{image_id}|r{repeat}"
