import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .config import ModelEntry, load_study, resolve_under_root
from .dataset import DatasetItem, load_manifest
from .execution_plan import (
    FullStudyPlanCell,
    inspect_full_study_execution_plan,
    load_full_study_plan,
)
from .hashing import sha256_file, sha256_text
from .ollama import OllamaTransport
from .protocol_freeze import ProtocolFreezeContract, audit_protocol_freeze
from .records import attempt_record_paths, read_attempt_record, write_attempt_record
from .runner import AttemptSpec, execute_attempt
from .schemas import (
    ContextualMetadataPayload,
    ErrorEvidence,
    InputEvidence,
    ModelIdentity,
    PromptEvidence,
    RunRecord,
    TelemetryEvidence,
    ValidationEvidence,
    VisualFactsPayload,
)
from .smoke import _git_state
from .writer_compatibility import _validate_purpose


class FullStudyTransport(Protocol):
    def version(self) -> str: ...

    def tags(self) -> dict[str, Any]: ...

    def generate(self, request: dict[str, Any]) -> dict[str, Any]: ...


class VisionSelectionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    selected_model_id: Literal[
        "qwen25vl-3b-baseline",
        "qwen35-9b",
        "gemma3-12b",
    ]
    decision_rule_id: str = Field(min_length=1)
    source_analysis_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decided_at: datetime


class FullStudyCollectionSummary(BaseModel):
    status: Literal["paused", "complete"]
    phase: Literal["primary_generation", "decomposed_writer", "context_ablation"]
    run_id: str
    plan_sha256: str
    expected_cells: int = Field(ge=0)
    completed_cells: int = Field(ge=0)
    valid_cells: int = Field(ge=0)
    failed_cells: int = Field(ge=0)
    upstream_failure_cells: int = Field(ge=0)
    raw_attempt_records: int = Field(ge=0)
    pending_cells: int = Field(ge=0)
    new_records_this_session: int = Field(ge=0)
    paused_on_transport_error: bool


