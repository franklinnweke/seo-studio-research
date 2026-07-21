# Full-study dataset human-check guide

Status: **128-item draft materialized; human item check required**

The current draft contains 128 mechanically licensed and contact-sheet-screened Wikimedia Commons items. Query-stratum suggestions reduce typing, but they are not ground truth. Gate 4 remains blocked until a project author checks every suggestion against the displayed pixels.

If `evaluation/dataset/images/full/` is not present in a fresh checkout, first create check copies and non-executable draft evidence. This requires Wikimedia Commons network access and still does not create the final manifest:

```bash
cd evaluation
PYTHONPATH=src .venv/bin/python scripts/materialize_full.py \
  --retrieved-at <ISO-8601-UTC> \
  --draft
```

## Start the human-check workspace

From the repository root:

```bash
python3 -m http.server 8765 --directory evaluation
```

Open:

```text
http://127.0.0.1:8765/review/full-study-dataset-check.html
```

Do not open the HTML with a `file://` URL; the browser will not load the JSONL workbook correctly. Use the exact `127.0.0.1` address above each time because browser local storage is origin-specific. Export `full-study-human-check-completed.jsonl` periodically and at completion.

## What “correct” means

A proposed visible fact is correct only when you can point to pixels supporting the entire sentence, it contains one independently judgeable proposition, and it does not infer identity, diagnosis, location, affiliation, price, quality, intent, or outcome.

Keep a proposed forbidden claim when it is a useful boundary the evaluated model must not cross. Keep an alt example only when it matches the frozen purpose as well as the image. Decorative and redundant items intentionally require no alt example.

Reject the entire image for unacceptable private/graphic/identifying detail, watermark or corruption, unusable crop, material duplication, source/licence mismatch, or poor fit for the frozen domain or purpose.

## Click sequence for each item

1. Inspect the image without opening the source details.
2. Click **Keep** or **Reject** for every proposed visible fact.
3. Click **Keep prohibited** or **Reject** for every proposed forbidden boundary.
4. Keep or reject the proposed alt example when one is required.
5. Use **Add a correction** only when all drafts miss an important fact or need safer wording.
6. Click **Accept image** or **Reject image**.
7. Confirm the four checks individually, or click **All four checks pass** only after inspecting them.
8. Click **Save & next**. A complete item shows `Complete · saved locally`.

Open the Commons source only after recording visible facts, then verify the file and licence. Do not copy source titles or descriptions into the evidence unless the pixels independently support them. Do not infer identity, diagnosis, affiliation, price, quality, outcome, or other non-visible information.

For the first item, the pixels support the proposed healthcare-interaction and equipment statements. Identity, diagnosis/medical result, and treatment outcome remain prohibited because the pixels do not establish them. The whole-image sensitivity decision remains yours and must follow the same rule you apply to every healthcare item.

## Validate and apply the completed check

First run a no-write validation:

```bash
PYTHONPATH=src .venv/bin/python scripts/apply_full_human_check.py \
  --check-file /path/to/full-study-human-check-completed.jsonl \
  --checker-role project-author \
  --reviewed-at YYYY-MM-DD
```

If all 128 items are accepted and complete, repeat with `--apply`. If any item is rejected, do not reduce the population or substitute an item informally. Record an additive replacement decision, select a new candidate from the same domain/query stratum, and repeat the check for that item. Accepted check evidence cannot be overwritten by rerunning the importer.

After application, materialize the final 1280px dataset, run `preflight`, and run `protocol-audit`. The final manifest must never be created from the pending draft placeholders.
