from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ValidationError

from .schemas import (
    ErrorEvidence,
    InputEvidence,
    ModelIdentity,
    PromptEvidence,
    RunRecord,
    TelemetryEvidence,
    ValidationEvidence,
)


class GenerationTransport(Protocol):
    def generate(self, request: dict[str, Any]) -> dict[str, Any]: ...


class AttemptSpec(BaseModel):
    experiment_id: str
    protocol_version: str
    run_id: str
    attempt_id: str
    repeat: int
    randomization_block: str
    git_commit: str
    dirty_worktree: bool
    ollama_version: str
    system_snapshot_ref: str
    model: ModelIdentity
    input: InputEvidence
    prompt: PromptEvidence
    generation_options: dict[str, Any]
    thinking_mode: Literal["disabled", "enabled"] = "disabled"
    sanitized_request: dict[str, Any]
    parser_version: str = "parser-v1"
    normalization_version: str = "normalization-v1"
    study_config_sha256: str = ""
    models_config_sha256: str = ""
    criteria_sha256: str = ""


def execute_attempt(
    spec: AttemptSpec,
    transport: GenerationTransport,
    request_payload: dict[str, Any] | None = None,
    response_model: type[BaseModel] | None = None,
) -> RunRecord:
    started_at = datetime.now(timezone.utc)
    started_clock = perf_counter()
    raw_response: dict[str, Any] = {}
    parsed_payload: dict[str, Any] | None = None
    validation = ValidationEvidence(valid=False, errors=[])
    error: ErrorEvidence | None = None
    http_status: int | None = None
    done_reason = ""
    native: dict[str, Any] = {}

    try:
        raw_response = transport.generate(request_payload or spec.sanitized_request)
        http_status = 200
        candidate = _candidate_payload(raw_response)
        if response_model is not None and isinstance(candidate, dict):
            try:
                parsed_payload = response_model.model_validate(candidate).model_dump(mode="json")
                validation = ValidationEvidence(valid=True, errors=[])
            except ValidationError as exc:
                validation = ValidationEvidence(
                    valid=False,
                    errors=[error["msg"] for error in exc.errors(include_url=False)],
                )
        else:
            parsed_payload = candidate if isinstance(candidate, dict) else None
            validation = ValidationEvidence(
                valid=parsed_payload is not None,
                errors=[] if parsed_payload is not None else ["structured payload missing or invalid"],
            )
        done_reason = raw_response.get("done_reason", "") if isinstance(raw_response.get("done_reason"), str) else ""
        native = raw_response
    except Exception as exc:
        error = ErrorEvidence(category="transport_error", message=str(exc) or exc.__class__.__name__)
        validation = ValidationEvidence(valid=False, errors=["transport failed"])

    ended_at = datetime.now(timezone.utc)
    telemetry = TelemetryEvidence(
        wall_duration_ms=(perf_counter() - started_clock) * 1000,
        total_duration_ns=_nonnegative_int(native.get("total_duration")),
        load_duration_ns=_nonnegative_int(native.get("load_duration")),
        prompt_eval_count=_nonnegative_int(native.get("prompt_eval_count")),
        prompt_eval_duration_ns=_nonnegative_int(native.get("prompt_eval_duration")),
        eval_count=_nonnegative_int(native.get("eval_count")),
        eval_duration_ns=_nonnegative_int(native.get("eval_duration")),
    )
    return RunRecord(
        **spec.model_dump(),
        started_at=started_at,
        ended_at=ended_at,
        raw_response=raw_response,
        parsed_payload=parsed_payload,
        validation=validation,
        http_status=http_status,
        error=error,
        done_reason=done_reason,
        telemetry=telemetry,
    )


def _nonnegative_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _candidate_payload(raw_response: dict[str, Any]) -> object:
    candidate = raw_response.get("parsed_payload")
    if isinstance(candidate, dict):
        return candidate
    response = raw_response.get("response")
    if not isinstance(response, str):
        return None
    import json

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return None
