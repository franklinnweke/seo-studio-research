import hashlib
import json
from pathlib import Path
import random
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .config import LoadedStudy, load_study
from .dataset import DatasetItem, load_manifest
from .hashing import sha256_file
from .protocol_freeze import ProtocolFreezeContract


FACT_CONDITIONS = {
    "qwen25vl-3b-baseline": "facts-qwen25vl-3b",
    "qwen35-9b": "facts-qwen35-9b",
    "gemma3-12b": "facts-gemma3-12b",
}
WRITER_CONDITIONS = {
    "qwen25vl-3b-baseline": "decomposed-qwen25vl-3b-to-qwen35",
    "qwen35-9b": "decomposed-qwen35-to-qwen35",
    "gemma3-12b": "decomposed-gemma3-12b-to-qwen35",
}
CONTEXT_CONDITIONS = {
    "visual_only": "context-selected-vision-visual-only",
    "brand_only": "context-selected-vision-brand-only",
    "page_purpose": "context-selected-vision-page-purpose",
}
DIRECT_CONDITION = "direct-qwen35-full-context"
WRITER_MODEL_ID = "qwen35-9b"


class FullStudyPlanCell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_version: Literal[1] = 1
    ordinal: int = Field(ge=1)
    cell_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    experiment_id: str = Field(min_length=1)
    protocol_version: str = Field(min_length=1)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase: Literal["primary_generation", "decomposed_writer", "context_ablation"]
    stage: Literal["vision_facts", "decomposed_writer", "direct_metadata", "context_writer"]
    condition_id: str = Field(min_length=1)
    image_id: str = Field(min_length=1)
    repeat: int = Field(ge=1)
    model_id: str = Field(min_length=1)
    source_model_id: str | None = None
    prompt_id: Literal["vision-facts-v1", "context-writer-v1", "direct-metadata-v1"]
    response_schema: Literal["visual-facts.schema.json", "metadata.schema.json"]
    context_mode: Literal[
        "none",
        "full",
        "visual_only",
        "brand_only",
        "page_purpose",
    ]
    dependency_cell_id: str | None = None
    dependency_selector: Literal["selected_vision_model"] | None = None
    randomization_block: str = Field(min_length=1)
    human_review: bool
    review_scope: Literal["none", "rq1", "metadata"]


class FullStudyPlanSummary(BaseModel):
    status: Literal["ready"]
    plan_version: Literal[1] = 1
    experiment_id: str
    protocol_version: str
    randomization_seed: int
    manifest_sha256: str
    plan_sha256: str
    cells: int
    primary_generation_cells: int
    decomposed_writer_cells: int
    context_ablation_cells: int
    human_review_items: int
    deferred_selection_cells: int


class FullStudyPlanValidation(BaseModel):
    status: Literal["valid", "invalid"]
    plan_sha256: str | None = None
    cells_checked: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)


def build_full_study_execution_plan(
    protocol_path: Path,
    config_path: Path,
    output_path: Path,
    summary_path: Path,
) -> tuple[FullStudyPlanSummary, Path]:
    protocol = ProtocolFreezeContract.model_validate_json(protocol_path.read_text())
    study = load_study(config_path)
    cells = _expected_cells(protocol, study)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(
            json.dumps(cell.model_dump(mode="json"), sort_keys=True, separators=(",", ":")) + "\n"
            for cell in cells
        )
    )
    summary = _summarize(protocol, cells, sha256_file(output_path))
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    )
    return summary, output_path


def validate_full_study_execution_plan(
    protocol_path: Path,
    config_path: Path,
    plan_path: Path,
    output_path: Path,
) -> tuple[FullStudyPlanValidation, Path]:
    summary = inspect_full_study_execution_plan(protocol_path, config_path, plan_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    )
    return summary, output_path


