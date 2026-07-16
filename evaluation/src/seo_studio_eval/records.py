import json
from pathlib import Path

from .schemas import RunRecord


def attempt_record_paths(run_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in run_dir.glob("*.json")
        if not path.name.endswith("-summary.json") and path.name != "run-accounting.json"
    )


def write_attempt_record(run_dir: Path, record: RunRecord) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    output_path = run_dir / f"{record.attempt_id}.json"
    with output_path.open("x", encoding="utf-8") as output:
        output.write(json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
    return output_path


def read_attempt_record(path: Path) -> RunRecord:
    return RunRecord.model_validate_json(path.read_text())
