# Healthcare Brand Sample Data

Use this dataset to manually test Phase 6 brand-context metadata generation.

## Files

- `brand-context.txt` contains the sample healthcare brand voice and SEO rules.
- `real-images/` contains five real healthcare-related JPG photos for model testing.
- `real-images-attribution.md` contains source, author, and license details for the real photos.
- `real-expected-results.json` contains target outputs and qualitative checks for the real photos.
- `real-expected-results.csv` contains a compact comparison table for the real photos.
- `images/` contains five generated healthcare-themed PNG fallback fixtures.
- `expected-results.json` contains target outputs and qualitative checks for the generated fixtures.
- `expected-results.csv` contains a compact comparison table for the generated fixtures.

## Manual Test Flow

1. Open Image Optimizer.
2. Upload all five files in `real-images/`.
3. Process the images with default settings.
4. Open SEO Metadata.
5. Upload `brand-context.txt` in the Brand Context panel.
6. Generate metadata.
7. Compare generated results with `real-expected-results.json`.

The AI output does not need to match exactly. A good result should:

- Use healthcare-specific but careful wording.
- Avoid diagnosis or treatment claims.
- Mention only visible image details.
- Keep filenames lowercase, hyphenated, and concise.
