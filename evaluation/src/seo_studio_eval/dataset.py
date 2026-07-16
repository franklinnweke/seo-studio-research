import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .config import resolve_under_root
from .hashing import sha256_file


ImagePurpose = Literal["informative", "decorative", "functional", "text", "complex", "redundant", "unknown"]


class DatasetItem(BaseModel):
    id: str = Field(min_length=1)
    image_path: Path
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    domain: str = Field(min_length=1)
    license: str = Field(min_length=1)
    purpose: ImagePurpose
    page_context_path: Path
    page_context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    brand_profile_path: Path
    brand_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


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
    )
    for relative_path, expected_hash, label in checks:
        path = resolve_under_root(root, relative_path)
        if not path.is_file():
            errors.append(f"{item.id}: missing {label} file {relative_path}")
            continue
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            errors.append(f"{item.id}: {label} SHA-256 mismatch")
    return errors
