import json
from datetime import datetime, timezone
from pathlib import Path
import tomllib
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from .accounting import effective_error_category, resolve_attempt_records
from .config import ModelEntry, load_study, resolve_under_root
from .dataset import DatasetItem, load_manifest
from .hashing import sha256_file, sha256_text
from .ollama import OllamaTransport
from .pilot import _verify_live_digests
from .records import attempt_record_paths, read_attempt_record, write_attempt_record
from .runner import AttemptSpec, execute_attempt
from .schemas import (
    ContextualMetadataPayload,
    InputEvidence,
    ModelIdentity,
    PromptEvidence,
    RunRecord,
    ValidationEvidence,
)
from .smoke import _git_state


class WriterTransport(Protocol):
    def version(self) -> str: ...

    def tags(self) -> dict[str, Any]: ...

    def generate(self, request: dict[str, Any]) -> dict[str, Any]: ...


class WriterCompatibilityCriteria(BaseModel):
    schema_version: Literal[1]
    criteria_id: str
    experiment_id: str
    protocol_version: str
    source_run_id: str
    writer_model_id: str
    source_selection_rule: Literal[
        "lexicographically_first_image_with_schema_valid_facts_from_every_candidate"
    ]
    prompt_id: str
    temperature: float
    seed: int
    thinking_mode: Literal["disabled"]
    context_window: int = Field(gt=0)
    output_token_limit: int = Field(gt=0)
    per_attempt_timeout_seconds: float = Field(gt=0)
    keep_alive: str
    hidden_retries_allowed: Literal[0]
    max_transport_attempts_per_source: int = Field(ge=1)
    required_valid_rate: float = Field(gt=0, le=1)


class WriterSourceResult(BaseModel):
    source_fact_attempt_id: str
    observed: int = Field(ge=0, le=1)
    valid: int = Field(ge=0, le=1)
    failed: int = Field(ge=0, le=1)
    wall_duration_ms: float = Field(ge=0)
    failure_category: str = ""


class WriterCompatibilitySummary(BaseModel):
    status: Literal["complete", "incomplete"]
    criteria_id: str
    run_id: str
    source_run_id: str
    selected_image_id: str
    writer_model_id: str
    writer_digest: str
    ollama_version: str
    expected_outcomes: int
    observed_outcomes: int
    valid_outcomes: int
    failed_outcomes: int
    raw_records: int
    superseded_transport_records: int
    required_valid_rate: float
    valid_rate: float
    threshold_met: bool
    git_commits: list[str]
    study_config_sha256: str
    models_config_sha256: str
    criteria_sha256: str
    prompt_template_sha256: str
    schema_sha256: str
    by_source_model: dict[str, WriterSourceResult]


def load_writer_criteria(path: Path) -> WriterCompatibilityCriteria:
    return WriterCompatibilityCriteria.model_validate(tomllib.loads(path.resolve().read_text()))


