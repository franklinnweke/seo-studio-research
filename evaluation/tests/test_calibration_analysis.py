import pytest
from pydantic import ValidationError

from seo_studio_eval.calibration_analysis import _linear_weighted_kappa, _nominal_cohens_kappa
from seo_studio_eval.schemas import AnnotationRecord


def annotation_payload() -> dict[str, object]:
    return {
        "rubric_version": "rubric-v1.1",
        "record_type": "individual",
        "item_id": "pilot-001",
        "review_item_id": "blind-001",
        "blinded_condition_id": "C001",
        "reviewer_alias": "R1",
        "repeat": 1,
        "calibration_item": True,
        "claims": [],
        "factual_grounding_score": 5,
        "salient_coverage_score": 5,
        "contextual_usefulness_score": 5,
        "redundancy_control_score": 5,
        "purpose_appropriateness_score": 5,
        "brand_alignment_score": 5,
        "safety_score": 5,
        "concision_fluency_score": 5,
        "disposition": "accept_unchanged",
        "notes": "",
    }


def test_annotation_v11_accepts_complete_scores_and_complete_system_failure() -> None:
    assert AnnotationRecord.model_validate(annotation_payload()).rubric_version == "rubric-v1.1"
    failure = annotation_payload()
    for field in (
        "factual_grounding_score",
        "salient_coverage_score",
        "contextual_usefulness_score",
        "redundancy_control_score",
        "purpose_appropriateness_score",
        "brand_alignment_score",
        "safety_score",
        "concision_fluency_score",
    ):
        failure[field] = None
    failure["disposition"] = "reject"
    failure["notes"] = "system_failure_no_output"
    assert AnnotationRecord.model_validate(failure).factual_grounding_score is None


def test_annotation_rejects_partial_null_rating_pattern() -> None:
    payload = annotation_payload()
    payload["factual_grounding_score"] = None
    with pytest.raises(ValidationError, match="every rating to null"):
        AnnotationRecord.model_validate(payload)


def test_linear_weighted_kappa_handles_agreement_and_prevalence_collapse() -> None:
    assert _linear_weighted_kappa([1, 2, 3], [1, 2, 3], [1, 2, 3, 4, 5]) == 1.0
    assert _linear_weighted_kappa([5, 5], [5, 5], [1, 2, 3, 4, 5]) is None


def test_nominal_cohens_kappa() -> None:
    # 100% agreement
    assert _nominal_cohens_kappa(["a", "b"], ["a", "b"], ["a", "b"]) == 1.0
    # 0% agreement
    assert _nominal_cohens_kappa(["a", "b"], ["b", "a"], ["a", "b"]) == -1.0
    # Expected chance agreement = 0.5, observed = 0.5 -> Kappa = 0
    assert _nominal_cohens_kappa(["a", "b"], ["a", "a"], ["a", "b"]) == 0.0


def test_agreement_metric_exposes_kappa_fields() -> None:
    from seo_studio_eval.calibration_analysis import AgreementMetric
    metric = AgreementMetric(n=10, exact_agreement=0.9, kappa=0.8, kappa_method="cohens_kappa")
    assert metric.kappa == 0.8
    assert metric.kappa_method == "cohens_kappa"


def test_calibration_analysis_invalid_rendering() -> None:
    from seo_studio_eval.calibration_analysis import CalibrationAnalysis, _render_report, AgreementMetric
    analysis = CalibrationAnalysis(
        status="invalid",
        calibration_items=15,
        valid_output_items=12,
        system_failure_items=3,
        reviewer_records={"R1": 15, "R2": 14},
        adjudicated_records=15,
        claim_counts={"R1": 73, "R2": 68, "adjudicated": 73},
        claim_label_agreement_estimable=False,
        claim_label_agreement=None,
        rating_agreement={},
        disposition_agreement_all_items=AgreementMetric(n=15),
        disposition_agreement_valid_outputs=AgreementMetric(n=12),
        timing={},
        projected_active_minutes_for_60_items={},
        source_sha256={},
        blocking_findings=["R2: review item population does not match calibration package"],
        cautions=[]
    )
    report = _render_report(analysis)
    assert "do not contain a complete, valid" in report
    assert "Metrics must not be interpreted until the listed population and input errors are corrected." in report
