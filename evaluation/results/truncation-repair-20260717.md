# Protocol 2.2 truncation-repair report

This report evaluates explicit system-level truncation handling. It does not rank factual quality, and it preserves the one-shot results separately.

- Repairs: `15` / `15`
- Valid repairs: `6`
- Hidden, quality, or timeout retries: `0`
- Pipeline-validity gate: `95%`

| Model condition | One-shot | Repairs valid | Pipeline valid | Gate | Remaining failures |
|---|---:|---:|---:|---:|---|
| `qwen25vl-3b-baseline` | 16/20 | 0/4 | 16/20 | fail | output_truncated: 4 |
| `qwen25vl-32b-compatibility-fallback` | 15/20 | 0/0 | 15/20 | fail | inference_timeout: 5 |
| `qwen35-9b` | 18/20 | 1/2 | 19/20 | pass | output_truncated: 1 |
| `gemma3-12b` | 19/20 | 0/1 | 19/20 | pass | output_truncated: 1 |
| `mistral-small31-24b` | 17/20 | 0/0 | 17/20 | fail | inference_timeout: 3 |
| `qwen36-27b-amendment` | 15/20 | 0/1 | 15/20 | fail | inference_timeout: 5 |
| `qwen36-35b-a3b-amendment` | 13/20 | 5/7 | 18/20 | fail | output_truncated: 2 |

## Advancement consequence

Eligible non-baseline challengers: `qwen35-9b, gemma3-12b`. The required count is met. The compatibility-screening set is `qwen25vl-3b-baseline, qwen35-9b, gemma3-12b`: the baseline reference plus the two eligible challengers. This set may enter blinded quality screening only after supervisor acknowledgement; no quality winner has been selected.

## Limitations

- Pipeline validity is a system-level outcome and must not be presented as one-shot model validity.
- The repair policy was introduced after pilot failure-taxonomy review and before final protocol freeze; both stages must be disclosed.
- Compatibility outcomes do not measure factual quality or rank the eligible challengers.
- Reviewer-time calibration and supervisor acknowledgement remain required before final protocol freeze.
