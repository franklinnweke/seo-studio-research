import json
from pathlib import Path

from seo_studio_eval.sample_size import build_sample_size_sensitivity


EVALUATION_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = EVALUATION_ROOT / "configs" / "full-study-protocol-v1.json"


def test_sample_size_sensitivity_is_deterministic_and_pre_data(tmp_path: Path) -> None:
    summary, output_path = build_sample_size_sensitivity(PROTOCOL, tmp_path / "sample-size.json")

    assert summary.status == "decision_recorded"
    assert summary.selected_decision == "estimation_first"
    assert summary.alpha_two_sided == 0.05
    assert summary.target_power == 0.80
    assert summary.rq1[0].independent_claims_per_condition == 435
    assert summary.rq1[0].images_by_icc["0.10"] == 120
    assert summary.rq2[0].paired_images_with_reserve == 127
    assert summary.rq3.paired_images_with_reserve == 35
    assert json.loads(output_path.read_text())["status"] == "decision_recorded"
