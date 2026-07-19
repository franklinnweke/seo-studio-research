# Full-study dataset human-review guide

Status: **128-item draft materialized; human item review required**

The current draft contains 128 mechanically licensed and visually screened Wikimedia Commons items. Automated and Codex-assisted preparation does not constitute the final human visual ground truth. Gate 4 remains blocked until a project author reviews every selected image individually.

If `evaluation/dataset/images/full/` is not present in a fresh checkout, first create review copies and non-executable draft evidence. This requires Wikimedia Commons network access and still does not create the final manifest:

```bash
cd evaluation
PYTHONPATH=src .venv/bin/python scripts/materialize_full.py \
  --retrieved-at <ISO-8601-UTC> \
  --draft
```

## Start the reviewer

From `evaluation/`:

```bash
python3 -m http.server 8765
```

Open:

```text
http://127.0.0.1:8765/review/full-study-dataset-review.html
```

The interface saves progress in browser local storage. Export `full-study-human-review-completed.jsonl` at the end and preserve it as a human-authored research artifact.

## Required decision for each item

1. Confirm that the frozen purpose fits the fictional placement.
2. Reject any watermark, corruption, material duplicate, unacceptable sensitive detail, or source mismatch.
3. Record atomic visible facts, one independently judgeable proposition per line.
4. Add tempting unsupported or sensitive claims to the forbidden list.
5. For informative, functional, text, and complex items, provide at least one defensible alt example. Decorative and redundant items intentionally use an empty alt example.
6. Add a concise note for ambiguity or any special adjudication boundary.

Do not copy the Commons title as a visible fact without checking the pixels. Do not infer identity, diagnosis, affiliation, price, quality, outcome, or other non-visible information.

## Validate and apply the completed review

First run a no-write validation:

```bash
PYTHONPATH=src .venv/bin/python scripts/apply_full_human_review.py \
  --review-file /path/to/full-study-human-review-completed.jsonl \
  --reviewer-role project-author \
  --reviewed-at YYYY-MM-DD
```

If all 128 items are accepted and complete, repeat with `--apply`. If any item is rejected, do not reduce the population or substitute an item informally. Record an additive replacement decision, select a new candidate from the same domain/query stratum, and repeat review for that item.

After application, materialize the final 1280px dataset, run `preflight`, and run `protocol-audit`. The final manifest must never be created from the pending draft placeholders.
