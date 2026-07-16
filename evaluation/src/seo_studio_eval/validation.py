import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from .records import read_attempt_record


class RunValidationSummary(BaseModel):
    status: Literal["valid", "invalid"]
    records_checked: int = Field(ge=0)
    valid_records: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)


def validate_run_directory(run_dir: Path) -> tuple[RunValidationSummary, Path]:
    errors: list[str] = []
    record_paths = sorted(
        path for path in run_dir.glob("*.json") if path.name not in {"validation-summary.json", "preflight-summary.json"}
    )
    valid_records = 0
    if not record_paths:
        errors.append("No attempt records found")
    for path in record_paths:
        try:
            read_attempt_record(path)
            valid_records += 1
        except (OSError, ValueError, ValidationError) as exc:
            errors.append(f"{path.name}: {exc}")

    summary = RunValidationSummary(
        status="valid" if not errors else "invalid",
        records_checked=len(record_paths),
        valid_records=valid_records,
        errors=errors,
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    output_path = run_dir / "validation-summary.json"
    output_path.write_text(json.dumps(summary.model_dump(), indent=2, sort_keys=True) + "\n")
    return summary, output_path
