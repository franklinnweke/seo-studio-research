import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Literal

from pydantic import BaseModel, Field

from .config import load_study, resolve_under_root
from .dataset import load_manifest
from .hashing import sha256_file
from .ollama import OllamaTransport
from .records import write_attempt_record
from .runner import AttemptSpec, execute_attempt
from .schemas import InputEvidence, ModelIdentity, PromptEvidence, VisualFactsPayload


class CompatibilityResult(BaseModel):
    model_id: str
    attempt_id: str
    valid: bool
    validation_errors: list[str] = Field(default_factory=list)
    wall_duration_ms: float = Field(ge=0)
    total_duration_ns: int = Field(ge=0)
    record_path: str


class CompatibilitySummary(BaseModel):
    status: Literal["compatible", "incomplete"]
    experiment_id: str
    image_id: str
    ollama_version: str
    timeout_seconds: float = Field(gt=0)
    results: list[CompatibilityResult]


def run_compatibility_smoke(
    config_path: Path,
    model_ids: list[str],
    image_id: str,
    base_url: str,
    output_dir: Path,
    timeout_seconds: float = 240.0,
) -> tuple[CompatibilitySummary, Path]:
    study = load_study(config_path)
    manifest = load_manifest(study.root, study.config.dataset_manifest)
    items = {item.id: item for item in manifest}
    if image_id not in items:
        raise ValueError(f"Unknown dataset image id: {image_id}")
    configured = {model.id: model for model in study.models.models}
    unknown = [model_id for model_id in model_ids if model_id not in study.config.model_ids]
    if unknown:
        raise ValueError(f"Models are not selected by the study config: {', '.join(unknown)}")
    if len(model_ids) != len(set(model_ids)):
        raise ValueError("Compatibility model ids must be unique")
    for model_id in model_ids:
        if not configured[model_id].expected_digest:
            raise ValueError(f"{model_id}: immutable digest is required before compatibility execution")

    transport = OllamaTransport(base_url, timeout_seconds=timeout_seconds)
    ollama_version = transport.version()
    item = items[image_id]
    image_path = resolve_under_root(study.root, item.image_path)
    image_base64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    prompt_path = study.root / "prompts" / "vision-facts-v1.txt"
    schema_path = study.root / "schemas" / "visual-facts.schema.json"
    prompt_text = prompt_path.read_text().strip()
    schema = VisualFactsPayload.model_json_schema()
    commit, dirty = _git_state(study.root.parent)
    run_id = datetime.now(timezone.utc).strftime("compatibility-%Y%m%dT%H%M%SZ")
    results: list[CompatibilityResult] = []

    for index, model_id in enumerate(model_ids, start=1):
        model = configured[model_id]
        attempt_id = f"{run_id}-{index:02d}-{model_id}-{image_id}"
        options = {"temperature": 0, "seed": study.config.seed, "num_predict": 384}
        request_payload = {
            "model": model.ollama_name,
            "prompt": prompt_text,
            "images": [image_base64],
            "stream": False,
            "format": schema,
            "think": False,
            "keep_alive": 0,
            "options": options,
        }
        sanitized_request = {
            "model": model.ollama_name,
            "prompt_sha256": sha256_file(prompt_path),
            "image_sha256": item.sha256,
            "format_schema_sha256": sha256_file(schema_path),
            "stream": False,
            "think": False,
            "keep_alive": 0,
            "options": options,
        }
        spec = AttemptSpec(
            experiment_id=study.config.experiment_id,
            protocol_version=study.config.protocol_version,
            run_id=run_id,
            attempt_id=attempt_id,
            repeat=1,
            randomization_block="compatibility-smoke",
            git_commit=commit,
            dirty_worktree=dirty,
            ollama_version=ollama_version,
            system_snapshot_ref="private-dgx-preflight",
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
                prompt_sha256=sha256_file(prompt_path),
                schema_sha256=sha256_file(schema_path),
                system_prompt_sha256=sha256_file(prompt_path),
            ),
            generation_options=options,
            thinking_mode="disabled",
            sanitized_request=sanitized_request,
        )
        record = execute_attempt(
            spec,
            transport,
            request_payload=request_payload,
            response_model=VisualFactsPayload,
        )
        record_path = write_attempt_record(output_dir, record)
        results.append(
            CompatibilityResult(
                model_id=model_id,
                attempt_id=attempt_id,
                valid=record.validation.valid,
                validation_errors=record.validation.errors,
                wall_duration_ms=record.telemetry.wall_duration_ms,
                total_duration_ns=record.telemetry.total_duration_ns,
                record_path=str(record_path),
            )
        )

    summary = CompatibilitySummary(
        status="compatible" if all(result.valid for result in results) else "incomplete",
        experiment_id=study.config.experiment_id,
        image_id=image_id,
        ollama_version=ollama_version,
        timeout_seconds=timeout_seconds,
        results=results,
    )
    summary_path = output_dir / "compatibility-summary.json"
    summary_path.write_text(json.dumps(summary.model_dump(), indent=2, sort_keys=True) + "\n")
    return summary, summary_path


def _git_state(repository_root: Path) -> tuple[str, bool]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return commit, bool(status.strip())
