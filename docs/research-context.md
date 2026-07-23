# SEO Studio compact research context

Last verified: July 23, 2026

Master-plan version: 2.3

Public repository: `https://github.com/franklinnweke/seo-studio-research`

Default release branch: `main`; source development lineage: `codex/research-context-aware-metadata`

Current gate: Gate 3 complete; the Gate 4 dataset, deterministic execution plan, checkpoint controls, and separate backup are ready, while protocol freeze remains blocked by listener-security verification and the deliberate draft-to-frozen transition

## Project in one paragraph

SEO Studio is a team-built Next.js and FastAPI image-optimization application with a self-hosted Ollama/DGX inference path. Franklin is leading the publication-oriented research extension: a controlled, reproducible evaluation of self-hosted multimodal pipelines for grounded, context-aware web image metadata. The paper evaluates metadata generation only. AI crop targeting remains a capstone feature and possible future study, not a primary paper outcome.

## Canonical decisions

- The research question is not simply which model writes the nicest caption. It evaluates grounded visual facts, purpose-aware metadata, unsupported claims, reliability, latency, and deployment trade-offs.
- Page context and human-confirmed image purpose are first-class inputs. Brand context may guide terminology but cannot prove visible content.
- Decorative and redundant placements require empty-alt support; functional images require action-oriented alt text.
- The product path and evaluation harness remain separate. Experiments do not run through browser clicks or mutable product state.
- Qwen3.5 9B is the fixed writer and the controlled direct-generation baseline.
- The deployed-stack screening set is Qwen2.5-VL 3B as the reference, Qwen3.5 9B as an eligible challenger/writer, and Gemma 3 12B as an eligible deployed-stack-compatible legacy-generation challenger.
- Gemma 4 was prospectively tested on an isolated newer runtime, failed the unchanged pipeline-validity gate at 18/20, and is reported as a current-generation exclusion. Gemma 3 must not be described as current, newest, or globally best.
- Only the same-model Qwen3.5 direct-versus-decomposed comparison supports a causal architecture claim. The selected-vision-model-plus-writer comparison is a production-system comparison.
- Human raters score one predeclared repeat. Other repeats measure stability and performance and are never searched for a best-looking output.
- No model-quality winner has been selected.

## Completed evidence

