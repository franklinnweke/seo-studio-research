import hashlib
from collections import defaultdict
from copy import deepcopy
from datetime import date
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


def apply_human_check_records(
    catalog: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    *,
    reviewer_role: str,
    checked_at: str,
) -> list[dict[str, Any]]:
    """Validate a complete check population and return an updated catalog copy."""
    if not isinstance(reviewer_role, str) or not reviewer_role.strip():
        raise ValueError("reviewer_role must be a non-empty public role label")
    role = reviewer_role.strip()
    if not isinstance(checked_at, str):
        raise ValueError("checked_at must be a valid ISO calendar date")
    try:
        parsed_date = date.fromisoformat(checked_at)
    except ValueError as exc:
        raise ValueError("checked_at must be a valid ISO calendar date") from exc
    if parsed_date.isoformat() != checked_at:
        raise ValueError("checked_at must use canonical YYYY-MM-DD format")

    catalog_ids = [required_text(row, "id") for row in catalog]
    if len(catalog_ids) != len(set(catalog_ids)):
        raise ValueError("full-study catalog ids must be unique")
    if any(row.get("visual_review", {}).get("status") == "accepted" for row in catalog):
        raise ValueError("refusing to overwrite accepted human-check evidence")

    checks_by_id: dict[str, dict[str, Any]] = {}
    for check in checks:
        if not isinstance(check, dict):
            raise ValueError("every human-check record must be an object")
        candidate_id = required_text(check, "candidate_id")
        if candidate_id in checks_by_id:
            raise ValueError(f"duplicate human-check candidate_id: {candidate_id}")
        checks_by_id[candidate_id] = check

    expected_ids = set(catalog_ids)
    if set(checks_by_id) != expected_ids:
        missing = sorted(expected_ids - set(checks_by_id))
        extra = sorted(set(checks_by_id) - expected_ids)
        raise ValueError(f"human-check population mismatch; missing={missing}, extra={extra}")

    updated = deepcopy(catalog)
    rejected: list[str] = []
    incomplete: list[str] = []
    mismatched: list[str] = []
    for row in updated:
        item_id = required_text(row, "id")
        check = checks_by_id[item_id]
        if check.get("domain") != row.get("domain") or check.get("purpose") != row.get("purpose"):
            mismatched.append(item_id)
            continue
        if check.get("human_decision") == "rejected":
            rejected.append(item_id)
            continue

        visible_facts = _text_list(check.get("reference_visible_facts"))
        forbidden_additions = _text_list(check.get("forbidden_claims_additions"))
        alt_examples = _text_list(check.get("adjudication_alt_examples"))
        required_checks = (
            "purpose_fit_confirmed",
            "privacy_and_sensitivity_checked",
            "duplicate_and_quality_checked",
            "source_and_license_checked",
        )
        alt_ok = row.get("purpose") in {"decorative", "redundant"} or bool(alt_examples)
        suggestions_decided = all(
            _suggestion_decisions_complete(check, suggestions_field, decisions_field)
            for suggestions_field, decisions_field in (
                ("suggested_visible_facts", "visible_fact_decisions"),
                ("suggested_forbidden_claims", "forbidden_claim_decisions"),
                ("suggested_alt_examples", "alt_example_decisions"),
            )
        )
        complete = (
            check.get("human_decision") == "accepted"
            and all(check.get(field) is True for field in required_checks)
            and bool(visible_facts)
            and alt_ok
            and suggestions_decided
        )
        if not complete:
            incomplete.append(item_id)
            continue

        row["reference_visible_facts"] = visible_facts
        row["forbidden_claims"] = _deduplicate_text(
            _text_list(row.get("forbidden_claims")) + forbidden_additions
        )
        row["adjudication_alt_examples"] = (
            [""] if row["purpose"] in {"decorative", "redundant"} else alt_examples
        )
        notes = check.get("human_notes")
        row["annotation_notes"] = (
            notes.strip() if isinstance(notes, str) and notes.strip() else "No additional check note."
        )
        row["visual_review"] = {
            "notes": row["annotation_notes"],
            "reviewed_at": checked_at,
            "reviewer_role": role,
            "status": "accepted",
        }

    if rejected or incomplete or mismatched:
        raise ValueError(
            "human checks cannot be applied; "
            f"rejected={rejected}, incomplete={incomplete}, metadata_mismatch={mismatched}"
        )
    return updated


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return _deduplicate_text(value)


def _suggestion_decisions_complete(
    check: dict[str, Any], suggestions_field: str, decisions_field: str
) -> bool:
    suggestions = check.get(suggestions_field, [])
    decisions = check.get(decisions_field, {})
    if not isinstance(suggestions, list) or not isinstance(decisions, dict):
        return False
    return all(
        decisions.get(str(index), decisions.get(index)) in {"kept", "rejected"}
        for index in range(len(suggestions))
    )


def _deduplicate_text(values: list[Any]) -> list[str]:
    cleaned = [value.strip() for value in values if isinstance(value, str) and value.strip()]
    return list(dict.fromkeys(cleaned))
