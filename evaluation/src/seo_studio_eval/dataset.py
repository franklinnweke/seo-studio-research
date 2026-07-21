import json
from datetime import date
from pathlib import Path
from typing import Literal

from PIL import Image
from pydantic import BaseModel, Field, field_validator, model_validator

from .config import resolve_under_root
from .hashing import sha256_file


ImagePurpose = Literal["informative", "decorative", "functional", "text", "complex", "redundant", "unknown"]


class AnalysisPopulations(BaseModel):
    rq1_claims: bool
    controlled_qwen35: bool
    production_metadata: bool
    context_ablation: bool

    @model_validator(mode="after")
    def validate_nesting(self) -> "AnalysisPopulations":
        if not self.rq1_claims or not self.controlled_qwen35:
            raise ValueError("every full-study item must enter RQ1 and controlled Qwen3.5")
        if self.context_ablation and not self.production_metadata:
            raise ValueError("context-ablation items must be in production metadata")
        return self


class VisualReviewEvidence(BaseModel):
    status: Literal["accepted"]
    reviewer_role: str = Field(min_length=1)
    reviewed_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    notes: str = Field(min_length=1)

    @field_validator("reviewed_at")
    @classmethod
    def validate_reviewed_at(cls, value: str) -> str:
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("reviewed_at must be a valid ISO calendar date") from exc
        if parsed.isoformat() != value:
            raise ValueError("reviewed_at must use canonical YYYY-MM-DD format")
        return value


class DatasetItem(BaseModel):
    id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    split: Literal["contract", "pilot", "full"]
    image_path: Path
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    image_bytes: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    preprocessing: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    license: str = Field(min_length=1)
    license_url: str = Field(min_length=1, pattern=r"^https://")
    license_evidence_path: Path
    license_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_url: str = Field(min_length=1, pattern=r"^https://")
    source_title: str = Field(min_length=1)
    author: str = Field(min_length=1)
    purpose: ImagePurpose
    page_context_id: str = Field(min_length=1)
    page_context_path: Path
    page_context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    brand_profile_id: str = Field(min_length=1)
    brand_profile_path: Path
    brand_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scene_tags: list[str] = Field(min_length=1)
    reference_visible_facts: list[str] = Field(min_length=1)
    forbidden_claims: list[str] = Field(min_length=1)
    adjudication_alt_examples: list[str] = Field(min_length=1)
    annotation_notes: str = Field(min_length=1)
    analysis_populations: AnalysisPopulations | None = None
    visual_review: VisualReviewEvidence | None = None

    @model_validator(mode="after")
    def validate_unique_annotations(self) -> "DatasetItem":
        for field_name in (
            "scene_tags",
            "reference_visible_facts",
            "forbidden_claims",
            "adjudication_alt_examples",
        ):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must not contain duplicates")
        if self.split == "full":
            if self.analysis_populations is None:
                raise ValueError("full-study items require analysis_populations")
            if self.visual_review is None:
                raise ValueError("full-study items require accepted human-check evidence")
            pending_values = (
                self.reference_visible_facts
                + self.adjudication_alt_examples
                + [self.annotation_notes]
            )
            if any("[PENDING" in value for value in pending_values):
                raise ValueError("full-study items cannot contain pending human-check placeholders")
        return self


class LicenseEvidence(BaseModel):
    item_id: str
    source_url: str = Field(pattern=r"^https://")
    source_title: str
    author: str
    license: str
    license_url: str = Field(pattern=r"^https://")
    original_media_url: str = Field(pattern=r"^https://")
    retrieved_at: str


def load_manifest(root: Path, manifest_path: Path) -> list[DatasetItem]:
    resolved = resolve_under_root(root, manifest_path)
    items: list[DatasetItem] = []
    for line_number, line in enumerate(resolved.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            items.append(DatasetItem.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"Invalid dataset manifest line {line_number}: {exc}") from exc
    if not items:
        raise ValueError("Dataset manifest is empty")
    ids = [item.id for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("Dataset item ids must be unique")
    return items


def verify_dataset_item(root: Path, item: DatasetItem) -> list[str]:
    errors: list[str] = []
    checks = (
        (item.image_path, item.sha256, "image"),
        (item.page_context_path, item.page_context_sha256, "page context"),
        (item.brand_profile_path, item.brand_profile_sha256, "brand profile"),
        (item.license_evidence_path, item.license_evidence_sha256, "license evidence"),
    )
    for relative_path, expected_hash, label in checks:
        path = resolve_under_root(root, relative_path)
        if not path.is_file():
            errors.append(f"{item.id}: missing {label} file {relative_path}")
            continue
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            errors.append(f"{item.id}: {label} SHA-256 mismatch")

    image_path = resolve_under_root(root, item.image_path)
    if image_path.is_file():
        if image_path.stat().st_size != item.image_bytes:
            errors.append(f"{item.id}: image byte count mismatch")
        try:
            with Image.open(image_path) as image:
                if image.size != (item.width, item.height):
                    errors.append(f"{item.id}: image dimensions mismatch")
                image.verify()
        except (OSError, ValueError) as exc:
            errors.append(f"{item.id}: image could not be decoded: {exc}")

    evidence_path = resolve_under_root(root, item.license_evidence_path)
    if evidence_path.is_file():
        try:
            evidence = LicenseEvidence.model_validate_json(evidence_path.read_text())
            expected = {
                "item_id": item.id,
                "source_url": item.source_url,
                "source_title": item.source_title,
                "author": item.author,
                "license": item.license,
                "license_url": item.license_url,
            }
            actual = evidence.model_dump(include=set(expected))
            if actual != expected:
                errors.append(f"{item.id}: license evidence does not match manifest")
        except (OSError, ValueError) as exc:
            errors.append(f"{item.id}: invalid license evidence: {exc}")

    for path_value, expected_id, label in (
        (item.page_context_path, item.page_context_id, "page context"),
        (item.brand_profile_path, item.brand_profile_id, "brand profile"),
    ):
        path = resolve_under_root(root, path_value)
        if path.is_file():
            try:
                payload = json.loads(path.read_text())
                if not isinstance(payload, dict) or payload.get("id") != expected_id:
                    errors.append(f"{item.id}: {label} id does not match manifest")
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"{item.id}: invalid {label}: {exc}")
    return errors
