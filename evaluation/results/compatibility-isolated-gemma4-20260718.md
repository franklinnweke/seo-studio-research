# Candidate amendment compatibility report

This report establishes configuration compatibility only. It must not be used to rank model quality.

- Analyzed outcomes: `60` / `60`
- Raw measured records: `62`
- Superseded transport records: `2`
- Frozen validity threshold: `95%`

| Model condition (configured order) | Valid | Rate | Gate | Median wall s | P95 wall s | Failure categories |
|---|---:|---:|---:|---:|---:|---|
| `qwen25vl-3b-baseline` | 20/20 | 100% | pass | 31.3 | 86.2 | none |
| `qwen35-9b` | 18/20 | 90% | fail | 49.0 | 239.1 | inference_timeout: 1, output_truncated: 1 |
| `gemma4-12b-amendment` | 17/20 | 85% | fail | 14.8 | 35.6 | output_truncated: 3 |

## Advancement consequence

Only `qwen25vl-3b-baseline` met the gate within this amendment. The amendment did not create the predeclared advancement set. Protocol reassessment is required before quality screening; the threshold must not be lowered after seeing these outcomes.

## Planning estimates

At the pilot's summed analyzed-attempt rate, a 120-item 3-model screen is approximately `4.8` active inference hours, excluding warm-ups, transport recovery, and operational pauses. A three-condition, one-rated-repeat package contains `360` outputs.

## Limitations

- Compatibility outcomes do not measure factual quality or establish a model ranking.
- Operational segmentation and tunnel interruptions limit interpretation of latency as production throughput.
- Only public licensed images and fictional contexts traversed the temporary approved collection paths.
- The predeclared eligible-challenger requirement was not met and must not be relaxed opportunistically.
