# SEO Studio Evaluation Harness

This package is the offline-first research execution path. It does not call the product API, discover product `.env` files, or access the DGX during unit tests.

Implemented commands:

```bash
python -m seo_studio_eval preflight --config configs/pilot.toml
python -m seo_studio_eval validate --run-dir runs/<experiment-id>
python -m seo_studio_eval compatibility-smoke --config configs/pilot.toml --model-id qwen35-9b --image-id healthcare-doctor-consultation-001 --base-url http://127.0.0.1:11435 --output-dir runs/<experiment-id> --timeout-seconds 240
python -m seo_studio_eval compatibility-pilot --config configs/pilot.toml --criteria configs/compatibility-criteria.toml --base-url http://127.0.0.1:<local-tunnel-port> --output-dir runs/<pilot-block> --run-id <pilot-run-id> --system-snapshot-ref <private-snapshot-reference> --max-new-attempts 10
python -m seo_studio_eval pilot-report --config configs/pilot.toml --criteria configs/compatibility-criteria.toml --run-dir runs/<pilot-block> --evidence results/<pilot-evidence>.json --output results/<pilot-report>.md --deviation-reference results/<deviation-log>.json
python -m seo_studio_eval writer-compatibility --config configs/pilot.toml --criteria configs/writer-compatibility-criteria.toml --source-run-dir runs/<complete-pilot-block> --base-url http://127.0.0.1:<local-tunnel-port> --output-dir runs/<writer-block> --run-id <writer-run-id> --system-snapshot-ref <private-snapshot-reference>
python -m seo_studio_eval writer-report --summary runs/<writer-block>/writer-summary.json --evidence results/<writer-evidence>.json --output results/<writer-report>.md
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

The preflight validates configuration structure, model declarations, dataset balance, source/license evidence, dimensions, paths, and SHA-256 hashes. Compatibility execution sends the actual image bytes but stores only their hash in the sanitized request evidence. Normalization creates a versioned derived artifact without changing raw evidence. Blinding writes reviewer material separately from its ignored private identity map and fails on detected model-name leakage. Run accounting separates analyzed outcomes from raw attempts, bounded transport recoveries, and disclosed legacy deviations while reporting missing, duplicate, unexpected, valid, and failed outcomes. `annotations/templates/rubric-v1.md` defines claim labels, rating anchors, purpose rules, and disposition categories.

Live inventory, SSH tunnels, model pulls, and DGX experiments are governed by `$davneet-dgx-access`; repository commands never contain the live connection profile. Research execution has no hidden retry. `configs/compatibility-criteria.toml` freezes the compatibility and fallback rules, while compatibility reports explicitly prohibit quality ranking from the one-image smoke data.

The compatibility pilot aborts after preserving the first transport-failure record. Resume the same append-only block only when its earlier records remain valid and incomplete; if the transport failure exposed a harness defect or invalidated the block, preserve it as an infrastructure incident and recollect under a new run ID. Never convert connection failures into model-compatibility failures.

The HTTP transport combines the socket timeout with an OS-level absolute wall-clock deadline on supported Unix main-thread execution. This prevents a dead direct or forwarded TCP socket from remaining blocked after the frozen inference window. A deadline expiry is a final `inference_timeout`; a connection reset received before the deadline remains a recoverable `transport_error` under the bounded recovery rule.

`--max-new-attempts` creates an intentional operational pause after the requested number of newly recorded measured attempts. Reinvoke the identical command and run ID to continue; completed attempt keys are verified and skipped, a new session warm-up is recorded, and the active model is unloaded at the end of the segment. The limit does not change randomized order or the expected 100-attempt matrix.

Raw `runs/`, dataset cache files, and private reviewer mappings are ignored by Git.

The completed July 16–17 compatibility block is summarized in `results/compatibility-pilot-20260717.json` and `.md`. Exactly one condition, Gemma 3 12B, met the frozen 95% gate. This is not a quality ranking: the two-eligible-challenger advancement rule is currently unsatisfied and requires a documented candidate amendment before quality screening. The threshold must not be lowered after observing the pilot.

`configs/writer-compatibility-criteria.toml` freezes the separate Qwen3.5 writer check. It deterministically chooses the lexicographically first image with schema-valid facts from every candidate, sends no pixels to the writer, labels visual facts/page context/brand context/confirmed purpose separately, disables thinking, fixes the context/output limits, allows no hidden validation retry, and requires valid purpose-aware metadata for all five source-fact conditions.

The completed writer pass is summarized in `results/writer-compatibility-20260717.json` and `.md`. The pinned Qwen3.5 writer produced valid purpose-aware metadata for all five candidate-fact inputs (5/5), with no image bytes and no hidden retries. This is compatibility evidence, not a metadata-quality comparison.
