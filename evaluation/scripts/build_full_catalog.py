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
CHECK_PATH = EVALUATION_ROOT / "dataset" / "full-study-human-check.jsonl"
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

# These prompts are deliberately derived only from the frozen query stratum. They are
# transcription aids for the human checker, not image labels or publication evidence.
CHECK_FACTS = {
    ("healthcare", "consultation"): ["A healthcare interaction between people is visible.", "Medical or examination equipment is visible."],
    ("healthcare", "nursing"): ["A healthcare worker is visible.", "A patient or clinical care activity is visible."],
    ("healthcare", "pharmacy"): ["Medicine containers or pharmacy shelving are visible.", "The setting contains healthcare products or equipment."],
    ("healthcare", "clinic-hero"): ["The image shows a healthcare-related environment.", "People or clinical furnishings are visible."],
    ("healthcare", "booking-action"): ["A healthcare-related person, place, or activity is visible.", "Medical clothing, equipment, or a clinical setting is visible."],
    ("healthcare", "health-signage"): ["A healthcare-related sign or written notice is visible.", "Readable text appears in the image."],
    ("healthcare", "clinical-complex"): ["The image shows a detailed clinical scene.", "Multiple people, objects, or pieces of equipment are visible."],
    ("healthcare", "waiting-area"): ["The image shows a waiting or seating area.", "Chairs or benches are visible."],
    ("retail_product", "market-vendor"): ["A vendor or seller is visible in a market setting.", "Products or goods are displayed for sale."],
    ("retail_product", "checkout"): ["The image shows a retail checkout area.", "A counter, register, basket, cart, or customer is visible."],
    ("retail_product", "product-display"): ["Products are arranged in a retail display.", "Shelves, racks, tables, or containers hold visible goods."],
    ("retail_product", "retail-hero"): ["The image shows a retail or market environment.", "Products, stalls, shelves, or shoppers are visible."],
    ("retail_product", "shop-action"): ["A shopping-related person, product, or setting is visible.", "Goods, shelves, a basket, cart, or storefront is visible."],
    ("retail_product", "store-signage"): ["A store sign, label, or written notice is visible.", "Readable text appears in the image."],
    ("retail_product", "busy-market"): ["The image shows a detailed market scene.", "Multiple people, stalls, products, or signs are visible."],
    ("retail_product", "aisle"): ["The image shows a store aisle or shopping area.", "Shelves, products, baskets, carts, or shoppers are visible."],
    ("hospitality_local_service", "restaurant-service"): ["A restaurant or dining-service scene is visible.", "Tables, food, serving items, staff, or diners are visible."],
    ("hospitality_local_service", "hotel-reception"): ["The image shows a hotel or guest reception area.", "A counter, desk, staff member, or guest is visible."],
    ("hospitality_local_service", "local-service"): ["A local service activity or setting is visible.", "A worker, customer, tools, or service furnishings are visible."],
    ("hospitality_local_service", "hospitality-hero"): ["The image shows a hospitality or guest-service environment.", "Guest seating, dining, lodging, or service features are visible."],
    ("hospitality_local_service", "reservation-action"): ["A hospitality-related place, service, or activity is visible.", "Dining, lodging, reception, or service features are visible."],
    ("hospitality_local_service", "hospitality-signage"): ["A hospitality-related sign or written notice is visible.", "Readable text appears in the image."],
    ("hospitality_local_service", "dining-complex"): ["The image shows a detailed dining scene.", "Multiple tables, people, dishes, furnishings, or serving items are visible."],
    ("hospitality_local_service", "guest-area"): ["The image shows a guest seating or common area.", "Seats, tables, furnishings, or guests are visible."],
    ("education_professional_service", "classroom"): ["The image shows a classroom or group learning environment.", "Students, an instructor, desks, or learning materials are visible."],
    ("education_professional_service", "library"): ["The image shows a library or study environment.", "Books, shelves, tables, or people studying are visible."],
    ("education_professional_service", "professional-meeting"): ["The image shows a workplace meeting.", "Several people, a meeting table, or presentation materials are visible."],
    ("education_professional_service", "education-hero"): ["The image shows a campus or learning environment.", "Buildings, seating, or study space is visible."],
    ("education_professional_service", "course-action"): ["A student or learner is using a laptop.", "The image depicts an education-related computer activity."],
    ("education_professional_service", "education-text"): ["A person is writing on a board or teaching surface.", "Visible writing or diagrams appear on the board."],
    ("education_professional_service", "workshop-complex"): ["The image shows a workshop or group learning session.", "Multiple participants, work surfaces, or learning materials are visible."],
    ("education_professional_service", "study-area"): ["The image shows a shared study area.", "Students, tables, laptops, books, or notebooks are visible."],
}

