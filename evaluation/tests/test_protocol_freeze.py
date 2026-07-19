import json
from pathlib import Path
import shutil

from seo_studio_eval.protocol_freeze import audit_protocol_freeze


EVALUATION_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = EVALUATION_ROOT / "configs" / "full-study-protocol-v1.draft.json"


def write_protocol_fixture(tmp_path: Path, payload: dict) -> Path:
    root = tmp_path / "evaluation"
    (root / "configs").mkdir(parents=True)
    shutil.copytree(EVALUATION_ROOT / "prompts", root / "prompts")
    protocol = root / "configs" / "protocol.json"
    protocol.write_text(json.dumps(payload))
    return protocol


def test_current_protocol_draft_is_structurally_valid_but_blocked(tmp_path: Path) -> None:
    summary, output_path = audit_protocol_freeze(PROTOCOL, tmp_path / "audit.json")

    assert summary.status == "draft_blocked"
    assert summary.errors == []
    assert summary.verified_prompt_hashes == 3
    assert "final dataset size is not set" in summary.blockers
    assert "listener security verification is pending" in summary.blockers
    assert output_path.is_file()


def test_protocol_audit_rejects_inconsistent_run_accounting(tmp_path: Path) -> None:
    payload = json.loads(PROTOCOL.read_text())
    payload["run_accounting"]["total_model_calls"] += 1
    invalid = write_protocol_fixture(tmp_path, payload)

    summary, _ = audit_protocol_freeze(invalid, tmp_path / "audit.json")

    assert summary.status == "invalid"
    assert "run accounting total_model_calls" in "\n".join(summary.errors)


def test_protocol_audit_rejects_prompt_hash_drift(tmp_path: Path) -> None:
    payload = json.loads(PROTOCOL.read_text())
    payload["prompts"][0]["sha256"] = "0" * 64
    invalid = write_protocol_fixture(tmp_path, payload)

    summary, _ = audit_protocol_freeze(invalid, tmp_path / "audit.json")

    assert summary.status == "invalid"
    assert "prompt SHA-256 mismatch" in "\n".join(summary.errors)