- Licensed 20-image pilot with hashes, licences, fictional contexts, brand profiles, purposes, reference facts, and forbidden claims.
- Five-condition deployed-stack compatibility screen and fixed Qwen3.5 writer compatibility check.
- Separate Qwen3.6 amendment under the unchanged 95% eligibility gate.
- Source-linked Protocol 2.2 truncation repairs with immutable original attempts.
- Separate isolated Gemma 4 amendment and repair stage without changing the supervisor's shared runtime or model store.
- Fixed-writer matrix: 60 balanced source cells, 46 schema-valid metadata outputs, and 14 explicit failures after upstream and writer failures are retained.
- Identity-safe three-condition blinded package with the private map kept outside Git.
- Human-check calibration: 15 blinded items, including 12 valid outputs and 3 explicit system failures.
- Final rubric-v1.1 recalibration: identical 76-item human-check inventories for R1, R2, and adjudication; 98.7% exact human-check label agreement; nominal Cohen's kappa 0.923; 91.7% exact valid-output disposition agreement; linear-weighted kappa 0.860; median 120 seconds per item for each reviewer.
- Analysis version 2 distinguishes nominal human-check label kappa from linear-weighted ordinal kappa and returns safe invalid/non-isomorphic reports.
- Working article scaffold at `docs/publication/seo-studio-manuscript.html`, with primary results explicitly pending.
- Structurally validated Gate 4 draft at `docs/publication/protocol-freeze-v1.md` with a machine-readable contract and blocker-reporting audit command. It is not frozen and does not authorize execution.
- All governance approvals were relayed on July 19, 2026 and preserved in a sanitized public record. Exact model digests and Ollama 0.24.0 were reverified read-only through `$davneet-dgx-access`; no mutation occurred.
- The pre-data sample-size sensitivity found that the original 60-image RQ1 subset could not support the approved five-point target under the displayed scenarios. Before primary output inspection, the project lead selected a practical estimation-first design: 128 licensed images balanced 32 per domain, all 128 in RQ1 and the controlled Qwen3.5 comparison, 64 in the other production metadata comparisons, and 36 in the context ablation.
- The approved design entails 3,012 planned stage cells and 876 unique human-check items. With three independently calibrated reviewers, 25% RQ1 overlap and 20% metadata overlap produce 1,071 assignments: 357 assignments or 714 active minutes per reviewer, excluding adjudication, breaks, and administration. Invalid upstream facts suppress the corresponding writer request while retaining an explicit failed downstream cell.
- The final publication dataset is materialized at `evaluation/dataset/manifest-full-v1.jsonl`: 128 unique image IDs and 128 unique image hashes, exact 32-per-domain balance, 128 RQ1/controlled-Qwen3.5 items, 64 production-metadata items, and 36 nested context-ablation items. Every row contains accepted project-author human-check evidence, fresh 1280px Commons-derived evidence, verified licence/context/brand hashes, and no pending placeholders.
- The project author manually completed all substantive decisions for all 128 items. The final export has 128 unique, accepted, structurally complete records and passes the no-write importer. Agentic help generated only the `human_notes` completion stamp; those notes are non-substantive, did not influence the decisions, and are excluded from analysis. This provenance is recorded in `evaluation/configs/full-study-human-check-provenance-20260722.json`.
- A context-isolated Codex agent performed a deterministic 24-cell internal diagnostic without the completed export, human decisions/notes, source descriptions, or prior conclusions. It agreed on 16/24 whole-image decisions, 35/48 visible-fact proposals, 72/72 prohibited boundaries, and 15/16 alt examples. The diagnostic is not calibrated-human evidence and must not enter the paper. It identifies eight whole-image disagreements plus two additional proposal-only items for a targeted project-author second look before the export is applied.
- The project author completed that targeted second look. All eight whole-image disagreements were manually changed to rejected, while both proposal-only items remained accepted with corrected fact/alt decisions. The rechecked export contains 120 accepted and eight rejected items with no pending records. The importer correctly refuses to apply it until one additive human-accepted replacement is supplied from each matching domain/query/purpose stratum. The diagnostic did not automatically change any label and remains excluded from the paper.
- Eight additive same-stratum replacements were independently human-checked and reconciled without overwriting the rejected evidence. The guarded reconciler rejects duplicate catalog IDs, metadata drift, incomplete decisions, target/stratum mismatch, and frozen-assignment drift. Two duplicate-candidate attempts remain diagnostic history; the final eight replacements are unique and inherit the rejected rows' analysis populations. The final 128-row human-check artifact is `evaluation/dataset/full-study-human-check-final-20260723.jsonl`, with reconciliation evidence at `evaluation/configs/full-study-replacement-reconciliation-20260723.json`.
- Product and evaluation CI workflows now enforce backend tests, OpenAPI drift, frontend lint/build, evaluation tests, JSON-schema drift, and licensed-pilot preflight. Ordinary GitHub runners never access the DGX or run model experiments.
- The deterministic plan at `evaluation/configs/full-study-execution-plan-v1.jsonl` contains exactly 3,012 cells: 1,536 primary-generation, 1,152 decomposed-writer, and 324 deferred context-ablation cells. It regenerates byte-for-byte from seed `1721844270`, yields exactly 876 repeat-1 human-review items, and keeps context-model selection unresolved until the frozen selection record exists.
- The full-study collector is phase-aware, append-only, resumable, plan-bound, digest-checked, storage-guarded, and prohibited from running against a draft protocol. One recorded transport recovery is permitted; timeout, schema, safety, and quality failures are final. Preserved pilot medians support a 34-hour planning estimate and 40-hour reservation, with at least 5 GiB free storage required.
- The DGX project workspace now provides the separately verified `supervisor-backup-01` destination. A sanitized artifact completed matching upload, remote, and round-trip SHA-256 checks; the destination is project-owned, permission-restricted, and had 268 GiB available. The private path remains outside Git.

The first non-common-inventory calibration remains preserved as diagnostic history. The final 76-item human-check recalibration is the authoritative feasibility result. Calibration evidence is not model-quality evidence.

Terminology rule for all future code comments, reports, documentation, and manuscript prose: call the manual reviewer action a **human check** and its agreement result **human-check label agreement**. Reserve **claim** only for an atomic proposition produced by a model and evaluated during grounding analysis. Do not use “human claim,” “human-check claim,” or similar mixed wording. Legacy schema keys and immutable evidence identifiers may retain `claim` where changing them would break reproducibility or data compatibility.

## Verification snapshot

Verified locally on July 23, 2026:

