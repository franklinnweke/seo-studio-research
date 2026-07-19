from copy import deepcopy

import pytest

from seo_studio_eval.full_dataset import REQUIRED_DOMAINS, assign_analysis_populations


PURPOSES = ("informative", "decorative", "functional", "text", "complex", "redundant")


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
