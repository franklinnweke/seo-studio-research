# Compatibility smoke report

This report establishes runtime and schema compatibility only. It must not be used to rank output quality or throughput.

- Observed: `2026-07-16T16:35:00Z`
- Runtime: Ollama `0.24.0` on `aarch64`
- Image: `healthcare-doctor-consultation-001`
- Prompt/schema: `vision-facts-v1` / `visual-facts.schema.json`
- Controls: temperature `0`, seed `20260716`, thinking `False`, hidden retries `0`

| Model condition | Digest prefix | Schema valid | Cold wall seconds | Prompt tokens | Output tokens |
|---|---|---:|---:|---:|---:|
| `qwen25vl-3b-baseline` | `fb90415cde1e` | yes | 47.0 | 1435 | 139 |
| `qwen25vl-32b-compatibility-fallback` | `3edc3a52fe98` | yes | 175.9 | 1435 | 118 |
| `qwen35-9b` | `6488c96fa5fa` | yes | 59.5 | 1128 | 132 |
| `gemma3-12b` | `f4031aab637d` | yes | 37.8 | 303 | 64 |
| `mistral-small31-24b` | `b9aaf0c2586a` | yes | 173.9 | 1802 | 238 |

## Limitations

- These are cold single-image compatibility observations, not quality or throughput estimates.
- The five-condition 20-image compatibility pilot remains to be executed.
- The MiniCPM preferred candidate could not be installed on the current shared Ollama runtime and was replaced under the predeclared compatibility rule.
