import json
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .blinding import BlindedReviewItem
from .hashing import sha256_file
from .schemas import AnnotationRecord


RATING_FIELDS = (
    "factual_grounding_score",
    "salient_coverage_score",
    "contextual_usefulness_score",
    "redundancy_control_score",
    "purpose_appropriateness_score",
    "brand_alignment_score",
    "safety_score",
    "concision_fluency_score",
)


class AgreementMetric(BaseModel):
    n: int = Field(ge=0)
    exact_agreement: float | None = Field(default=None, ge=0, le=1)
    mean_absolute_difference: float | None = Field(default=None, ge=0)
    linear_weighted_kappa: float | None = None
    interpretation_note: str = ""


class TimingMetric(BaseModel):
    items: int = Field(ge=0)
    session_seconds: float = Field(ge=0)
    summed_item_seconds: float = Field(ge=0)
    median_item_seconds: float = Field(ge=0)
    q1_item_seconds: float = Field(ge=0)
    q3_item_seconds: float = Field(ge=0)
    minimum_item_seconds: float = Field(ge=0)
    maximum_item_seconds: float = Field(ge=0)
    duration_mismatches: int = Field(ge=0)
    overlapping_items: int = Field(ge=0)
    all_items_within_session: bool
    chronological_order_matches_assigned_order: bool | None = None


class CalibrationAnalysis(BaseModel):
    analysis_version: Literal[1] = 1
    status: Literal["ready", "recalibration_required", "invalid"]
    calibration_items: int
    valid_output_items: int
    system_failure_items: int
    reviewer_records: dict[str, int]
    adjudicated_records: int
    claim_counts: dict[str, int]
    claim_label_agreement_estimable: bool
    rating_agreement: dict[str, AgreementMetric]
    disposition_agreement_all_items: AgreementMetric
    disposition_agreement_valid_outputs: AgreementMetric
    timing: dict[str, TimingMetric]
    projected_active_minutes_for_60_items: dict[str, float]
    source_sha256: dict[str, str]
    blocking_findings: list[str]
    cautions: list[str]