def collect_full_study_phase(
    protocol_path: Path,
    config_path: Path,
    plan_path: Path,
    *,
    phase: Literal["primary_generation", "decomposed_writer", "context_ablation"],
    base_url: str,
    run_dir: Path,
    run_id: str,
    system_snapshot_ref: str,
    max_new_attempts: int | None = None,
    vision_selection_path: Path | None = None,
    transport: FullStudyTransport | None = None,
    require_freeze: bool = True,
) -> tuple[FullStudyCollectionSummary, Path]:
    if max_new_attempts is not None and max_new_attempts < 1:
        raise ValueError("max_new_attempts must be positive")
    protocol = ProtocolFreezeContract.model_validate_json(protocol_path.read_text())
    study = load_study(config_path)
    plan_validation = inspect_full_study_execution_plan(protocol_path, config_path, plan_path)
    if plan_validation.status != "valid" or plan_validation.plan_sha256 is None:
        raise ValueError("Execution plan is invalid: " + "; ".join(plan_validation.errors))
    plan_hash = plan_validation.plan_sha256
    protocol_hash = sha256_file(protocol_path)
    if protocol.operational_readiness.execution_plan_sha256 != plan_hash:
        raise ValueError("Execution plan hash does not match the protocol")
    if require_freeze:
        audit, _ = audit_protocol_freeze(
            protocol_path,
            run_dir / "evidence" / "pre-execution-protocol-audit.json",
        )
        if audit.status != "freeze_ready":
            raise ValueError(
                "Full-study collection is prohibited until the protocol audit is freeze_ready: "
                + "; ".join(audit.blockers + audit.errors)
            )

    free_gib = shutil.disk_usage(run_dir.parent if run_dir.parent.exists() else study.root).free / (
        1024**3
    )
    if free_gib < protocol.operational_readiness.minimum_free_storage_gib:
        raise ValueError(
            f"Free storage is {free_gib:.2f} GiB; "
            f"{protocol.operational_readiness.minimum_free_storage_gib:.2f} GiB is required"
        )

    commit, dirty = _git_state(study.root.parent)
    if dirty and not study.config.allow_dirty_worktree:
        raise ValueError("Full-study collection requires a clean Git worktree")
    all_cells = load_full_study_plan(plan_path)
    cells_by_id = {cell.cell_id: cell for cell in all_cells}
    cells = [cell for cell in all_cells if cell.phase == phase]
    items = {
        item.id: item for item in load_manifest(study.root, study.config.dataset_manifest)
    }
    models = {model.id: model for model in study.models.models}
    selected_model_id = _selected_model_id(phase, vision_selection_path, plan_hash)
    existing = _load_existing_records(
        run_dir,
        protocol,
        run_id,
        plan_hash,
        cells_by_id,
    )
    active_transport = transport or OllamaTransport(
        base_url,
        timeout_seconds=protocol.execution.per_attempt_timeout_seconds,
    )
    ollama_version = active_transport.version()
    required_model_ids = {cell.model_id for cell in cells}
    if phase == "context_ablation" and selected_model_id:
        required_model_ids.add(selected_model_id)
    _verify_live_digests(
        [models[model_id] for model_id in sorted(required_model_ids)],
        active_transport.tags(),
    )

    new_records = 0
    paused_on_transport = False
    for cell_index, cell in enumerate(cells):
        prior = existing.get(cell.cell_id, [])
        final = [record for record in prior if not _recoverable_transport(record)]
        if final:
            _verify_record_matches_cell(final[0], cell, plan_hash)
            continue
        transports = [record for record in prior if _recoverable_transport(record)]
        if len(transports) > 1:
            raise ValueError(f"Transport recovery limit exceeded for {cell.cell_id}")
        if max_new_attempts is not None and new_records >= max_new_attempts:
            break

        dependency = _dependency_record(
            cell,
            existing,
            selected_model_id=selected_model_id,
        )
        attempt_number = len(transports) + 1
        supersedes = transports[-1].attempt_id if transports else ""
        next_cell = cells[cell_index + 1] if cell_index + 1 < len(cells) else None
        session_limit_reached = (
            max_new_attempts is not None and new_records + 1 >= max_new_attempts
        )
        keep_alive: str | int = (
            0
            if session_limit_reached
            or next_cell is None
            or next_cell.randomization_block != cell.randomization_block
            else protocol.execution.keep_alive
        )
        if dependency is not None and not dependency.validation.valid:
            record = _upstream_failure_record(
                protocol,
                study,
                cell,
                items[cell.image_id],
                models[cell.model_id],
                dependency,
                plan_hash,
                protocol_hash,
                run_id,
                system_snapshot_ref,
                commit,
                dirty,
                ollama_version,
            )
        else:
            record = _execute_cell(
                protocol,
                study,
                cell,
                items[cell.image_id],
                models[cell.model_id],
                dependency,
                plan_hash,
                protocol_hash,
                run_id,
                system_snapshot_ref,
                commit,
                dirty,
                ollama_version,
                active_transport,
                attempt_number,
                supersedes,
                keep_alive,
            )
        write_attempt_record(run_dir, record)
        existing.setdefault(cell.cell_id, []).append(record)
        new_records += 1
        if _recoverable_transport(record):
            paused_on_transport = True
            break

    summary = _collection_summary(
        phase,
        run_id,
        plan_hash,
        cells,
        existing,
        new_records,
        paused_on_transport,
    )
    summary_path = run_dir / f"{phase}-summary.json"
    _write_json_atomic(summary_path, summary.model_dump(mode="json"))
    return summary, summary_path