def run_writer_compatibility(
    config_path: Path,
    criteria_path: Path,
    source_run_dir: Path,
    base_url: str,
    output_dir: Path,
    run_id: str,
    system_snapshot_ref: str,
    *,
    transport: WriterTransport | None = None,
) -> tuple[WriterCompatibilitySummary, Path]:
    study = load_study(config_path)
    criteria = load_writer_criteria(criteria_path)
    source_summary = json.loads((source_run_dir / "pilot-summary.json").read_text())
    if source_summary.get("status") != "complete" or source_summary.get("run_id") != criteria.source_run_id:
        raise ValueError("Writer compatibility requires the declared complete source pilot")

    configured = {model.id: model for model in study.models.models}
    writer = configured.get(criteria.writer_model_id)
    if writer is None or not writer.expected_digest:
        raise ValueError("Writer model requires a configured immutable digest")
    source_resolution = resolve_attempt_records(source_run_dir)
    source_records = _select_common_source_records(
        study.config.model_ids,
        source_resolution.selected.values(),
        configured,
    )
    selected_image_id = next(iter(source_records.values())).input.image_id
    manifest = {item.id: item for item in load_manifest(study.root, study.config.dataset_manifest)}
    item = manifest[selected_image_id]

    active_transport = transport or OllamaTransport(
        base_url, timeout_seconds=criteria.per_attempt_timeout_seconds
    )
    ollama_version = active_transport.version()
    _verify_live_digests([writer], active_transport.tags())
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "writer-summary.json"
    existing = _existing_writer_records(output_dir, criteria, run_id, study.config.model_ids)
    commit, dirty = _git_state(study.root.parent)
    prompt_path = study.root / "prompts" / "context-writer-v1.txt"
    schema_path = study.root / "schemas" / "metadata.schema.json"
    schema = ContextualMetadataPayload.model_json_schema()
    options = {
        "temperature": criteria.temperature,
        "seed": criteria.seed,
        "num_ctx": criteria.context_window,
        "num_predict": criteria.output_token_limit,
    }
    pending = [
        model_id
        for model_id in study.config.model_ids
        if not any(not _is_recoverable_transport(record) for record in existing.get(model_id, []))
    ]
    for pending_index, source_model_id in enumerate(pending, start=1):
        prior = existing.get(source_model_id, [])
        transports = [record for record in prior if _is_recoverable_transport(record)]
        if len(transports) >= criteria.max_transport_attempts_per_source:
            raise ValueError(f"Writer transport-attempt limit reached: {source_model_id}")
        collection_attempt = len(transports) + 1
        source_record = source_records[source_model_id]
        attempt_id = f"{run_id}-{pending_index:02d}-{source_model_id}-c{collection_attempt}"
        keep_alive: str | int = 0 if pending_index == len(pending) else criteria.keep_alive
        record = _execute_writer_attempt(
            study.root,
            criteria,
            run_id,
            attempt_id,
            source_model_id,
            source_record,
            item,
            writer,
            commit,
            dirty,
            ollama_version,
            system_snapshot_ref,
            sha256_file(study.config_path),
            sha256_file(resolve_under_root(study.root, study.config.models_config)),
            sha256_file(criteria_path.resolve()),
            prompt_path,
            schema_path,
            schema,
            options,
            keep_alive,
            active_transport,
            collection_attempt,
            transports[-1].attempt_id if transports else "",
        )
        write_attempt_record(output_dir, record)
        existing.setdefault(source_model_id, []).append(record)
        summary = _build_summary(
            criteria,
            run_id,
            selected_image_id,
            writer,
            ollama_version,
            study.config.model_ids,
            source_records,
            existing,
            sha256_file(study.config_path),
            sha256_file(resolve_under_root(study.root, study.config.models_config)),
            sha256_file(criteria_path.resolve()),
            sha256_file(prompt_path),
            sha256_file(schema_path),
        )
        _write_summary(summary_path, summary)
        if _is_recoverable_transport(record):
            return summary, summary_path

    summary = _build_summary(
        criteria,
        run_id,
        selected_image_id,
        writer,
        ollama_version,
        study.config.model_ids,
        source_records,
        existing,
        sha256_file(study.config_path),
        sha256_file(resolve_under_root(study.root, study.config.models_config)),
        sha256_file(criteria_path.resolve()),
        sha256_file(prompt_path),
        sha256_file(schema_path),
    )
    _write_summary(summary_path, summary)
    return summary, summary_path


def _select_common_source_records(
    model_ids: list[str],
    records: Any,
    configured: dict[str, ModelEntry],
) -> dict[str, RunRecord]:
    records_by_model: dict[str, dict[str, RunRecord]] = {model_id: {} for model_id in model_ids}
    for record in records:
        if record.model.id in records_by_model and record.validation.valid:
            records_by_model[record.model.id][record.input.image_id] = record
    common = set.intersection(*(set(records_by_model[model_id]) for model_id in model_ids))
    if not common:
        raise ValueError("No common image has schema-valid facts from every candidate")
    selected_image_id = sorted(common)[0]
    selected = {
        model_id: records_by_model[model_id][selected_image_id] for model_id in model_ids
    }
    mismatches = [
        model_id
        for model_id, record in selected.items()
        if record.model.digest != configured[model_id].expected_digest
    ]
    if mismatches:
        raise ValueError("Source fact digest mismatch: " + ", ".join(mismatches))
    return selected


def _existing_writer_records(
    output_dir: Path,
    criteria: WriterCompatibilityCriteria,
    run_id: str,
    source_model_ids: list[str],
) -> dict[str, list[RunRecord]]:
    grouped: dict[str, list[RunRecord]] = {}
    for path in attempt_record_paths(output_dir):
        record = read_attempt_record(path)
        if record.experiment_id != criteria.experiment_id or record.run_id != run_id:
            raise ValueError(f"Writer run directory mixes experiment identities: {path.name}")
        source_model_id = record.sanitized_request.get("source_vision_model_id")
        if source_model_id not in source_model_ids:
            raise ValueError(f"Writer record has unknown source model: {path.name}")
        grouped.setdefault(str(source_model_id), []).append(record)
    for records in grouped.values():
        records.sort(key=lambda record: (record.collection_attempt, record.started_at))
        outcomes = [record for record in records if not _is_recoverable_transport(record)]
        if len(outcomes) > 1:
            raise ValueError("Writer run contains multiple final outcomes for one source")
    return grouped


