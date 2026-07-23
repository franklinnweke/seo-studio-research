import json
from pathlib import Path
import shutil

from seo_studio_eval.protocol_freeze import audit_protocol_freeze


EVALUATION_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = EVALUATION_ROOT / "configs" / "full-study-protocol-v1.json"
SAMPLE_SIZE_DECISION = EVALUATION_ROOT / "configs" / "full-study-sample-size-decision-20260719.json"


def write_protocol_fixture(tmp_path: Path, payload: dict) -> Path:
    root = tmp_path / "evaluation"
    (root / "configs").mkdir(parents=True)
    shutil.copytree(EVALUATION_ROOT / "prompts", root / "prompts")
    protocol = root / "configs" / "protocol.json"
    protocol.write_text(json.dumps(payload))
    return protocol


def test_current_protocol_is_frozen_and_ready(tmp_path: Path) -> None:
    summary, output_path = audit_protocol_freeze(PROTOCOL, tmp_path / "audit.json")
    payload = json.loads(PROTOCOL.read_text())

    assert summary.status == "freeze_ready"
    assert summary.errors == []
    assert summary.verified_prompt_hashes == 3
    assert summary.blockers == []
    assert payload["infrastructure"]["listener_security_verified"] is False
    assert output_path.is_file()


def test_protocol_audit_rejects_inconsistent_run_accounting(tmp_path: Path) -> None:
    payload = json.loads(PROTOCOL.read_text())
    payload["run_accounting"]["total_model_calls"] += 1
    invalid = write_protocol_fixture(tmp_path, payload)

    summary, _ = audit_protocol_freeze(invalid, tmp_path / "audit.json")

    assert summary.status == "invalid"
    assert "run accounting total_model_calls" in "\n".join(summary.errors)


def test_protocol_audit_rejects_inconsistent_review_workload(tmp_path: Path) -> None:
    payload = json.loads(PROTOCOL.read_text())
    payload["run_accounting"]["projected_minutes_per_reviewer"] += 1
    invalid = write_protocol_fixture(tmp_path, payload)

    summary, _ = audit_protocol_freeze(invalid, tmp_path / "audit.json")

    assert summary.status == "invalid"
    assert "projected_minutes_per_reviewer" in "\n".join(summary.errors)


def test_protocol_contract_rejects_domain_total_mismatch(tmp_path: Path) -> None:
    payload = json.loads(PROTOCOL.read_text())
    payload["dataset"]["domains"]["healthcare"] -= 1
    invalid = write_protocol_fixture(tmp_path, payload)

    summary, _ = audit_protocol_freeze(invalid, tmp_path / "audit.json")

    assert summary.status == "invalid"
    assert "domain counts must sum to final_items" in "\n".join(summary.errors)


def test_protocol_audit_rejects_empty_materialized_manifest(tmp_path: Path) -> None:
    payload = json.loads(PROTOCOL.read_text())
    payload["dataset"]["manifest_sha256"] = (
        "e3b0c44298fc1c149afbf4c8996fb924"
        "27ae41e4649b934ca495991b7852b855"
    )
    invalid = write_protocol_fixture(tmp_path, payload)
    manifest = invalid.parents[1] / payload["dataset"]["manifest_path"]
    manifest.parent.mkdir(parents=True)
    manifest.write_text("")

    summary, _ = audit_protocol_freeze(invalid, tmp_path / "audit.json")

    assert summary.status == "invalid"
    assert "Dataset manifest is empty" in "\n".join(summary.errors)


def test_protocol_audit_rejects_manifest_hash_drift(tmp_path: Path) -> None:
    payload = json.loads(PROTOCOL.read_text())
    payload["dataset"]["manifest_sha256"] = "0" * 64
    invalid = write_protocol_fixture(tmp_path, payload)
    manifest = invalid.parents[1] / payload["dataset"]["manifest_path"]
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}\n")

    summary, _ = audit_protocol_freeze(invalid, tmp_path / "audit.json")

    assert summary.status == "invalid"
    assert "full-study dataset manifest SHA-256 mismatch" in summary.errors


def test_protocol_audit_rejects_manifest_path_escape(tmp_path: Path) -> None:
    payload = json.loads(PROTOCOL.read_text())
    payload["dataset"]["manifest_path"] = "../../outside-manifest.jsonl"
    invalid = write_protocol_fixture(tmp_path, payload)
    outside = invalid.parents[2] / "outside-manifest.jsonl"
    outside.write_text("{}\n")

    summary, _ = audit_protocol_freeze(invalid, tmp_path / "audit.json")

    assert summary.status == "invalid"
    assert "full-study dataset manifest path escapes evaluation root" in summary.errors


def test_protocol_audit_rejects_sample_size_decision_hash_drift(tmp_path: Path) -> None:
    payload = json.loads(PROTOCOL.read_text())
    invalid = write_protocol_fixture(tmp_path, payload)
    decision = invalid.parents[1] / payload["dataset"]["sample_size_decision_path"]
    decision.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SAMPLE_SIZE_DECISION, decision)
    decision.write_text(decision.read_text() + "\n")

    summary, _ = audit_protocol_freeze(invalid, tmp_path / "audit.json")

    assert summary.status == "invalid"
    assert "sample-size decision record SHA-256 mismatch" in summary.errors


def test_protocol_audit_rejects_sample_size_decision_path_escape(tmp_path: Path) -> None:
    payload = json.loads(PROTOCOL.read_text())
    payload["dataset"]["sample_size_decision_path"] = "../../outside-decision.json"
    invalid = write_protocol_fixture(tmp_path, payload)
    outside = invalid.parents[2] / "outside-decision.json"
    shutil.copyfile(SAMPLE_SIZE_DECISION, outside)

    summary, _ = audit_protocol_freeze(invalid, tmp_path / "audit.json")

    assert summary.status == "invalid"
    assert "sample-size decision path escapes evaluation root" in summary.errors


def test_protocol_audit_rejects_prompt_hash_drift(tmp_path: Path) -> None:
    payload = json.loads(PROTOCOL.read_text())
    payload["prompts"][0]["sha256"] = "0" * 64
    invalid = write_protocol_fixture(tmp_path, payload)

    summary, _ = audit_protocol_freeze(invalid, tmp_path / "audit.json")

    assert summary.status == "invalid"
    assert "prompt SHA-256 mismatch" in "\n".join(summary.errors)