def _execute_cell(
    protocol: ProtocolFreezeContract,
    study,
    cell: FullStudyPlanCell,
    item: DatasetItem,
    model: ModelEntry,
    dependency: RunRecord | None,
    plan_hash: str,
    protocol_sha256: str,
    run_id: str,
    system_snapshot_ref: str,
    commit: str,
    dirty: bool,
    ollama_version: str,
    transport: FullStudyTransport,
    collection_attempt: int,
    supersedes_attempt_id: str,
    keep_alive: str | int,
) -> RunRecord:
    prompt_path = study.root / "prompts" / f"{cell.prompt_id}.txt"
    schema_path = study.root / "schemas" / cell.response_schema
    schema_model = (
        VisualFactsPayload if cell.response_schema == "visual-facts.schema.json"
        else ContextualMetadataPayload
    )
    schema = schema_model.model_json_schema()
    options = {
        "temperature": protocol.execution.temperature,
        "seed": protocol.execution.randomization_seed,
        "num_ctx": protocol.execution.context_window,
        "num_predict": (
            protocol.execution.facts_output_token_limit
            if cell.stage == "vision_facts"
            else protocol.execution.metadata_output_token_limit
        ),
    }
    prompt = _render_prompt(study.root, prompt_path, item, cell.context_mode, dependency)
    request_payload: dict[str, Any] = {
        "model": model.ollama_name,
        "prompt": prompt,
        "stream": False,
        "format": schema,
        "think": False,
        "keep_alive": keep_alive,
        "options": options,
    }
    sends_pixels = cell.stage in {"vision_facts", "direct_metadata"}
    if sends_pixels:
        image_path = resolve_under_root(study.root, item.image_path)
        request_payload["images"] = [base64.b64encode(image_path.read_bytes()).decode("ascii")]

    attempt_id = f"{run_id}-{cell.ordinal:04d}-{cell.cell_id}-c{collection_attempt}"
    source_cell_id = dependency.plan_cell_id if dependency is not None else ""
    spec = AttemptSpec(
        experiment_id=protocol.protocol_id,
        protocol_version=protocol.protocol_version,
        run_id=run_id,
        attempt_id=attempt_id,
        repeat=cell.repeat,
        randomization_block=cell.randomization_block,
        git_commit=commit,
        dirty_worktree=dirty,
        ollama_version=ollama_version,
        system_snapshot_ref=system_snapshot_ref,
        model=_model_identity(model),
        input=_input_evidence(item),
        prompt=PromptEvidence(
            prompt_id=cell.prompt_id,
            prompt_sha256=sha256_text(prompt),
            schema_sha256=sha256_file(schema_path),
            system_prompt_sha256=sha256_text(""),
        ),
        generation_options=options,
        thinking_mode="disabled",
        sanitized_request={
            "model": model.ollama_name,
            "prompt_sha256": sha256_text(prompt),
            "image_sha256": item.sha256,
            "pixels_sent": sends_pixels,
            "source_plan_cell_id": source_cell_id,
            "page_context_sha256": item.page_context_sha256,
            "brand_profile_sha256": item.brand_profile_sha256,
            "purpose": item.purpose,
            "context_mode": cell.context_mode,
            "stream": False,
            "think": False,
            "keep_alive": keep_alive,
            "options": options,
        },
        study_config_sha256=sha256_file(study.config_path),
        models_config_sha256=sha256_file(
            resolve_under_root(study.root, study.config.models_config)
        ),
        criteria_sha256=protocol_sha256,
        collection_attempt=collection_attempt,
        supersedes_attempt_id=supersedes_attempt_id,
        plan_sha256=plan_hash,
        plan_cell_id=cell.cell_id,
        condition_id=cell.condition_id,
        stage=cell.stage,
        source_plan_cell_id=source_cell_id,
        context_mode=cell.context_mode,
    )
    record = execute_attempt(
        spec,
        transport,
        request_payload=request_payload,
        response_model=schema_model,
    )
    return _validate_purpose(record, item.purpose) if cell.stage != "vision_facts" else record


def _render_prompt(
    root: Path,
    prompt_path: Path,
    item: DatasetItem,
    context_mode: str,
    dependency: RunRecord | None,
) -> str:
    instruction = prompt_path.read_text().strip()
    if context_mode == "none":
        return instruction
    page = json.loads(resolve_under_root(root, item.page_context_path).read_text())
    brand = json.loads(resolve_under_root(root, item.brand_profile_path).read_text())
    purpose = {"purpose": item.purpose, "purpose_confirmed": True}
    facts = dependency.parsed_payload if dependency is not None else None
    if context_mode == "visual_only":
        page, brand, purpose = {}, {}, {}
    elif context_mode == "brand_only":
        page, purpose = {}, {}
    elif context_mode == "page_purpose":
        brand = {}
    canonical = lambda value: json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    sections = [f"/no_think\n{instruction}\nReturn only JSON matching the supplied schema."]
    if facts is not None:
        sections.append(
            f"[VISUAL_FACTS_JSON]\n{canonical(facts)}\n[/VISUAL_FACTS_JSON]"
        )
    sections.extend(
        [
            f"[PAGE_CONTEXT_JSON]\n{canonical(page)}\n[/PAGE_CONTEXT_JSON]",
            f"[BRAND_CONTEXT_JSON]\n{canonical(brand)}\n[/BRAND_CONTEXT_JSON]",
            f"[CONFIRMED_PURPOSE_JSON]\n{canonical(purpose)}\n[/CONFIRMED_PURPOSE_JSON]",
        ]
    )
    return "\n\n".join(sections)


