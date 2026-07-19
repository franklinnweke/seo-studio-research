import json
from pathlib import Path
from typing import Any

from seo_studio_eval.blinding import build_blinded_package
from seo_studio_eval.calibration import build_calibration_package
from seo_studio_eval.config import load_study
from seo_studio_eval.dataset import load_manifest
from seo_studio_eval.normalization import normalize_metadata_pipeline
from seo_studio_eval.records import write_attempt_record
from seo_studio_eval.runner import AttemptSpec, execute_attempt
from seo_studio_eval.schemas import InputEvidence, ModelIdentity, PromptEvidence, VisualFactsPayload
from seo_studio_eval.writer_matrix import build_writer_matrix_report, run_writer_matrix


class MatrixTransport:
    def __init__(self, writer_name: str, writer_digest: str) -> None:
        self.writer_name = writer_name
        self.writer_digest = writer_digest
        self.requests: list[dict[str, Any]] = []

    def version(self) -> str:
        return "0.24.0"

    def tags(self) -> dict[str, Any]:
        return {"models": [{"name": self.writer_name, "digest": self.writer_digest}]}

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(request)
        return {
            "response": json.dumps(
                {
                    "filename": "grounded-scene",
                    "alt_text": "A grounded scene.",
                    "caption": "A grounded scene is shown.",
                    "confidence": 0.8,
                    "purpose_rationale": "The confirmed purpose requires a concise description.",
                    "warnings": [],
                }
            ),
            "done_reason": "stop",
        }


class FactsTransport:
    def __init__(self, valid: bool = True) -> None:
        self.valid = valid

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        if not self.valid:
            return {"response": '{"summary":', "done_reason": "length"}
        return {
            "response": json.dumps(
                {
                    "summary": "A grounded scene.",
                    "people": [],
                    "objects": ["object"],
                    "setting": "indoor",
                    "visible_text": [],
                    "uncertain_facts": [],
                    "forbidden_inferences_observed": [],
                }
            ),
            "done_reason": "stop",
        }


