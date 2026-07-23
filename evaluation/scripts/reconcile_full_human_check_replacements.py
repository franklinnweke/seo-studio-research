#!/usr/bin/env python3
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path

from seo_studio_eval.full_dataset import reconcile_human_check_replacements


EVALUATION_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = EVALUATION_ROOT / "dataset" / "full-study-catalog.json"
PRIOR_CHECK_PATH = (
    EVALUATION_ROOT / "dataset" / "full-study-human-check-recheck-20260722.jsonl"
)
REPLACEMENT_TEMPLATE_PATH = (
    EVALUATION_ROOT / "dataset" / "full-study-human-check-replacements.jsonl"
)
FINAL_CHECK_PATH = (
    EVALUATION_ROOT / "dataset" / "full-study-human-check-final-20260723.jsonl"
)
AUDIT_PATH = (
    EVALUATION_ROOT
    / "configs"
    / "full-study-replacement-reconciliation-20260723.json"
)
ASSIGNMENT_SEED = 1721844270
PUBLIC_DOMAIN_URL = (
    "https://commons.wikimedia.org/wiki/Commons:Copyright_tags#Public_domain"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile accepted same-stratum replacements into the full-study dataset"
    )
    parser.add_argument("--replacement-check-file", type=Path, required=True)
    parser.add_argument("--raw-replacement-check-file", type=Path)
    parser.add_argument("--prior-check-file", type=Path, default=PRIOR_CHECK_PATH)
    parser.add_argument(
        "--replacement-template", type=Path, default=REPLACEMENT_TEMPLATE_PATH
    )
    parser.add_argument("--checker-role", default="project-author")
    parser.add_argument("--reviewed-at", default=date.today().isoformat())
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    catalog = _load_json(CATALOG_PATH)
    prior_checks = _load_jsonl(args.prior_check_file)
    replacement_template = _load_jsonl(args.replacement_template)
    replacement_checks = _load_jsonl(args.replacement_check_file)
    updated_catalog, final_checks, replacement_rows = reconcile_human_check_replacements(
        catalog,
        prior_checks,
        replacement_template,
        replacement_checks,
        reviewer_role=args.checker_role,
        checked_at=args.reviewed_at,
        assignment_seed=ASSIGNMENT_SEED,
    )

    audit = {
        "analysis_version": 1,
        "assignment_seed": ASSIGNMENT_SEED,
        "checker_role": args.checker_role,
        "final_items": len(updated_catalog),
        "metadata_normalization": {
            "affected_candidate_ids": sorted(
                row["candidate_id"]
                for row in replacement_checks
                if row.get("license") == "Public domain"
                and row.get("license_url") == PUBLIC_DOMAIN_URL
            ),
            "field": "license_url",
            "reason": (
                "Wikimedia Commons returns no LicenseUrl for these public-domain "
                "records; the evaluation materializer uses the canonical Commons "
                "public-domain documentation URL."
            ),
            "substantive_human_decisions_changed": False,
            "value": PUBLIC_DOMAIN_URL,
        },
        "prior_check": _file_record(args.prior_check_file),
        "raw_replacement_check": (
            _file_record(args.raw_replacement_check_file)
            if args.raw_replacement_check_file
            else None
        ),
        "replacement_check": _file_record(args.replacement_check_file),
        "replacement_template": _file_record(args.replacement_template),
        "replacements": replacement_rows,
        "reviewed_at": args.reviewed_at,
        "status": "ready",
    }

    if args.apply:
        CATALOG_PATH.write_text(
            json.dumps(updated_catalog, indent=2, sort_keys=True) + "\n"
        )
        _write_jsonl(FINAL_CHECK_PATH, final_checks)
        audit["catalog"] = _file_record(CATALOG_PATH)
        audit["final_check"] = _file_record(FINAL_CHECK_PATH)
        AUDIT_PATH.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")

    summary = {
        "applied": args.apply,
        "final_items": len(updated_catalog),
        "replacements": len(replacement_rows),
        "status": "ready",
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


def _load_json(path: Path) -> list[dict]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, list) or not all(
        isinstance(record, dict) for record in payload
    ):
        raise ValueError(f"{path}: expected an array of objects")
    return payload


def _load_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: invalid JSON on line {line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{path}: line {line_number} must contain an object")
        records.append(value)
    return records


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    )


def _file_record(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    try:
        display_path = str(resolved.relative_to(EVALUATION_ROOT))
    except ValueError:
        display_path = resolved.name
    return {
        "path": display_path,
        "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    raise SystemExit(main())
