import json
from pathlib import Path
from typing import Any

import pytest

from seo_studio_eval.config import load_study
from seo_studio_eval.ollama import OllamaHTTPError
from seo_studio_eval.pilot import run_compatibility_pilot


class FakePilotTransport:
    def __init__(self, tags: list[dict[str, str]]) -> None:
        self._tags = tags
        self.requests: list[dict[str, Any]] = []

    def version(self) -> str:
        return "0.24.0"

    def tags(self) -> dict[str, Any]:
        return {"models": self._tags}

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(request)
        return {
            "response": json.dumps(
                {
                    "summary": "A test image.",
                    "people": [],
                    "objects": [],
                    "setting": "",
                    "visible_text": [],
                    "uncertain_facts": [],
                    "forbidden_inferences_observed": [],
                }
            ),
            "done_reason": "stop",
            "total_duration": 100,
            "load_duration": 10,
            "prompt_eval_count": 12,
            "eval_count": 8,
        }


class InterruptingPilotTransport(FakePilotTransport):
    def __init__(self, tags: list[dict[str, str]], fail_on_call: int) -> None:
        super().__init__(tags)
        self.fail_on_call = fail_on_call

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        if len(self.requests) + 1 == self.fail_on_call:
            self.requests.append(request)
            raise ConnectionError("synthetic tunnel reset")
        return super().generate(request)


class WarmupRejectingPilotTransport(FakePilotTransport):
    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        if not self.requests:
            self.requests.append(request)
            raise OllamaHTTPError(500, "image: unknown format")
        return super().generate(request)


def _live_tags(config_path: Path) -> list[dict[str, str]]:
    study = load_study(config_path)
    configured = {model.id: model for model in study.models.models}
    return [
        {
            "name": configured[model_id].ollama_name,
            "digest": configured[model_id].expected_digest,
        }
        for model_id in study.config.model_ids
    ]


def test_pilot_runs_warmups_and_complete_deterministic_matrix(tmp_path: Path) -> None:
    evaluation_root = Path(__file__).resolve().parents[1]
    config_path = evaluation_root / "configs" / "pilot.toml"
    criteria_path = evaluation_root / "configs" / "compatibility-criteria.toml"
    transport = FakePilotTransport(_live_tags(config_path))
    progress: list[dict[str, Any]] = []

    summary, summary_path = run_compatibility_pilot(
        config_path,
        criteria_path,
        "http://127.0.0.1:11435",
        tmp_path,
        "pilot-test-run",
        "private-test-snapshot",
        transport=transport,
        progress=progress.append,
    )

    assert summary.status == "complete"
    assert summary.expected_attempts == 100
    assert summary.observed_attempts == 100
    assert summary.valid_attempts == 100
    assert summary.failed_attempts == 0
    assert summary.warmup_records == 5
    assert summary.all_models_meet_threshold is True
    assert summary.aborted_on_transport_error is False
    assert summary.abort_attempt_id == ""
    assert len(transport.requests) == 105
    assert sum(event["event"] == "warmup_complete" for event in progress) == 5
    assert sum(event["event"] == "attempt_complete" for event in progress) == 100
    assert summary_path.is_file()
    assert len(list(tmp_path.glob("*.json"))) == 101
    assert len(list((tmp_path / "warmups").glob("*.json"))) == 5
    assert all('"images"' not in path.read_text() for path in tmp_path.glob("*.json"))
    assert sum(request["keep_alive"] == 0 for request in transport.requests) == 5

    resumed_transport = FakePilotTransport(_live_tags(config_path))
    resumed, _ = run_compatibility_pilot(
        config_path,
        criteria_path,
        "http://127.0.0.1:11435",
        tmp_path,
        "pilot-test-run",
        "private-test-snapshot",
        transport=resumed_transport,
    )

    assert resumed.status == "complete"
    assert resumed.model_order == summary.model_order
    assert resumed.image_order_by_model == summary.image_order_by_model
    assert resumed_transport.requests == []
    assert resumed.warmup_records == 5