FUNCTIONAL_ALT_BY_DOMAIN = {
    "healthcare": "Open appointment booking for medical services.",
    "retail_product": "Open the online shopping or product-selection page.",
    "hospitality_local_service": "Open the reservation or service-booking page.",
    "education_professional_service": "Open course registration or online learning information.",
}

def main() -> int:
    parser = argparse.ArgumentParser(description="Build the selected full-study candidate catalog")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace pending draft catalog/workbook files; accepted check evidence is never overwritten",
    )
    args = parser.parse_args()
    if CATALOG_PATH.exists():
        existing = json.loads(CATALOG_PATH.read_text())
        if any(
            row.get("visual_review", {}).get("status") == "accepted"
            for row in existing
        ):
            raise ValueError("refusing to overwrite a catalog containing accepted human checks")
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
    CHECK_PATH.write_text(
        "".join(json.dumps(_check_row(row), sort_keys=True) + "\n" for row in catalog)
    )
    summary = {
        "catalog": str(CATALOG_PATH.relative_to(EVALUATION_ROOT)),
        "domain_counts": dict(sorted(domain_counts.items())),
        "human_check_status": "pending",
        "items": len(catalog),
        "population_seed": SEED,
        "human_check_workbook": str(CHECK_PATH.relative_to(EVALUATION_ROOT)),
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
        "annotation_notes": "[PENDING HUMAN ITEM CHECK] Verify visible facts, exclusions, purpose fit, sensitive content, duplication, and alt example.",
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
            "source_url": candidate["source_url"],
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
            "notes": "Contact-sheet screening passed; individual human check remains required.",
            "reviewed_at": "2026-07-19",
            "reviewer_role": "pending-human-check",
            "status": "pending_human_check",
        },
    }


def _check_row(catalog_row: dict[str, Any]) -> dict[str, Any]:
    discovery = catalog_row["discovery_evidence"]
    domain = catalog_row["domain"]
    purpose = catalog_row["purpose"]
    query_id = catalog_row["scene_tags"][1]
    fact_suggestions = CHECK_FACTS[(domain, query_id)]
    alt_suggestions = (
        []
        if purpose in {"decorative", "redundant"}
        else [FUNCTIONAL_ALT_BY_DOMAIN[domain]]
        if purpose == "functional"
        else [fact_suggestions[0]]
    )
    return {
        "adjudication_alt_examples": [],
        "candidate_id": catalog_row["id"],
        "description": discovery["description"],
        "domain": domain,
        "forbidden_claims_additions": [],
        "human_decision": "pending",
        "human_notes": "",
        "page_context": catalog_row["page_context"],
        "purpose": purpose,
        "reference_visible_facts": [],
        "suggested_alt_examples": alt_suggestions,
        "suggested_forbidden_claims": catalog_row["forbidden_claims"],
        "suggested_visible_facts": fact_suggestions,
        "suggestion_provenance": "Query-stratum draft suggestions; human pixel-level verification required.",
        "source_title": discovery["source_title"],
        "source_url": discovery["source_url"],
        "thumbnail_path": f"dataset/images/full/{catalog_row['id']}.jpg",
    }


if __name__ == "__main__":
    raise SystemExit(main())
