# SEO Studio full-study protocol freeze v1

Status: **draft; full-study execution prohibited**

Protocol ID: `seo-studio-full-study-v1`

Machine-readable contract: `evaluation/configs/full-study-protocol-v1.draft.json`

Created: July 19, 2026

This is the Gate 4 operational protocol derived from the canonical master architecture. It converts completed pilot evidence into an exact proposed full-study design. Until every blocker in `protocol-audit` is cleared, this document is a draft and must not be cited as a frozen protocol.

## 1. Evidence boundary and advancement decision

The licensed 20-image pilot, its 60-cell blinded package, and all calibration items are excluded from primary inference. They remain compatibility, configuration, reviewer-feasibility, and workload evidence. They may appear in the paper only as pilot results with that limitation.

The model comparison is hierarchical:

1. The completed compatibility stage reports the five original deployed-stack candidates and the prospectively recorded amendments.
2. The unchanged 95% pipeline-validity rule advanced three unique conditions to primary quality evaluation:
   - Qwen2.5-VL 3B as the below-gate reference required by the baseline rule;
   - Qwen3.5 9B as an eligible challenger and fixed writer;
   - Gemma 3 12B as an eligible deployed-stack-compatible legacy-generation challenger.
3. Gemma 4 and Qwen3.6 conditions remain disclosed prospective exclusions. They do not enter the primary quality population.

This design therefore does not claim that five models received full human quality evaluation. It claims a five-condition compatibility screen followed by a three-condition prospectively advanced quality study.

## 2. Research questions and single primary outcomes

| RQ | Frozen question wording proposed for approval | One primary outcome |
|---|---|---|
| RQ1 | After the five-condition compatibility screen, how accurately do the three prospectively advanced self-hosted multimodal conditions extract grounded visual facts? | Hallucinated-claim rate on every claim in the complete 60-image primary population |
| RQ2 | Does Qwen3.5 decomposition improve metadata acceptability relative to direct Qwen3.5 generation under otherwise matched controls? | Accept unchanged/minor edit versus major edit/reject disposition rate |
| RQ3 | How does permitted brand, page, and confirmed-purpose context affect metadata usefulness? | Contextual-usefulness rating |
| RQ4 | Which eligible configuration provides the most defensible deployment trade-off? | Predeclared quality-reliability-latency-operational-cost Pareto position |

Supported-claim precision is a key RQ1 secondary outcome and remains part of the selection rule. Salient coverage, schema validity, failure rate, redundancy, brand alignment, safety, concision, latency, throughput, token counts, package size, memory, and cost components are secondary outcomes.

Approved minimum scientifically meaningful effects, defined without inspecting primary quality results, are:

- RQ1: 5 percentage points absolute hallucinated-claim rate;
- RQ2: 10 percentage points absolute acceptable-disposition rate;
- RQ3: 0.5 points on the five-point contextual-usefulness scale.

The team and supervisor approved these values on July 19, 2026. The resulting pre-data sensitivity calculation is recorded in `docs/publication/sample-size-sensitivity-v1.md`. It shows that the provisional population is not adequate under every reasonable planning scenario, so final sample size remains blocked on an explicit design choice rather than being inferred from approval alone.

## 3. Dataset design

- Pilot/calibration images: excluded from primary inference.
- Final split: new `full` images only.
- Provisional final population: 120 licensed images.
- Domain target before sample-size adjustment: 30 each for healthcare, retail/product, hospitality/local service, and education/professional service.
- Complete RQ1 claim-level population: a deterministic stratified 60-image subset, initially 15 per domain.
- Context-ablation population: a deterministic stratified 30-image subset nested inside the 60-image population.
- Primary images may not be used for prompt tuning or replacement based on observed outputs.
- Every manifest row must retain image, licence, context, brand, purpose, visible-fact, forbidden-claim, preprocessing, and SHA-256 evidence.

The final population size and domain counts remain unset until the meaningful-effect simulation, reviewer burden, DGX runtime, storage, and licence review are approved. The future manifest path is `evaluation/dataset/manifest-full-v1.jsonl`.

## 4. Conditions

### 4.1 RQ1 vision facts

Each of the three conditions receives the same preprocessed image, `vision-facts-v1`, and `visual-facts.schema.json`:

- `facts-qwen25vl-3b`;
- `facts-qwen35-9b`;
- `facts-gemma3-12b`.

Every claim from repeat 1 for all three conditions on all 60 primary images is annotated. Failures remain in denominators under the predeclared failure policy.

### 4.2 RQ2 controlled architecture comparison

- Direct: `direct-qwen35-full-context` receives the image and full permitted context.
- Decomposed: `decomposed-qwen35-to-qwen35` generates facts from the image, then metadata from facts and the same permitted context.

Both conditions use Qwen3.5, the same metadata schema, context window, temperature, thinking mode, output limit, preprocessing, repeat rule, and timeout. This is the only comparison that supports a causal decomposition claim.

The other decomposed conditions support a production-system decision, not a pure architecture claim:

- `decomposed-qwen25vl-3b-to-qwen35`;
- `decomposed-gemma3-12b-to-qwen35`.

### 4.3 RQ3 context ablation

After the winning vision condition is selected by the frozen rule, reuse its already-recorded facts on the predeclared 30-image subset:

| ID | Writer inputs |
|---|---|
| `context-selected-vision-visual-only` | Visual facts only |
| `context-selected-vision-brand-only` | Visual facts and brand context |
| `context-selected-vision-page-purpose` | Visual facts, page context, and confirmed purpose |
| `context-selected-vision-brand-page-purpose` | Visual facts, brand context, page context, and confirmed purpose |

