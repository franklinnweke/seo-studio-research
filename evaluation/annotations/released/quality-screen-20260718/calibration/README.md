# Blinded calibration session

Use this 15-item subset before any primary quality scoring. It contains five images crossed with all three anonymous conditions and was selected deterministically from the leakage-checked 60-cell package.

1. Each reviewer reads `evaluation/annotations/templates/rubric-v1.md` and independently rates every calibration item without consulting another reviewer or the private condition map.
2. Each reviewer copies `reviewer-timing-template.json`, assigns a non-identifying reviewer alias, and records session and per-item elapsed time. Keep completed timing and annotation records in the ignored private annotation area until the retention plan is confirmed.
3. Treat `valid: false` with `output: null` as an observed system failure, not missing data. Apply the rubric's reject rule; do not regenerate, impute, or remove the item.
4. After independent scoring, compare rubric interpretation and discuss disagreements using only the image, permitted context, confirmed purpose, rubric anchors, and blinded output. Do not speculate about model identity.
5. Record any clarified anchor language before primary review begins. Do not change the generated outputs, review IDs, condition labels, or calibration population.
6. Use observed elapsed time and disagreement burden to update the reviewer-workload calculation. Do not use calibration quality differences to choose a significance-friendly final sample size.

The private map must remain closed until individual scoring, adjudication, and the predeclared analysis lock are complete.
