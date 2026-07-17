# Candidate amendment compatibility report

This report establishes configuration compatibility only. It must not be used to rank model quality.

- Analyzed outcomes: `40` / `40`
- Raw measured records: `42`
- Superseded transport records: `2`
- Frozen validity threshold: `95%`

| Model condition (configured order) | Valid | Rate | Gate | Median wall s | P95 wall s | Failure categories |
|---|---:|---:|---:|---:|---:|---|
| `qwen36-27b-amendment` | 15/20 | 75% | fail | 151.7 | 240.0 | inference_timeout: 4, output_truncated: 1 |
| `qwen36-35b-a3b-amendment` | 13/20 | 65% | fail | 65.9 | 157.0 | output_truncated: 7 |

## Advancement consequence

No amendment model met the gate. Neither amendment candidate qualified, so the candidate amendment did not create the required advancement set. Protocol reassessment is required before quality screening; the threshold must not be lowered after seeing these outcomes.

## Planning estimates

At the pilot's summed analyzed-attempt rate, a 120-item 2-model screen is approximately `8.1` active inference hours, excluding warm-ups, transport recovery, and operational pauses. A three-condition, one-rated-repeat package contains `360` outputs.

## Limitations

- Compatibility outcomes do not measure factual quality or establish a model ranking.
- Operational segmentation and unstable direct connectivity limit interpretation of latency as production throughput.
- Only public licensed images and fictional contexts traversed the temporary approved collection paths.
- The predeclared two-eligible-challenger advancement requirement was not met and must not be relaxed opportunistically.