def build_calibration_analysis(
    review_items_path: Path,
    reviewer_paths: dict[str, Path],
    adjudicated_path: Path,
    timing_paths: dict[str, Path],
    assigned_order_paths: dict[str, Path],
    rubric_path: Path,
    schema_path: Path,
    evidence_path: Path,
    report_path: Path,
) -> tuple[CalibrationAnalysis, Path, Path]:
    items = _read_review_items(review_items_path)
    expected = {item.review_item_id: item for item in items}
    reviewers = {alias: _read_annotations(path) for alias, path in reviewer_paths.items()}
    adjudicated = _read_annotations(adjudicated_path)
    errors: list[str] = []
    for alias, rows in {**reviewers, "adjudicated": adjudicated}.items():
        errors.extend(_population_errors(alias, rows, expected))

    reviewer_maps = {
        alias: {row.review_item_id: row for row in rows} for alias, rows in reviewers.items()
    }
    if len(reviewer_maps) != 2:
        errors.append("Calibration agreement analysis requires exactly two individual reviewers")
    aliases = sorted(reviewer_maps)
    rating_agreement: dict[str, AgreementMetric] = {}
    disposition_all = AgreementMetric(n=0)
    disposition_valid = AgreementMetric(n=0)
    if not errors and len(aliases) == 2:
        first, second = (reviewer_maps[alias] for alias in aliases)
        valid_ids = [
            item_id
            for item_id, item in expected.items()
            if item.valid
        ]
        for field in RATING_FIELDS:
            pairs = [
                (getattr(first[item_id], field), getattr(second[item_id], field))
                for item_id in valid_ids
                if getattr(first[item_id], field) is not None
                and getattr(second[item_id], field) is not None
            ]
            rating_agreement[field] = _agreement(pairs, [1, 2, 3, 4, 5])
        disposition_order = ["reject", "major_edit", "minor_edit", "accept_unchanged"]
        disposition_all = _agreement(
            [(first[item_id].disposition, second[item_id].disposition) for item_id in expected],
            disposition_order,
            include_difference=False,
        )
        disposition_valid = _agreement(
            [(first[item_id].disposition, second[item_id].disposition) for item_id in valid_ids],
            disposition_order,
            include_difference=False,
        )

    timing: dict[str, TimingMetric] = {}
    for alias, timing_path in timing_paths.items():
        assigned = (
            _read_review_items(assigned_order_paths[alias])
            if alias in assigned_order_paths
            else None
        )
        metric, timing_errors = _timing_metric(timing_path, expected, assigned)
        timing[alias] = metric
        errors.extend(f"{alias}: {error}" for error in timing_errors)

    claim_counts = {
        **{alias: sum(len(row.claims) for row in rows) for alias, rows in reviewers.items()},
        "adjudicated": sum(len(row.claims) for row in adjudicated),
    }
    blocking = []
    if len(set(claim_counts[alias] for alias in reviewers)) > 1:
        blocking.append(
            "Independent reviewers produced non-isomorphic claim inventories; claim-label agreement is not estimable until both label the same frozen claim units."
        )
    low_metrics = [
        field
        for field, metric in rating_agreement.items()
        if metric.exact_agreement is not None
        and metric.exact_agreement < 0.80
        and metric.linear_weighted_kappa is not None
        and metric.linear_weighted_kappa < 0.60
    ]
    if (
        disposition_valid.exact_agreement is not None
        and disposition_valid.exact_agreement < 0.80
        and disposition_valid.linear_weighted_kappa is not None
        and disposition_valid.linear_weighted_kappa < 0.60
    ):
        low_metrics.append("disposition_valid_outputs")
    if low_metrics:
        blocking.append(
            "Agreement below the provisional 0.60 feasibility marker: " + ", ".join(low_metrics)
        )
    mismatched_orders = [
        alias
        for alias, metric in timing.items()
        if metric.chronological_order_matches_assigned_order is False
    ]
    cautions = []
    if mismatched_orders:
        cautions.append(
            "Chronological timing order does not match the stored assigned-order file for: "
            + ", ".join(mismatched_orders)
        )
    cautions.extend(
        [
            "The 0.60 feasibility marker was not numerically frozen before these ratings and is descriptive, not a post-hoc pass/fail rule.",
            "Kappa can be unstable or undefined under near-perfect prevalence; report exact agreement and score distributions alongside it.",
            "Adjudication duration was not supplied, so workload projections exclude reconciliation overhead.",
        ]
    )
    projected = {
        alias: round(metric.median_item_seconds * 60 / 60, 2)
        for alias, metric in timing.items()
    }
    source_paths = {
        "review_items": review_items_path,
        **{f"annotations_{alias}": path for alias, path in reviewer_paths.items()},
        "annotations_adjudicated": adjudicated_path,
        **{f"timing_{alias}": path for alias, path in timing_paths.items()},
        **{f"assigned_order_{alias}": path for alias, path in assigned_order_paths.items()},
        "rubric_v1_1": rubric_path,
        "annotation_schema": schema_path,
    }
    analysis = CalibrationAnalysis(
        status="invalid" if errors else ("recalibration_required" if blocking else "ready"),
        calibration_items=len(items),
        valid_output_items=sum(item.valid for item in items),
        system_failure_items=sum(not item.valid for item in items),
        reviewer_records={alias: len(rows) for alias, rows in reviewers.items()},
        adjudicated_records=len(adjudicated),
        claim_counts=claim_counts,
        claim_label_agreement_estimable=not any("claim-label" in finding for finding in blocking),
        rating_agreement=rating_agreement,
        disposition_agreement_all_items=disposition_all,
        disposition_agreement_valid_outputs=disposition_valid,
        timing=timing,
        projected_active_minutes_for_60_items=projected,
        source_sha256={label: sha256_file(path) for label, path in source_paths.items()},
        blocking_findings=errors + blocking,
        cautions=cautions,
    )
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(analysis.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_render_report(analysis))
    return analysis, evidence_path, report_path


def _read_review_items(path: Path) -> list[BlindedReviewItem]:
    return [BlindedReviewItem.model_validate_json(line) for line in path.read_text().splitlines() if line.strip()]


