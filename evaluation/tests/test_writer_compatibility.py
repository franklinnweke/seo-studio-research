import json
from pathlib import Path
from typing import Any

from seo_studio_eval.config import load_study
from seo_studio_eval.pilot import run_compatibility_pilot
from seo_studio_eval.writer_compatibility import run_writer_compatibility


class FullyValidTransport:
    def __init__(self, tags: list[dict[str, str]]) -> None:
        self._tags = tags
        self.requests: list[dict[str, Any]] = []

    def version(self) -> str:
        return "0.24.0"

    def tags(self) -> dict[str, Any]:
        return {"models": self._tags}

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(request)
        if "images" in request:
            payload = {
                "summary": "A grounded scene.",
                "people": [],
                "objects": ["object"],
                "setting": "indoor",
                "visible_text": [],
                "uncertain_facts": [],
                "forbidden_inferences_observed": [],
            }
        else:
            payload = {
                "filename": "grounded-scene",
                "alt_text": "A grounded scene.",
                "caption": "A grounded scene is shown.",
                "confidence": 0.8,
                "purpose_rationale": "The confirmed purpose requires a concise description.",
                "warnings": [],
            }
        return {
            "response": json.dumps(payload),
            "done_reason": "stop",
            "total_duration": 100,
        }


def test_writer_compatibility_uses_common_facts_without_images(tmp_path: Path) -> None:
    evaluation_root = Path(__file__).resolve().parents[1]
    config_path = evaluation_root / "configs" / "pilot.toml"
    study = load_study(config_path)
    configured = {model.id: model for model in study.models.models}
    tags = [
        {
            "name": configured[model_id].ollama_name,
            "digest": configured[model_id].expected_digest,
        }
        for model_id in study.config.model_ids
    ]
    source_transport = FullyValidTransport(tags)
    source_dir = tmp_path / "source"
    run_compatibility_pilot(
        config_path,
        evaluation_root / "configs" / "compatibility-criteria.toml",
        "http://127.0.0.1:11435",
        source_dir,
        "pilot-compatibility-clean6-20260716",
        "private-test-snapshot",
        transport=source_transport,
    )

    writer_transport = FullyValidTransport(tags)
    summary, summary_path = run_writer_compatibility(
        config_path,
        evaluation_root / "configs" / "writer-compatibility-criteria.toml",
        source_dir,
        "http://127.0.0.1:11435",
        tmp_path / "writer",
        "writer-compatibility-test",
        "private-test-snapshot",
        transport=writer_transport,
    )

    assert summary.status == "complete"
    assert summary.expected_outcomes == 5
    assert summary.valid_outcomes == 5
    assert summary.threshold_met is True
    assert summary.selected_image_id == "education-history-infographic-020"
    assert summary_path.is_file()
    assert len(writer_transport.requests) == 5
    assert all("images" not in request for request in writer_transport.requests)
    assert all(request["think"] is False for request in writer_transport.requests)
    assert all(request["options"]["num_ctx"] == 8192 for request in writer_transport.requests)
