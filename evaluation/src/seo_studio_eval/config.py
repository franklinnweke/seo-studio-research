from dataclasses import dataclass
from pathlib import Path
import re
import tomllib
from typing import Literal

from pydantic import BaseModel, Field, model_validator


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ModelEntry(BaseModel):
    id: str = Field(min_length=1)
    ollama_name: str = Field(min_length=1)
    expected_digest: str = ""
    family: str = Field(min_length=1)
    parameters: str = Field(min_length=1)
    quantization: str = Field(min_length=1)
    role: str = Field(min_length=1)
    license: str = Field(min_length=1)
    frozen: bool = False

    @model_validator(mode="after")
    def validate_digest(self) -> "ModelEntry":
        if self.expected_digest and not SHA256_PATTERN.fullmatch(self.expected_digest):
            raise ValueError("expected_digest must be an empty value or a full lowercase SHA-256 digest")
        if self.frozen and not self.expected_digest:
            raise ValueError("frozen models require expected_digest")
        return self


class ModelConfig(BaseModel):
    schema_version: Literal[1]
    models: list[ModelEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "ModelConfig":
        ids = [model.id for model in self.models]
        if len(ids) != len(set(ids)):
            raise ValueError("model ids must be unique")
        return self


class StudyConfig(BaseModel):
    schema_version: Literal[1]
    experiment_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    protocol_version: str = Field(min_length=1)
    study_mode: Literal["pilot", "full"]
    dataset_manifest: Path
    models_config: Path
    output_dir: Path
    model_ids: list[str] = Field(min_length=1)
    repeats: int = Field(ge=1)
    seed: int
    require_frozen_models: bool
    allow_dirty_worktree: bool


@dataclass(frozen=True)
class LoadedStudy:
    root: Path
    config_path: Path
    config: StudyConfig
    models: ModelConfig


def load_study(config_path: Path) -> LoadedStudy:
    resolved_config = config_path.resolve()
    root = resolved_config.parent.parent
    config = StudyConfig.model_validate(tomllib.loads(resolved_config.read_text()))
    model_path = resolve_under_root(root, config.models_config)
    models = ModelConfig.model_validate(tomllib.loads(model_path.read_text()))
    models_by_id = {model.id: model for model in models.models}

    missing_ids = [model_id for model_id in config.model_ids if model_id not in models_by_id]
    if missing_ids:
        raise ValueError(f"Study references unknown model ids: {', '.join(missing_ids)}")
    if len(config.model_ids) != len(set(config.model_ids)):
        raise ValueError("Study model_ids must be unique")
    if config.require_frozen_models:
        unfrozen = [model_id for model_id in config.model_ids if not models_by_id[model_id].frozen]
        if unfrozen:
            raise ValueError(f"Full-study configuration contains unfrozen models: {', '.join(unfrozen)}")
    if config.study_mode == "full" and config.allow_dirty_worktree:
        raise ValueError("Full-study configuration cannot allow a dirty worktree")

    return LoadedStudy(root=root, config_path=resolved_config, config=config, models=models)


def resolve_under_root(root: Path, value: Path) -> Path:
    candidate = (root / value).resolve() if not value.is_absolute() else value.resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"Configured path escapes the evaluation root: {value}")
    return candidate
