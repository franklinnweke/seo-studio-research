# Sprint 2 Implementation Submission

## Project

SEO Studio is a capstone proof of concept for image optimization and AI-assisted SEO metadata workflows.

## Sprint 2 Focus

Sprint 2 focused on improving the image workflow after the Sprint 1 optimizer foundation:

- AI image metadata generation with local Ollama models.
- Brand context upload for TXT, DOCX, and PDF files.
- SEO metadata review UI with regenerate, preview, download, and export workflows.
- CSV/ZIP metadata export support.
- Dashboard workflow refinement now present on `main` after the latest remote update.
- Documentation and sprint task/status tracking for rubric evidence.

## How To Run Locally

Recommended professor run path:

```bash
unzip seo-studio-sprint-2-submission.zip
cd seo-studio-sprint-2-submission
./scripts/dev.sh
```

Then open:

```text
Frontend: http://127.0.0.1:3000
Backend:  http://127.0.0.1:8000
Swagger:  http://127.0.0.1:8000/docs
```

Manual run path:

```bash
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev -- --hostname 127.0.0.1 --port 3000
```

## Runtime Note

On the review machine, Node `v26.0.0` caused Next.js/Turbopack to hang while compiling `/` and repeatedly print:

```text
[DEP0205] DeprecationWarning: `module.register()` is deprecated.
```

Use an active Node LTS version, preferably Node 22 or Node 24, for the frontend dev server. The backend health check passed locally at `http://127.0.0.1:8000/health`.

## Optional AI Setup

AI metadata generation requires Ollama and local models:

```bash
ollama pull qwen2.5vl:3b
ollama serve
```

Useful environment variables:

```text
SEO_STUDIO_AI_PROVIDER=ollama
SEO_STUDIO_OLLAMA_BASE_URL=http://localhost:11434
SEO_STUDIO_VISION_MODEL=qwen2.5vl:3b
SEO_STUDIO_LANGUAGE_MODEL=qwen2.5vl:3b
SEO_STUDIO_OLLAMA_TIMEOUT_SECONDS=600
SEO_STUDIO_AI_LANGUAGE_TIMEOUT_SECONDS=120
SEO_STUDIO_AI_CROP_TIMEOUT_SECONDS=120
SEO_STUDIO_AI_PREVIEW_MAX_WIDTH=1024
```

Without Ollama, image upload, compression, conversion, resizing, API docs, and backend tests can still be reviewed.

## Demo Script

1. Start the app and open the dashboard.
2. Open Image Optimizer.
3. Upload one or more images, or a ZIP containing images.
4. Process the images to WebP/JPG/PNG and show cleaned filenames and size reductions.
5. Copy or preserve the image job ID.
6. Open SEO Metadata.
7. Load the image job ID.
8. Upload a brand context TXT, DOCX, or PDF file.
9. Show the attached document list and context preview.
10. Generate AI metadata if Ollama is available.
11. Regenerate one image row, open details, preview/download the image, and export selected metadata ZIP.
12. Open Swagger at `/docs` and show the metadata/brand-context endpoints.

## Verification Completed

```text
Backend tests: cd backend && .venv/bin/pytest
Result: 62 passed

Frontend lint: cd frontend && npm run lint
Result: passed
```

## Included Sprint 2 Task Evidence

See:

```text
docs/sprint-2-implementation-status.csv
docs/project-sprint-progress.csv
docs/sprint-milestone-plan.md
```

## Known Limitations

- Frontend dev server should be run with Node LTS; Node 26 caused a Turbopack compile hang locally.
- AI metadata quality depends on the local Ollama model setup.
- Metadata edits in the UI are local until persisted approval/update endpoints are implemented.
- Website crawler and broken-link tools are still Sprint 3+ work.
- The dashboard workflow refinement is included in the final `main` branch state packaged for submission.
