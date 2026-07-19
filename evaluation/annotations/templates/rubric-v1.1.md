# SEO Studio blinded review rubric v1.1

This rubric is for the predeclared first repeat only. Reviewers must not attempt to identify a model, compare latency, consult the private condition map, or use the catalog's adjudication examples. Rate the output against the image, fictional page context, brand profile, and confirmed purpose supplied in the reviewer interface.

## Claim labels

- `supported`: directly visible in the image or, for a purpose/terminology statement, explicitly supported by permitted context.
- `unsupported`: plausible but not established by the permitted evidence.
- `contradicted`: conflicts with visible or permitted evidence.
- `not_verifiable_from_permitted_evidence`: cannot be checked from the evidence a writer condition was allowed to use.

Brand or page context can support wording, audience, and purpose. It cannot prove that an object, person, action, identity, diagnosis, location, or outcome is visible.

### Calibration clarification: claim units and labels

- Annotate the semantic propositions communicated by the metadata, not metalinguistic statements such as “the caption says…” or “the filename is…”. Filename tokens count only when they communicate a descriptive proposition.
- Split conjunctions when each part can be independently supported or contradicted.
- Count each unique atomic proposition once per output. If the same proposition appears in multiple fields, score the repetition under redundancy control rather than duplicating the claim unit.
- Numeric confidence is not a claim. A warning or instruction such as “do not infer identity” is not a factual claim unless it also asserts a fact about the image.
- Use `unsupported` when a concrete visible or contextual proposition is plausible but is not established by the supplied evidence. Use `not_verifiable_from_permitted_evidence` for identity, intent, diagnosis, outcome, or another proposition the permitted evidence cannot resolve. Use `contradicted` only when the evidence affirmatively conflicts with the proposition.
- Agreement analysis requires a common claim inventory. After independent claim extraction, reconcile claim boundaries without model identities, then have reviewers independently label the same frozen inventory.

### Calibration clarification: grounding caps

- A contradicted central claim (e.g., misidentifying the primary body part or action being performed) caps the Factual Grounding score at 1.
- A contradicted minor claim (e.g., misidentifying a peripheral item like "umbrellas" when only trees are present) caps the Factual Grounding score at 3.
- An unsupported claim (e.g., claiming a "bottle of water" is in a basket when not visible) caps the Factual Grounding score at 3.

## Five-point ratings

Use 2 or 4 when performance falls between the anchors.

| Dimension | 1 | 3 | 5 |
|---|---|---|---|
| Factual grounding | Major unsupported, contradicted, or unsafe content | Mostly supported with a limited factual problem | Every factual claim is supported |
| Salient coverage | Misses the image's central useful content | Covers the main subject but omits useful detail | Covers the important content without padding |
| Contextual usefulness | Does not communicate the image's role on the page | Partly useful but generic or incomplete | Clearly communicates the role for the declared audience |
| Redundancy control | Repeats nearby text without adding needed meaning | Some avoidable repetition | Avoids repetition or correctly uses empty alt text |
| Purpose appropriateness | Violates the confirmed purpose | Partly follows the purpose but needs revision | Correctly handles informative, decorative, redundant, functional, text, or complex purpose |
| Brand alignment | Conflicts with approved terminology/tone | Neutral or partially aligned | Uses approved terminology naturally without inventing claims |
| Safety | Contains a sensitive or prohibited inference | Borderline wording that should be revised | No identity, diagnosis, outcome, or other prohibited inference |
| Concision and fluency | Unclear, fragmented, or substantially verbose | Understandable but needs editing | Clear, concise, and natural |

For a supplied metadata output, use `null` for redundancy control or brand alignment only when the dimension is genuinely inapplicable. Do not use `null` to avoid a difficult judgment.

### Calibration clarification: system failures

When `valid=false` and `output=null`, record `claims=[]`, set all eight rating fields to `null`, choose `reject`, and add `system_failure_no_output` to the note. Analyze this as an observed reliability failure and reject disposition, not as content-quality scores. Never regenerate, impute, or remove the item.

### Calibration clarification: dimension rules
1. **Redundancy Control**:
   - Word-for-word repetition of nearby page context text or section headings in the output caption is a severe redundancy issue (score 2).
   - Moderate overlap or highly similar phrasing is scored 3 or 4.
   - Repeating the same proposition across filename, alt text, and caption is evaluated here even when the proposition is factually supported.
2. **Salient Coverage**:
   - Score coverage against the content needed for the confirmed purpose, not against every visible detail.
   - For informative images, omitting the central subject or action caps the score at 2; omitting a useful secondary detail caps it at 4.
   - For functional images, do not require exhaustive visual description. Missing the control action is primarily a purpose/contextual-usefulness defect rather than a visual-detail omission.
3. **Contextual Usefulness**:
   - Score whether the metadata communicates the image's actual role to the supplied audience in the supplied page context.
   - For functional images, an action stated only in the caption but absent from alt text caps contextual usefulness at 3. If no field communicates the action or destination, cap it at 2.
4. **Purpose Appropriateness**:
   - For **Functional** images, alt text that is purely descriptive (narrating visual details) and fails to state the control action or booking link destination is a severe purpose violation (score 2), requiring a `major_edit`.
5. **Brand Alignment**:
   - Using non-approved terms (e.g., "students" instead of the brand-approved "learners") is a brand alignment issue and must be scored 4 or lower.

### Calibration clarification: disposition mapping

- Use `minor_edit` only when the central metadata can remain and the problem can be removed or corrected locally, such as one peripheral unsupported detail or a terminology substitution.
- Use `major_edit` when the central alt text, purpose handling, primary subject/action, or functional destination must be rewritten.
- Use `reject` for a system failure/no output, a dangerous or unusable result, an empty value when meaning is required, or a non-empty alt value when emptiness is required.
- A low score does not mechanically determine disposition; apply the edit-scope definitions above and explain any borderline decision.

## Overall disposition

- `accept_unchanged`: publishable as supplied.
- `minor_edit`: preserves the central output and needs only local wording, punctuation, or concision changes.
- `major_edit`: requires a substantive factual, purpose, safety, or coverage rewrite.
- `reject`: unusable, dangerous, empty when meaning is required, or non-empty when an empty value is required.

## Purpose-specific rules

- Decorative and redundant placements should normally have `alt=""`; visual detail in the catalog is grounding evidence, not a requirement to write alt text.
- Functional alt text communicates the link or control action rather than narrating every visual detail.
- Text images include only clearly legible, relevant text.
- Complex images use a short identifying alt value and the declared long-description path; do not require a full transcription in alt text.
- Informative descriptions prioritize content that matters to the supplied page purpose.

## Review sequence

1. Read the confirmed purpose and permitted context.
2. Inspect the image at the provided resolution.
3. Segment the output into independently verifiable claims and label every claim.
4. Apply all eight ratings.
5. Choose one disposition and add a short note for any rating below 5.
6. Submit without discussing the item with another reviewer. Adjudication occurs later in a separately labelled record.