def _upstream_failure_record(
    protocol: ProtocolFreezeContract,
    study,
    cell: FullStudyPlanCell,
    item: DatasetItem,
    model: ModelEntry,
    dependency: RunRecord,
    plan_hash: str,
    protocol_sha256: str,
    run_id: str,
    system_snapshot_ref: str,
    commit: str,
    dirty: bool,
    ollama_version: str,
) -> RunRecord:
    now = datetime.now(timezone.utc)
    prompt_path = study.root / "prompts" / f"{cell.prompt_id}.txt"
    schema_path = study.root / "schemas" / cell.response_schema
    return RunRecord(
        experiment_id=protocol.protocol_id,
        protocol_version=protocol.protocol_version,
        run_id=run_id,
        attempt_id=f"{run_id}-{cell.ordinal:04d}-{cell.cell_id}-upstream-failure",
        repeat=cell.repeat,
        randomization_block=cell.randomization_block,
        started_at=now,
        ended_at=now,
        git_commit=commit,
        dirty_worktree=dirty,
        ollama_version=ollama_version,
        system_snapshot_ref=system_snapshot_ref,
        model=_model_identity(model),
        input=_input_evidence(item),
        prompt=PromptEvidence(
            prompt_id=cell.prompt_id,
            prompt_sha256=sha256_file(prompt_path),
            schema_sha256=sha256_file(schema_path),
            system_prompt_sha256=sha256_text(""),
        ),
        generation_options={},
        thinking_mode="disabled",
        sanitized_request={
            "model_request_sent": False,
            "source_plan_cell_id": dependency.plan_cell_id,
            "source_attempt_id": dependency.attempt_id,
        },
        raw_response={},
        parsed_payload=None,
        validation=ValidationEvidence(
            valid=False,
            errors=["upstream visual-facts outcome was invalid; writer was not called"],
        ),
        error=ErrorEvidence(
            category="upstream_failure",
            message="writer stage not attempted because its frozen source outcome was invalid",
        ),
        telemetry=TelemetryEvidence(wall_duration_ms=0),
        parser_version="parser-v1",
        normalization_version="normalization-v1",
        study_config_sha256=sha256_file(study.config_path),
        models_config_sha256=sha256_file(
            resolve_under_root(study.root, study.config.models_config)
        ),
        criteria_sha256=protocol_sha256,
        plan_sha256=plan_hash,
        plan_cell_id=cell.cell_id,
        condition_id=cell.condition_id,
        stage=cell.stage,
        source_plan_cell_id=dependency.plan_cell_id,
        context_mode=cell.context_mode,
    )


def _dependency_record(
    cell: FullStudyPlanCell,
    existing: dict[str, list[RunRecord]],
    *,
    selected_model_id: str | None,
) -> RunRecord | None:
    dependency_id = cell.dependency_cell_id
    if cell.dependency_selector == "selected_vision_model":
        if selected_model_id is None:
            raise ValueError("Context-ablation cells require a vision selection record")
        dependency_id = (
            f"facts-{selected_model_id.replace('-baseline', '')}-"
            f"r{cell.repeat}-{cell.image_id}"
        )
    if dependency_id is None:
        return None
    records = existing.get(dependency_id, [])
    final = [record for record in records if not _recoverable_transport(record)]
    if not final:
        raise ValueError(
            f"{cell.cell_id}: required source cell {dependency_id} has no final outcome"
        )
    if len(final) != 1:
        raise ValueError(f"{dependency_id}: multiple final outcomes found")
    return final[0]


def _load_existing_records(
    run_dir: Path,
    protocol: ProtocolFreezeContract,
    run_id: str,
    plan_hash: str,
    cells_by_id: dict[str, FullStudyPlanCell],
) -> dict[str, list[RunRecord]]:
    grouped: dict[str, list[RunRecord]] = {}
    for path in attempt_record_paths(run_dir):
        record = read_attempt_record(path)
        if record.experiment_id != protocol.protocol_id or record.run_id != run_id:
            raise ValueError(f"Run directory mixes experiment or run identities: {path.name}")
        if record.plan_sha256 != plan_hash or not record.plan_cell_id:
            raise ValueError(f"Run record is not bound to the frozen plan: {path.name}")
        if record.plan_cell_id not in cells_by_id:
            raise ValueError(f"Run record references an unknown plan cell: {path.name}")
        _verify_record_matches_cell(
            record,
            cells_by_id[record.plan_cell_id],
            plan_hash,
        )
        grouped.setdefault(record.plan_cell_id, []).append(record)
    for cell_id, records in grouped.items():
        finals = [record for record in records if not _recoverable_transport(record)]
        transports = [record for record in records if _recoverable_transport(record)]
        if len(finals) > 1:
            raise ValueError(f"Multiple final outcomes found for {cell_id}")
        if len(transports) > 1:
            raise ValueError(f"Transport recovery limit exceeded for {cell_id}")
    return grouped