def _execute_writer_attempt(
    root: Path,
    criteria: WriterCompatibilityCriteria,
    run_id: str,
    attempt_id: str,
    source_model_id: str,
    source_record: RunRecord,
    item: DatasetItem,
    writer: ModelEntry,
    commit: str,
    dirty: bool,
    ollama_version: str,
    system_snapshot_ref: str,
    study_config_sha256: str,
    models_config_sha256: str,
    criteria_sha256: str,
    prompt_path: Path,
    schema_path: Path,
    schema: dict[str, Any],
    options: dict[str, Any],
    keep_alive: str | int,
    transport: WriterTransport,
    collection_attempt: int,
    supersedes_attempt_id: str,
) -> RunRecord:
    page_context = json.loads(resolve_under_root(root, item.page_context_path).read_text())
    brand_context = json.loads(resolve_under_root(root, item.brand_profile_path).read_text())
    confirmed_purpose = {"purpose": item.purpose, "purpose_confirmed": True}
    prompt = _writer_prompt(
        prompt_path.read_text().strip(),
        source_record.parsed_payload or {},
        page_context,
        brand_context,
        confirmed_purpose,
    )
    request_payload = {
        "model": writer.ollama_name,
        "prompt": prompt,
        "stream": False,
        "format": schema,
        "think": False,
        "keep_alive": keep_alive,
        "options": options,
    }
    spec = AttemptSpec(
        experiment_id=criteria.experiment_id,
        protocol_version=criteria.protocol_version,
        run_id=run_id,
        attempt_id=attempt_id,
        repeat=1,
        randomization_block=f"facts-source-{source_model_id}",
        git_commit=commit,
        dirty_worktree=dirty,
        ollama_version=ollama_version,
        system_snapshot_ref=system_snapshot_ref,
        model=ModelIdentity(
            id=writer.id,
            ollama_name=writer.ollama_name,
            digest=writer.expected_digest,
            family=writer.family,
            parameters=writer.parameters,
            quantization=writer.quantization,
            license=writer.license,
        ),
        input=InputEvidence(
            image_id=f"{item.id}--facts-{source_model_id}",
            image_sha256=item.sha256,
            dataset_stratum=item.domain,
            purpose=item.purpose,
            page_context_sha256=item.page_context_sha256,
            brand_profile_sha256=item.brand_profile_sha256,
        ),
        prompt=PromptEvidence(
            prompt_id=criteria.prompt_id,
            prompt_sha256=sha256_text(prompt),
            schema_sha256=sha256_file(schema_path),
            system_prompt_sha256=sha256_text(""),
        ),
        generation_options=options,
        thinking_mode="disabled",
        sanitized_request={
            "model": writer.ollama_name,
            "source_vision_model_id": source_model_id,
            "source_fact_attempt_id": source_record.attempt_id,
            "source_fact_digest": source_record.model.digest,
            "prompt_sha256": sha256_text(prompt),
            "page_context_sha256": item.page_context_sha256,
            "brand_profile_sha256": item.brand_profile_sha256,
            "purpose": item.purpose,
            "stream": False,
            "think": False,
            "keep_alive": keep_alive,
            "options": options,
        },
        study_config_sha256=study_config_sha256,
        models_config_sha256=models_config_sha256,
        criteria_sha256=criteria_sha256,
        collection_attempt=collection_attempt,
        supersedes_attempt_id=supersedes_attempt_id,
    )
    record = execute_attempt(
        spec,
        transport,
        request_payload=request_payload,
        response_model=ContextualMetadataPayload,
    )
    return _validate_purpose(record, item.purpose)


def _writer_prompt(
    instruction: str,
    facts: dict[str, Any],
    page_context: dict[str, Any],
    brand_context: dict[str, Any],
    confirmed_purpose: dict[str, Any],
) -> str:
    canonical = lambda value: json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return (
        f"/no_think\n{instruction}\nReturn only JSON matching the supplied schema.\n\n"
        f"[VISUAL_FACTS_JSON]\n{canonical(facts)}\n[/VISUAL_FACTS_JSON]\n\n"
        f"[PAGE_CONTEXT_JSON]\n{canonical(page_context)}\n[/PAGE_CONTEXT_JSON]\n\n"
        f"[BRAND_CONTEXT_JSON]\n{canonical(brand_context)}\n[/BRAND_CONTEXT_JSON]\n\n"
        f"[CONFIRMED_PURPOSE_JSON]\n{canonical(confirmed_purpose)}\n[/CONFIRMED_PURPOSE_JSON]"
    )


def _validate_purpose(record: RunRecord, purpose: str) -> RunRecord:
    if not record.validation.valid or record.parsed_payload is None:
        return record
    alt_text = str(record.parsed_payload.get("alt_text", "")).strip()
    invalid = (purpose in {"decorative", "redundant"} and alt_text) or (
        purpose not in {"decorative", "redundant"} and not alt_text
    )
    if not invalid:
        return record
    return record.model_copy(
        update={
            "validation": ValidationEvidence(
                valid=False,
                errors=[f"metadata violates confirmed {purpose} alt-text rule"],
            )
        }
    )


