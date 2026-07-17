# Compatibility pilot report

This report establishes configuration compatibility only. It must not be used to rank model quality.

- Analyzed outcomes: `100` / `100`
- Raw measured records: `105`
- Superseded transport records: `4`
- Frozen validity threshold: `95%`

| Model condition (configured order) | Valid | Rate | Gate | Median wall s | P95 wall s | Failure categories |
|---|---:|---:|---:|---:|---:|---|
| `qwen25vl-3b-baseline` | 16/20 | 80% | fail | 49.4 | 137.9 | output_truncated: 4 |
| `qwen25vl-32b-compatibility-fallback` | 15/20 | 75% | fail | 180.6 | 240.3 | inference_timeout: 5 |
| `qwen35-9b` | 18/20 | 90% | fail | 62.0 | 178.4 | output_truncated: 2 |
| `gemma3-12b` | 19/20 | 95% | pass | 40.4 | 45.2 | output_truncated: 1 |
| `mistral-small31-24b` | 17/20 | 85% | fail | 159.8 | 240.2 | inference_timeout: 3 |

## Advancement consequence

Only `gemma3-12b` met the gate. The required two eligible challengers are unavailable, so a candidate amendment is required before quality screening. The threshold must not be lowered after seeing these outcomes.

## Planning estimates

At the pilot's summed analyzed-attempt rate, a 120-item 5-model screen is approximately `17.4` active inference hours, excluding warm-ups, transport recovery, and operational pauses. A three-condition, one-rated-repeat package contains `360` outputs.

## Limitations

- Compatibility outcomes do not measure factual quality or establish a model ranking.
- Operational segmentation and unstable direct connectivity limit interpretation of latency as production throughput.
- Only public licensed images and fictional contexts traversed the temporary approved collection paths.
- The predeclared two-eligible-challenger advancement requirement was not met and must not be relaxed opportunistically.
