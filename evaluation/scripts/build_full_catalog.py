#!/usr/bin/env python3
import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from seo_studio_eval.full_dataset import assign_analysis_populations


EVALUATION_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES_PATH = EVALUATION_ROOT / "dataset" / "cache" / "full-study-candidates" / "candidates.json"
SELECTION_PATH = EVALUATION_ROOT / "configs" / "full-study-selection-20260719.json"
CATALOG_PATH = EVALUATION_ROOT / "dataset" / "full-study-catalog.json"
REVIEW_PATH = EVALUATION_ROOT / "dataset" / "full-study-human-review.jsonl"
SEED = 1721844270

DOMAIN_SETTINGS = {
    "healthcare": {
        "brand_profile_id": "northstar-health-v1",
        "brand_profile_path": "dataset/brand-profiles/northstar-health-v1.json",
        "page_title": "Northstar Health Services",
        "audience": "Patients and caregivers",
        "forbidden_claims": [
            "a person's identity",
            "a diagnosis or medical result",
            "a treatment outcome",
        ],
    },
    "retail_product": {
        "brand_profile_id": "cedar-market-v1",
        "brand_profile_path": "dataset/brand-profiles/cedar-market-v1.json",
        "page_title": "Cedar Market Shopping Guide",
        "audience": "Local shoppers",
        "forbidden_claims": [
            "a person's identity",
            "a product price not clearly visible",
            "product origin, freshness, or certification not shown",
        ],
    },
    "hospitality_local_service": {
        "brand_profile_id": "harbour-house-v1",
        "brand_profile_path": "dataset/brand-profiles/harbour-house-v1.json",
        "page_title": "Harbour House Guest Services",
        "audience": "Prospective guests and local-service customers",
        "forbidden_claims": [
            "a person's identity",
            "availability, rating, or price",
            "service quality or an outcome not shown",
        ],
    },
    "education_professional_service": {
        "brand_profile_id": "horizon-learning-v1",
        "brand_profile_path": "dataset/brand-profiles/horizon-learning-v1.json",
        "page_title": "Horizon Learning and Professional Services",
        "audience": "Students, educators, and professionals",
        "forbidden_claims": [
            "a person's identity",
            "academic affiliation or achievement not established",
            "private information on a screen or document",
        ],
    },
}

