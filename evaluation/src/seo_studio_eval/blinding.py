import hashlib
import json
from pathlib import Path
import random
from typing import Any, Literal

from pydantic import BaseModel, Field

from .normalization import NormalizedRecord, read_normalized_records


class BlindedReviewItem(BaseModel):
    package_version: Literal["blind-v1"] = "blind-v1"
    review_item_id: str
    image_id: str
    blinded_condition_id: str
    repeat: int = Field(ge=1)
    valid: bool
    output: dict[str, Any] | None


class BlindingSummary(BaseModel):
    status: Literal["ready", "invalid"]
    items_written: int = Field(ge=0)
    conditions_blinded: int = Field(ge=0)
    valid_items: int = Field(default=0, ge=0)
    invalid_items: int = Field(default=0, ge=0)
    items_per_condition: dict[str, int] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


def build_blinded_package(
    normalized_path: Path,
    review_dir: Path,
    mapping_dir: Path,
    seed: int,
) -> tuple[BlindingSummary, Path, Path]:
    records = read_normalized_records(normalized_path)
    errors = _leakage_errors(records)
    errors.extend(_balance_errors(records))
    condition_keys = sorted({record.model_id for record in records})
    shuffled = condition_keys.copy()
    random.Random(seed).shuffle(shuffled)
    condition_map = {model_id: f"C{index:03d}" for index, model_id in enumerate(shuffled, start=1)}

    review_dir.mkdir(parents=True, exist_ok=True)
    mapping_dir.mkdir(parents=True, exist_ok=True)
    package_path = review_dir / "review-items.blind-v1.jsonl"
    mapping_path = mapping_dir / "reviewer-map.private.jsonl"
    if errors:
        summary = BlindingSummary(
            status="invalid",
            items_written=0,
            conditions_blinded=len(condition_map),
            valid_items=0,
            invalid_items=0,
            items_per_condition={},
            errors=errors,
        )
        (review_dir / "blinding-summary.json").write_text(
            json.dumps(summary.model_dump(), indent=2, sort_keys=True) + "\n"
        )
        return summary, package_path, mapping_path

    blinded_items: list[BlindedReviewItem] = []
    private_rows: list[dict[str, str | int]] = []
    for record in records:
        stable_attempt_id = record.source_attempt_id or record.attempt_id
        review_item_id = hashlib.sha256(
            f"blind-v1:{seed}:{stable_attempt_id}".encode("utf-8")
        ).hexdigest()[:16]
        blinded_items.append(
            BlindedReviewItem(
                review_item_id=review_item_id,
                image_id=record.image_id,
                blinded_condition_id=condition_map[record.model_id],
                repeat=record.repeat,
                valid=record.valid,
                output=record.output,
            )
        )
        private_rows.append(
            {
                "review_item_id": review_item_id,
                "attempt_id": record.attempt_id,
                "source_attempt_id": stable_attempt_id,
                "effective_attempt_id": record.effective_attempt_id or record.attempt_id,
                "repair_attempt_id": record.repair_attempt_id,
                "writer_attempt_id": record.writer_attempt_id,
                "pipeline_stage": record.pipeline_stage,
                "model_id": record.model_id,
                "model_name": record.model_name,
                "blinded_condition_id": condition_map[record.model_id],
                "seed": seed,
            }
        )

    blinded_items.sort(key=lambda item: hashlib.sha256(f"{seed}:{item.review_item_id}".encode()).hexdigest())
    _write_jsonl(package_path, [item.model_dump(mode="json") for item in blinded_items])
    _write_jsonl(mapping_path, private_rows)

    summary = BlindingSummary(
        status="ready" if not errors else "invalid",
        items_written=len(blinded_items),
        conditions_blinded=len(condition_map),
        valid_items=sum(item.valid for item in blinded_items),
        invalid_items=sum(not item.valid for item in blinded_items),
        items_per_condition={
            condition_map[model_id]: sum(record.model_id == model_id for record in records)
            for model_id in condition_keys
        },
        errors=errors,
    )
    (review_dir / "blinding-summary.json").write_text(
        json.dumps(summary.model_dump(), indent=2, sort_keys=True) + "\n"
    )
    return summary, package_path, mapping_path


def _leakage_errors(records: list[NormalizedRecord]) -> list[str]:
    errors: list[str] = []
    identity_values = {
        value.lower()
        for record in records
        for value in (record.model_id, record.model_name)
        if value
    }
    for record in records:
        serialized_output = json.dumps(record.output, ensure_ascii=False).lower()
        leaked_values = {value for value in identity_values if value in serialized_output}
        if leaked_values:
            errors.append(
                f"{record.attempt_id}: output contains model identity: {', '.join(sorted(leaked_values))}"
            )
    return errors


def _balance_errors(records: list[NormalizedRecord]) -> list[str]:
    errors: list[str] = []
    keys = [(record.model_id, record.image_id, record.repeat) for record in records]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        errors.append(
            "Duplicate condition/image/repeat outcomes: "
            + ", ".join("|".join(map(str, key)) for key in duplicates)
        )
    image_sets = {
        model_id: {(record.image_id, record.repeat) for record in records if record.model_id == model_id}
        for model_id in sorted({record.model_id for record in records})
    }
    if image_sets and len({frozenset(values) for values in image_sets.values()}) != 1:
        errors.append("Conditions do not contain the same image/repeat population")
    return errors


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, sort_keys=True) + "\n")