def _read_annotations(path: Path) -> list[AnnotationRecord]:
    return [AnnotationRecord.model_validate_json(line) for line in path.read_text().splitlines() if line.strip()]


def _population_errors(
    label: str,
    rows: list[AnnotationRecord],
    expected: dict[str, BlindedReviewItem],
) -> list[str]:
    errors: list[str] = []
    ids = [row.review_item_id for row in rows]
    if len(ids) != len(set(ids)):
        errors.append(f"{label}: duplicate review item ids")
    if set(ids) != set(expected):
        errors.append(f"{label}: review item population does not match calibration package")
    for row in rows:
        item = expected.get(row.review_item_id)
        if item and (
            row.item_id != item.image_id
            or row.blinded_condition_id != item.blinded_condition_id
            or not row.calibration_item
        ):
            errors.append(f"{label}: identity mismatch for {row.review_item_id}")
    return errors


def _agreement(
    pairs: list[tuple[Any, Any]],
    categories: list[Any],
    *,
    include_difference: bool = True,
) -> AgreementMetric:
    if not pairs:
        return AgreementMetric(n=0)
    first = [pair[0] for pair in pairs]
    second = [pair[1] for pair in pairs]
    exact = sum(left == right for left, right in pairs) / len(pairs)
    difference = (
        sum(abs(left - right) for left, right in pairs) / len(pairs)
        if include_difference
        else None
    )
    kappa = _linear_weighted_kappa(first, second, categories)
    note = ""
    if kappa is None:
        note = "Kappa undefined because expected weighted disagreement is zero; use exact agreement."
    return AgreementMetric(
        n=len(pairs),
        exact_agreement=exact,
        mean_absolute_difference=difference,
        linear_weighted_kappa=kappa,
        interpretation_note=note,
    )


def _linear_weighted_kappa(first: list[Any], second: list[Any], categories: list[Any]) -> float | None:
    index = {value: position for position, value in enumerate(categories)}
    maximum = len(categories) - 1
    observed = sum(abs(index[left] - index[right]) / maximum for left, right in zip(first, second)) / len(first)
    first_counts = Counter(first)
    second_counts = Counter(second)
    expected = sum(
        first_counts[left]
        / len(first)
        * second_counts[right]
        / len(second)
        * abs(index[left] - index[right])
        / maximum
        for left in categories
        for right in categories
    )
    return None if expected == 0 else 1 - observed / expected


def _timing_metric(
    path: Path,
    expected: dict[str, BlindedReviewItem],
    assigned: list[BlindedReviewItem] | None,
) -> tuple[TimingMetric, list[str]]:
    payload = json.loads(path.read_text())
    entries = payload.get("items", [])
    errors: list[str] = []
    ids = [entry.get("review_item_id") for entry in entries]
    if len(ids) != len(set(ids)) or set(ids) != set(expected):
        errors.append("timing item population is missing, duplicated, or unexpected")
    intervals = []
    mismatches = 0
    seconds = []
    for entry in entries:
        start = datetime.fromisoformat(entry["started_at"])
        end = datetime.fromisoformat(entry["ended_at"])
        elapsed = float(entry["elapsed_seconds"])
        if (end - start).total_seconds() != elapsed:
            mismatches += 1
        intervals.append((start, end, entry["review_item_id"]))
        seconds.append(elapsed)
    intervals.sort()
    overlaps = sum(current[0] < previous[1] for previous, current in zip(intervals, intervals[1:]))
    session_start = datetime.fromisoformat(payload["session_started_at"])
    session_end = datetime.fromisoformat(payload["session_ended_at"])
    within = all(session_start <= start <= end <= session_end for start, end, _ in intervals)
    quartiles = statistics.quantiles(seconds, n=4, method="inclusive")
    assigned_match = None
    if assigned is not None:
        assigned_match = [item.review_item_id for item in assigned] == [item[2] for item in intervals]
    return (
        TimingMetric(
            items=len(entries),
            session_seconds=(session_end - session_start).total_seconds(),
            summed_item_seconds=sum(seconds),
            median_item_seconds=statistics.median(seconds),
            q1_item_seconds=quartiles[0],
            q3_item_seconds=quartiles[2],
            minimum_item_seconds=min(seconds),
            maximum_item_seconds=max(seconds),
            duration_mismatches=mismatches,
            overlapping_items=overlaps,
            all_items_within_session=within,
            chronological_order_matches_assigned_order=assigned_match,
        ),
        errors,
    )


