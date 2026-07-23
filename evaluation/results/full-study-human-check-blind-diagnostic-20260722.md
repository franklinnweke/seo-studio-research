# Full-study human-check blind diagnostic

Date: July 22, 2026  
Status: **internal quality control only; not publication evidence**

## Outcome

The project author manually reviewed all 128 candidate images and made the substantive image, fact, prohibited-boundary, alt-example, and required-check decisions. Agentic help generated only the accepted-item `human_notes` text as a mechanical completion stamp. The note text did not make or alter the decisions and is excluded from substantive analysis.

A context-isolated Codex agent then independently checked a deterministic 24-image diagnostic sample: one lexicographically first item from every domain × purpose cell. It received the pixels, fictional placement, and pending proposals, but not the completed export, human decisions, human notes, Commons title/description, private model map, or prior conclusions.

| Decision unit | Exact agreement | Interpretation |
|---|---:|---|
| Whole-image decision | 16/24 (66.7%) | Eight candidates need a targeted project-author second look |
| Visible-fact proposal | 35/48 (72.9%) | Most differences follow the same domain/purpose-fit concerns |
| Prohibited boundary | 72/72 (100%) | No diagnostic disagreement |
| Alt example | 15/16 (93.8%) | One wording decision differed |

These rates do not estimate study reviewer reliability. The agent is not a calibrated human rater, the diagnostic sample was intentionally small, and the exercise occurred after the human check. The numbers must not enter the paper as research findings.

## Targeted second look

The agent rejected eight images that the project author accepted:

| Candidate | Diagnostic concern to reconsider |
|---|---|
| `education-professional-service-04-p45407708` | The cityscape may not independently establish a campus or learning environment. |
| `healthcare-07-p17612961` | The clinical-room image may be too dim or blurry for the frozen quality requirement. |
| `healthcare-05-p31233936` | The historical domestic gathering may not provide a clear healthcare visual or functional healthcare cue. |
| `healthcare-08-p15423478` | The corridor or rail-station scene may not fit the healthcare waiting-area placement. |
| `hospitality-local-service-04-p11211711` | The dusty, partially dismantled interior may be a poor hospitality-placement fit. |
| `hospitality-local-service-05-p25376838` | Food and drink are visible, but the pixels may not establish the proposed booking action or service. |
| `hospitality-local-service-08-p27554645` | The building exterior may not establish a guest or common area. |
| `retail-product-06-p104282087` | The storefront sign may be too faint or partially legible for the text/readability stratum. |

The project author remains authoritative. For each item, inspect the image and frozen fictional placement again, then either confirm the existing decision or correct it. Do not adopt the agent decision automatically.

## Additional proposal-level differences

The 13 visible-fact differences occurred on the eight candidates above plus:

- `healthcare-01-p192668490`: the human rejected proposal 0 while the diagnostic agent kept it. The same item contains the only alt-example disagreement.
- `retail-product-04-p147675226`: the human kept proposal 1 while the diagnostic agent rejected it.

These two items do not require whole-image rejection, but their cited proposal decisions should be quickly reconfirmed during the targeted pass.

## Decision

- Preserve the completed 128-item export and its hash.
- Preserve human authorship of all substantive decisions.
- Record the mechanical note assistance transparently and exclude note prose from analysis.
- Make no automatic label changes from this diagnostic.
- Recheck the eight whole-image disagreements and the two additional proposal-only items before applying the export and materializing the final manifest.

The machine-readable diagnostic is `full-study-human-check-blind-diagnostic-20260722.json`.
