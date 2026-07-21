#!/usr/bin/env python3
import argparse
from datetime import date
import json
from pathlib import Path

from seo_studio_eval.full_dataset import apply_human_check_records


EVALUATION_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = EVALUATION_ROOT / "dataset" / "full-study-catalog.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply completed human checks to the full-study catalog")
    parser.add_argument("--check-file", "--review-file", dest="check_file", type=Path, required=True)
    parser.add_argument("--checker-role", "--reviewer-role", dest="checker_role", required=True, help="Non-identifying public role label")
    parser.add_argument("--reviewed-at", default=date.today().isoformat())
    parser.add_argument("--apply", action="store_true", help="Write accepted human-check evidence into the catalog")
    args = parser.parse_args()

    catalog = json.loads(CATALOG_PATH.read_text())
    checks = _load_jsonl(args.check_file)
    updated = apply_human_check_records(
        catalog,
        checks,
        reviewer_role=args.checker_role,
        checked_at=args.reviewed_at,
    )
    if args.apply:
        CATALOG_PATH.write_text(json.dumps(updated, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"applied": args.apply, "items": len(updated), "status": "ready"}, sort_keys=True))
    return 0


def _load_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid human-check JSON on line {line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"human-check line {line_number} must contain an object")
        records.append(value)
    return records


if __name__ == "__main__":
    raise SystemExit(main())
