import hashlib
from collections import defaultdict
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any


REQUIRED_DOMAINS = (
    "healthcare",
    "retail_product",
    "hospitality_local_service",
    "education_professional_service",
)

HUMAN_CHECK_RESPONSE_FIELDS = frozenset(
    {
        "adjudication_alt_examples",
        "alt_example_decisions",
        "custom_alt_examples",
        "custom_forbidden_claims",
        "custom_visible_facts",
        "duplicate_and_quality_checked",
        "forbidden_claim_decisions",
        "forbidden_claims_additions",
        "human_decision",
        "human_notes",
        "privacy_and_sensitivity_checked",
        "purpose_fit_confirmed",
        "reference_visible_facts",
        "source_and_license_checked",
        "verification_ui_version",
        "visible_fact_decisions",
    }
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
    selection_ids = [_analysis_selection_id(row) for row in catalog]
    if len(selection_ids) != len(set(selection_ids)):
        raise ValueError("full-study analysis selection identities must be unique")

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
                seed, namespace, purpose, _analysis_selection_id(row)
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


def _analysis_selection_id(row: dict[str, Any]) -> str:
    replacement = row.get("replacement_evidence")
    if isinstance(replacement, dict) and replacement.get("replacement_for"):
        return required_text(replacement, "replacement_for")
    return required_text(row, "id")


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


def reconcile_human_check_replacements(
    catalog: list[dict[str, Any]],
    prior_checks: list[dict[str, Any]],
    replacement_template: list[dict[str, Any]],
    replacement_checks: list[dict[str, Any]],
    *,
    reviewer_role: str,
    checked_at: str,
    assignment_seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Replace rejected rows additively and apply a complete accepted population.

    Replacement records must match a pre-human-check template, cover every rejected
    row exactly once, and stay in the original domain/query/purpose stratum. The
    rejected row remains identifiable through ``replacement_evidence`` and supplies
    the frozen analysis-selection identity.
    """
    catalog_by_id = _unique_records(catalog, "id", "catalog")
    prior_by_id = _unique_records(prior_checks, "candidate_id", "prior human-check")
    template_by_id = _unique_records(
        replacement_template, "candidate_id", "replacement template"
    )
    replacements_by_id = _unique_records(
        replacement_checks, "candidate_id", "replacement human-check"
    )

    if set(prior_by_id) != set(catalog_by_id):
        raise ValueError("prior human-check population must match the catalog exactly")
    if set(template_by_id) != set(replacements_by_id):
        raise ValueError("replacement human-check population must match its template")
    for candidate_id, check in replacements_by_id.items():
        if _immutable_check_fields(check) != _immutable_check_fields(
            template_by_id[candidate_id]
        ):
            raise ValueError(
                f"{candidate_id}: replacement candidate metadata differs from its template"
            )

    rejected_ids = {
        candidate_id
        for candidate_id, check in prior_by_id.items()
        if check.get("human_decision") == "rejected"
    }
    if not rejected_ids:
        raise ValueError("prior human-check evidence contains no rejected rows")
    replacement_targets: dict[str, dict[str, Any]] = {}
    for check in replacement_checks:
        candidate_id = required_text(check, "candidate_id")
        replacement_for = required_text(check, "replacement_for")
        if replacement_for in replacement_targets:
            raise ValueError(f"duplicate replacement target: {replacement_for}")
        if candidate_id in catalog_by_id:
            raise ValueError(f"{candidate_id}: replacement id already exists in catalog")
        replacement_targets[replacement_for] = check
    if set(replacement_targets) != rejected_ids:
        missing = sorted(rejected_ids - set(replacement_targets))
        extra = sorted(set(replacement_targets) - rejected_ids)
        raise ValueError(
            f"replacement targets must cover rejected rows exactly; missing={missing}, extra={extra}"
        )

    reconciled_catalog: list[dict[str, Any]] = []
    reconciled_checks: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    for original in catalog:
        original_id = required_text(original, "id")
        prior_check = prior_by_id[original_id]
        if original_id not in replacement_targets:
            reconciled_catalog.append(deepcopy(original))
            reconciled_checks.append(deepcopy(prior_check))
            continue

        replacement_check = replacement_targets[original_id]
        _validate_replacement_stratum(original, replacement_check)
        replacement_catalog_row = _replacement_catalog_row(original, replacement_check)
        reconciled_catalog.append(replacement_catalog_row)
        reconciled_checks.append(deepcopy(replacement_check))
        audit_rows.append(
            {
                "inherited_analysis_populations": deepcopy(
                    original.get("analysis_populations")
                ),
                "replacement_candidate_id": required_text(
                    replacement_check, "candidate_id"
                ),
                "replacement_for": original_id,
                "stratum": {
                    "domain": required_text(replacement_check, "domain"),
                    "purpose": required_text(replacement_check, "purpose"),
                    "query_id": required_text(replacement_check, "query_id"),
                },
            }
        )

    assignments = assign_analysis_populations(reconciled_catalog, seed=assignment_seed)
    for row in reconciled_catalog:
        item_id = required_text(row, "id")
        if row.get("analysis_populations") != assignments[item_id]:
            raise ValueError(
                f"{item_id}: inherited analysis populations do not match the frozen selection identity"
            )

    applied_catalog = apply_human_check_records(
        reconciled_catalog,
        reconciled_checks,
        reviewer_role=reviewer_role,
        checked_at=checked_at,
    )
    return applied_catalog, reconciled_checks, audit_rows


def _unique_records(
    records: list[dict[str, Any]], key: str, label: str
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError(f"every {label} record must be an object")
        record_id = required_text(record, key)
        if record_id in result:
            raise ValueError(f"duplicate {label} {key}: {record_id}")
        result[record_id] = record
    return result


def _immutable_check_fields(check: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in check.items()
        if key not in HUMAN_CHECK_RESPONSE_FIELDS
    }


def _validate_replacement_stratum(
    original: dict[str, Any], replacement: dict[str, Any]
) -> None:
    original_id = required_text(original, "id")
    candidate_id = required_text(replacement, "candidate_id")
    if replacement.get("replacement_for") != original_id:
        raise ValueError(f"{candidate_id}: replacement target does not match original row")
    if replacement.get("domain") != original.get("domain"):
        raise ValueError(f"{candidate_id}: replacement domain does not match")
    if replacement.get("purpose") != original.get("purpose"):
        raise ValueError(f"{candidate_id}: replacement purpose does not match")
    query_id = required_text(replacement, "query_id")
    scene_tags = original.get("scene_tags")
    if not isinstance(scene_tags, list) or query_id not in scene_tags:
        raise ValueError(f"{candidate_id}: replacement query stratum does not match")
    replacement_context = replacement.get("page_context")
    original_context = original.get("page_context")
    if not isinstance(replacement_context, dict) or not isinstance(original_context, dict):
        raise ValueError(f"{candidate_id}: replacement page context is invalid")
    for field in ("page_title", "section_heading", "audience", "language", "nearby_text"):
        if replacement_context.get(field) != original_context.get(field):
            raise ValueError(f"{candidate_id}: replacement page-context {field} differs")

    expected_thumbnail = f"dataset/images/full/{candidate_id}.jpg"
    if replacement.get("thumbnail_path") != expected_thumbnail:
        raise ValueError(f"{candidate_id}: replacement thumbnail path is not canonical")


def _replacement_catalog_row(
    original: dict[str, Any], replacement: dict[str, Any]
) -> dict[str, Any]:
    candidate_id = required_text(replacement, "candidate_id")
    try:
        pageid = int(candidate_id.rsplit("-p", maxsplit=1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError(f"{candidate_id}: candidate id does not contain a Commons page id") from exc

    row = deepcopy(original)
    row["id"] = candidate_id
    row["filename"] = Path(required_text(replacement, "thumbnail_path")).name
    row["asset"] = {
        "expected_license": required_text(replacement, "license"),
        "kind": "commons",
        "pageid": pageid,
    }
    prior_discovery = original.get("discovery_evidence")
    query = (
        prior_discovery.get("query")
        if isinstance(prior_discovery, dict)
        else required_text(replacement, "query_id")
    )
    row["discovery_evidence"] = {
        "candidate_id": candidate_id,
        "description": required_text(replacement, "description"),
        "query": query,
        "source_title": required_text(replacement, "source_title"),
        "source_url": required_text(replacement, "source_url"),
        "thumbnail_path": required_text(replacement, "thumbnail_path"),
    }
    row["page_context"] = deepcopy(replacement["page_context"])
    row["scene_tags"] = [
        required_text(replacement, "domain"),
        required_text(replacement, "query_id"),
        required_text(replacement, "purpose"),
    ]
    row["reference_visible_facts"] = ["[PENDING HUMAN VISIBLE FACT]"]
    row["adjudication_alt_examples"] = ["[PENDING HUMAN ALT EXAMPLE]"]
    row["annotation_notes"] = "[PENDING HUMAN REPLACEMENT CHECK]"
    row["visual_review"] = {
        "notes": "Additive same-stratum replacement pending final application.",
        "reviewed_at": row.get("visual_review", {}).get("reviewed_at", "2026-07-19"),
        "reviewer_role": "pending-human-check",
        "status": "pending_human_check",
    }
    row["replacement_evidence"] = {
        "replacement_for": required_text(replacement, "replacement_for"),
        "selection_identity": required_text(replacement, "replacement_for"),
    }
    return row


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
