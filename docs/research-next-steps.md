# SEO Studio research continuation checklist

Last verified: July 19, 2026

Starting point: 128-image estimation-first design approved; manifest and listener-security evidence pending

This is the short operational view of the canonical master plan. It does not replace `publication-research-architecture.md`.

## 0. Consolidate the accepted state

- [x] Synchronize every public document and manuscript occurrence to the final accepted 76-claim/98.7% calibration figures.
- [x] Keep the final calibration JSON and Markdown together and verify their hashes and byte-for-byte regeneration.
- [x] Run evaluation tests, backend tests, frontend lint/build, OpenAPI drift checks, schema validation, dataset validation, and `git diff --check`.
- [ ] Review the working tree carefully and commit only the intended research/calibration/documentation changes. Do not stage `submissions/`, browser output, screenshots, caches, or unrelated teammate files.
- [x] Record the accepted calibration state in the durable compact handoff; repeat it in the eventual commit message.

Exit: the accepted evidence and documentation are consistent, tested, and intentionally committed.

## 1. Close administrative and infrastructure prerequisites

- [x] Complete the private supervisor record with name, role, acknowledgement date, communication method, and private evidence reference. Do not commit the communication itself.
- [x] Agree provisional authorship order and CRediT responsibilities with both teammates and the supervisor; keep the private details outside Git until manuscript authorship is populated.
- [x] Confirm the institutional publication route and course-based ethics determination with no external participant recruitment.
- [ ] Through `$davneet-dgx-access` and the institution/supervisor, close the remaining listener/firewall security finding. DGX identity, allowed-data policy, dedicated workspace, limited supported telemetry, and SSH-tunnel topology are confirmed.
- [x] Choose the approved SSH-tunnel path to the shared Ollama runtime for the evaluated deployed-stack system; public direct access is not required.
- [ ] Add missing CI gates for backend tests, frontend lint/build, evaluation tests, and OpenAPI drift.

Exit: the deferred Gate 1 listener-security requirement is documented as passed or explicitly constrained; Gate 3 administration is already complete.

## 2. Produce the protocol-freeze accounting sheet

Draft created: `docs/publication/protocol-freeze-v1.md` and `evaluation/configs/full-study-protocol-v1.draft.json`. The offline audit validates its structure, prompt hashes, and arithmetic while returning a blocking status until the approvals and final values below are complete.

All governance approvals and exact model identities are recorded. The project lead selected the practical estimation-first option after reviewing `docs/publication/sample-size-sensitivity-v1.md`; the dated decision record is `evaluation/configs/full-study-sample-size-decision-20260719.json`.

Before inspecting additional comparative quality outputs, freeze an exact accounting table containing:

- [ ] dataset images by split, domain, purpose, and diagnostic stratum;
- [x] model and condition IDs, immutable digests, runtime, context window, prompt/output limits, seed, temperature, thinking mode, preprocessing, and keep-alive policy;
- [x] attempts per model × image × architecture × context condition × repeat;
- [x] which repeat enters human quality review and why;
- [x] the complete 128-image RQ1 claim-level population;
- [x] expected valid/failure denominators and system-failure treatment;
- [ ] projected DGX hours, disk space, and backup location;
- [x] 876 unique outputs, 1,071 assignments, three reviewers, 25%/20% overlap, 714 active minutes per reviewer, independent adjudication, and predeclared reduction priority;
- [x] minimum scientifically meaningful effects, statistical tests, multiplicity control, confidence intervals, missingness/failure policy, and tie-breaking rule;
- [x] the existing 60-cell package is pilot/calibration evidence excluded from primary inference.

The approved draft treats the existing 20-image package as pilot/calibration evidence, reports five original conditions plus amendments for compatibility, and advances three conditions to primary quality evaluation. The protocol remains a draft until the manifest and security blockers are cleared.

Exit: supervisor/team approval of a dated, versioned protocol and run-accounting sheet. Tag the protocol/configuration commit.

## 3. Complete and freeze the publication dataset

- [x] Select the practical estimation-first sample size before primary output inspection: 128 images, 32 per domain.
- [ ] Materialize 128 licensed images across the four balanced domains; include all 128 in RQ1 and the controlled Qwen3.5 comparison, a deterministic 64-image subset in other production metadata comparisons, and a nested 36-image context subset.
- [ ] Preserve source, author, licence, retrieval date, image hash, dimensions, split, domain, purpose, context, reference facts, forbidden claims, and preprocessing evidence.
- [ ] Keep pilot/development and final evaluation images separate.
- [ ] Validate all images visually and mechanically; resolve licence or duplicate-hash issues before freeze.
- [ ] Freeze fictional page contexts, brand profiles, human-confirmed purposes, manifests, and preprocessing hashes.

