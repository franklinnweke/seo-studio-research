# SEO Studio documentation index

Last verified: July 22, 2026

Public repository: [`franklinnweke/seo-studio-research`](https://github.com/franklinnweke/seo-studio-research)

Default release branch: `main` (published from the original `codex/research-context-aware-metadata` development lineage)

This page is the entry point for project documentation. Chat history is useful background, but it is not an authority source. When documents disagree, follow the authority order in the master research plan.

## Start here

| Document | Purpose | Authority |
|---|---|---|
| [Compact research context](research-context.md) | Fast handoff containing the current scope, evidence, decisions, gate, and safety boundaries | Current-state summary; update after every gate |
| [Research next steps](research-next-steps.md) | Ordered execution checklist from the present gate through publication | Operational view derived from the master plan |
| [Research master architecture](publication-research-architecture.md) | Complete architecture, protocol, governance, paper plan, and definitions of done | Canonical project and research source of truth |
| [Frozen Gate 4 protocol](publication/protocol-freeze-v1.md) | Exact full-study conditions, controls, accounting, statistics, and amendment rule | Frozen operational authority |
| [Working manuscript](publication/seo-studio-manuscript.html) | Evidence-honest article draft with pending primary-results sections | Draft only; generated evidence outranks prose |

Recommended reading order for a new person or agent:

1. This index.
2. [Compact research context](research-context.md).
3. [Research next steps](research-next-steps.md).
4. The relevant section of the [master architecture](publication-research-architecture.md).
5. The applicable protocol, result, or code contract linked below.

## Research protocol and evidence

| Artifact | What it establishes |
|---|---|
| [Evaluation harness guide](../evaluation/README.md) | Commands, evidence boundaries, immutable-run rules, and completed compatibility stages |
| [Machine-readable Gate 4 protocol](../evaluation/configs/full-study-protocol-v1.json) | Frozen models, prompt hashes, dataset plan, execution controls, outcomes, accounting, and approvals |
| [Current Gate 4 audit](../evaluation/results/full-study-protocol-audit-v1.json) | Machine verification that the protocol is `freeze_ready` |
| [Deterministic execution plan](../evaluation/configs/full-study-execution-plan-v1.jsonl) | Exact seeded order and dependencies for all 3,012 planned stage cells |
| [Execution-plan validation](../evaluation/results/full-study-execution-plan-validation-v1.json) | Confirms byte-stable regeneration, exact cell counts, and zero plan errors |
| [Operational-readiness evidence](../evaluation/configs/full-study-operational-readiness-v1.json) | Pilot-derived runtime/storage estimates, checkpoint controls, stop conditions, and verified backup reference |
| [Infrastructure update](../evaluation/configs/full-study-infrastructure-update-20260723.json) | Sanitized DGX backup verification, SSH-tunnel confirmation, and observed listener posture |
| [All-approvals relay](../evaluation/configs/full-study-approval-20260719.json) | Sanitized record of governance approvals; private names and communications remain outside Git |
| [Full-study runtime reverification](../evaluation/configs/full-study-runtime-reverification-20260719.json) | Read-only Ollama/runtime and exact three-model digest evidence |
| [Listener-state reverification](../evaluation/configs/full-study-listener-reverification-20260723.json) | Sanitized read-only confirmation of the observed all-interface Ollama listener; operational context only |
| [Sample-size sensitivity](publication/sample-size-sensitivity-v1.md) | Pre-data calculation testing whether the provisional population can resolve the approved effects |
| [Sample-size evidence JSON](../evaluation/results/full-study-sample-size-sensitivity-v1.json) | Reproducible machine-readable sensitivity results and the recorded estimation-first selection |
| [Approved 128-image decision](../evaluation/configs/full-study-sample-size-decision-20260719.json) | Pre-data selection of the practical estimation-first design, domain allocation, review populations, workload, and inferential limits |
| [Full-study dataset check guide](publication/full-study-dataset-check-guide.md) | Required 128-item human visual check, export, validation, replacement, and final-materialization procedure |
| [Final full-study catalog](../evaluation/dataset/full-study-catalog.json) | Final 128 accepted identities, sources, contexts, purposes, additive replacement links, and frozen 128/64/36 population assignments |
| [Original human-check workbook](../evaluation/dataset/full-study-human-check.jsonl) | Preserved pending input to the original local check workspace; historical preparation evidence only |
| [Human-check provenance record](../evaluation/configs/full-study-human-check-provenance-20260722.json) | Records that all substantive decisions were manual and that agentic help generated only the non-substantive completion note |
| [Blind diagnostic report](../evaluation/results/full-study-human-check-blind-diagnostic-20260722.md) | Internal 24-cell quality-control comparison and targeted recheck list; explicitly excluded from publication evidence |
| [Human-check reconciliation](../evaluation/configs/full-study-human-check-reconciliation-20260722.json) | Records the project-author recheck, eight whole-image rejections, two proposal corrections, and the required additive replacement boundary |
| [Rechecked human-check export](../evaluation/dataset/full-study-human-check-recheck-20260722.jsonl) | Immutable 128-row recheck evidence: 120 accepted and eight rejected; not directly applicable until replacements are accepted |
| [Replacement reconciliation](../evaluation/configs/full-study-replacement-reconciliation-20260723.json) | Eight same-stratum replacements, inherited population assignments, metadata normalization, and source/final hashes |
| [Final human-check evidence](../evaluation/dataset/full-study-human-check-final-20260723.jsonl) | Final 128-row project-author population: 128 accepted and 128 unique IDs |
| [Final publication manifest](../evaluation/dataset/manifest-full-v1.jsonl) | Executable 128-item manifest with unique image hashes, accepted human-check evidence, and verified licence/context/brand hashes |
| [Final materialization summary](../evaluation/dataset/full-study-materialization-summary.json) | Retrieval timestamp, population counts, assignment seed, and final manifest path |
| [Rubric v1.1](../evaluation/annotations/templates/rubric-v1.1.md) | Frozen human-check dimensions and labels, purpose rules, and failure handling |
| [Final calibration report](../evaluation/results/recal_analysis_results.md) | Reviewer feasibility on 15 blinded items and the final 76-item human-check inventory |
| [Calibration evidence JSON](../evaluation/results/recal-analysis-20260719.json) | Machine-readable analysis version 2, source hashes, agreement, timing, and status |
| [Deployed-stack compatibility report](../evaluation/results/compatibility-pilot-20260717.md) | Original compatibility screen; not a quality ranking |
| [Qwen3.6 amendment](../evaluation/results/compatibility-amendment-20260717.md) | Additive candidate amendment under the unchanged gate |
| [Protocol 2.2 repair report](../evaluation/results/truncation-repair-20260717.md) | Source-linked truncation repairs and eligible deployed-stack challengers |
| [Gemma 4 isolated amendment](../evaluation/results/compatibility-isolated-gemma4-20260718.md) | Current-generation compatibility correction and exclusion boundary |
| [Gemma 4 repair report](../evaluation/results/truncation-repair-isolated-gemma4-20260718.md) | Final isolated pipeline-validity decision |
| [Writer compatibility](../evaluation/results/writer-compatibility-20260717.md) | Fixed Qwen3.5 writer compatibility; not quality evidence |
| [Fixed-writer matrix](../evaluation/results/writer-matrix-20260718.md) | Structural metadata outcomes used to build the blinded 60-cell package |

Raw run directories, reviewer identities, the private condition map, live DGX details, and supervisor communications are deliberately excluded from this index and from Git.

## Product and capstone documents

| Document | Purpose |
|---|---|
| [Repository README](../README.md) | Local development, tests, and product status |
| [Capstone proposal](capstone-proposal.md) | Original problem, benefits, scope, timeline, and team charter |
| [Product project plan](project-plan.md) | Broader application roadmap; not the publication protocol |
| [Sprint milestone plan](sprint-milestone-plan.md) | Course delivery and rubric evidence |
| [Sprint 2 submission guide](sprint-2-submission-readme.md) | Preserved sprint submission context |

The product plan includes crop/resize work. AI cropping remains outside the primary research paper and must not be reintroduced as a paper outcome without a formal protocol amendment.

## Document maintenance rules

- Update `research-context.md` after a gate closes, an authoritative decision changes, or new evidence is accepted.
- Update `research-next-steps.md` when a gate changes; do not silently remove incomplete requirements.
- Update the master architecture through an explicit decision record when scope, models, outcomes, thresholds, or governance change.
- Generate reported numbers from normalized evidence. Do not manually reconcile conflicting values in the manuscript.
- Use `$davneet-dgx-access` for every live DGX operation. Do not create a competing connection runbook in the repository.
- Keep the working manuscript marked pending until the primary analysis is frozen.
