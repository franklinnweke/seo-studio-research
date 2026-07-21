from copy import deepcopy
import json
from pathlib import Path

import pytest

from seo_studio_eval.full_dataset import (
    REQUIRED_DOMAINS,
    apply_human_check_records,
    assign_analysis_populations,
)


PURPOSES = ("informative", "decorative", "functional", "text", "complex", "redundant")
EVALUATION_ROOT = Path(__file__).resolve().parents[1]


def catalog_fixture() -> list[dict]:
    return [
        {
            "id": f"{domain.replace('_', '-')}-{index:03d}",
            "domain": domain,
            "purpose": PURPOSES[index % len(PURPOSES)],
        }
        for domain in REQUIRED_DOMAINS
        for index in range(32)
    ]


def test_full_study_population_assignment_is_balanced_nested_and_deterministic() -> None:
    catalog = catalog_fixture()
    first = assign_analysis_populations(catalog, seed=1721844270)
    second = assign_analysis_populations(list(reversed(deepcopy(catalog))), seed=1721844270)

    assert first == second
    assert sum(value["rq1_claims"] for value in first.values()) == 128
    assert sum(value["controlled_qwen35"] for value in first.values()) == 128
    assert sum(value["production_metadata"] for value in first.values()) == 64
    assert sum(value["context_ablation"] for value in first.values()) == 36
    assert all(
        not value["context_ablation"] or value["production_metadata"]
        for value in first.values()
    )
    for domain in REQUIRED_DOMAINS:
        domain_ids = {row["id"] for row in catalog if row["domain"] == domain}
        assert sum(first[item_id]["production_metadata"] for item_id in domain_ids) == 16
        assert sum(first[item_id]["context_ablation"] for item_id in domain_ids) == 9


def test_full_study_population_assignment_rejects_wrong_domain_count() -> None:
    catalog = catalog_fixture()[:-1]

    with pytest.raises(ValueError, match="expected 32 catalog items"):
        assign_analysis_populations(catalog, seed=1721844270)


def test_full_study_population_assignment_rejects_duplicate_ids() -> None:
    catalog = catalog_fixture()
    catalog[1]["id"] = catalog[0]["id"]

    with pytest.raises(ValueError, match="ids must be unique"):
        assign_analysis_populations(catalog, seed=1721844270)


def human_check_fixture() -> tuple[list[dict], dict]:
    catalog = [
        {
            "id": "healthcare-example-001",
            "domain": "healthcare",
            "purpose": "informative",
            "forbidden_claims": ["identity"],
            "visual_review": {"status": "pending_human_check"},
        }
    ]
    check = {
        "candidate_id": "healthcare-example-001",
        "domain": "healthcare",
        "purpose": "informative",
        "human_decision": "accepted",
        "purpose_fit_confirmed": True,
        "privacy_and_sensitivity_checked": True,
        "duplicate_and_quality_checked": True,
        "source_and_license_checked": True,
        "reference_visible_facts": ["A hospital bed is visible."],
        "forbidden_claims_additions": ["diagnosis"],
        "adjudication_alt_examples": ["Hospital bed in a clinical room."],
        "suggested_visible_facts": ["A hospital bed is visible."],
        "suggested_forbidden_claims": ["diagnosis"],
        "suggested_alt_examples": ["Hospital bed in a clinical room."],
        "visible_fact_decisions": {"0": "kept"},
        "forbidden_claim_decisions": {"0": "kept"},
        "alt_example_decisions": {"0": "kept"},
        "human_notes": "",
    }
    return catalog, check


def test_checked_in_catalog_and_human_check_workbook_are_isomorphic() -> None:
    catalog = json.loads(
        (EVALUATION_ROOT / "dataset" / "full-study-catalog.json").read_text()
    )
    checks = [
        json.loads(line)
        for line in (
            EVALUATION_ROOT / "dataset" / "full-study-human-check.jsonl"
        ).read_text().splitlines()
        if line.strip()
    ]

    assert len(catalog) == len(checks) == 128
    assert [row["id"] for row in catalog] == [row["candidate_id"] for row in checks]
    assert all(row["visual_review"]["status"] == "pending_human_check" for row in catalog)
    assert all(row["discovery_evidence"]["source_url"] for row in catalog)
    assert all(row["page_context"] for row in checks)
    assert all(row["human_decision"] == "pending" for row in checks)
    assert all(len(row["suggested_visible_facts"]) == 2 for row in checks)
    assert all(len(row["suggested_forbidden_claims"]) >= 1 for row in checks)
    assert sum(bool(row["suggested_alt_examples"]) for row in checks) == 96
    assert all(row["suggestion_provenance"].startswith("Query-stratum") for row in checks)
    assert all(
        suggestion not in {row["source_title"], row["description"]}
        for row in checks
        for field in ("suggested_visible_facts", "suggested_alt_examples")
        for suggestion in row[field]
    )


def test_human_check_rejects_non_list_visible_facts() -> None:
    catalog, check = human_check_fixture()
    check["reference_visible_facts"] = "A hospital bed is visible."

    with pytest.raises(ValueError, match=r"incomplete=\['healthcare-example-001'\]"):
        apply_human_check_records(
            catalog, [check], reviewer_role="project-author", checked_at="2026-07-21"
        )


def test_human_check_requires_every_draft_suggestion_to_be_decided() -> None:
    catalog, check = human_check_fixture()
    check["alt_example_decisions"] = {}

    with pytest.raises(ValueError, match=r"incomplete=\['healthcare-example-001'\]"):
        apply_human_check_records(
            catalog, [check], reviewer_role="project-author", checked_at="2026-07-21"
        )


def test_human_check_applies_complete_records_without_mutating_input() -> None:
    catalog, check = human_check_fixture()
    original = deepcopy(catalog)

    updated = apply_human_check_records(
        catalog, [check], reviewer_role="project-author", checked_at="2026-07-21"
    )

    assert updated[0]["reference_visible_facts"] == ["A hospital bed is visible."]
    assert updated[0]["forbidden_claims"] == ["identity", "diagnosis"]
    assert updated[0]["visual_review"]["status"] == "accepted"
    assert catalog == original


def test_human_check_rejects_duplicate_candidate_ids() -> None:
    catalog, check = human_check_fixture()

    with pytest.raises(ValueError, match="duplicate human-check candidate_id"):
        apply_human_check_records(
            catalog, [check, deepcopy(check)], reviewer_role="project-author", checked_at="2026-07-21"
        )


def test_human_check_rejects_catalog_metadata_tampering() -> None:
    catalog, check = human_check_fixture()
    check["purpose"] = "decorative"

    with pytest.raises(ValueError, match=r"metadata_mismatch=\['healthcare-example-001'\]"):
        apply_human_check_records(
            catalog, [check], reviewer_role="project-author", checked_at="2026-07-21"
        )


def test_human_check_rejects_invalid_calendar_date() -> None:
    catalog, check = human_check_fixture()

    with pytest.raises(ValueError, match="valid ISO calendar date"):
        apply_human_check_records(
            catalog, [check], reviewer_role="project-author", checked_at="2026-02-30"
        )


def test_human_check_refuses_to_overwrite_accepted_evidence() -> None:
    catalog, check = human_check_fixture()
    catalog[0]["visual_review"]["status"] = "accepted"

    with pytest.raises(ValueError, match="refusing to overwrite accepted"):
        apply_human_check_records(
            catalog, [check], reviewer_role="project-author", checked_at="2026-07-21"
        )
