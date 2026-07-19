# SEO Studio Evaluation Harness

This package is the offline-first research execution path. It does not call the product API, discover product `.env` files, or access the DGX during unit tests.

Implemented commands:

```bash
python -m seo_studio_eval preflight --config configs/pilot.toml
python -m seo_studio_eval preflight --config configs/pilot-amendment.toml
python -m seo_studio_eval preflight --config configs/pilot-truncation-repair.toml
python -m seo_studio_eval preflight --config configs/pilot-isolated-gemma4.toml
python -m seo_studio_eval validate --run-dir runs/<experiment-id>
python -m seo_studio_eval compatibility-smoke --config configs/pilot.toml --model-id qwen35-9b --image-id healthcare-doctor-consultation-001 --base-url http://127.0.0.1:11435 --output-dir runs/<experiment-id> --timeout-seconds 240
python -m seo_studio_eval compatibility-pilot --config configs/pilot.toml --criteria configs/compatibility-criteria.toml --base-url http://127.0.0.1:<local-tunnel-port> --output-dir runs/<pilot-block> --run-id <pilot-run-id> --system-snapshot-ref <private-snapshot-reference> --max-new-attempts 10
python -m seo_studio_eval truncation-repair-plan --config configs/pilot-truncation-repair.toml --criteria configs/truncation-repair-criteria.toml --source-run-dir runs/<original-pilot> --source-run-dir runs/<candidate-amendment> --output results/<repair-plan>.json
python -m seo_studio_eval truncation-repair --config configs/pilot-truncation-repair.toml --criteria configs/truncation-repair-criteria.toml --source-run-dir runs/<original-pilot> --source-run-dir runs/<candidate-amendment> --base-url http://127.0.0.1:<local-tunnel-port> --output-dir runs/<repair-block> --run-id <repair-run-id> --system-snapshot-ref <private-snapshot-reference>
python -m seo_studio_eval truncation-repair-report --source-config configs/pilot.toml --source-config configs/pilot-amendment.toml --source-run-dir runs/<original-pilot> --source-run-dir runs/<candidate-amendment> --repair-run-dir runs/<repair-block> --criteria configs/truncation-repair-criteria.toml --evidence results/<repair-evidence>.json --output results/<repair-report>.md
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

The Qwen3.6 candidate amendment is isolated in `configs/candidate-amendment-20260717.json`, `configs/models-amendment.toml`, and `configs/pilot-amendment.toml`. It supplements rather than rewrites the original five-model matrix. The completed amendment report is `results/compatibility-amendment-20260717.json` and `.md`: dense Qwen3.6 completed 15/20 valid outcomes and Qwen3.6 MoE completed 13/20, so neither met the unchanged 95% gate. Comparative quality inspection remains prohibited.

Failure taxonomy showed that every schema-invalid outcome across the original and amendment matrices ended with Ollama `done_reason=length`; it exhausted the 384-token cap rather than demonstrating a generic JSON-schema failure. Protocol 2.2 therefore defines a system-level truncation repair without lowering the gate: exactly one explicit 768-token recovery for each frozen length-truncated source outcome, no recovery for timeouts or quality, the same prompt/schema/image/seed/temperature/thinking settings, the same 240-second deadline, and no further validation retry. `results/truncation-repair-plan-20260717.json` freezes the 15 source-linked repairs before execution. The source records remain immutable and the repaired pipeline outcome must be reported separately from one-shot compatibility.

The completed Protocol 2.2 stage is summarized in `results/truncation-repair-20260717.json` and `.md`. All 15 planned repairs were collected and validated; 6 repaired successfully and 9 remained invalid, with no transport failures. Qwen3.5 reached 19/20 pipeline validity and Gemma remained 19/20, creating the required two eligible non-baseline challengers at the unchanged 95% gate. The comparison set for quality screening is the below-gate Qwen2.5-VL 3B reference baseline plus eligible Qwen3.5 and Gemma challengers. This is not a quality ranking, and supervisor acknowledgement remains required before protocol freeze and comparative inspection.

The pre-freeze catalog correction is recorded in `configs/gemma4-candidate-amendment-20260717.json`. The same-size `gemma4:12b-it-q4_K_M` condition was selected and committed before any pull or task-output inspection. The additive pull stopped at manifest resolution with HTTP 412 because the shared Ollama 0.24.0 runtime is too old; no model layer was installed and the shared service was not upgraded. The project team subsequently authorized and installed an official Ollama 0.32.1 ARM64 runtime, separate model store, and loopback-only listener for the baseline, Qwen3.5, and Gemma 4 conditions. Sanitized runtime and digest evidence is frozen in `configs/isolated-runtime-evidence-20260717.json`; live access remains governed by `$davneet-dgx-access`. The isolated criteria explicitly fix an 8192-token context window for all three conditions while leaving the earlier default-context evidence unchanged. The stage produces exactly one 20-image block per condition—60 measured outputs total—and those same outputs become the blinded pilot quality-screening package rather than being generated twice. Historical Gemma 3 evidence remains intact and is defensible as an installed, deployment-compatible, same-scale cross-family comparator selected under the then-frozen shared Ollama 0.24.0 inventory. It must not be described as the newest Gemma generation; the pre-freeze catalog audit found and corrected that narrower recency claim before quality ranking.

The isolated one-shot matrix is complete with 60 analyzed outcomes and 62 raw records: Qwen2.5-VL 3B produced 20/20 schema-valid outputs, Qwen3.5 produced 18/20, and Gemma 4 produced 17/20. Two tunnel failures were superseded by explicitly linked bounded recoveries. Failure-metadata review—without comparative claim inspection—found four `done_reason=length` outcomes at the frozen 384-token cap (Qwen3.5: one; Gemma 4: three) and one final Qwen3.5 inference timeout, which is not repairable. `results/truncation-repair-isolated-gemma4-plan-20260718.json` freezes exactly those four Protocol 2.2 repairs before any 768-token call. These outcomes remain compatibility evidence only.
