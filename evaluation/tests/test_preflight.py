from pathlib import Path
import shutil

import pytest

from seo_studio_eval.config import load_study
from seo_studio_eval.preflight import run_preflight


EVALUATION_ROOT = Path(__file__).resolve().parents[1]


def copy_evaluation_fixture(tmp_path: Path, config_name: str = "pilot.toml") -> Path:
    shutil.copytree(EVALUATION_ROOT / "configs", tmp_path / "configs")
    shutil.copytree(EVALUATION_ROOT / "dataset", tmp_path / "dataset")
    return tmp_path / "configs" / config_name


def test_offline_preflight_validates_hashes_and_reports_unfrozen_models(tmp_path: Path) -> None:
    config_path = copy_evaluation_fixture(tmp_path)

    summary, output_path = run_preflight(config_path)

    assert summary.status == "ready"
    assert summary.dataset_items_checked == 20
    assert summary.selected_models_checked == 5
    assert summary.domain_counts == {
        "education_professional_service": 5,
        "healthcare": 5,
        "hospitality_local_service": 5,
        "retail_product": 5,
    }
    assert summary.purpose_counts == {
        "complex": 1,
        "decorative": 2,
        "functional": 2,
        "informative": 12,
        "redundant": 1,
        "text": 2,
    }
    assert any("not protocol-frozen" in warning for warning in summary.warnings)
    assert output_path.is_file()


def test_offline_preflight_fails_after_dataset_tampering(tmp_path: Path) -> None:
    config_path = copy_evaluation_fixture(tmp_path, "contract.toml")
    (tmp_path / "dataset" / "fixtures" / "solid-blue.png").write_text("tampered")

    summary, _ = run_preflight(config_path)

    assert summary.status == "incomplete"
    assert "synthetic-solid-blue-001: image SHA-256 mismatch" in summary.errors
    assert "synthetic-solid-blue-001: image byte count mismatch" in summary.errors
    assert any("image could not be decoded" in error for error in summary.errors)


def test_full_study_rejects_unfrozen_models_and_dirty_override(tmp_path: Path) -> None:
    config_path = copy_evaluation_fixture(tmp_path)
    content = config_path.read_text().replace('study_mode = "pilot"', 'study_mode = "full"')
    content = content.replace("require_frozen_models = false", "require_frozen_models = true")
    config_path.write_text(content)

    with pytest.raises(ValueError, match="unfrozen models"):
        load_study(config_path)
