# SEO Studio research continuation checklist

Last verified: July 23, 2026

Starting point: Gate 4 is frozen and audit-ready; measured primary-generation collection is next

This is the short operational view of the canonical master plan. It does not replace `publication-research-architecture.md`.

## 0. Consolidate the accepted state

- [x] Synchronize every public document and manuscript occurrence to the final accepted 76-item human-check/98.7% calibration figures.
- [x] Keep the final calibration JSON and Markdown together and verify their hashes and byte-for-byte regeneration.
- [x] Run evaluation tests, backend tests, frontend lint/build, OpenAPI drift checks, schema validation, dataset validation, and `git diff --check`.
- [x] Review the working tree carefully and commit only intended research/calibration/documentation changes. Keep `submissions/`, browser output, screenshots, caches, generated full-study draft binaries, and unrelated teammate files unstaged.
- [x] Record the accepted calibration state in the durable compact handoff; repeat it in the eventual commit message.

Exit: the accepted evidence and documentation are consistent, tested, and intentionally committed.

## 1. Close administrative and infrastructure prerequisites

- [x] Complete the private supervisor record with name, role, acknowledgement date, communication method, and private evidence reference. Do not commit the communication itself.
- [x] Agree provisional authorship order and CRediT responsibilities with both teammates and the supervisor; keep the private details outside Git until manuscript authorship is populated.
- [x] Confirm the institutional publication route and course-based ethics determination with no external participant recruitment.
- [x] Record the observed listener posture without making it a scientific execution gate. DGX identity, allowed-data policy, dedicated workspace, limited supported telemetry, and SSH-tunnel topology are confirmed.
- [x] Choose the approved SSH-tunnel path to the shared Ollama runtime for the evaluated deployed-stack system; public direct access is not required.
- [x] Add CI gates for backend tests, OpenAPI drift, frontend lint/build, evaluation tests, JSON-schema drift, and licensed-pilot preflight; prohibit DGX inference on ordinary hosted runners.

Exit: research access and preservation requirements are complete; infrastructure hardening is outside the study gate.

## 2. Produce the protocol-freeze accounting sheet

Frozen protocol: `docs/publication/protocol-freeze-v1.md` and `evaluation/configs/full-study-protocol-v1.json`. The offline audit validates its structure, prompt hashes, execution plan, evidence hashes, and accounting.

All governance approvals and exact model identities are recorded. The project lead selected the practical estimation-first option after reviewing `docs/publication/sample-size-sensitivity-v1.md`; the dated decision record is `evaluation/configs/full-study-sample-size-decision-20260719.json`.

Before inspecting additional comparative quality outputs, freeze an exact accounting table containing:

- [x] dataset images by split, domain, purpose, and diagnostic stratum;
- [x] model and condition IDs, immutable digests, runtime, context window, prompt/output limits, seed, temperature, thinking mode, preprocessing, and keep-alive policy;
- [x] attempts per model × image × architecture × context condition × repeat;
- [x] which repeat enters human quality review and why;
- [x] the complete 128-image RQ1 claim-level population;
- [x] expected valid/failure denominators and system-failure treatment;
- [x] projected DGX hours and disk space, based on preserved pilot timing and record-size evidence;
- [x] private reference to a verified backup destination outside the active run directory;
- [x] 876 unique outputs, 1,071 assignments, three reviewers, 25%/20% overlap, 714 active minutes per reviewer, independent adjudication, and predeclared reduction priority;
- [x] minimum scientifically meaningful effects, statistical tests, multiplicity control, confidence intervals, missingness/failure policy, and tie-breaking rule;
- [x] the existing 60-cell package is pilot/calibration evidence excluded from primary inference.

The frozen design treats the existing 20-image package as pilot/calibration evidence, reports five original conditions plus amendments for compatibility, and advances three conditions to primary quality evaluation. The final manifest is present and valid.

Exit: supervisor/team approval of a dated, versioned protocol and run-accounting sheet. Tag the protocol/configuration commit.

## 3. Complete and freeze the publication dataset

- [x] Select the practical estimation-first sample size before primary output inspection: 128 images, 32 per domain.
- [x] Assemble 128 mechanically licensed candidates across the four balanced domains; assign all 128 to RQ1 and the controlled Qwen3.5 comparison, a deterministic 64-image subset to other production metadata comparisons, and a nested 36-image context subset.
- [x] Preserve draft source, author, licence, retrieval date, image identity, dimensions, split, domain, purpose, fictional context, and deterministic population evidence.
- [x] Keep pilot/development and final evaluation images separate.
- [x] Have a project author inspect all 128 images in the local human-check workspace, explicitly keep/reject every query-stratum draft, add a correction only when needed, confirm purpose/source/licence/quality/sensitivity, and export the completed check artifact. The project author confirms that every substantive decision was manual. Agentic help generated only the non-substantive completion note, which is disclosed and excluded from analysis.
- [x] Reopen the eight whole-image disagreements and two additional proposal-only differences listed in `evaluation/results/full-study-human-check-blind-diagnostic-20260722.md`. The project author rejected all eight whole-image items and corrected both proposal-only items; no label was changed automatically.
- [x] Resolve the eight rejected items through additive, documented replacements from the same domain/query/purpose strata; preserve the rejected evidence and inherit each rejected item's analysis-population flags.
- [x] Apply the rechecked export with the guarded replacement reconciler and preserve the applied evidence hash.
- [x] Materialize fresh 1280px final files and validate image hashes, licence evidence, dimensions, duplicate hashes, and the exact 32-per-domain allocation.
- [x] Freeze fictional page contexts, brand profiles, human-confirmed purposes, manifests, and preprocessing hashes.

Exit: immutable dataset manifest and validation report with no unresolved licence or split leakage.

## 4. Freeze and preflight the experiment

- [x] Freeze model/config files and full digests.
- [x] Freeze direct, decomposed, production-system, and context-ablation prompts and schemas.
- [x] Preflight every final model/condition without inspecting comparative quality; the offline full-study preflight is `ready` with zero errors or warnings.
- [x] Confirm the DGX workspace, available storage, and supported telemetry path.
- [x] Verify the separate backup destination with matching upload, remote, and round-trip hashes.
- [x] Keep listener posture as factual operational evidence rather than a protocol-freeze blocker.
- [x] Generate and hash-validate the complete 3,012-cell execution plan from the frozen seed.
- [x] Verify append-only checkpoint/resume behavior, recorded transport recovery, drift rejection, and stop conditions.

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
