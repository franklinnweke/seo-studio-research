from pathlib import Path
import json
import tomllib

from seo_studio_eval.config import ModelEntry, load_study
from seo_studio_eval.dataset import load_manifest
from seo_studio_eval.records import read_attempt_record, write_attempt_record
from seo_studio_eval.runner import AttemptSpec, execute_attempt
from seo_studio_eval.schemas import InputEvidence, ModelIdentity, PromptEvidence, VisualFactsPayload
from seo_studio_eval.truncation_repair import (
    TruncationRepairCriteria,
    run_truncation_repair,
    select_truncation_sources,
)


class TruncatedTransport:
    def generate(self, request):
        return {"response": '{"summary":"unfinished"', "done_reason": "length"}


class SuccessfulRepairTransport:
    def __init__(self, tags):
        self._tags = tags
        self.requests = []

    def version(self):
        return "0.24.0"

    def tags(self):
        return {"models": self._tags}

    def generate(self, request):
        self.requests.append(request)
        return {
            "response": json.dumps(
                {
                    "summary": "A repaired test image.",
                    "people": [],
                    "objects": [],
                    "setting": "",
                    "visible_text": [],
                    "uncertain_facts": [],
                    "forbidden_inferences_observed": [],
                }
            ),
            "done_reason": "stop",
        }


def test_truncation_repair_population_selects_only_frozen_length_outcomes(tmp_path: Path) -> None:
    digest = "a" * 64
    model = ModelEntry(
        id="model-a",
        ollama_name="model:a",
        expected_digest=digest,
        family="Test",
        parameters="1B",
        quantization="Q4",
        role="vision_candidate",
        license="Apache-2.0",
    )
    spec = AttemptSpec(
        experiment_id="source-pilot",
        protocol_version="2.1-pilot",
        run_id="source-run",
        attempt_id="source-length-001",
        repeat=1,
        randomization_block="block-1",
        git_commit="abc123",
        dirty_worktree=False,
        ollama_version="0.24.0",
        system_snapshot_ref="snapshot",
        model=ModelIdentity(
            id=model.id,
            ollama_name=model.ollama_name,
            digest=digest,
            family=model.family,
            parameters=model.parameters,
            quantization=model.quantization,
            license=model.license,
        ),
        input=InputEvidence(
            image_id="image-001",
            image_sha256="b" * 64,
            dataset_stratum="test",
            purpose="informative",
            page_context_sha256="c" * 64,
            brand_profile_sha256="d" * 64,
        ),
        prompt=PromptEvidence(
            prompt_id="vision-facts-v1",
            prompt_sha256="e" * 64,
            schema_sha256="f" * 64,
            system_prompt_sha256="0" * 64,
        ),
        generation_options={"temperature": 0, "seed": 42, "num_predict": 384},
        thinking_mode="disabled",
        sanitized_request={"model": model.ollama_name},
    )
    record = execute_attempt(spec, TruncatedTransport(), response_model=VisualFactsPayload)
    write_attempt_record(tmp_path, record)
    criteria = TruncationRepairCriteria(
        schema_version=1,
        criteria_id="repair-test",
        purpose="test",
        source_done_reason="length",
        source_output_token_limit=384,
        recovery_output_token_limit=768,
        expected_repairs=1,
        required_repairs_by_model={"model-a": 1},
        per_attempt_timeout_seconds=240,
        hidden_retries_allowed=0,
        explicit_repair_attempts_per_truncation=1,
        abort_on_transport_error=True,
        max_transport_attempts_per_item=3,
        temperature=0,
        seed=42,
        thinking_mode="disabled",
        warmup_manifest=Path("dataset/manifest-contract.jsonl"),
        warmup_image_id="synthetic-solid-blue-001",
        keep_alive="10m",
    )

    selected = select_truncation_sources([tmp_path], {model.id: model}, criteria)

    assert list(selected.values()) == [record]


def test_truncation_repair_executes_only_frozen_source_population(tmp_path: Path) -> None:
    evaluation_root = Path(__file__).resolve().parents[1]
    config_path = evaluation_root / "configs" / "pilot-truncation-repair.toml"
    criteria_path = evaluation_root / "configs" / "truncation-repair-criteria.toml"
    study = load_study(config_path)
    criteria = TruncationRepairCriteria.model_validate(tomllib.loads(criteria_path.read_text()))
    models = {model.id: model for model in study.models.models}
    manifest = load_manifest(study.root, study.config.dataset_manifest)
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "repair"
    source_index = 0
    for model_id, required in criteria.required_repairs_by_model.items():
        model = models[model_id]
        for item in manifest[:required]:
            source_index += 1
            spec = AttemptSpec(
                experiment_id="source-pilot",
                protocol_version="2.1-pilot",
                run_id="source-run",
                attempt_id=f"source-length-{source_index:03d}",
                repeat=1,
                randomization_block="source",
                git_commit="abc123",
                dirty_worktree=False,
                ollama_version="0.24.0",
                system_snapshot_ref="source-snapshot",
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
                    image_id=item.id,
                    image_sha256=item.sha256,
                    dataset_stratum=item.domain,
                    purpose=item.purpose,
                    page_context_sha256=item.page_context_sha256,
                    brand_profile_sha256=item.brand_profile_sha256,
                ),
                prompt=PromptEvidence(
                    prompt_id="vision-facts-v1",
                    prompt_sha256="e" * 64,
                    schema_sha256="f" * 64,
                    system_prompt_sha256="e" * 64,
                ),
                generation_options={
                    "temperature": 0,
                    "seed": criteria.seed,
                    "num_predict": criteria.source_output_token_limit,
                },
                thinking_mode="disabled",
                sanitized_request={"model": model.ollama_name},
            )
            write_attempt_record(
                source_dir,
                execute_attempt(spec, TruncatedTransport(), response_model=VisualFactsPayload),
            )
    transport = SuccessfulRepairTransport(
        [
            {"name": models[model_id].ollama_name, "digest": models[model_id].expected_digest}
            for model_id in study.config.model_ids
        ]
    )

    summary, summary_path = run_truncation_repair(
        config_path,
        criteria_path,
        [source_dir],
        "http://127.0.0.1:11435",
        output_dir,
        "repair-test-run",
        "private-test-snapshot",
        transport=transport,
    )

    assert summary.status == "complete"
    assert summary.expected_repairs == 15
    assert summary.observed_repairs == 15
    assert summary.valid_repairs == 15
    assert summary.all_truncations_repaired is True
    assert summary.warmup_records == 5
    assert len(transport.requests) == 20
    assert summary_path.is_file()
    assert (output_dir / "plans" / "truncation-repair-plan.json").is_file()
    measured = [
        read_attempt_record(path)
        for path in output_dir.glob("*.json")
        if not path.name.endswith("-summary.json")
    ]
    assert len(measured) == 15
    assert all(record.generation_options["num_predict"] == 768 for record in measured)
    assert all(record.sanitized_request["repair_trigger"] == "done_reason_length" for record in measured)
