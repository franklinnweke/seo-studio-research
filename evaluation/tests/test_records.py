from pathlib import Path
from typing import Any

import pytest

from seo_studio_eval.accounting import effective_error_category
from seo_studio_eval.ollama import OllamaHTTPError, OllamaTimeoutError, OllamaTransport
from seo_studio_eval.records import read_attempt_record, write_attempt_record
from seo_studio_eval.runner import AttemptSpec, execute_attempt
from seo_studio_eval.schemas import InputEvidence, ModelIdentity, PromptEvidence, VisualFactsPayload
from seo_studio_eval.validation import validate_run_directory


class FakeOllamaTransport:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        return {
            "model": "qwen3.5:latest",
            "parsed_payload": {"alt_text": "A synthetic blue square."},
            "done_reason": "stop",
            "total_duration": 100,
            "prompt_eval_count": 12,
            "eval_count": 8,
        }


class FailingOllamaTransport:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        raise TimeoutError("synthetic timeout")


class RejectingOllamaTransport:
    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        raise OllamaHTTPError(500, "image: unknown format")


class TimingOutOllamaTransport:
    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        raise OllamaTimeoutError("Ollama inference timed out after 240s")


class RawStructuredTransport:
    def __init__(self, response: str) -> None:
        self.response = response
        self.request: dict[str, Any] | None = None

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        self.request = request
        return {"response": self.response, "done_reason": "stop"}


def make_spec(attempt_id: str = "attempt-001") -> AttemptSpec:
    return AttemptSpec(
        experiment_id="pilot-v1",
        protocol_version="2.1-pilot",
        run_id="run-001",
        attempt_id=attempt_id,
        repeat=1,
        randomization_block="block-1",
        git_commit="abc123",
        dirty_worktree=False,
        ollama_version="0.24.0",
        system_snapshot_ref="snapshot.json",
        model=ModelIdentity(
            id="qwen35-9b",
            ollama_name="qwen3.5:latest",
            digest="a" * 64,
            family="Qwen3.5",
            parameters="9.7B",
            quantization="Q4_K_M",
            license="Apache-2.0",
        ),
        input=InputEvidence(
            image_id="synthetic-001",
            image_sha256="b" * 64,
            dataset_stratum="synthetic",
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
        generation_options={"temperature": 0, "seed": 42},
        thinking_mode="disabled",
        sanitized_request={"model": "qwen3.5:latest", "image_sha256": "b" * 64},
    )


def test_fake_ollama_attempt_preserves_telemetry_and_is_append_only(tmp_path: Path) -> None:
    transport = FakeOllamaTransport()
    record = execute_attempt(make_spec(), transport)
    output_path = write_attempt_record(tmp_path, record)
    loaded = read_attempt_record(output_path)

    assert transport.calls == 1
    assert loaded.validation.valid is True
    assert loaded.parsed_payload == {"alt_text": "A synthetic blue square."}
    assert loaded.telemetry.total_duration_ns == 100
    assert loaded.telemetry.prompt_eval_count == 12
    assert loaded.retry_count == 0
    with pytest.raises(FileExistsError):
        write_attempt_record(tmp_path, record)


def test_failed_attempt_is_recorded_without_hidden_retry(tmp_path: Path) -> None:
    transport = FailingOllamaTransport()
    record = execute_attempt(make_spec("attempt-failed"), transport)
    write_attempt_record(tmp_path, record)

    assert transport.calls == 1
    assert record.validation.valid is False
    assert record.error is not None
    assert record.error.category == "transport_error"
    assert record.retry_count == 0
    summary, _ = validate_run_directory(tmp_path)
    assert summary.status == "valid"
    assert summary.records_checked == 1


def test_ollama_http_failure_is_not_mislabeled_as_transport_loss() -> None:
    record = execute_attempt(make_spec("attempt-http-error"), RejectingOllamaTransport())

    assert record.validation.valid is False
    assert record.http_status == 500
    assert record.error is not None
    assert record.error.category == "ollama_http_error"
    assert record.retry_count == 0


def test_inference_timeout_is_a_final_non_transport_outcome() -> None:
    record = execute_attempt(make_spec("attempt-timeout"), TimingOutOllamaTransport())

    assert record.validation.valid is False
    assert record.error is not None
    assert record.error.category == "inference_timeout"
    assert record.retry_count == 0


def test_ollama_transport_enforces_absolute_deadline(monkeypatch) -> None:
    import time

    def stalled_urlopen(*_args, **_kwargs):
        time.sleep(1)
        raise AssertionError("absolute deadline did not interrupt the stalled socket")

    monkeypatch.setattr("seo_studio_eval.ollama.urlopen", stalled_urlopen)

    with pytest.raises(OllamaTimeoutError, match="timed out after 0.05s"):
        OllamaTransport("http://127.0.0.1:11435", timeout_seconds=0.05).version()


def test_run_validation_fails_when_no_attempt_records_exist(tmp_path: Path) -> None:
    summary, output_path = validate_run_directory(tmp_path)

    assert summary.status == "invalid"
    assert summary.errors == ["No attempt records found"]
    assert output_path.is_file()


def test_schema_constrained_attempt_uses_actual_request_without_recording_image_bytes() -> None:
    transport = RawStructuredTransport(
        '{"summary":"A blue square","people":[],"objects":[],"setting":"",'
        '"visible_text":[],"uncertain_facts":[],"forbidden_inferences_observed":[]}'
    )
    actual_request = {"model": "qwen3.5:latest", "images": ["base64-secret"]}

    record = execute_attempt(
        make_spec("schema-valid"),
        transport,
        request_payload=actual_request,
        response_model=VisualFactsPayload,
    )

    assert transport.request == actual_request
    assert record.validation.valid is True
    assert record.parsed_payload is not None
    assert record.parsed_payload["summary"] == "A blue square"
    assert "images" not in record.sanitized_request


def test_schema_constrained_attempt_records_validation_failure_without_retry() -> None:
    transport = RawStructuredTransport('{"summary":7,"unexpected":true}')

    record = execute_attempt(
        make_spec("schema-invalid"),
        transport,
        response_model=VisualFactsPayload,
    )

    assert record.validation.valid is False
    assert record.retry_count == 0
    assert record.error is None
    assert record.parsed_payload is None


def test_length_limited_invalid_output_is_classified_as_truncation() -> None:
    transport = RawStructuredTransport('{"summary":"unfinished"')

    record = execute_attempt(
        make_spec("schema-truncated"),
        transport,
        response_model=VisualFactsPayload,
    )
    record = record.model_copy(update={"done_reason": "length"})

    assert record.validation.valid is False
    assert effective_error_category(record) == "output_truncated"
