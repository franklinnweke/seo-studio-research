# Protocol 2.2 truncation-repair report

This report evaluates explicit system-level truncation handling. It does not rank factual quality, and it preserves the one-shot results separately.

- Repairs: `4` / `4`
- Valid repairs: `2`
- Hidden, quality, or timeout retries: `0`
- Pipeline-validity gate: `95%`

| Model condition | One-shot | Repairs valid | Pipeline valid | Gate | Remaining failures |
|---|---:|---:|---:|---:|---|
| `qwen25vl-3b-baseline` | 20/20 | 0/0 | 20/20 | pass | none |
| `qwen35-9b` | 18/20 | 1/1 | 19/20 | pass | inference_timeout: 1 |
| `gemma4-12b-amendment` | 17/20 | 1/3 | 18/20 | fail | output_truncated: 2 |

## Advancement consequence

Eligible non-baseline challengers: `qwen35-9b`. The required count is not met, so no quality-screening set is formed and the protocol requires reassessment before comparative inspection.

## Limitations

- Pipeline validity is a system-level outcome and must not be presented as one-shot model validity.
- The repair policy was predeclared before isolated collection; the exact repair population was frozen after one-shot failure classification and before any repair call.
- Compatibility outcomes do not measure factual quality or rank the eligible challengers.
- Reviewer-time calibration and supervisor acknowledgement remain required before final protocol freeze.