PURPOSE_CONTEXT = {
    "informative": "Learn about the service, environment, or activity presented in this section.",
    "decorative": "The adjacent copy contains the meaningful information; the image supplies visual atmosphere only.",
    "functional": "Selecting the image opens the relevant service or registration action.",
    "text": "This section helps visitors understand visible signs or written information.",
    "complex": "This section introduces a detailed scene that may require a fuller explanation.",
    "redundant": "The adjacent text already communicates the same subject and purpose as the image.",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the selected full-study candidate catalog")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace pending draft catalog/workbook files; accepted review evidence is never overwritten",
    )
    args = parser.parse_args()
    if CATALOG_PATH.exists():
        existing = json.loads(CATALOG_PATH.read_text())
        if any(
            row.get("visual_review", {}).get("status") == "accepted"
            for row in existing
        ):
            raise ValueError("refusing to overwrite a catalog containing accepted human review")
        if not args.force:
            raise FileExistsError("draft catalog exists; pass --force for a deliberate rebuild")

    candidates = json.loads(CANDIDATES_PATH.read_text())
    selection = json.loads(SELECTION_PATH.read_text())
    rejected = set(selection["rejected_candidate_ids"])
    candidate_ids = {row["candidate_id"] for row in candidates}
    unknown_rejections = sorted(rejected - candidate_ids)
    if unknown_rejections:
        raise ValueError("selection references unknown candidates: " + ", ".join(unknown_rejections))

    selected = [row for row in candidates if row["candidate_id"] not in rejected]
    if len(selected) != 128:
        raise ValueError(f"selection must contain 128 items; found {len(selected)}")
    domain_counts = Counter(row["domain"] for row in selected)
    if set(domain_counts.values()) != {32} or set(domain_counts) != set(DOMAIN_SETTINGS):
        raise ValueError(f"selection domain counts are invalid: {dict(domain_counts)}")
    query_counts = Counter((row["domain"], row["query_id"]) for row in selected)
    if set(query_counts.values()) != {4}:
        raise ValueError(f"each domain/query group must contribute four items: {dict(query_counts)}")

    catalog = [_catalog_row(row) for row in selected]
    assignments = assign_analysis_populations(catalog, seed=SEED)
    for row in catalog:
        row["analysis_populations"] = assignments[row["id"]]
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n")
    REVIEW_PATH.write_text(
        "".join(json.dumps(_review_row(row), sort_keys=True) + "\n" for row in selected)
    )
    summary = {
        "catalog": str(CATALOG_PATH.relative_to(EVALUATION_ROOT)),
        "domain_counts": dict(sorted(domain_counts.items())),
        "human_review_status": "pending",
        "items": len(catalog),
        "population_seed": SEED,
        "review_workbook": str(REVIEW_PATH.relative_to(EVALUATION_ROOT)),
        "selection": str(SELECTION_PATH.relative_to(EVALUATION_ROOT)),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


def _catalog_row(candidate: dict[str, Any]) -> dict[str, Any]:
    item_id = candidate["candidate_id"]
    domain = candidate["domain"]
    purpose = candidate["purpose_hint"]
    settings = DOMAIN_SETTINGS[domain]
    context: dict[str, Any] = {
        "audience": settings["audience"],
        "id": f"{item_id}-context",
        "language": "en-CA",
        "nearby_text": PURPOSE_CONTEXT[purpose],
        "page_title": settings["page_title"],
        "page_url": f"https://example.invalid/full-study/{domain.replace('_', '-')}/{item_id}",
        "section_heading": candidate["query_id"].replace("-", " ").title(),
    }
    if purpose == "functional":
        context["functional_action"] = "Open the relevant service or registration page"
        context["link_destination"] = f"/actions/{item_id}"
    return {
        "adjudication_alt_examples": (
            [""] if purpose in {"decorative", "redundant"} else ["[PENDING HUMAN ALT EXAMPLE]"]
        ),
        "annotation_notes": "[PENDING HUMAN ITEM REVIEW] Verify visible facts, exclusions, purpose fit, sensitive content, duplication, and alt example.",
        "asset": {
            "expected_license": candidate["license"],
            "kind": "commons",
            "pageid": candidate["pageid"],
        },
        "brand_profile_id": settings["brand_profile_id"],
        "brand_profile_path": settings["brand_profile_path"],
        "discovery_evidence": {
            "candidate_id": item_id,
            "description": candidate["description"],
            "query": candidate["query"],
            "source_title": candidate["source_title"],
            "thumbnail_path": candidate["thumbnail_path"],
        },
        "domain": domain,
        "filename": f"{item_id}.jpg",
        "forbidden_claims": settings["forbidden_claims"],
        "id": item_id,
        "page_context": context,
        "purpose": purpose,
        "reference_visible_facts": ["[PENDING HUMAN VISIBLE FACT]"],
        "scene_tags": [domain, candidate["query_id"], purpose],
        "visual_review": {
            "notes": "Contact-sheet screening passed; individual human review remains required.",
            "reviewed_at": "2026-07-19",
            "reviewer_role": "pending-human-review",
            "status": "pending_human_review",
        },
    }


def _review_row(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "adjudication_alt_examples": [],
        "candidate_id": candidate["candidate_id"],
        "description": candidate["description"],
        "domain": candidate["domain"],
        "forbidden_claims_additions": [],
        "human_decision": "pending",
        "human_notes": "",
        "purpose": candidate["purpose_hint"],
        "reference_visible_facts": [],
        "source_title": candidate["source_title"],
        "source_url": candidate["source_url"],
        "thumbnail_path": f"dataset/images/full/{candidate['candidate_id']}.jpg",
    }


if __name__ == "__main__":
    raise SystemExit(main())