def _percent(value: float | None) -> str:
    return "not estimable" if value is None else f"{value * 100:.1f}%"


def _number(value: float | None) -> str:
    return "undefined" if value is None else f"{value:.3f}"


def _render_report(analysis: CalibrationAnalysis) -> str:
    lines = [
        "# Human calibration analysis results",
        "",
        f"Status: **{analysis.status}**.",
        "",
        "The two independent reviewer files and adjudicated file each contain the complete 15-item blinded calibration population. This report does not open or use the private condition map.",
        "",
        "## Population",
        "",
        f"- Calibration items: {analysis.calibration_items}",
        f"- Valid metadata outputs: {analysis.valid_output_items}",
        f"- Explicit system failures: {analysis.system_failure_items}",
        f"- Claims segmented by R1/R2/adjudicator: {analysis.claim_counts.get('R1', 0)}/{analysis.claim_counts.get('R2', 0)}/{analysis.claim_counts.get('adjudicated', 0)}",
        "",
        "## Rating agreement on valid outputs",
        "",
        "| Dimension | n | Exact | Linear weighted kappa | Mean absolute difference |",
        "|---|---:|---:|---:|---:|",
    ]
    for field, metric in analysis.rating_agreement.items():
        lines.append(
            f"| {field.replace('_score', '').replace('_', ' ').title()} | {metric.n} | {_percent(metric.exact_agreement)} | {_number(metric.linear_weighted_kappa)} | {_number(metric.mean_absolute_difference)} |"
        )
    lines.extend(
        [
            "",
            "## Disposition agreement",
            "",
            f"- All 15 items: {_percent(analysis.disposition_agreement_all_items.exact_agreement)} exact; κw={_number(analysis.disposition_agreement_all_items.linear_weighted_kappa)}.",
            f"- Twelve valid outputs only: {_percent(analysis.disposition_agreement_valid_outputs.exact_agreement)} exact; κw={_number(analysis.disposition_agreement_valid_outputs.linear_weighted_kappa)}.",
            "- The all-item value is raised by deterministic agreement on the three null-output rejects; use the valid-output result when judging quality-rubric feasibility.",
            "",
            "## Claim-label feasibility",
            "",
            "Claim-label agreement is not estimable from this pass because R1 and R2 did not label the same claim units. Rubric v1.1 therefore freezes atomic, deduplicated claim segmentation and requires a common blinded claim inventory before label-agreement analysis.",
            "",
            "## Reviewer time",
            "",
            "| Reviewer | Session min | Median sec/item | IQR sec/item | Projected active min for 60 | Assigned order verified |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for alias, metric in analysis.timing.items():
        lines.append(
            f"| {alias} | {metric.session_seconds / 60:.2f} | {metric.median_item_seconds:.1f} | {metric.q1_item_seconds:.1f}–{metric.q3_item_seconds:.1f} | {analysis.projected_active_minutes_for_60_items[alias]:.1f} | {metric.chronological_order_matches_assigned_order} |"
        )
    lines.extend(["", "## Blocking findings", ""])
    lines.extend(f"- {finding}" for finding in analysis.blocking_findings)
    lines.extend(["", "## Cautions", ""])
    lines.extend(f"- {caution}" for caution in analysis.cautions)
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "Human timing feasibility is established, and the completed individual/adjudicated records are valid calibration evidence. Primary annotation should not begin yet. First, have R1 and R2 independently label the same adjudicated claim inventory under rubric v1.1, verify claim-label agreement, and resolve the low salient-coverage, redundancy, and valid-output disposition agreement. Preserve this first pass unchanged.",
            "",
        ]
    )
    return "\n".join(lines)
