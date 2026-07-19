import hashlib
from collections import defaultdict
from typing import Any


REQUIRED_DOMAINS = (
    "healthcare",
    "retail_product",
    "hospitality_local_service",
    "education_professional_service",
)


def assign_analysis_populations(
    catalog: list[dict[str, Any]],
    *,
    seed: int,
    expected_per_domain: int = 32,
    production_per_domain: int = 16,
    context_per_domain: int = 9,
) -> dict[str, dict[str, bool]]:
    """Assign frozen review populations without using model outputs.

    Selection is invariant to catalog row order. Within each domain, items are
    grouped by purpose, hash-ordered, and selected round-robin across purposes.
    The context population is selected from the production population with a
    separate hash namespace, so it is always nested.
    """
    if context_per_domain > production_per_domain:
        raise ValueError("context_per_domain cannot exceed production_per_domain")

    ids = [required_text(row, "id") for row in catalog]
    if len(ids) != len(set(ids)):
        raise ValueError("full-study catalog ids must be unique")

    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in catalog:
        by_domain[required_text(row, "domain")].append(row)
        required_text(row, "purpose")

    if set(by_domain) != set(REQUIRED_DOMAINS):
        raise ValueError(
            "full-study catalog domains must be exactly: " + ", ".join(REQUIRED_DOMAINS)
        )
    for domain in REQUIRED_DOMAINS:
        if len(by_domain[domain]) != expected_per_domain:
            raise ValueError(
                f"{domain}: expected {expected_per_domain} catalog items, "
                f"found {len(by_domain[domain])}"
            )

    assignments: dict[str, dict[str, bool]] = {
        item_id: {
            "rq1_claims": True,
            "controlled_qwen35": True,
            "production_metadata": False,
            "context_ablation": False,
        }
        for item_id in ids
    }
    for domain in REQUIRED_DOMAINS:
        production = _balanced_hash_selection(
            by_domain[domain], production_per_domain, seed, f"{domain}:production"
        )
        context = _balanced_hash_selection(
            production, context_per_domain, seed, f"{domain}:context"
        )
        for row in production:
            assignments[required_text(row, "id")]["production_metadata"] = True
        for row in context:
            assignments[required_text(row, "id")]["context_ablation"] = True
    return assignments


def _balanced_hash_selection(
    rows: list[dict[str, Any]],
    count: int,
    seed: int,
    namespace: str,
) -> list[dict[str, Any]]:
    if count > len(rows):
        raise ValueError(f"cannot select {count} items from a population of {len(rows)}")
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[required_text(row, "purpose")].append(row)
    for purpose, bucket in buckets.items():
        bucket.sort(
            key=lambda row: _selection_key(
                seed, namespace, purpose, required_text(row, "id")
            )
        )

    selected: list[dict[str, Any]] = []
    purpose_order = sorted(buckets)
    while len(selected) < count:
        progressed = False
        for purpose in purpose_order:
            if buckets[purpose] and len(selected) < count:
                selected.append(buckets[purpose].pop(0))
                progressed = True
        if not progressed:
            raise RuntimeError("balanced selection exhausted before reaching target")
    return selected


def _selection_key(seed: int, namespace: str, purpose: str, item_id: str) -> str:
    value = f"{seed}:{namespace}:{purpose}:{item_id}".encode()
    return hashlib.sha256(value).hexdigest()


def required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()
