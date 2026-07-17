# Fixed-writer compatibility report

This report establishes schema and purpose-rule compatibility only. It must not be used to rank output quality.

- Writer: `qwen35-9b` / `6488c96fa5fa`
- Deterministically selected image: `education-library-study-017`
- Valid outcomes: `5` / `5`
- Pixels sent to writer: `no`
- Hidden retries: `0`

| Source visual-facts condition | Valid | Writer wall seconds | Failure category |
|---|---:|---:|---|
| `gemma3-12b` | yes | 24.7 | none |
| `mistral-small31-24b` | yes | 25.9 | none |
| `qwen25vl-32b-compatibility-fallback` | yes | 30.2 | none |
| `qwen25vl-3b-baseline` | yes | 34.1 | none |
| `qwen35-9b` | yes | 24.3 | none |

## Limitations

- This five-call pass establishes schema and purpose-rule compatibility only.
- It does not compare metadata quality or replace the controlled architecture experiment.
- The selected image was determined by a frozen common-validity rule, not output quality inspection.