- evaluation suite: 71 tests passed;
- backend suite: 96 tests passed;
- frontend ESLint and production build: passed;
- checked-in OpenAPI contract: matches the generated FastAPI schema;
- deployed-stack and isolated-amendment preflights: ready on all 20 licensed pilot items;
- final calibration JSON and Markdown: regenerate byte-for-byte from the accepted inputs;
- initial human-check export: 128 rows, 128 unique IDs, 128 accepted, zero pending/rejected, SHA-256 `70db7af4b81dde1cd2fe40438b015f4757570f4b15cb118f85b5090518b269c1`; preserved as pre-reconciliation evidence;
- rechecked human-check export: 128 rows, 128 unique IDs, 120 accepted, eight rejected, zero pending, SHA-256 `d080622a657ee8182b096b8e104856394e0b0c912817a282234461ce2406ecf5`; the importer refusal is the expected population-preservation control;
- human-check provenance: substantive decisions manual; agent-assisted notes limited to mechanical completion confirmation and excluded from substantive analysis;
- blind 24-cell diagnostic: preserved as internal quality control only, with no automatic changes to human labels;
- final human-check artifact: 128 rows, 128 accepted, 128 unique IDs, SHA-256 `4a59df585780a98ec24f7e5c9335a803be19ef9774ddd8e1d4b844c60f5e4f29`;
- final manifest: 128 rows, 128 unique IDs, 128 unique image hashes, exact 32-per-domain balance, SHA-256 `1eb4842442fafb80642d43bdc74252d5cfdfbf75bdcf52a476975ca921f87e56`;
- full-study preflight: `ready`, 128 items checked, three selected models checked, zero errors and zero warnings;
- execution-plan validation: `valid`, 3,012 cells checked, zero errors, SHA-256 `87daaa61f17d59a364b3632e9c3d205372bf878567be9afb82a5a3cddb30eccc`;
- Gate 4 draft audit: structurally valid with three verified prompt hashes and zero errors; only `protocol status is draft` and `listener security verification is pending` remain;
- Markdown index and handoff links: no broken local targets;
- `git diff --check`: clean.
- required `$davneet-dgx-access` status check: key authentication and expected host succeeded; shared Ollama 0.24.0 was active; the three frozen study packages remained installed; no model was loaded; the all-interfaces version endpoint was externally reachable; the security blocker remains; no DGX mutation occurred. Sanitized evidence is in `evaluation/configs/full-study-listener-reverification-20260723.json`.

The deployed-stack preflight still warns that the five legacy screening model identities are not protocol-frozen. This is expected for the preserved pilot configuration and must be resolved for whichever conditions enter the frozen full study.

## Current research boundary

Technical calibration has passed; the review protocol is feasible; and the final dataset, deterministic plan, and checkpoint controls are ready. Full-study execution remains prohibited until the protocol audit reports `freeze_ready`.

Outstanding technical freeze work:

- resolve the failed private listener-reachability check through an approved mitigation; the dedicated workspace and limited non-GPU telemetry path are verified;
- deliberately change the protocol from draft to frozen only after listener-security evidence is recorded, then regenerate the audit and require `freeze_ready`.

The Gate 4 draft resolves the design hierarchy: five original deployed-stack conditions plus amendments are reported for compatibility, while Qwen2.5-VL 3B, Qwen3.5 9B, and Gemma 3 12B enter the primary quality comparison. RQ1 has one primary outcome—hallucinated-claim rate—with supported-claim precision retained as the key secondary outcome. The study is estimation-first: report effect sizes and uncertainty, and do not reinterpret an underpowered null as evidence of equivalence.

## Safety, privacy, and ownership

- The DGX belongs to the project supervisor/program coordinator. The team is authorized to use it for the project but must never delete, overwrite, relocate, or repurpose the owner's files or shared resources.
- Invoke `$davneet-dgx-access` before every live DGX check or command. Its private connection profile is authoritative and must not be copied into repository documentation.
- Do not expose Ollama unauthenticated to the public internet.
- Keep credentials, live addresses, key paths, raw run directories, reviewer identities, the condition map, and private supervisor communications out of Git.
- Use only licensed/public research images, fictional contexts, and approved project data until the institutional data boundary is confirmed.

## Repository and evidence hygiene

- Preserve the compatibility, amendment, repair, writer, normalized, blinded, calibration, and adjudication artifacts. Do not rerun completed cells unless a formally recorded protocol amendment requires it.
- Never lower the eligibility gate after observing results.
- Never treat compatibility rates as quality rankings.
- Never open the private condition map during blinded annotation or quality adjudication.
- Never type final paper numbers by hand when they can be generated from evidence.
- Preserve unrelated team work, including the upload-flow branch and PR #33.

## Compact handoff for a new chat or agent

1. Read `docs/README.md`, this file, and `docs/research-next-steps.md`.
2. Read only the master-plan sections relevant to the current gate.
3. Inspect `git status`, the active branch, recent commits, and existing uncommitted work.
4. Treat calibration as final at 76 human-check items, 98.7% exact agreement, and Cohen's kappa 0.923.
5. Do not name a winning model or infer primary quality results.
6. Treat the final 128 accepted items, preserved eight rejections, eight additive same-stratum replacements, exact 32-per-domain balance, and frozen 128/64/36 populations as final dataset evidence. Do not rematerialize or substitute an image without an additive protocol amendment, and do not run the full study until Gate 4 is explicitly frozen.
7. For any DGX action, invoke `$davneet-dgx-access` and preserve the no-deletion boundary.
