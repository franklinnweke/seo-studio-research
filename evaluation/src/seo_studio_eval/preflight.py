import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .config import load_study, resolve_under_root
from .dataset import load_manifest, verify_dataset_item
from .hashing import sha256_file


class PreflightSummary(BaseModel):
    status: Literal["ready", "incomplete"]
    experiment_id: str
    config_sha256: str
    models_config_sha256: str
    dataset_items_checked: int = Field(ge=0)
    selected_models_checked: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    domain_counts: dict[str, int] = Field(default_factory=dict)
    purpose_counts: dict[str, int] = Field(default_factory=dict)


def run_preflight(config_path: Path) -> tuple[PreflightSummary, Path]:
    study = load_study(config_path)
    errors: list[str] = []
    warnings: list[str] = []
    manifest = load_manifest(study.root, study.config.dataset_manifest)
    for item in manifest:
        errors.extend(verify_dataset_item(study.root, item))

    if len(manifest) != study.config.expected_dataset_items:
        errors.append(
            "dataset item count does not match configuration: "
            f"expected {study.config.expected_dataset_items}, found {len(manifest)}"
        )
    wrong_split = [item.id for item in manifest if item.split != study.config.dataset_split]
    if wrong_split:
        errors.append(f"dataset split mismatch: {', '.join(wrong_split)}")

    domain_counts = _counts(item.domain for item in manifest)
    purpose_counts = _counts(item.purpose for item in manifest)
    missing_domains = [domain for domain in study.config.required_domains if domain not in domain_counts]
    missing_purposes = [purpose for purpose in study.config.required_purposes if purpose not in purpose_counts]
    if missing_domains:
        errors.append(f"required domains missing from dataset: {', '.join(missing_domains)}")
    if missing_purposes:
        errors.append(f"required purposes missing from dataset: {', '.join(missing_purposes)}")

    models_by_id = {model.id: model for model in study.models.models}
    for model_id in study.config.model_ids:
        model = models_by_id[model_id]
        if not model.frozen:
            warnings.append(f"{model_id}: model identity is not protocol-frozen")
        if not model.expected_digest:
            warnings.append(f"{model_id}: expected digest awaits compatibility preflight")
        if model.license == "REQUIRES_PILOT_VERIFICATION":
            warnings.append(f"{model_id}: license verification is incomplete")

    models_path = resolve_under_root(study.root, study.config.models_config)
    summary = PreflightSummary(
        status="ready" if not errors else "incomplete",
        experiment_id=study.config.experiment_id,
        config_sha256=sha256_file(study.config_path),
        models_config_sha256=sha256_file(models_path),
        dataset_items_checked=len(manifest),
        selected_models_checked=len(study.config.model_ids),
        errors=errors,
        warnings=warnings,
        domain_counts=domain_counts,
        purpose_counts=purpose_counts,
    )
    output_dir = resolve_under_root(study.root, study.config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "preflight-summary.json"
    output_path.write_text(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
    return summary, output_path


def _counts(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))
