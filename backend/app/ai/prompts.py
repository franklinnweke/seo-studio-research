IMAGE_METADATA_PROMPT = """You are generating SEO-friendly image metadata.

Return only valid JSON.

Tasks:
1. Describe the image accurately.
2. Generate concise alt text.
3. Generate an SEO-friendly filename.
4. Avoid keyword stuffing.
5. Do not invent details that are not visible.
6. Use lowercase hyphenated filenames.
7. Do not include the file extension in the filename.

Return:
{
  "filename": "",
  "alt_text": "",
  "caption": "",
  "confidence": 0.0
}
"""

IMAGE_METADATA_BRAND_CONTEXT_BLOCK = """

Brand context:
{brand_context}

Use brand context only for tone, audience, approved terminology, and filename wording.
Do not claim visible details from the brand context unless they are visible in the image.
"""

IMAGE_METADATA_RETRY_PROMPT = """Return only valid JSON for the provided image.

Do not include markdown, commentary, code fences, or explanations.

Required JSON shape:
{
  "filename": "lowercase-hyphenated-filename-without-extension",
  "alt_text": "Concise accessible alt text.",
  "caption": "Short accurate caption.",
  "confidence": 0.0
}
"""

IMAGE_METADATA_DESCRIPTION_PROMPT = """Describe this image accurately in one concise sentence.

Only mention details visible in the image.
"""

PAGE_METADATA_PROMPT = """You are generating SEO metadata for a website page.

Return only valid JSON with summary, seo_title, meta_description, and confidence.
"""

VISUAL_FACTS_PROMPT_VERSION = "visual-facts-v1"
CONTEXTUAL_METADATA_PROMPT_VERSION = "contextual-metadata-v1"
DIRECT_METADATA_PROMPT_VERSION = "direct-metadata-v1"
PURPOSE_SUGGESTION_PROMPT_VERSION = "purpose-suggestion-v1"

VISUAL_FACTS_PROMPT_V1 = """You inspect image pixels for a grounded metadata experiment.

Return only JSON matching the supplied schema. Report visible evidence only. Do not write alt text,
captions, filenames, SEO copy, page purpose, brand claims, identity, demographics, emotions, intent,
location, or other inferences that are not directly supported by pixels. Put uncertain observations
in uncertain_facts and any tempting prohibited inference in forbidden_inferences_observed.
"""

CONTEXTUAL_METADATA_PROMPT_V1 = """/no_think
You write accessible web image metadata from separately labelled evidence classes.

Evidence rules:
- VISUAL_FACTS_JSON is the only source for claims about visible image content.
- PAGE_CONTEXT_JSON supplies placement and audience context, not visible facts.
- BRAND_CONTEXT supplies tone and approved terminology, not visible facts.
- CONFIRMED_PURPOSE_JSON is a human decision and controls the alt-text strategy.
- Decorative and redundant images require empty alt text.
- Do not merge contextual claims into visual claims or invent unsupported details.
- Return only JSON matching the supplied schema, with an extension-free lowercase hyphenated filename.

[VISUAL_FACTS_JSON]
{visual_facts_json}
[/VISUAL_FACTS_JSON]

[PAGE_CONTEXT_JSON]
{page_context_json}
[/PAGE_CONTEXT_JSON]

[BRAND_CONTEXT]
{brand_context}
[/BRAND_CONTEXT]

[CONFIRMED_PURPOSE_JSON]
{image_context_json}
[/CONFIRMED_PURPOSE_JSON]
"""

DIRECT_METADATA_PROMPT_V1 = """/no_think
You inspect the attached image and write accessible web image metadata in one step.

Context rules:
- Treat the attached image pixels as the only source for visible-content claims.
- PAGE_CONTEXT_JSON supplies placement and audience context, not visible facts.
- BRAND_CONTEXT supplies tone and approved terminology, not visible facts.
- CONFIRMED_PURPOSE_JSON is a human decision and controls the alt-text strategy.
- Decorative and redundant images require empty alt text.
- Do not invent unsupported details.
- Return only JSON matching the supplied schema, with an extension-free lowercase hyphenated filename.

[PAGE_CONTEXT_JSON]
{page_context_json}
[/PAGE_CONTEXT_JSON]

[BRAND_CONTEXT]
{brand_context}
[/BRAND_CONTEXT]

[CONFIRMED_PURPOSE_JSON]
{image_context_json}
[/CONFIRMED_PURPOSE_JSON]
"""

PURPOSE_SUGGESTION_PROMPT_V1 = """/no_think
Suggest the role this image most likely serves at its stated page placement.

Return only JSON matching the supplied schema. Choose one purpose from informative, decorative,
functional, text, complex, redundant, or unknown. Page context may support the role decision but
must not be treated as evidence of visible image content. Use unknown when the role cannot be
determined reliably. This is an AI suggestion that a human must confirm.

[PAGE_CONTEXT_JSON]
{page_context_json}
[/PAGE_CONTEXT_JSON]
"""