def test_writer_matrix_preserves_upstream_failure_and_builds_balanced_blind_package(
    tmp_path: Path,
) -> None:
    evaluation_root = Path(__file__).resolve().parents[1]
    config_path = evaluation_root / "configs" / "pilot.toml"
    study = load_study(config_path)
    models = {model.id: model for model in study.models.models}
    selected_models = ["qwen25vl-3b-baseline", "qwen35-9b", "gemma3-12b"]
    items = {
        item.id: item
        for item in load_manifest(study.root, study.config.dataset_manifest)
        if item.id in {"healthcare-doctor-consultation-001", "healthcare-blood-pressure-003"}
    }
    source_dir = tmp_path / "source"
    repair_dir = tmp_path / "repair"
    attempt_number = 0
    for model_id in selected_models:
        model = models[model_id]
        for image_id, item in sorted(items.items()):
            attempt_number += 1
            spec = AttemptSpec(
                experiment_id="seo-studio-pilot-v1",
                protocol_version="2.1-pilot",
                run_id="source-test",
                attempt_id=f"source-{attempt_number:02d}",
                repeat=1,
                randomization_block=model_id,
                git_commit="abc123",
                dirty_worktree=False,
                ollama_version="0.24.0",
                system_snapshot_ref="private-test-snapshot",
                model=ModelIdentity(
                    id=model.id,
                    ollama_name=model.ollama_name,
                    digest=model.expected_digest,
                    family=model.family,
                    parameters=model.parameters,
                    quantization=model.quantization,
                    license=model.license,
                ),
                input=InputEvidence(
                    image_id=image_id,
                    image_sha256=item.sha256,
                    dataset_stratum=item.domain,
                    purpose=item.purpose,
                    page_context_sha256=item.page_context_sha256,
                    brand_profile_sha256=item.brand_profile_sha256,
                ),
                prompt=PromptEvidence(
                    prompt_id="vision-facts-v1",
                    prompt_sha256="a" * 64,
                    schema_sha256="b" * 64,
                    system_prompt_sha256="c" * 64,
                ),
                generation_options={"temperature": 0},
                sanitized_request={"model": model.ollama_name},
            )
            is_failed_cell = model_id == "qwen25vl-3b-baseline" and image_id.endswith("003")
            write_attempt_record(
                source_dir,
                execute_attempt(
                    spec,
                    FactsTransport(valid=not is_failed_cell),
                    response_model=VisualFactsPayload,
                ),
            )
    (source_dir / "pilot-summary.json").write_text(
        json.dumps({"status": "complete", "run_id": "source-test"}) + "\n"
    )
    repair_dir.mkdir(parents=True)
    (repair_dir / "truncation-repair-summary.json").write_text(
        json.dumps({"status": "complete", "run_id": "repair-test"}) + "\n"
    )
    criteria_path = tmp_path / "writer-matrix.toml"
    criteria_path.write_text(
        "\n".join(
            [
                "schema_version = 1",
                'criteria_id = "writer-matrix-test"',
                'experiment_id = "seo-studio-writer-matrix-test"',
                'protocol_version = "2.4-test"',
                'source_run_id = "source-test"',
                'repair_run_id = "repair-test"',
                'source_model_ids = ["qwen25vl-3b-baseline", "qwen35-9b", "gemma3-12b"]',
                'writer_model_id = "qwen35-9b"',
                'prompt_id = "context-writer-v1"',
                "temperature = 0",
                "seed = 20260716",
                'thinking_mode = "disabled"',
                "context_window = 8192",
                "output_token_limit = 420",
                "per_attempt_timeout_seconds = 240",
                'keep_alive = "10m"',
                "hidden_retries_allowed = 0",
                "max_transport_attempts_per_cell = 3",
                "expected_source_cells = 6",
                "expected_writer_calls = 5",
                "expected_upstream_failures = 1",
                "pixels_sent_to_writer = false",
                "validation_retries_allowed = 0",
            ]
        )
        + "\n"
    )

    writer = models["qwen35-9b"]
    transport = MatrixTransport(writer.ollama_name, writer.expected_digest)
    writer_dir = tmp_path / "writer"
    summary, _ = run_writer_matrix(
        config_path,
        criteria_path,
        [source_dir],
        [repair_dir],
        "http://127.0.0.1:11434",
        writer_dir,
        "writer-matrix-test",
        "private-test-snapshot",
        transport=transport,
    )

    assert summary.status == "complete"
    assert summary.expected_source_cells == 6
    assert summary.observed_writer_outcomes == 5
    assert summary.upstream_failures == 1
    assert len(transport.requests) == 5
    assert all("images" not in request for request in transport.requests)
    evidence_path, report_path = build_writer_matrix_report(
        writer_dir / "writer-matrix-summary.json",
        tmp_path / "results" / "writer-matrix.json",
        tmp_path / "results" / "writer-matrix.md",
    )
    assert json.loads(evidence_path.read_text())["quality_ranking_permitted"] is False
    assert "Do not use this report to rank" in report_path.read_text()

    normalized_summary, normalized_path = normalize_metadata_pipeline(
        [source_dir],
        [repair_dir],
        writer_dir,
        tmp_path / "normalized",
        model_ids=selected_models,
        writer_criteria_path=criteria_path,
        writer_run_id="writer-matrix-test",
    )
    assert normalized_summary.status == "normalized"
    assert normalized_summary.records_written == 6
    assert normalized_summary.upstream_failures_preserved == 1
    rows = [json.loads(line) for line in normalized_path.read_text().splitlines()]
    assert sum(row["pipeline_stage"] == "upstream_failure" for row in rows) == 1
    assert sum(row["pipeline_stage"] == "fixed_writer" for row in rows) == 5

    blind_summary, package_path, mapping_path = build_blinded_package(
        normalized_path,
        tmp_path / "review",
        tmp_path / "private",
        seed=20260716,
    )
    assert blind_summary.status == "ready"
    assert blind_summary.items_written == 6
    assert blind_summary.invalid_items == 1
    assert "qwen35-9b" not in package_path.read_text()
    assert "writer_attempt_id" in mapping_path.read_text()

    calibration_summary, calibration_path, timing_path = build_calibration_package(
        package_path,
        tmp_path / "calibration",
        seed=20260716,
        image_count=1,
        expected_conditions=3,
    )
    assert calibration_summary.status == "ready"
    assert calibration_summary.items_written == 3
    assert len(calibration_path.read_text().splitlines()) == 3
    assert len(json.loads(timing_path.read_text())["items"]) == 3