def test_pilot_stops_before_generation_on_live_digest_mismatch(tmp_path: Path) -> None:
    evaluation_root = Path(__file__).resolve().parents[1]
    config_path = evaluation_root / "configs" / "pilot.toml"
    tags = _live_tags(config_path)
    tags[0]["digest"] = "0" * 64
    transport = FakePilotTransport(tags)

    with pytest.raises(ValueError, match="Live model identity mismatch"):
        run_compatibility_pilot(
            config_path,
            evaluation_root / "configs" / "compatibility-criteria.toml",
            "http://127.0.0.1:11435",
            tmp_path,
            "pilot-test-run",
            "private-test-snapshot",
            transport=transport,
        )

    assert transport.requests == []


def test_pilot_aborts_after_first_recorded_transport_failure(tmp_path: Path) -> None:
    evaluation_root = Path(__file__).resolve().parents[1]
    config_path = evaluation_root / "configs" / "pilot.toml"
    transport = InterruptingPilotTransport(_live_tags(config_path), fail_on_call=3)

    summary, _ = run_compatibility_pilot(
        config_path,
        evaluation_root / "configs" / "compatibility-criteria.toml",
        "http://127.0.0.1:11435",
        tmp_path,
        "pilot-interrupted-run",
        "private-test-snapshot",
        transport=transport,
    )

    assert summary.status == "incomplete"
    assert summary.observed_attempts == 2
    assert summary.valid_attempts == 1
    assert summary.failed_attempts == 1
    assert summary.warmup_records == 1
    assert summary.aborted_on_transport_error is True
    assert summary.abort_attempt_id
    assert len(transport.requests) == 3
    assert len(list(tmp_path.glob("*.json"))) == 3

    recovery_transport = FakePilotTransport(_live_tags(config_path))
    recovered, _ = run_compatibility_pilot(
        config_path,
        evaluation_root / "configs" / "compatibility-criteria.toml",
        "http://127.0.0.1:11435",
        tmp_path,
        "pilot-interrupted-run",
        "private-test-snapshot",
        transport=recovery_transport,
        max_new_attempts=5,
    )

    assert recovered.status == "paused"
    assert recovered.observed_attempts == 6
    assert recovered.valid_attempts == 6
    assert recovered.failed_attempts == 0
    assert recovered.raw_measured_records == 7
    assert recovered.superseded_transport_records == 1
    assert len(recovery_transport.requests) == 6


def test_pilot_pauses_and_resumes_at_new_attempt_limit(tmp_path: Path) -> None:
    evaluation_root = Path(__file__).resolve().parents[1]
    config_path = evaluation_root / "configs" / "pilot.toml"
    criteria_path = evaluation_root / "configs" / "compatibility-criteria.toml"
    first_transport = FakePilotTransport(_live_tags(config_path))

    first, _ = run_compatibility_pilot(
        config_path,
        criteria_path,
        "http://127.0.0.1:11435",
        tmp_path,
        "pilot-paused-run",
        "private-test-snapshot",
        transport=first_transport,
        max_new_attempts=5,
    )

    assert first.status == "paused"
    assert first.observed_attempts == 5
    assert first.new_attempts_this_session == 5
    assert first.max_new_attempts == 5
    assert len(first_transport.requests) == 6

    second_transport = FakePilotTransport(_live_tags(config_path))
    second, _ = run_compatibility_pilot(
        config_path,
        criteria_path,
        "http://127.0.0.1:11435",
        tmp_path,
        "pilot-paused-run",
        "private-test-snapshot",
        transport=second_transport,
        max_new_attempts=5,
    )

    assert second.status == "paused"
    assert second.observed_attempts == 10
    assert second.new_attempts_this_session == 5
    assert second.warmup_records == 2
    assert len(second_transport.requests) == 6


def test_pilot_records_http_rejected_warmup_without_transport_abort(tmp_path: Path) -> None:
    evaluation_root = Path(__file__).resolve().parents[1]
    config_path = evaluation_root / "configs" / "pilot.toml"
    transport = WarmupRejectingPilotTransport(_live_tags(config_path))

    summary, _ = run_compatibility_pilot(
        config_path,
        evaluation_root / "configs" / "compatibility-criteria.toml",
        "http://127.0.0.1:11435",
        tmp_path,
        "pilot-warmup-rejected-run",
        "private-test-snapshot",
        transport=transport,
        max_new_attempts=5,
    )

    assert summary.status == "paused"
    assert summary.aborted_on_transport_error is False
    assert summary.observed_attempts == 5
    assert summary.valid_attempts == 5
    assert summary.warmup_records == 1
    assert len(transport.requests) == 6
