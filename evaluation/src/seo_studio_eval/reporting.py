import json
from pathlib import Path
from typing import Any


def build_compatibility_report(evidence_path: Path, output_path: Path) -> Path:
    evidence = json.loads(evidence_path.read_text())
    if not isinstance(evidence, dict) or evidence.get("stage") != "single-image compatibility smoke":
        raise ValueError("Compatibility evidence has an unsupported stage")
    results = evidence.get("results")
    if not isinstance(results, list) or not results:
        raise ValueError("Compatibility evidence must contain results")
    rows: list[str] = []
    for result in results:
        if not isinstance(result, dict):
            raise ValueError("Compatibility result must be an object")
        model_id = _required(result, "model_id")
        digest = _required(result, "digest")
        schema_valid = result.get("schema_valid")
        wall_duration_ms = result.get("wall_duration_ms")
        if not isinstance(schema_valid, bool) or not isinstance(wall_duration_ms, (int, float)):
            raise ValueError(f"{model_id}: invalid compatibility result fields")
        rows.append(
            f"| `{model_id}` | `{digest[:12]}` | {'yes' if schema_valid else 'no'} | "
            f"{wall_duration_ms / 1000:.1f} | {int(result.get('prompt_tokens', 0))} | "
            f"{int(result.get('output_tokens', 0))} |"
        )

    limitations = evidence.get("limitations", [])
    if not isinstance(limitations, list) or not all(isinstance(item, str) for item in limitations):
        raise ValueError("Compatibility limitations must be a list of strings")
    runtime = evidence.get("runtime", {})
    request = evidence.get("request_contract", {})
    lines = [
        "# Compatibility smoke report",
        "",
        "This report establishes runtime and schema compatibility only. It must not be used to rank output quality or throughput.",
        "",
        f"- Observed: `{evidence.get('observed_at', '')}`",
        f"- Runtime: Ollama `{runtime.get('ollama_version', '')}` on `{runtime.get('architecture', '')}`",
        f"- Image: `{request.get('image_id', '')}`",
        f"- Prompt/schema: `{request.get('prompt_id', '')}` / `{request.get('structured_schema', '')}`",
        f"- Controls: temperature `{request.get('temperature')}`, seed `{request.get('seed')}`, thinking `{request.get('thinking')}`, hidden retries `{request.get('hidden_retries')}`",
        "",
        "| Model condition | Digest prefix | Schema valid | Cold wall seconds | Prompt tokens | Output tokens |",
        "|---|---|---:|---:|---:|---:|",
        *rows,
        "",
        "## Limitations",
        "",
        *[f"- {item}" for item in limitations],
        "",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))
    return output_path


def _required(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Compatibility result is missing {key}")
    return value
