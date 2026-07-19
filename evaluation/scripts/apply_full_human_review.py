#!/usr/bin/env python3
import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any


EVALUATION_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = EVALUATION_ROOT / "dataset" / "full-study-catalog.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply completed human review to the full-study catalog")
    parser.add_argument("--review-file", type=Path, required=True)
    parser.add_argument("--reviewer-role", required=True, help="Non-identifying public role label")
    parser.add_argument("--reviewed-at", default=date.today().isoformat())
    parser.add_argument("--apply", action="store_true", help="Write accepted review into the catalog")
    args = parser.parse_args()

    catalog = json.loads(CATALOG_PATH.read_text())
    reviews = _load_jsonl(args.review_file)
    by_id = {row["candidate_id"]: row for row in reviews}
    expected_ids = {row["id"] for row in catalog}
    if set(by_id) != expected_ids:
        missing = sorted(expected_ids - set(by_id))
        extra = sorted(set(by_id) - expected_ids)
        raise ValueError(f"review population mismatch; missing={missing}, extra={extra}")

    rejected: list[str] = []
    incomplete: list[str] = []
    for row in catalog:
        review = by_id[row["id"]]
        if review.get("human_decision") == "rejected":
            rejected.append(row["id"])
            continue
        if not _review_complete(review):
            incomplete.append(row["id"])
            continue
        row["reference_visible_facts"] = _unique(review["reference_visible_facts"])
        row["forbidden_claims"] = _unique(
            row["forbidden_claims"] + review.get("forbidden_claims_additions", [])
        )
        row["adjudication_alt_examples"] = (
            [""]
            if row["purpose"] in {"decorative", "redundant"}
            else _unique(review["adjudication_alt_examples"])
        )
        row["annotation_notes"] = review.get("human_notes", "No additional review note.") or "No additional review note."
        row["visual_review"] = {
            "notes": row["annotation_notes"],
            "reviewed_at": args.reviewed_at,
            "reviewer_role": args.reviewer_role,
            "status": "accepted",
        }

    if rejected or incomplete:
        raise ValueError(
            f"human review cannot be applied; rejected={rejected}, incomplete={incomplete}"
        )
    if args.apply:
        CATALOG_PATH.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"applied": args.apply, "items": len(catalog), "status": "ready"}, sort_keys=True))
    return 0


def _review_complete(row: dict[str, Any]) -> bool:
    required_checks = (
        "purpose_fit_confirmed",
        "privacy_and_sensitivity_checked",
        "duplicate_and_quality_checked",
        "source_and_license_checked",
    )
    alt_ok = row.get("purpose") in {"decorative", "redundant"} or bool(
        row.get("adjudication_alt_examples")
    )
    return (
        row.get("human_decision") == "accepted"
        and all(row.get(field) is True for field in required_checks)
        and bool(row.get("reference_visible_facts"))
        and alt_ok
    )


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _unique(values: list[str]) -> list[str]:
    cleaned = [value.strip() for value in values if isinstance(value, str) and value.strip()]
    return list(dict.fromkeys(cleaned))


if __name__ == "__main__":
    raise SystemExit(main())
