from collections import Counter
import json
import math
from pathlib import Path
from statistics import median
from typing import Any

from .accounting import effective_error_category, resolve_attempt_records
from .config import load_study
from .dataset import load_manifest
from .hashing import sha256_file
from .pilot import PilotRunSummary, load_compatibility_criteria
from .records import attempt_record_paths


def build_pilot_report(
    config_path: Path,
    criteria_path: Path,
    run_dir: Path,
    evidence_path: Path,
    report_path: Path,
    deviation_reference: str = "",
) -> tuple[Path, Path]:
    study = load_study(config_path)
    criteria = load_compatibility_criteria(criteria_path)
    summary = PilotRunSummary.model_validate_json((run_dir / "pilot-summary.json").read_text())
    is_candidate_amendment = "amendment" in summary.protocol_version.lower()
    resolution = resolve_attempt_records(run_dir)
    expected = criteria.pilot_items * len(study.config.model_ids)
    if summary.status != "complete" or len(resolution.selected) != expected:
        raise ValueError("Pilot report requires a complete compatibility matrix")
    if resolution.duplicate_keys:
        raise ValueError("Pilot report cannot resolve duplicate outcome keys")

    configured = {model.id: model for model in study.models.models}
    model_results: list[dict[str, Any]] = []
    eligible_models: list[str] = []
    for model_id in study.config.model_ids:
        records = [record for record in resolution.selected.values() if record.model.id == model_id]
        valid = sum(record.validation.valid for record in records)
        observed = len(records)
        rate = valid / observed if observed else 0.0
        threshold_met = observed == criteria.pilot_items and rate >= criteria.minimum_schema_valid_rate
        if threshold_met:
            eligible_models.append(model_id)
        durations = sorted(record.telemetry.wall_duration_ms / 1000 for record in records)
        failures = Counter(
            effective_error_category(record)
            for record in records
            if not record.validation.valid
        )
        model = configured[model_id]
        model_results.append(
            {
                "model_id": model_id,
                "ollama_name": model.ollama_name,
                "digest": model.expected_digest,
                "observed": observed,
                "valid": valid,
                "failed": observed - valid,
                "schema_valid_rate": rate,
                "threshold_met": threshold_met,
                "failure_categories": dict(sorted(failures.items())),
                "median_wall_seconds": round(median(durations), 3),
                "p95_wall_seconds_nearest_rank": round(_nearest_rank(durations, 0.95), 3),
            }
        )

    raw_records = resolution.all_records
    started_at = min(record.started_at for record in raw_records)
    ended_at = max(record.ended_at for record in raw_records)
    analyzed_records = list(resolution.selected.values())
    active_wall_seconds = sum(record.telemetry.wall_duration_ms for record in analyzed_records) / 1000
    claim_counts = [
        _visual_fact_claim_count(record.parsed_payload)
        for record in analyzed_records
        if record.validation.valid and record.parsed_payload is not None
    ]
    manifest = load_manifest(study.root, study.config.dataset_manifest)
    finalist_outputs = 120 * 3
    reviewer_scenarios = {
        f"{minutes}_minutes_per_output_two_reviewers_hours": round(
            finalist_outputs * 2 * minutes / 60, 1
        )
        for minutes in (2, 3, 5)
    }
    evidence = {
        "evidence_version": 1,
        "stage": (
            "20-image candidate-amendment compatibility pilot"
            if is_candidate_amendment
            else "20-image configuration compatibility pilot"
        ),
        "quality_ranking_permitted": False,
        "run_id": summary.run_id,
        "experiment_id": summary.experiment_id,
        "protocol_version": summary.protocol_version,
        "criteria_id": summary.criteria_id,
        "collection_window": {
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
            "elapsed_hours_including_operational_pauses": round(
                (ended_at - started_at).total_seconds() / 3600, 3
            ),
            "analyzed_attempt_wall_hours": round(active_wall_seconds / 3600, 3),
            "raw_attempt_record_bytes": sum(
                path.stat().st_size for path in attempt_record_paths(run_dir)
            ),
        },
        "runtime": {
            "ollama_version": summary.ollama_version,
            "system_snapshot_ref": summary.system_snapshot_ref,
            "git_commits": sorted({record.git_commit for record in raw_records}),
            "tracked_worktree_clean_for_final_segment": not summary.dirty_worktree,
            "access_authority": "$davneet-dgx-access",
            "temporary_collection_path": (
                "direct public-data-only path followed by a temporary localhost-only SSH tunnel under the documented network-verification deferral"
                if is_candidate_amendment
                else "direct public-data-only path under documented network-verification deferral"
            ),
        },
        "frozen_contract": {
            "dataset_items": len(manifest),
            "models": len(study.config.model_ids),
            "temperature": criteria.temperature,
            "seed": criteria.seed,
            "thinking_mode": criteria.thinking_mode,
            "output_token_limit": criteria.output_token_limit,
            "timeout_seconds": criteria.per_attempt_timeout_seconds,
            "hidden_retries": criteria.hidden_retries_allowed,
            "minimum_schema_valid_rate": criteria.minimum_schema_valid_rate,
            "study_config_sha256": sha256_file(study.config_path),
            "models_config_sha256": sha256_file(study.root / study.config.models_config),
            "criteria_sha256": sha256_file(criteria_path.resolve()),
        },
        "accounting": {
            "expected_analyzed_outcomes": expected,
            "observed_analyzed_outcomes": len(analyzed_records),
            "valid_outcomes": sum(record.validation.valid for record in analyzed_records),
            "failed_outcomes": sum(not record.validation.valid for record in analyzed_records),
            "raw_measured_records": len(raw_records),
            "superseded_transport_records": resolution.superseded_transport_attempts,
            "legacy_implementation_deviation_records": resolution.implementation_deviation_attempts,
            "missing_outcomes": 0,
            "unexpected_outcomes": 0,
        },
        "results_in_configured_non_ranked_order": model_results,
        "advancement": {
            "eligible_models": eligible_models,
            "eligible_challenger_count": len(
                [model_id for model_id in eligible_models if model_id != "qwen25vl-3b-baseline"]
            ),
            "required_eligible_challengers": 2,
            "status": (
                "ready_for_quality_screening"
                if len([model_id for model_id in eligible_models if model_id != "qwen25vl-3b-baseline"]) >= 2
                else (
                    "candidate_amendment_failed_protocol_reassessment_required"
                    if is_candidate_amendment
                    else "candidate_amendment_required_before_quality_screening"
                )
            ),
        },
        "planning_estimates": {
            "screening_model_count": len(study.config.model_ids),
            "projected_120_item_configured_model_screening_wall_hours_at_pilot_rate": round(
                active_wall_seconds * (120 / len(manifest)) / 3600, 1
            ),
            "median_visible_fact_claims_per_valid_output": round(median(claim_counts), 1),
            "planned_three_condition_outputs_for_one_rated_repeat": finalist_outputs,
            "reviewer_burden_scenarios": reviewer_scenarios,
            "note": "Reviewer time scenarios are planning assumptions, not observed review-time estimates; calibrate before protocol freeze.",
        },
        "deviation_reference": deviation_reference,
        "limitations": [
            "Compatibility outcomes do not measure factual quality or establish a model ranking.",
            "Operational segmentation and unstable direct connectivity limit interpretation of latency as production throughput.",
            "Only public licensed images and fictional contexts traversed the temporary approved collection paths.",
            "The predeclared two-eligible-challenger advancement requirement was not met and must not be relaxed opportunistically.",
        ],
    }
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_render_markdown(evidence))
    return evidence_path, report_path


