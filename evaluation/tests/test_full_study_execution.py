import json
from pathlib import Path
from typing import Any

import pytest

from seo_studio_eval.execution_plan import (
    build_full_study_execution_plan,
    validate_full_study_execution_plan,
)
from seo_studio_eval.full_study import collect_full_study_phase
from seo_studio_eval.records import attempt_record_paths


EVALUATION_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = EVALUATION_ROOT / "configs" / "full-study-protocol-v1.json"
CONFIG = EVALUATION_ROOT / "configs" / "full-study.toml"
PINNED_PLAN = EVALUATION_ROOT / "configs" / "full-study-execution-plan-v1.jsonl"


class FakeFullStudyTransport:
    def __init__(self, *, fail_transport: bool = False) -> None:
        self.fail_transport = fail_transport
        self.calls = 0

    def version(self) -> str:
        return "0.24.0"

    def tags(self) -> dict[str, Any]:
        models = json.loads(PROTOCOL.read_text())["model_identities"]
        names = {
            "qwen25vl-3b-baseline": "qwen2.5vl:3b",
            "qwen35-9b": "qwen3.5:latest",
            "gemma3-12b": "gemma3:12b",
        }
        return {
            "models": [
                {"name": names[item["model_id"]], "digest": item["expected_digest"]}
                for item in models
            ]
        }

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        if self.fail_transport:
            raise ConnectionResetError("synthetic transport interruption")
        properties = request["format"]["properties"]
        if "summary" in properties:
            payload = {
                "summary": "A synthetic scene.",
                "people": [],
                "objects": [],
                "setting": "",
                "visible_text": [],
                "uncertain_facts": [],
                "forbidden_inferences_observed": [],
            }
        else:
            payload = {
                "filename": "synthetic-scene.jpg",
                "alt_text": "A synthetic scene.",
                "caption": "A synthetic scene.",
                "confidence": 0.8,
                "purpose_rationale": "The image is informative.",
                "warnings": [],
            }
        return {"parsed_payload": payload, "done_reason": "stop"}


def _generate_plan(tmp_path: Path) -> Path:
    plan = tmp_path / "plan.jsonl"
    build_full_study_execution_plan(
        PROTOCOL,
        CONFIG,
        plan,
        tmp_path / "plan-summary.json",
    )
    return plan


def test_execution_plan_is_deterministic_and_matches_frozen_accounting(
    tmp_path: Path,
) -> None:
    first = _generate_plan(tmp_path / "first")
    second = _generate_plan(tmp_path / "second")

    assert first.read_bytes() == second.read_bytes() == PINNED_PLAN.read_bytes()
    summary, _ = validate_full_study_execution_plan(
        PROTOCOL,
        CONFIG,
        first,
        tmp_path / "validation.json",
    )
    rows = [json.loads(line) for line in first.read_text().splitlines()]

    assert summary.status == "valid"
    assert summary.cells_checked == 3012
    assert sum(row["phase"] == "primary_generation" for row in rows) == 1536
    assert sum(row["phase"] == "decomposed_writer" for row in rows) == 1152
    assert sum(row["phase"] == "context_ablation" for row in rows) == 324
    assert sum(row["human_review"] for row in rows) == 876
    assert sum(row["dependency_selector"] == "selected_vision_model" for row in rows) == 324


