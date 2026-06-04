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