def inspect_full_study_execution_plan(
    protocol_path: Path,
    config_path: Path,
    plan_path: Path,
) -> FullStudyPlanValidation:
    errors: list[str] = []
    observed: list[FullStudyPlanCell] = []
    try:
        protocol = ProtocolFreezeContract.model_validate_json(protocol_path.read_text())
        study = load_study(config_path)
        for line_number, line in enumerate(plan_path.read_text().splitlines(), start=1):
            if not line.strip():
                continue
            try:
                observed.append(FullStudyPlanCell.model_validate_json(line))
            except (ValidationError, ValueError) as exc:
                errors.append(f"plan line {line_number}: {exc}")
        expected = _expected_cells(protocol, study)
        if observed != expected:
            errors.extend(_plan_difference_errors(observed, expected))
    except (OSError, ValidationError, ValueError) as exc:
        errors.append(str(exc))

    plan_hash = sha256_file(plan_path) if plan_path.is_file() else None
    summary = FullStudyPlanValidation(
        status="valid" if not errors else "invalid",
        plan_sha256=plan_hash,
        cells_checked=len(observed),
        errors=errors,
    )
    return summary


def load_full_study_plan(plan_path: Path) -> list[FullStudyPlanCell]:
    cells: list[FullStudyPlanCell] = []
    for line_number, line in enumerate(plan_path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            cells.append(FullStudyPlanCell.model_validate_json(line))
        except (ValidationError, ValueError) as exc:
            raise ValueError(f"Invalid execution plan line {line_number}: {exc}") from exc
    if not cells:
        raise ValueError("Execution plan is empty")
    return cells


def _expected_cells(
    protocol: ProtocolFreezeContract,
    study: LoadedStudy,
) -> list[FullStudyPlanCell]:
    if protocol.execution.randomization_seed is None:
        raise ValueError("Protocol randomization seed is required to generate the execution plan")
    if study.config.study_mode != "full":
        raise ValueError("Execution plans require a full-study configuration")
    if study.config.experiment_id != protocol.protocol_id:
        raise ValueError("Study experiment_id does not match protocol_id")
    if study.config.repeats != protocol.execution.repeats:
        raise ValueError("Study repeats do not match the protocol")
    if study.config.seed != protocol.execution.randomization_seed:
        raise ValueError("Study seed does not match the protocol")
    if set(study.config.model_ids) != set(FACT_CONDITIONS):
        raise ValueError("Full-study model set does not match the predeclared conditions")
    if set(protocol.condition_ids) != {
        *FACT_CONDITIONS.values(),
        *WRITER_CONDITIONS.values(),
        *CONTEXT_CONDITIONS.values(),
        "context-selected-vision-brand-page-purpose",
        DIRECT_CONDITION,
    }:
        raise ValueError("Protocol condition IDs do not match the full-study design")

    manifest_path = study.root / study.config.dataset_manifest
    if sha256_file(manifest_path) != protocol.dataset.manifest_sha256:
        raise ValueError("Study manifest hash does not match the protocol")
    items = load_manifest(study.root, study.config.dataset_manifest)
    items_by_id = {item.id: item for item in items}
    ordered_ids = sorted(items_by_id)
    seed = protocol.execution.randomization_seed
    cells: list[FullStudyPlanCell] = []

    for repeat in range(1, protocol.execution.repeats + 1):
        blocks: list[tuple[str, str, str]] = [
            ("vision_facts", model_id, FACT_CONDITIONS[model_id])
            for model_id in study.config.model_ids
        ]
        blocks.append(("direct_metadata", WRITER_MODEL_ID, DIRECT_CONDITION))
        _shuffle(blocks, seed, f"primary-blocks-r{repeat}")
        for stage, model_id, condition_id in blocks:
            image_ids = ordered_ids.copy()
            _shuffle(image_ids, seed, f"{stage}:{model_id}:r{repeat}")
            for image_id in image_ids:
                item = items_by_id[image_id]
                if stage == "vision_facts":
                    cell_id = _fact_cell_id(model_id, image_id, repeat)
                    cells.append(
                        _cell(
                            protocol,
                            cell_id=cell_id,
                            phase="primary_generation",
                            stage="vision_facts",
                            condition_id=condition_id,
                            image_id=image_id,
                            repeat=repeat,
                            model_id=model_id,
                            prompt_id="vision-facts-v1",
                            response_schema="visual-facts.schema.json",
                            context_mode="none",
                            randomization_block=f"r{repeat}-facts-{model_id}",
                            human_review=repeat == protocol.execution.human_repeat,
                            review_scope="rq1" if repeat == protocol.execution.human_repeat else "none",
                        )
                    )
                else:
                    cells.append(
                        _cell(
                            protocol,
                            cell_id=f"direct-r{repeat}-{image_id}",
                            phase="primary_generation",
                            stage="direct_metadata",
                            condition_id=condition_id,
                            image_id=image_id,
                            repeat=repeat,
                            model_id=model_id,
                            prompt_id="direct-metadata-v1",
                            response_schema="metadata.schema.json",
                            context_mode="full",
                            randomization_block=f"r{repeat}-direct-{model_id}",
                            human_review=repeat == protocol.execution.human_repeat,
                            review_scope="metadata"
                            if repeat == protocol.execution.human_repeat
                            else "none",
                        )
                    )

    for repeat in range(1, protocol.execution.repeats + 1):
        source_models = list(study.config.model_ids)
        _shuffle(source_models, seed, f"writer-blocks-r{repeat}")
        for source_model_id in source_models:
            image_ids = ordered_ids.copy()
            _shuffle(image_ids, seed, f"writer:{source_model_id}:r{repeat}")
            for image_id in image_ids:
                item = items_by_id[image_id]
                human_review = (
                    repeat == protocol.execution.human_repeat
                    and (
                        source_model_id == WRITER_MODEL_ID
                        or bool(
                            item.analysis_populations
                            and item.analysis_populations.production_metadata
                        )
                    )
                )
                cells.append(
                    _cell(
                        protocol,
                        cell_id=f"writer-{_slug(source_model_id)}-r{repeat}-{image_id}",
                        phase="decomposed_writer",
                        stage="decomposed_writer",
                        condition_id=WRITER_CONDITIONS[source_model_id],
                        image_id=image_id,
                        repeat=repeat,
                        model_id=WRITER_MODEL_ID,
                        source_model_id=source_model_id,
                        prompt_id="context-writer-v1",
                        response_schema="metadata.schema.json",
                        context_mode="full",
                        dependency_cell_id=_fact_cell_id(source_model_id, image_id, repeat),
                        randomization_block=f"r{repeat}-writer-from-{source_model_id}",
                        human_review=human_review,
                        review_scope="metadata" if human_review else "none",
                    )
                )

    context_items = [
        item
        for item in items
        if item.analysis_populations and item.analysis_populations.context_ablation
    ]
    for repeat in range(1, protocol.execution.repeats + 1):
        context_rows = [
            (mode, item.id)
            for mode in CONTEXT_CONDITIONS
            for item in context_items
        ]
        _shuffle(context_rows, seed, f"context-r{repeat}")
        for mode, image_id in context_rows:
            cells.append(
                _cell(
                    protocol,
                    cell_id=f"context-{mode.replace('_', '-')}-r{repeat}-{image_id}",
                    phase="context_ablation",
                    stage="context_writer",
                    condition_id=CONTEXT_CONDITIONS[mode],
                    image_id=image_id,
                    repeat=repeat,
                    model_id=WRITER_MODEL_ID,
                    prompt_id="context-writer-v1",
                    response_schema="metadata.schema.json",
                    context_mode=mode,
                    dependency_selector="selected_vision_model",
                    randomization_block=f"r{repeat}-context-selected-vision",
                    human_review=repeat == protocol.execution.human_repeat,
                    review_scope="metadata"
                    if repeat == protocol.execution.human_repeat
                    else "none",
                )
            )

    return [cell.model_copy(update={"ordinal": index}) for index, cell in enumerate(cells, start=1)]


def _cell(
    protocol: ProtocolFreezeContract,
    *,
    cell_id: str,
    phase: Literal["primary_generation", "decomposed_writer", "context_ablation"],
    stage: Literal["vision_facts", "decomposed_writer", "direct_metadata", "context_writer"],
    condition_id: str,
    image_id: str,
    repeat: int,
    model_id: str,
    prompt_id: Literal["vision-facts-v1", "context-writer-v1", "direct-metadata-v1"],
    response_schema: Literal["visual-facts.schema.json", "metadata.schema.json"],
    context_mode: Literal["none", "full", "visual_only", "brand_only", "page_purpose"],
    randomization_block: str,
    human_review: bool,
    review_scope: Literal["none", "rq1", "metadata"],
    source_model_id: str | None = None,
    dependency_cell_id: str | None = None,
    dependency_selector: Literal["selected_vision_model"] | None = None,
) -> FullStudyPlanCell:
    return FullStudyPlanCell(
        ordinal=1,
        cell_id=cell_id,
        experiment_id=protocol.protocol_id,
        protocol_version=protocol.protocol_version,
        manifest_sha256=protocol.dataset.manifest_sha256 or "",
        phase=phase,
        stage=stage,
        condition_id=condition_id,
        image_id=image_id,
        repeat=repeat,
        model_id=model_id,
        source_model_id=source_model_id,
        prompt_id=prompt_id,
        response_schema=response_schema,
        context_mode=context_mode,
        dependency_cell_id=dependency_cell_id,
        dependency_selector=dependency_selector,
        randomization_block=randomization_block,
        human_review=human_review,
        review_scope=review_scope,
    )


def _summarize(
    protocol: ProtocolFreezeContract,
    cells: list[FullStudyPlanCell],
    plan_hash: str,
) -> FullStudyPlanSummary:
    return FullStudyPlanSummary(
        status="ready",
        experiment_id=protocol.protocol_id,
        protocol_version=protocol.protocol_version,
        randomization_seed=protocol.execution.randomization_seed or 0,
        manifest_sha256=protocol.dataset.manifest_sha256 or "",
        plan_sha256=plan_hash,
        cells=len(cells),
        primary_generation_cells=sum(cell.phase == "primary_generation" for cell in cells),
        decomposed_writer_cells=sum(cell.phase == "decomposed_writer" for cell in cells),
        context_ablation_cells=sum(cell.phase == "context_ablation" for cell in cells),
        human_review_items=sum(cell.human_review for cell in cells),
        deferred_selection_cells=sum(
            cell.dependency_selector == "selected_vision_model" for cell in cells
        ),
    )


def _plan_difference_errors(
    observed: list[FullStudyPlanCell],
    expected: list[FullStudyPlanCell],
) -> list[str]:
    errors: list[str] = []
    if len(observed) != len(expected):
        errors.append(f"execution plan has {len(observed)} cells; expected {len(expected)}")
    observed_ids = [cell.cell_id for cell in observed]
    if len(observed_ids) != len(set(observed_ids)):
        errors.append("execution plan cell IDs are not unique")
    if [cell.ordinal for cell in observed] != list(range(1, len(observed) + 1)):
        errors.append("execution plan ordinals are not contiguous from 1")
    for index, (actual, wanted) in enumerate(zip(observed, expected), start=1):
        if actual != wanted:
            errors.append(
                f"execution plan differs from the deterministic contract at ordinal {index}"
            )
            break
    return errors


def _fact_cell_id(model_id: str, image_id: str, repeat: int) -> str:
    return f"facts-{_slug(model_id)}-r{repeat}-{image_id}"


def _slug(value: str) -> str:
    return value.replace("-baseline", "")


def _shuffle(values: list, seed: int, label: str) -> None:
    derived = int.from_bytes(
        hashlib.sha256(f"{seed}:{label}".encode()).digest()[:8],
        byteorder="big",
    )
    random.Random(derived).shuffle(values)
