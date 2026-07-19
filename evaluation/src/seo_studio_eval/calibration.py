import json
from pathlib import Path
import random
from typing import Any, Literal

from pydantic import BaseModel, Field

from .blinding import BlindedReviewItem


class CalibrationSummary(BaseModel):
    status: Literal["ready", "invalid"]
    seed: int
    images_selected: int = Field(ge=0)
    conditions_per_image: int = Field(ge=0)
    items_written: int = Field(ge=0)
    valid_items: int = Field(ge=0)
    invalid_items: int = Field(ge=0)
    selected_image_ids: list[str]
    errors: list[str] = Field(default_factory=list)


def build_calibration_package(
    review_items_path: Path,
    output_dir: Path,
    *,
    seed: int,
    image_count: int,
    expected_conditions: int,
) -> tuple[CalibrationSummary, Path, Path]:
    items = _read_review_items(review_items_path)
    by_image: dict[str, list[BlindedReviewItem]] = {}
    for item in items:
        by_image.setdefault(item.image_id, []).append(item)
    errors: list[str] = []
    for image_id, image_items in sorted(by_image.items()):
        conditions = [item.blinded_condition_id for item in image_items]
        if len(image_items) != expected_conditions or len(conditions) != len(set(conditions)):
            errors.append(
                f"{image_id}: expected {expected_conditions} unique conditions, found {len(set(conditions))}"
            )
    if len(by_image) < image_count:
        errors.append(f"Requested {image_count} images from a {len(by_image)}-image package")

    image_ids = sorted(by_image)
    random.Random(seed).shuffle(image_ids)
    selected_image_ids = sorted(image_ids[:image_count]) if not errors else []
    selected = [item for item in items if item.image_id in set(selected_image_ids)]
    output_dir.mkdir(parents=True, exist_ok=True)
    package_path = output_dir / "calibration-items.blind-v1.jsonl"
    timing_path = output_dir / "reviewer-timing-template.json"
    if not errors:
        _write_jsonl(package_path, [item.model_dump(mode="json") for item in selected])
        timing_template = {
            "template_version": 1,
            "reviewer_alias": "",
            "session_started_at": "",
            "session_ended_at": "",
            "instructions": (
                "Record wall-clock start/end times for the shared calibration session and elapsed "
                "seconds per item. Do not enter a model guess or consult the private condition map."
            ),
            "items": [
                {
                    "review_item_id": item.review_item_id,
                    "started_at": "",
                    "ended_at": "",
                    "elapsed_seconds": None,
                    "notes": "",
                }
                for item in selected
            ],
        }
        timing_path.write_text(json.dumps(timing_template, indent=2, sort_keys=True) + "\n")
    summary = CalibrationSummary(
        status="ready" if not errors else "invalid",
        seed=seed,
        images_selected=len(selected_image_ids),
        conditions_per_image=expected_conditions,
        items_written=len(selected),
        valid_items=sum(item.valid for item in selected),
        invalid_items=sum(not item.valid for item in selected),
        selected_image_ids=selected_image_ids,
        errors=errors,
    )
    (output_dir / "calibration-summary.json").write_text(
        json.dumps(summary.model_dump(), indent=2, sort_keys=True) + "\n"
    )
    return summary, package_path, timing_path


def _read_review_items(path: Path) -> list[BlindedReviewItem]:
    items: list[BlindedReviewItem] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            items.append(BlindedReviewItem.model_validate_json(line))
        except ValueError as exc:
            raise ValueError(f"Invalid blinded review item line {line_number}: {exc}") from exc
    if not items:
        raise ValueError("Blinded review package is empty")
    review_ids = [item.review_item_id for item in items]
    if len(review_ids) != len(set(review_ids)):
        raise ValueError("Blinded review package contains duplicate review item ids")
    return items


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, sort_keys=True) + "\n")
