# Full-study sample-size sensitivity v1

Status: **pre-data decision recorded**

Source contract: `evaluation/configs/full-study-protocol-v1.draft.json`

This calculation uses the approved minimum meaningful effects, two-sided alpha 0.05, 80% target power, and a 10% reserve. It does not inspect pilot or primary comparative quality effects. Its purpose is to test whether the proposed population is capable of resolving the effects the team says matter.

## RQ1: five-percentage-point hallucinated-claim difference

The claim calculation uses a two-proportion approximation, six claims per output as a planning assumption, and a cluster design effect for claims nested within images.

| Reference → comparison rate | Independent claims/condition | Images at ICC .05 | Images at ICC .10 | Images at ICC .20 |
|---|---:|---:|---:|---:|
| 10% → 5% | 435 | 100 | 120 | 160 |
| 15% → 10% | 686 | 158 | 189 | 252 |
| 20% → 15% | 906 | 208 | 250 | 333 |

The selected 128-image claim population covers the displayed 100- and 120-image low-rate scenarios, but not the 160-image high-clustering scenario or the displayed moderate-rate scenarios. The result is sensitive to the true claim count and within-image correlation, which must be reported as planning assumptions rather than estimated model effects.

## RQ2: ten-percentage-point acceptable-disposition difference

The paired binary approximation depends on the proportion of image pairs with discordant dispositions.

| Discordant-pair rate | Paired images | With 10% reserve |
|---:|---:|---:|
| 15% | 116 | 127 |
| 25% | 194 | 214 |
| 35% | 273 | 300 |

The selected 128-image controlled Qwen3.5 population reaches the favorable 127-pair scenario, but not the higher-discordance scenarios.

## RQ3: 0.5-point contextual-usefulness difference

Assuming a one-point paired standard deviation, the standardized effect is 0.5 and the planning value is 35 paired images after reserve. The selected 36-image context subset reaches this planning value.

## Recorded design decision

Before opening primary outputs, the project lead selected option 3 with targeted population increases: 128 total and RQ1/RQ2 images, plus 36 context-ablation images. The complete decision and revised workload are recorded in `evaluation/configs/full-study-sample-size-decision-20260719.json`.

The planning options considered were:

1. Increase the final and human-annotated populations and resource the added reviewer workload.
2. Retain a feasible population but approve larger minimum meaningful effects before data inspection.
3. Retain the current effects as estimation targets and explicitly describe the study as underpowered for confirmatory detection.

The approved hybrid preserves the independently defined meaningful effects as interpretation thresholds and improves precision over the provisional plan without claiming comprehensive confirmatory power. The paper must emphasize effect sizes and confidence intervals, and it must describe null findings as inconclusive whenever scientifically meaningful effects remain compatible with those intervals.

Machine-readable results are generated at `evaluation/results/full-study-sample-size-sensitivity-v1.json`.
