# Human calibration analysis results

Status: **recalibration_required**.

The two independent reviewer files and adjudicated file each contain the complete 15-item blinded calibration population. This report does not open or use the private condition map.

## Population

- Calibration items: 15
- Valid metadata outputs: 12
- Explicit system failures: 3
- Claims segmented by R1/R2/adjudicator: 64/103/79

## Rating agreement on valid outputs

| Dimension | n | Exact | Linear weighted kappa | Mean absolute difference |
|---|---:|---:|---:|---:|
| Factual Grounding | 12 | 66.7% | 0.610 | 0.417 |
| Salient Coverage | 12 | 50.0% | 0.238 | 0.667 |
| Contextual Usefulness | 12 | 66.7% | 0.500 | 0.333 |
| Redundancy Control | 12 | 50.0% | 0.067 | 1.167 |
| Purpose Appropriateness | 12 | 50.0% | 0.586 | 0.500 |
| Brand Alignment | 12 | 91.7% | 0.000 | 0.083 |
| Safety | 12 | 100.0% | undefined | 0.000 |
| Concision Fluency | 12 | 100.0% | 1.000 | 0.000 |

## Disposition agreement

- All 15 items: 53.3% exact; κw=0.615.
- Twelve valid outputs only: 41.7% exact; κw=0.263.
- The all-item value is raised by deterministic agreement on the three null-output rejects; use the valid-output result when judging quality-rubric feasibility.

## Claim-label feasibility

Claim-label agreement is not estimable from this pass because R1 and R2 did not label the same claim units. Rubric v1.1 therefore freezes atomic, deduplicated claim segmentation and requires a common blinded claim inventory before label-agreement analysis.

## Reviewer time

| Reviewer | Session min | Median sec/item | IQR sec/item | Projected active min for 60 | Assigned order verified |
|---|---:|---:|---:|---:|---|
| R1 | 27.75 | 120.0 | 110.0–130.0 | 120.0 | False |
| R2 | 29.92 | 125.0 | 97.5–130.0 | 125.0 | True |

## Blocking findings

- Independent reviewers produced non-isomorphic claim inventories; claim-label agreement is not estimable until both label the same frozen claim units.
- Agreement below the provisional 0.60 feasibility marker: salient_coverage_score, contextual_usefulness_score, redundancy_control_score, purpose_appropriateness_score, disposition_valid_outputs

## Cautions

- Chronological timing order does not match the stored assigned-order file for: R1
- The 0.60 feasibility marker was not numerically frozen before these ratings and is descriptive, not a post-hoc pass/fail rule.
- Kappa can be unstable or undefined under near-perfect prevalence; report exact agreement and score distributions alongside it.
- Adjudication duration was not supplied, so workload projections exclude reconciliation overhead.

## Decision

Human timing feasibility is established, and the completed individual/adjudicated records are valid calibration evidence. Primary annotation should not begin yet. First, have R1 and R2 independently label the same adjudicated claim inventory under rubric v1.1, verify claim-label agreement, and resolve the low salient-coverage, redundancy, and valid-output disposition agreement. Preserve this first pass unchanged.