def test_plan_validation_rejects_order_or_cell_drift(tmp_path: Path) -> None:
    plan = _generate_plan(tmp_path)
    rows = plan.read_text().splitlines()
    first = json.loads(rows[0])
    first["condition_id"] = "changed-after-freeze"
    rows[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
    plan.write_text("\n".join(rows) + "\n")

    summary, _ = validate_full_study_execution_plan(
        PROTOCOL,
        CONFIG,
        plan,
        tmp_path / "validation.json",
    )

    assert summary.status == "invalid"
    assert "differs from the deterministic contract" in "\n".join(summary.errors)


def test_collection_resumes_without_repeating_completed_cells(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr("seo_studio_eval.full_study._git_state", lambda _path: ("abc123", False))
    run_dir = tmp_path / "run"
    first_transport = FakeFullStudyTransport()
    first, _ = collect_full_study_phase(
        PROTOCOL,
        CONFIG,
        PINNED_PLAN,
        phase="primary_generation",
        base_url="http://127.0.0.1:11435",
        run_dir=run_dir,
        run_id="full-test",
        system_snapshot_ref="private-test-snapshot",
        max_new_attempts=2,
        transport=first_transport,
        require_freeze=False,
    )
    second_transport = FakeFullStudyTransport()
    second, _ = collect_full_study_phase(
        PROTOCOL,
        CONFIG,
        PINNED_PLAN,
        phase="primary_generation",
        base_url="http://127.0.0.1:11435",
        run_dir=run_dir,
        run_id="full-test",
        system_snapshot_ref="private-test-snapshot",
        max_new_attempts=2,
        transport=second_transport,
        require_freeze=False,
    )

    assert first.status == "paused"
    assert first.completed_cells == 2
    assert second.completed_cells == 4
    assert first_transport.calls == 2
    assert second_transport.calls == 2
    assert len(attempt_record_paths(run_dir)) == 4


def test_transport_recovery_is_explicit_and_bounded(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("seo_studio_eval.full_study._git_state", lambda _path: ("abc123", False))
    run_dir = tmp_path / "run"
    failed, _ = collect_full_study_phase(
        PROTOCOL,
        CONFIG,
        PINNED_PLAN,
        phase="primary_generation",
        base_url="http://127.0.0.1:11435",
        run_dir=run_dir,
        run_id="transport-test",
        system_snapshot_ref="private-test-snapshot",
        max_new_attempts=5,
        transport=FakeFullStudyTransport(fail_transport=True),
        require_freeze=False,
    )
    recovered_transport = FakeFullStudyTransport()
    recovered, _ = collect_full_study_phase(
        PROTOCOL,
        CONFIG,
        PINNED_PLAN,
        phase="primary_generation",
        base_url="http://127.0.0.1:11435",
        run_dir=run_dir,
        run_id="transport-test",
        system_snapshot_ref="private-test-snapshot",
        max_new_attempts=1,
        transport=recovered_transport,
        require_freeze=False,
    )

    assert failed.paused_on_transport_error is True
    assert failed.completed_cells == 0
    assert recovered.completed_cells == 1
    assert recovered.raw_attempt_records == 2
    assert recovered_transport.calls == 1


def test_resume_rejects_existing_record_drift(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("seo_studio_eval.full_study._git_state", lambda _path: ("abc123", False))
    run_dir = tmp_path / "run"
    collect_full_study_phase(
        PROTOCOL,
        CONFIG,
        PINNED_PLAN,
        phase="primary_generation",
        base_url="http://127.0.0.1:11435",
        run_dir=run_dir,
        run_id="drift-test",
        system_snapshot_ref="private-test-snapshot",
        max_new_attempts=1,
        transport=FakeFullStudyTransport(),
        require_freeze=False,
    )
    record_path = attempt_record_paths(run_dir)[0]
    payload = json.loads(record_path.read_text())
    payload["condition_id"] = "changed-after-collection"
    record_path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="Existing outcome drift"):
        collect_full_study_phase(
            PROTOCOL,
            CONFIG,
            PINNED_PLAN,
            phase="primary_generation",
            base_url="http://127.0.0.1:11435",
            run_dir=run_dir,
            run_id="drift-test",
            system_snapshot_ref="private-test-snapshot",
            max_new_attempts=1,
            transport=FakeFullStudyTransport(),
            require_freeze=False,
        )


def test_collection_refuses_draft_protocol_before_network_use(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr("seo_studio_eval.full_study._git_state", lambda _path: ("abc123", False))
    transport = FakeFullStudyTransport()

    draft_payload = json.loads(PROTOCOL.read_text())
    draft_payload["status"] = "draft"
    draft_protocol = tmp_path / "draft-protocol.json"
    draft_protocol.write_text(json.dumps(draft_payload))

    with pytest.raises(ValueError, match="freeze_ready"):
        collect_full_study_phase(
            draft_protocol,
            CONFIG,
            PINNED_PLAN,
            phase="primary_generation",
            base_url="http://127.0.0.1:11435",
            run_dir=tmp_path / "run",
            run_id="blocked-test",
            system_snapshot_ref="private-test-snapshot",
            max_new_attempts=1,
            transport=transport,
        )

    assert transport.calls == 0


def test_context_collection_requires_frozen_selection_record_before_network(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr("seo_studio_eval.full_study._git_state", lambda _path: ("abc123", False))
    transport = FakeFullStudyTransport()

    with pytest.raises(ValueError, match="immutable vision selection record"):
        collect_full_study_phase(
            PROTOCOL,
            CONFIG,
            PINNED_PLAN,
            phase="context_ablation",
            base_url="http://127.0.0.1:11435",
            run_dir=tmp_path / "run",
            run_id="context-test",
            system_snapshot_ref="private-test-snapshot",
            max_new_attempts=1,
            transport=transport,
            require_freeze=False,
        )

    assert transport.calls == 0