The combined brand/page/purpose condition is the predeclared product candidate. The primary RQ3 contrast is combined context versus visual facts only. Other contrasts are Holm-corrected secondary comparisons.

## 5. Generation controls

| Control | Draft value |
|---|---|
| Repeats | 3 measured repeats |
| Human-rated repeat | Repeat 1 only |
| Temperature | 0 |
| Thinking | Disabled |
| Context window | 8192 tokens |
| Visual-facts output limit | 768 tokens |
| Metadata output limit | 420 tokens |
| Attempt timeout | 240 seconds |
| Keep alive | 10 minutes within a model block |
| Hidden retries | 0 |
| Randomization seed | 1721844270, deterministically derived from SHA-256(`seo-studio-full-study-v1`) |

Prompt candidates are hash-pinned in the machine-readable contract. A read-only `$davneet-dgx-access` check on July 19, 2026 reverified Ollama 0.24.0 and exact full digests for all three models; the sanitized evidence is `evaluation/configs/full-study-runtime-reverification-20260719.json`. No model was loaded and no server mutation occurred.

## 6. Provisional run accounting

For 120 final images, three models, and three repeats:

| Stage | Formula | Calls |
|---|---:|---:|
| Vision facts | 120 × 3 × 3 | 1,080 |
| Fixed-writer metadata | 120 × 3 × 3 | 1,080 |
| Direct Qwen3.5 metadata | 120 × 3 | 360 |
| Incremental context calls | 30 × 3 non-duplicate contexts × 3 | 270 |
| Total unique model calls | Sum | **2,790** |

The combined-context condition for the selected vision model already exists in the fixed-writer stage and is not counted twice.

Human repeat-1 material contains:

- 180 RQ1 visual-fact outputs;
- 180 decomposed metadata outputs;
- 60 direct metadata outputs;
- 90 additional context outputs;
- 510 unique review items total.

Reviewer allocation proposal:

- both reviewers annotate all 180 primary RQ1 fact outputs;
- the 330 unique metadata outputs use balanced assignment plus 20% shared overlap;
- total assignments: 756;
- projected load: 378 items or 756 active minutes per reviewer at the calibrated 120 seconds per item;
- adjudication, breaks, and administration are additional.

The proposed reviewer burden was approved on July 19, 2026. However, the approved five-point RQ1 sensitivity target may require increasing the claim population, which would require a new workload calculation and additive approval. If burden is reduced, the complete double-coded RQ1 population is protected first; reductions must use a predeclared balanced rule for secondary metadata ratings.

## 7. Statistical plan

- RQ1 primary analysis: image-clustered comparison of hallucinated-claim rate, with cluster-bootstrap confidence intervals and three planned system contrasts corrected by Holm. A logistic mixed-effects model with image as a random effect is a sensitivity analysis.
- RQ2 primary analysis: binary acceptable disposition using a logistic mixed-effects model with condition fixed and image/reviewer random effects; the controlled direct-versus-decomposed contrast is primary.
- RQ3 primary analysis: ordinal mixed-effects model for contextual usefulness with condition fixed and image/reviewer random effects; combined context versus facts only is primary.
- RQ4: Pareto analysis using the frozen quality, reliability, warm-latency, and operational-cost dimensions; ties break by failure rate and then median warm latency.
- Capstone fallback: item aggregation, Friedman tests for repeated ordinal conditions, Holm-corrected paired Wilcoxon contrasts, and image-level bootstrap confidence intervals.
- Effect sizes and uncertainty are reported regardless of statistical significance.
- System failures remain in accounting and sensitivity analyses; they are never regenerated for quality.
- Multiplicity families and the minimum meaningful effects must be approved before primary output inspection.

## 8. Blinding and annotation

- Two calibrated reviewers use rubric v1.1; R3 adjudicates disagreements.
- Reviewers see no model, condition, latency, run-order, or author identity.
- The private map remains closed until annotations and the analysis input table are hash-frozen.
- Repeat 1 is the only human-rated repeat.
- Every claim in the complete RQ1 population is labeled supported, unsupported, contradicted, or not verifiable from permitted evidence.
- Individual annotations, timing, adjudication, and agreement remain separate artifacts.

## 9. Freeze blockers

The July 19 approval relay closes supervisor record, authorship/CRediT, publication route, ethics, data/network policy, reviewer burden, meaningful effects, and full-study authorization subject to technical freeze. Read-only inspection also verified the dedicated project workspace, available storage, and the supported telemetry scope. `nvidia-smi` is unavailable, so complete GPU-VRAM and measured-energy claims are prohibited. The machine audit must continue returning `draft_blocked` until all remaining technical requirements are complete:

- choose the final sample-size option and approve its revised workload;
- set final item and domain counts;
- materialize and validate the full-study dataset manifest;
- resolve the failed private listener-reachability check through an institution-approved mitigation, then verify it without publishing connection details;
- change protocol status only after the resulting audit has no blockers.

Run the offline audit with:

```bash
PYTHONPATH=src .venv/bin/python -m seo_studio_eval protocol-audit \
  --protocol configs/full-study-protocol-v1.draft.json \
  --output results/full-study-protocol-audit-v1.json
```

The command must return non-zero while blockers remain. It must return `freeze_ready` before the draft is renamed, committed on a clean tree, tagged, and used for full-study collection.

## 10. Deviation rule

After freeze, no model, prompt, schema, threshold, dataset member, repeat, reviewer rule, retry rule, statistic, or condition may be silently changed. Every necessary change requires an additive dated amendment that preserves the frozen contract and affected evidence.
