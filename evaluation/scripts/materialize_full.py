#!/usr/bin/env python3
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import shutil
import time
from typing import Any

from materialize_pilot import fetch_commons_metadata_batch, materialize_item

from seo_studio_eval.dataset import DatasetItem, verify_dataset_item
from seo_studio_eval.full_dataset import REQUIRED_DOMAINS, assign_analysis_populations


EVALUATION_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = EVALUATION_ROOT / "dataset" / "full-study-catalog.json"
FINAL_MANIFEST_PATH = EVALUATION_ROOT / "dataset" / "manifest-full-v1.jsonl"
DRAFT_MANIFEST_PATH = EVALUATION_ROOT / "dataset" / "manifest-full-v1.draft.jsonl"
SEED = 1721844270


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialize the declared 128-item licensed full-study dataset"
    )
    parser.add_argument("--retrieved-at", required=True, help="ISO-8601 retrieval timestamp")
    parser.add_argument("--force", action="store_true", help="Replace generated full-study artifacts")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse only images with matching partial evidence from this retrieval timestamp",
    )
    parser.add_argument(
        "--request-delay-seconds",
        type=float,
        default=1.0,
        help="Delay between Commons media requests to avoid rate limiting",
    )
    parser.add_argument(
        "--draft",
        action="store_true",
        help="Allow pending visual review and write only the non-executable draft manifest",
    )
    args = parser.parse_args()
    datetime.fromisoformat(args.retrieved_at.replace("Z", "+00:00"))
    if args.request_delay_seconds < 0:
        raise ValueError("request-delay-seconds cannot be negative")

    catalog = json.loads(CATALOG_PATH.read_text())
    if not isinstance(catalog, list) or len(catalog) != 128:
        raise ValueError("full-study catalog must contain exactly 128 items")
    assignments = assign_analysis_populations(catalog, seed=SEED)
    for entry in catalog:
        if entry.get("analysis_populations") != assignments[entry["id"]]:
            raise ValueError(
                f"{entry['id']}: catalog analysis populations do not match the frozen seed"
            )
    _validate_check_states(catalog, allow_pending=args.draft)

    manifest_path = DRAFT_MANIFEST_PATH if args.draft else FINAL_MANIFEST_PATH
    if manifest_path.exists() and not args.force:
        raise FileExistsError(f"{manifest_path.name} exists; pass --force to replace it")

    image_dir = EVALUATION_ROOT / "dataset" / "images" / "full"
    license_dir = EVALUATION_ROOT / "dataset" / "licenses" / "full"
    context_dir = EVALUATION_ROOT / "dataset" / "page-contexts" / "full"
    for directory in (image_dir, license_dir, context_dir):
        directory.mkdir(parents=True, exist_ok=True)

    if args.draft:
        for entry in catalog:
            cached_thumbnail = EVALUATION_ROOT / entry["discovery_evidence"]["thumbnail_path"]
            destination = image_dir / entry["filename"]
            if not destination.is_file():
                shutil.copyfile(cached_thumbnail, destination)

    pageids = [int(row["asset"]["pageid"]) for row in catalog]
    if len(pageids) != len(set(pageids)):
        raise ValueError("full-study Commons page ids must be unique")
    sources: dict[int, dict[str, str]] = {}
    for start in range(0, len(pageids), 50):
        sources.update(fetch_commons_metadata_batch(pageids[start : start + 50]))
        if args.request_delay_seconds:
            time.sleep(args.request_delay_seconds)
    rows: list[dict[str, Any]] = []
    for entry in catalog:
        reuse_existing_image = args.draft or (
            args.resume
            and _has_matching_partial_evidence(
                entry,
                image_dir=image_dir,
                license_dir=license_dir,
                context_dir=context_dir,
                retrieved_at=args.retrieved_at,
            )
        )
        row = materialize_item(
            entry,
            image_dir,
            license_dir,
            context_dir,
            args.retrieved_at,
            sources,
            reuse_existing_image=reuse_existing_image,
        )
        if args.request_delay_seconds and not reuse_existing_image:
            time.sleep(args.request_delay_seconds)
        row["split"] = "full"
        if args.draft:
            row["preprocessing"] = "wikimedia_candidate_thumbnail_640_draft_v1"
        row["analysis_populations"] = assignments[row["id"]]
        row["visual_review"] = entry["visual_review"]
        rows.append(row)

    if not args.draft:
        _validate_final_rows(rows)
    manifest_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    summary = {
        "catalog": str(CATALOG_PATH.relative_to(EVALUATION_ROOT)),
        "context_ablation_items": sum(
            row["analysis_populations"]["context_ablation"] for row in rows
        ),
        "draft": args.draft,
        "items": len(rows),
        "manifest": str(manifest_path.relative_to(EVALUATION_ROOT)),
        "production_metadata_items": sum(
            row["analysis_populations"]["production_metadata"] for row in rows
        ),
        "retrieved_at": args.retrieved_at,
        "resumed": args.resume,
        "rq1_items": sum(row["analysis_populations"]["rq1_claims"] for row in rows),
        "seed": SEED,
    }
    summary_name = "full-study-materialization-draft-summary.json" if args.draft else "full-study-materialization-summary.json"
    (EVALUATION_ROOT / "dataset" / summary_name).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


def _has_matching_partial_evidence(
    entry: dict[str, Any],
    *,
    image_dir: Path,
    license_dir: Path,
    context_dir: Path,
    retrieved_at: str,
) -> bool:
    item_id = entry.get("id")
    filename = entry.get("filename")
    context = entry.get("page_context")
    if not isinstance(item_id, str) or not isinstance(filename, str):
        return False
    if not isinstance(context, dict):
        return False
    image_path = image_dir / filename
    license_path = license_dir / f"{item_id}.json"
    context_path = context_dir / f"{item_id}.json"
    if not all(path.is_file() for path in (image_path, license_path, context_path)):
        return False
    try:
        license_payload = json.loads(license_path.read_text())
        context_payload = json.loads(context_path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return (
        license_payload.get("item_id") == item_id
        and license_payload.get("retrieved_at") == retrieved_at
        and context_payload.get("id") == context.get("id")
    )


def _validate_check_states(catalog: list[dict[str, Any]], *, allow_pending: bool) -> None:
    permitted = {"accepted", "pending_human_check"} if allow_pending else {"accepted"}
    invalid: list[str] = []
    for row in catalog:
        check = row.get("visual_review")
        if not isinstance(check, dict) or check.get("status") not in permitted:
            invalid.append(str(row.get("id", "<missing-id>")))
    if invalid:
        requirement = "accepted or pending" if allow_pending else "human-accepted"
        raise ValueError(f"{requirement} visual check missing for: {', '.join(invalid)}")


def _validate_final_rows(rows: list[dict[str, Any]]) -> None:
    parsed = [DatasetItem.model_validate(row) for row in rows]
    domains = Counter(item.domain for item in parsed)
    expected_domains = {domain: 32 for domain in REQUIRED_DOMAINS}
    if dict(domains) != expected_domains:
        raise ValueError(f"full-study domain counts are {dict(domains)}; expected {expected_domains}")
    errors = [error for item in parsed for error in verify_dataset_item(EVALUATION_ROOT, item)]
    if errors:
        raise ValueError("full-study dataset verification failed: " + "; ".join(errors))


if __name__ == "__main__":
    raise SystemExit(main())