def _collection_summary(
    phase: str,
    run_id: str,
    plan_hash: str,
    cells: list[FullStudyPlanCell],
    existing: dict[str, list[RunRecord]],
    new_records: int,
    paused_on_transport: bool,
) -> FullStudyCollectionSummary:
    outcomes = [
        next(
            (
                record
                for record in existing.get(cell.cell_id, [])
                if not _recoverable_transport(record)
            ),
            None,
        )
        for cell in cells
    ]
    completed = [record for record in outcomes if record is not None]
    pending = len(cells) - len(completed)
    return FullStudyCollectionSummary(
        status="complete" if pending == 0 else "paused",
        phase=phase,
        run_id=run_id,
        plan_sha256=plan_hash,
        expected_cells=len(cells),
        completed_cells=len(completed),
        valid_cells=sum(record.validation.valid for record in completed),
        failed_cells=sum(not record.validation.valid for record in completed),
        upstream_failure_cells=sum(
            record.error is not None and record.error.category == "upstream_failure"
            for record in completed
        ),
        raw_attempt_records=sum(
            len(existing.get(cell.cell_id, [])) for cell in cells
        ),
        pending_cells=pending,
        new_records_this_session=new_records,
        paused_on_transport_error=paused_on_transport,
    )


def _verify_record_matches_cell(
    record: RunRecord,
    cell: FullStudyPlanCell,
    plan_hash: str,
) -> None:
    expected = {
        "plan_sha256": plan_hash,
        "plan_cell_id": cell.cell_id,
        "condition_id": cell.condition_id,
        "stage": cell.stage,
        "repeat": cell.repeat,
        "image_id": cell.image_id,
        "model_id": cell.model_id,
    }
    actual = {
        "plan_sha256": record.plan_sha256,
        "plan_cell_id": record.plan_cell_id,
        "condition_id": record.condition_id,
        "stage": record.stage,
        "repeat": record.repeat,
        "image_id": record.input.image_id,
        "model_id": record.model.id,
    }
    if actual != expected:
        raise ValueError(f"Existing outcome drift for {cell.cell_id}: {actual} != {expected}")


def _selected_model_id(
    phase: str,
    selection_path: Path | None,
    plan_hash: str,
) -> str | None:
    if phase != "context_ablation":
        if selection_path is not None:
            raise ValueError("Vision selection record is only valid for context ablation")
        return None
    if selection_path is None:
        raise ValueError("Context ablation requires an immutable vision selection record")
    selection = VisionSelectionRecord.model_validate_json(selection_path.read_text())
    if selection.execution_plan_sha256 != plan_hash:
        raise ValueError("Vision selection record references a different execution plan")
    return selection.selected_model_id


def _verify_live_digests(models: list[ModelEntry], payload: dict[str, Any]) -> None:
    live = {
        str(entry.get("name") or entry.get("model")): entry.get("digest")
        for entry in payload.get("models", [])
        if isinstance(entry, dict)
    }
    mismatches = [
        f"{model.id}: expected {model.expected_digest}, live "
        f"{live.get(model.ollama_name, 'missing')}"
        for model in models
        if live.get(model.ollama_name) != model.expected_digest
    ]
    if mismatches:
        raise ValueError("Live model identity mismatch: " + "; ".join(mismatches))


def _recoverable_transport(record: RunRecord) -> bool:
    return record.error is not None and record.error.category == "transport_error"


def _model_identity(model: ModelEntry) -> ModelIdentity:
    return ModelIdentity(
        id=model.id,
        ollama_name=model.ollama_name,
        digest=model.expected_digest,
        family=model.family,
        parameters=model.parameters,
        quantization=model.quantization,
        license=model.license,
    )


def _input_evidence(item: DatasetItem) -> InputEvidence:
    return InputEvidence(
        image_id=item.id,
        image_sha256=item.sha256,
        dataset_stratum=item.domain,
        purpose=item.purpose,
        page_context_sha256=item.page_context_sha256,
        brand_profile_sha256=item.brand_profile_sha256,
    )


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)
