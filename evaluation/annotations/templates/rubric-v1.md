# SEO Studio blinded review rubric v1

This rubric is for the predeclared first repeat only. Reviewers must not attempt to identify a model, compare latency, consult the private condition map, or use the catalog's adjudication examples. Rate the output against the image, fictional page context, brand profile, and confirmed purpose supplied in the reviewer interface.

## Claim labels

- `supported`: directly visible in the image or, for a purpose/terminology statement, explicitly supported by permitted context.
- `unsupported`: plausible but not established by the permitted evidence.
- `contradicted`: conflicts with visible or permitted evidence.
- `not_verifiable_from_permitted_evidence`: cannot be checked from the evidence a writer condition was allowed to use.

Brand or page context can support wording, audience, and purpose. It cannot prove that an object, person, action, identity, diagnosis, location, or outcome is visible.

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

Use `null` for redundancy control or brand alignment only when the supplied condition makes the dimension genuinely inapplicable. Do not use `null` to avoid a difficult judgment.

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