def _nearest_rank(values: list[float], probability: float) -> float:
    if not values:
        return 0.0
    return values[max(0, math.ceil(probability * len(values)) - 1)]


def _visual_fact_claim_count(payload: dict[str, Any]) -> int:
    count = 1 if payload.get("summary") else 0
    count += 1 if payload.get("setting") else 0
    for key in (
        "people",
        "objects",
        "visible_text",
        "uncertain_facts",
        "forbidden_inferences_observed",
    ):
        value = payload.get(key)
        if isinstance(value, list):
            count += len(value)
    return count


def _render_markdown(evidence: dict[str, Any]) -> str:
    lines = [
        (
            "# Candidate amendment compatibility report"
            if evidence["advancement"]["status"] == "candidate_amendment_failed_protocol_reassessment_required"
            else "# Compatibility pilot report"
        ),
        "",
        "This report establishes configuration compatibility only. It must not be used to rank model quality.",
        "",
        f"- Analyzed outcomes: `{evidence['accounting']['observed_analyzed_outcomes']}` / `{evidence['accounting']['expected_analyzed_outcomes']}`",
        f"- Raw measured records: `{evidence['accounting']['raw_measured_records']}`",
        f"- Superseded transport records: `{evidence['accounting']['superseded_transport_records']}`",
        f"- Frozen validity threshold: `{evidence['frozen_contract']['minimum_schema_valid_rate']:.0%}`",
        "",
        "| Model condition (configured order) | Valid | Rate | Gate | Median wall s | P95 wall s | Failure categories |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for result in evidence["results_in_configured_non_ranked_order"]:
        failures = ", ".join(
            f"{key}: {value}" for key, value in result["failure_categories"].items()
        ) or "none"
        lines.append(
            f"| `{result['model_id']}` | {result['valid']}/{result['observed']} | "
            f"{result['schema_valid_rate']:.0%} | {'pass' if result['threshold_met'] else 'fail'} | "
            f"{result['median_wall_seconds']:.1f} | {result['p95_wall_seconds_nearest_rank']:.1f} | {failures} |"
        )
    lines.extend(
        [
            "",
            "## Advancement consequence",
            "",
            _advancement_consequence(evidence),
            "",
            "## Planning estimates",
            "",
            f"At the pilot's summed analyzed-attempt rate, a 120-item {evidence['planning_estimates']['screening_model_count']}-model screen is approximately "
            f"`{evidence['planning_estimates']['projected_120_item_configured_model_screening_wall_hours_at_pilot_rate']}` active inference hours, excluding warm-ups, transport recovery, and operational pauses. "
            f"A three-condition, one-rated-repeat package contains `{evidence['planning_estimates']['planned_three_condition_outputs_for_one_rated_repeat']}` outputs.",
            "",
            "## Limitations",
            "",
        ]
    )
    lines.extend(f"- {limitation}" for limitation in evidence["limitations"])
    return "\n".join(lines) + "\n"


def _advancement_consequence(evidence: dict[str, Any]) -> str:
    eligible_models = evidence["advancement"]["eligible_models"]
    eligible = ", ".join(eligible_models)
    if evidence["advancement"]["status"] == "candidate_amendment_failed_protocol_reassessment_required":
        opening = (
            f"Only `{eligible}` met the gate within this amendment."
            if eligible_models
            else "No amendment model met the gate."
        )
        return (
            f"{opening} Neither amendment candidate qualified, "
            "so the candidate amendment did not create the required advancement set. Protocol reassessment "
            "is required before quality screening; the threshold must not be lowered after seeing these outcomes."
        )
    opening = f"Only `{eligible}` met the gate." if eligible_models else "No model met the gate."
    return (
        f"{opening} The required two eligible challengers are unavailable, so a "
        "candidate amendment is required before quality screening. The threshold must not be lowered after "
        "seeing these outcomes."
    )
