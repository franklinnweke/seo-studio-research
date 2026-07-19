# Full-study sample-size sensitivity v1

Status: **pre-data decision required**

Source contract: `evaluation/configs/full-study-protocol-v1.draft.json`

This calculation uses the approved minimum meaningful effects, two-sided alpha 0.05, 80% target power, and a 10% reserve. It does not inspect pilot or primary comparative quality effects. Its purpose is to test whether the proposed population is capable of resolving the effects the team says matter.

## RQ1: five-percentage-point hallucinated-claim difference

The claim calculation uses a two-proportion approximation, six claims per output as a planning assumption, and a cluster design effect for claims nested within images.

| Reference → comparison rate | Independent claims/condition | Images at ICC .05 | Images at ICC .10 | Images at ICC .20 |
|---|---:|---:|---:|---:|
| 10% → 5% | 435 | 100 | 120 | 160 |
| 15% → 10% | 686 | 158 | 189 | 252 |
| 20% → 15% | 906 | 208 | 249 | 332 |

The proposed 60-image claim population is below every displayed scenario. A 120-image population reaches only the low-rate, moderate-clustering scenario. The result is sensitive to the true claim count and within-image correlation, which must be reported as planning assumptions rather than estimated model effects.

## RQ2: ten-percentage-point acceptable-disposition difference

The paired binary approximation depends on the proportion of image pairs with discordant dispositions.

| Discordant-pair rate | Paired images | With 10% reserve |
|---:|---:|---:|
| 15% | 116 | 127 |
| 25% | 194 | 214 |
| 35% | 273 | 300 |

Even the favorable displayed case is slightly above the provisional 120-image population.

## RQ3: 0.5-point contextual-usefulness difference

Assuming a one-point paired standard deviation, the standardized effect is 0.5 and the planning value is 35 paired images after reserve. The proposed 30-image context subset is slightly below this value.

## Required design decision

Choose one option before opening primary outputs:

1. Increase the final and human-annotated populations and resource the added reviewer workload.
2. Retain a feasible population but approve larger minimum meaningful effects before data inspection.
3. Retain the current effects as estimation targets and explicitly describe the study as underpowered for confirmatory detection.

Option 1 is strongest scientifically but materially increases DGX time and claim annotation. Option 2 is defensible only if the larger effects are genuinely the smallest differences that matter, not because they make the design easier. Option 3 supports an exploratory publication but weakens confirmatory claims.

Machine-readable results are generated at `evaluation/results/full-study-sample-size-sensitivity-v1.json`.