Exit: immutable dataset manifest and validation report with no unresolved licence or split leakage.

## 4. Freeze and preflight the experiment

- [ ] Freeze model/config files and full digests.
- [ ] Freeze direct, decomposed, production-system, and context-ablation prompts and schemas.
- [ ] Preflight every final model/condition without inspecting comparative quality.
- [ ] Confirm the DGX workspace, storage, backups, secure access, and telemetry path.
- [ ] Generate the complete randomized execution plan from the frozen seed.
- [ ] Verify append-only checkpoint/resume behavior and stop conditions.

Exit: Gate 4 passed. No later convenience change may overwrite the frozen protocol; deviations require an additive record.

## 5. Execute full data collection

- [ ] Invoke `$davneet-dgx-access` and refresh live status before every DGX session.
- [ ] Run frozen attempts in the planned randomized/counterbalanced order.
- [ ] Preserve failures and bounded recoveries; never regenerate for quality.
- [ ] Keep cold-load, warm inference, transport incidents, and operational pauses distinguishable.
- [ ] Validate and back up append-only records after each segment.
- [ ] Produce sanitized run accounting without opening the private condition map.

Exit: expected cells are present or explicitly failed, source hashes match, deviations are documented, and raw evidence is immutable.

## 6. Blind and annotate

- [ ] Normalize records and generate identity-safe reviewer packages with automated leakage checks.
- [ ] Keep the condition map private and closed to reviewers and quality adjudicators.
- [ ] Independently calibrate the third reviewer under rubric v1.1 without opening the private condition map.
- [ ] Human-rate only the frozen repeat and 1,071-assignment balanced structure.
- [ ] Annotate every claim in the complete primary RQ1 population.
- [ ] Preserve individual R1/R2/R3 records, timing, independent adjudication, and agreement analysis.
- [ ] Stop and recalibrate only if a predeclared reliability rule fails; do not change anchors to favour a condition.

Exit: Gate 6 annotation population is complete, blinded, schema-valid, and agreement-reportable.

## 7. Analyze and select the deployment model

- [ ] Compute objective reliability, schema, latency, throughput, token, and resource metrics.
- [ ] Compute supported-claim precision, hallucinated-claim performance, salient coverage, human ratings, disposition, and agreement.
- [ ] Run the controlled Qwen3.5 direct-versus-decomposed analysis separately from the production-system comparison.
- [ ] Run the predeclared context ablation or its frozen reduced subset.
- [ ] Report failures in denominators and include sensitivity analyses.
- [ ] Apply the frozen eligibility, Pareto, and tie-breaking selection rule.
- [ ] Open the private model map only at the predeclared unblinding step after quality data are frozen.

Exit: generated tables, figures, statistical output, decision report, and one defensible deployment recommendation.

## 8. Complete the manuscript and release package

- [ ] Generate manuscript numbers, tables, and figures directly from normalized analysis artifacts.
- [ ] Write methods, results, discussion, threats, limitations, introduction, conclusion, and abstract in that order.
- [ ] Complete CRediT, ethics, consent if applicable, data/code availability, funding/conflicts, and AI-use disclosures.
- [ ] Ensure claims remain limited to the deployed SEO Studio system and tested packages.
- [ ] Prepare supplementary protocol, dataset card, model/config table, rubric, run accounting, and deviation log.
- [ ] Obtain teammate and supervisor review before the school/venue submission route.
- [ ] Merge product/research work through reviewed branches, tag the release, and create the portfolio entry only with accurate submission/publication status.

Exit: Gate 8 release is reproducible, appropriately licensed, evidence-linked, and approved for the stated venue.

## Stop conditions

Stop rather than improvise if any of these occurs:

- protocol, model, prompt, threshold, dataset, or statistic changes after freeze without an amendment;
- a DGX action would alter owner-managed files, shared services, firewall state, or model storage without explicit authorization;
- the reviewer package leaks model identity;
- a licence, data-policy, ethics, or authorship question is unresolved for the proposed action;
- run records are missing, mutable, duplicated, or cannot be hash-verified;
- reviewer burden exceeds the frozen maximum;
- someone proposes choosing outputs, repeats, sample size, or analysis because results look favourable.
