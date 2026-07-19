# SEO Studio compact research context

Last verified: July 19, 2026

Master-plan version: 2.3

Public repository: `https://github.com/franklinnweke/seo-studio-research`

Default release branch: `main`; source development lineage: `codex/research-context-aware-metadata`

Current gate: technical Gate 3 complete; administrative Gate 3 closure and Gate 4 protocol freeze pending

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
- Human calibration: 15 blinded items, including 12 valid outputs and 3 explicit system failures.
- Final rubric-v1.1 recalibration: identical 76-claim inventories for R1, R2, and adjudication; 98.7% exact claim-label agreement; nominal Cohen's kappa 0.923; 91.7% exact valid-output disposition agreement; linear-weighted kappa 0.860; median 120 seconds per item for each reviewer.
- Analysis version 2 distinguishes nominal claim-label kappa from linear-weighted ordinal kappa and returns safe invalid/non-isomorphic reports.
- Working article scaffold at `docs/publication/seo-studio-manuscript.html`, with primary results explicitly pending.
- Structurally validated Gate 4 draft at `docs/publication/protocol-freeze-v1.md` with a machine-readable contract and blocker-reporting audit command. It is not frozen and does not authorize execution.
- All governance approvals were relayed on July 19, 2026 and preserved in a sanitized public record. Exact model digests and Ollama 0.24.0 were reverified read-only through `$davneet-dgx-access`; no mutation occurred.
- The pre-data sample-size sensitivity found that the 60-image RQ1 subset cannot support the approved five-point target under the displayed scenarios. The final population therefore remains a scientific design decision, not an administrative approval gap.

The first non-common-inventory calibration remains preserved as diagnostic history. The final 76-claim recalibration is the authoritative feasibility result. Calibration evidence is not model-quality evidence.

## Verification snapshot

Verified locally on July 19, 2026:

- evaluation suite: 43 tests passed;
- backend suite: 96 tests passed;
- frontend ESLint and production build: passed;
- checked-in OpenAPI contract: matches the generated FastAPI schema;
- deployed-stack and isolated-amendment preflights: ready on all 20 licensed pilot items;
- final calibration JSON and Markdown: regenerate byte-for-byte from the accepted inputs;
- Gate 4 draft audit: structurally valid with three verified prompt hashes and zero errors; governance and model-identity blockers are closed, while dataset/sample-size and infrastructure evidence remain;
- Markdown index and handoff links: no broken local targets;
- `git diff --check`: clean.

The deployed-stack preflight still warns that the five legacy screening model identities are not protocol-frozen. This is expected for the preserved pilot configuration and must be resolved for whichever conditions enter the frozen full study.

## Current research boundary

Technical calibration has passed, and the review protocol is feasible. Full-study execution has not been authorized by protocol freeze. Before opening or scoring remaining comparative outputs as primary evidence, the team must close the administrative/security items and freeze the final design.

Outstanding technical freeze work:

- choose the sample-size option after reviewing the pre-data sensitivity results;
- freeze final item/domain counts and the RQ1/context populations;
- materialize and validate the new full-study manifest;
- resolve the failed private listener-reachability check through an approved mitigation; the dedicated workspace and limited non-GPU telemetry path are verified;
- regenerate the audit and freeze only when it reports no blockers.

The Gate 4 draft resolves the design hierarchy: five original deployed-stack conditions plus amendments are reported for compatibility, while Qwen2.5-VL 3B, Qwen3.5 9B, and Gemma 3 12B enter the primary quality comparison. RQ1 has one primary outcome—hallucinated-claim rate—with supported-claim precision retained as the key secondary outcome. These decisions are approved, but the contract remains a draft until its technical blockers are cleared.

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
4. Treat calibration as final at 76 claims, 98.7% exact agreement, and Cohen's kappa 0.923.
5. Do not name a winning model or infer primary quality results.
6. Do not run the full study until Gate 4 is explicitly frozen.
7. For any DGX action, invoke `$davneet-dgx-access` and preserve the no-deletion boundary.
