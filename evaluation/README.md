# SEO Studio Evaluation Harness

This package is the offline-first research execution path. It does not call the product API, discover product `.env` files, or access the DGX during unit tests.

Implemented commands:

```bash
python -m seo_studio_eval preflight --config configs/pilot.toml
python -m seo_studio_eval validate --run-dir runs/<experiment-id>
python -m seo_studio_eval compatibility-smoke --config configs/pilot.toml --model-id qwen35-9b --image-id healthcare-doctor-consultation-001 --base-url http://127.0.0.1:11435 --output-dir runs/<experiment-id> --timeout-seconds 240
python -m seo_studio_eval compatibility-pilot --config configs/pilot.toml --criteria configs/compatibility-criteria.toml --base-url http://127.0.0.1:<local-tunnel-port> --output-dir runs/<pilot-block> --run-id <pilot-run-id> --system-snapshot-ref <private-snapshot-reference>
python -m seo_studio_eval normalize --run-dir runs/<block-a> --run-dir runs/<block-b> --output-dir results/normalized/<experiment-id>
python -m seo_studio_eval blind --normalized-records results/normalized/<experiment-id>/records.normalization-v1.jsonl --review-dir annotations/released/<experiment-id> --mapping-dir annotations/private/<experiment-id> --seed 20260716
python -m seo_studio_eval account --config configs/pilot.toml --run-dir runs/<block-a> --run-dir runs/<block-b> --output results/tables/<experiment-id>-run-accounting.json
python -m seo_studio_eval compatibility-report --evidence results/compatibility-20260716.json --output results/compatibility-20260716.md
```

The pilot dataset is generated from the declared catalog with:

```bash
python scripts/materialize_pilot.py --retrieved-at <ISO-8601-UTC> --force
```

The materializer requires explicit network access, retrieves only the declared Wikimedia Commons records, verifies the expected license, and writes image, attribution, context, and hash evidence. The synthetic contract fixture remains separate in `manifest-contract.jsonl`.

The preflight validates configuration structure, model declarations, dataset balance, source/license evidence, dimensions, paths, and SHA-256 hashes. Compatibility execution sends the actual image bytes but stores only their hash in the sanitized request evidence. Normalization creates a versioned derived artifact without changing raw evidence. Blinding writes reviewer material separately from its ignored private identity map and fails on detected model-name leakage. Run accounting reports missing, duplicate, unexpected, valid, and failed attempts across one or more run blocks. `annotations/templates/rubric-v1.md` defines claim labels, rating anchors, purpose rules, and disposition categories.

Live inventory, SSH tunnels, model pulls, and DGX experiments are governed by `$davneet-dgx-access`; repository commands never contain the live connection profile. Research execution has no hidden retry. `configs/compatibility-criteria.toml` freezes the compatibility and fallback rules, while compatibility reports explicitly prohibit quality ranking from the one-image smoke data.

Raw `runs/`, dataset cache files, and private reviewer mappings are ignored by Git.