def _build_summary(
    criteria: WriterCompatibilityCriteria,
    run_id: str,
    selected_image_id: str,
    writer: ModelEntry,
    ollama_version: str,
    source_model_ids: list[str],
    source_records: dict[str, RunRecord],
    existing: dict[str, list[RunRecord]],
    study_config_sha256: str,
    models_config_sha256: str,
    criteria_sha256: str,
    prompt_template_sha256: str,
    schema_sha256: str,
) -> WriterCompatibilitySummary:
    by_source: dict[str, WriterSourceResult] = {}
    raw_records = [record for records in existing.values() for record in records]
    superseded = 0
    for source_model_id in source_model_ids:
        records = existing.get(source_model_id, [])
        outcomes = [record for record in records if not _is_recoverable_transport(record)]
        transports = [record for record in records if _is_recoverable_transport(record)]
        outcome = outcomes[0] if outcomes else None
        if outcome is not None:
            superseded += len(transports)
        by_source[source_model_id] = WriterSourceResult(
            source_fact_attempt_id=source_records[source_model_id].attempt_id,
            observed=1 if outcome is not None else 0,
            valid=1 if outcome is not None and outcome.validation.valid else 0,
            failed=1 if outcome is not None and not outcome.validation.valid else 0,
            wall_duration_ms=outcome.telemetry.wall_duration_ms if outcome is not None else 0,
            failure_category=(
                "" if outcome is None or outcome.validation.valid else effective_error_category(outcome)
            ),
        )
    observed = sum(result.observed for result in by_source.values())
    valid = sum(result.valid for result in by_source.values())
    valid_rate = valid / observed if observed else 0.0
    return WriterCompatibilitySummary(
        status="complete" if observed == len(source_model_ids) else "incomplete",
        criteria_id=criteria.criteria_id,
        run_id=run_id,
        source_run_id=criteria.source_run_id,
        selected_image_id=selected_image_id,
        writer_model_id=writer.id,
        writer_digest=writer.expected_digest,
        ollama_version=ollama_version,
        expected_outcomes=len(source_model_ids),
        observed_outcomes=observed,
        valid_outcomes=valid,
        failed_outcomes=observed - valid,
        raw_records=len(raw_records),
        superseded_transport_records=superseded,
        required_valid_rate=criteria.required_valid_rate,
        valid_rate=valid_rate,
        threshold_met=observed == len(source_model_ids) and valid_rate >= criteria.required_valid_rate,
        git_commits=sorted({record.git_commit for record in raw_records}),
        study_config_sha256=study_config_sha256,
        models_config_sha256=models_config_sha256,
        criteria_sha256=criteria_sha256,
        prompt_template_sha256=prompt_template_sha256,
        schema_sha256=schema_sha256,
        by_source_model=by_source,
    )


def _is_recoverable_transport(record: RunRecord) -> bool:
    return effective_error_category(record) == "transport_error"


def _write_summary(path: Path, summary: WriterCompatibilitySummary) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def build_writer_report(
    summary_path: Path,
    evidence_path: Path,
    report_path: Path,
) -> tuple[Path, Path]:
    summary = WriterCompatibilitySummary.model_validate_json(summary_path.read_text())
    if summary.status != "complete":
        raise ValueError("Writer report requires a complete writer compatibility pass")
    evidence = {
        "evidence_version": 1,
        "stage": "candidate-facts-to-fixed-writer compatibility",
        "quality_ranking_permitted": False,
        "pixels_sent_to_writer": False,
        **summary.model_dump(mode="json"),
        "limitations": [
            "This five-call pass establishes schema and purpose-rule compatibility only.",
            "It does not compare metadata quality or replace the controlled architecture experiment.",
            "The selected image was determined by a frozen common-validity rule, not output quality inspection.",
        ],
    }
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    lines = [
        "# Fixed-writer compatibility report",
        "",
        "This report establishes schema and purpose-rule compatibility only. It must not be used to rank output quality.",
        "",
        f"- Writer: `{summary.writer_model_id}` / `{summary.writer_digest[:12]}`",
        f"- Deterministically selected image: `{summary.selected_image_id}`",
        f"- Valid outcomes: `{summary.valid_outcomes}` / `{summary.expected_outcomes}`",
        f"- Pixels sent to writer: `no`",
        f"- Hidden retries: `0`",
        "",
        "| Source visual-facts condition | Valid | Writer wall seconds | Failure category |",
        "|---|---:|---:|---|",
    ]
    for source_model_id, result in summary.by_source_model.items():
        lines.append(
            f"| `{source_model_id}` | {'yes' if result.valid else 'no'} | "
            f"{result.wall_duration_ms / 1000:.1f} | {result.failure_category or 'none'} |"
        )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {limitation}" for limitation in evidence["limitations"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n")
    return evidence_path, report_path
