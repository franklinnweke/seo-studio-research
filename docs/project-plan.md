# seo-studio Project Plan

## Overview

`seo-studio` is a proof-of-concept platform for AI-powered image and website optimization.

The POC will validate the core workflow before adding production-scale infrastructure. It will support batch image upload, image compression, image conversion, filename cleanup, AI-generated image metadata, website crawling, broken link checking, AI-generated SEO metadata, and export generation.

## Goals

- Build a working local image optimization pipeline.
- Support single image, multi-image, and ZIP upload.
- Compress and convert images for web use.
- Generate AI-powered image filenames, alt text, and captions.
- Let users review, edit, regenerate, and approve generated metadata.
- Crawl websites with optional Basic Auth.
- Detect broken links and report their source pages.
- Generate page summaries, SEO titles, and meta descriptions.
- Export processed images and reports as CSV, JSON, XLSX, and ZIP.
- Keep the POC lightweight and easy to run locally.

## Non-Goals for the POC

- Multi-tenant user accounts
- Authentication and permissions
- Billing and subscriptions
- CMS plugin integrations
- Kubernetes deployment
- Distributed microservices
- Enterprise-scale crawling
- Large-scale image processing
- Direct CMS publishing

## Tech Stack

### Frontend

- Next.js
- Tailwind CSS
- shadcn/ui-style component system
- TanStack Table
- react-hook-form
- zod
- lucide-react

### Backend

- FastAPI
- Python 3.11+
- Pillow first, with pyvips as a later performance option
- httpx
- BeautifulSoup4
- pandas
- openpyxl

### AI Runtime

- Ollama for local development
- Default model: `llama3.2-vision`
- Alternative model: `llava:7b`

## Repository Structure

```text
seo-studio/
  frontend/
  backend/
  shared/
  docs/
```

### Frontend Structure

```text
frontend/
  app/
  components/
  lib/
  hooks/
  types/
  styles/
```

### Backend Structure

```text
backend/
  app/
    main.py
    routes/
      image_jobs.py
      website_jobs.py
      exports.py
      settings.py
    services/
      image_processor.py
      ai_metadata_service.py
      crawler_service.py
      broken_link_service.py
      metadata_generator.py
      export_service.py
    ai/
      ollama_client.py
      prompts.py
    models/
      job.py
      image_result.py
      page_result.py
      broken_link_result.py
    storage/
      uploads/
      processed/
      exports/
      temp/
    utils/
      slugify.py
      zip_utils.py
      file_utils.py
      cleanup.py
      validators.py
  requirements.txt
  tests/
```

### Shared Structure

```text
shared/
  api-contracts/
  schemas/
  docs/
```

## Architecture

### POC Architecture

```text
Next.js Frontend
    -> FastAPI Backend
    -> Ollama Local AI Runtime
```

The frontend handles upload, settings, review, and exports.

The backend handles uploads, image processing, AI calls, crawling, broken link checks, metadata generation, and export generation.

Ollama runs as a separate local process and exposes its local HTTP API.

### POC Persistence Model

The POC uses local file storage plus JSON metadata files instead of a database.

Uploaded files are stored on disk under:

```text
backend/app/storage/uploads/{job_id}/
  job.json
  images/
  archives/
```

Processed files and exports are stored under:

```text
backend/app/storage/processed/{job_id}/
backend/app/storage/exports/{job_id}/
```

`job.json` acts as the temporary metadata store for POC workflows. It can contain job status, uploaded file records, generated metadata, page crawl results, broken link results, and export references as phases are added.

The POC should not store binary image data in a database.

### Production Evolution

```text
Next.js Frontend
    -> FastAPI API Server
    -> Redis Queue
    -> Worker Service
    -> GPU Inference Service
    -> Object Storage / Database
```

The POC should stay as a modular monolith. Long-running workers, Redis, PostgreSQL, object storage, and authentication are beta or production concerns.

## Local Defaults

- Backend URL: `http://localhost:8000`
- Frontend URL: `http://localhost:3000`
- Ollama URL: `http://localhost:11434`
- Default AI model: `llama3.2-vision`
- Default output format: `webp`
- Default image quality: `80`
- Default resize: none
- Default metadata stripping: enabled
- Max images per batch: 20-50
- Max individual image size: 5MB initially
- AI preview max width: 1024px
- AI processing batch size: 1

## API Summary

The backend uses FastAPI's built-in OpenAPI generation. Swagger UI is available at `/docs`, ReDoc is available at `/redoc`, and the canonical API contract is `/openapi.json`.

Generated API contracts should be committed to:

```text
shared/api-contracts/openapi.json
```

Every backend endpoint must include:

- A typed request model when the endpoint accepts structured input.
- A typed response model.
- A clear Swagger summary.
- A human-readable Swagger description.
- Documented success and common error responses.
- Accurate tags for grouping in Swagger.

### Image Jobs

- `POST /api/jobs/images`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/files`
- `PATCH /api/jobs/{job_id}/images/{image_id}`
- `POST /api/jobs/{job_id}/images/{image_id}/regenerate`
- `POST /api/jobs/{job_id}/images/{image_id}/accept`
- `POST /api/jobs/{job_id}/images/accept-all`

### Website Jobs

- `POST /api/jobs/website`
- `GET /api/jobs/{job_id}/pages`
- `GET /api/jobs/{job_id}/pages/{page_id}`
- `GET /api/jobs/{job_id}/links`
- `GET /api/jobs/{job_id}/broken-links`

### Exports

- `GET /api/jobs/{job_id}/export.csv`
- `GET /api/jobs/{job_id}/export.json`
- `GET /api/jobs/{job_id}/export.xlsx`
- `GET /api/jobs/{job_id}/export.zip`

### Settings

- `GET /api/settings`
- `PATCH /api/settings`

## Phase Plan

### Phase 0: Project Setup

Create the monorepo foundation and local development setup.

Backend tasks:

- Create FastAPI app.
- Add health check endpoint.
- Add CORS configuration.
- Add config management.
- Add logging.
- Create storage folders.
- Add base route, service, model, AI, and utility modules.

Frontend tasks:

- Create Next.js app.
- Install Tailwind CSS.
- Add component system foundation.
- Add base layout.
- Add sidebar navigation.
- Add dashboard shell.
- Add API client utility.

Manual verification:

- Backend starts locally.
- `GET /health` returns healthy status.
- Frontend starts locally.
- Dashboard loads in the browser.
- Frontend can call the backend health endpoint.

Follow-up:

- Move to image upload only after both apps run independently.

### Phase 0.5: API Documentation Baseline

Make Swagger/OpenAPI documentation a required part of the backend contract before Phase 1.

Backend tasks:

- Configure FastAPI title, summary, description, version, docs URL, ReDoc URL, and OpenAPI JSON URL.
- Add OpenAPI tag metadata for health, settings, image jobs, website jobs, and exports.
- Replace scaffold `dict` route responses with Pydantic response models.
- Add endpoint summaries and descriptions to all existing routes.
- Add `shared/api-contracts/openapi.json` as the canonical generated API contract.
- Add an export script for regenerating `openapi.json`.
- Add tests that verify docs routes, OpenAPI metadata, route descriptions, tags, and response schemas.

Manual verification:

- Open `http://127.0.0.1:8000/docs`.
- Confirm endpoints are grouped under readable tags.
- Confirm current endpoints show summaries, descriptions, and response schemas.
- Open `http://127.0.0.1:8000/redoc`.
- Open `http://127.0.0.1:8000/openapi.json`.
- Confirm `shared/api-contracts/openapi.json` exists after running the export script.

Follow-up:

- Build Phase 1 upload APIs with Swagger-ready contracts from the beginning.

### Phase 1: Image Upload System

Allow users to upload images and ZIP files.

Backend tasks:

- Accept uploaded files with FastAPI `UploadFile`.
- Create a unique `job_id`.
- Save uploads to `storage/uploads/{job_id}`.
- Safely extract ZIP files.
- Validate `.jpg`, `.jpeg`, `.png`, `.webp`, and `.zip`.
- Reject unsupported file types.
- Return job metadata and uploaded file list.
- Document supported file types, ZIP behavior, max file size, success response, and validation errors in Swagger.

Frontend tasks:

- Add Axios as the standard frontend HTTP client.
- Add TanStack Query as the standard server-state layer.
- Add React Query provider at the app root.
- Add `react-dropzone` upload dropzone.
- Add accepted file type hints.
- Add Axios upload progress through `onUploadProgress`.
- Display uploaded file list.
- Show validation errors.

Manual verification:

- Upload one image.
- Upload multiple images.
- Upload a ZIP file.
- Confirm unsupported files are rejected.
- Confirm backend job folder is created.

Follow-up:

- Add processing settings once uploads are reliable.

### Phase 2: Image Compression

Compress uploaded images with configurable settings.

Status: implemented.

Backend tasks:

- Load uploaded images.
- Normalize orientation.
- Resize when enabled.
- Strip metadata when enabled.
- Apply lossy or lossless compression.
- Save processed files to `storage/processed/{job_id}`.
- Record original size, processed size, dimensions, and reduction percent.

Frontend tasks:

- Add compression settings card.
- Add quality slider.
- Add resize selector.
- Add metadata stripping switch.
- Show compression result table.

Manual verification:

- Compress JPG, PNG, and WebP files.
- Confirm processed files are created.
- Confirm size values and reduction percentage are shown.
- Confirm original files remain unchanged.
- Confirm the quality slider defaults to `80`.
- Confirm resize defaults to `none`.
- Confirm metadata stripping defaults to enabled.

Follow-up:

- Add output format conversion after compression results are tracked.

### Phase 3: Image Conversion

Convert images between common web formats.

Status: implemented.

Backend tasks:

- Detect source image format.
- Support output options: keep original, WebP, JPG, PNG.
- Convert JPG to WebP.
- Convert PNG to WebP.
- Convert PNG to JPG.
- Flatten transparency to white when converting transparent PNGs to JPG.
- Save converted output with the correct extension.

Frontend tasks:

- Add output format selector.
- Add transparency warning for PNG to JPG.
- Show output format in results table.

Manual verification:

- Convert JPG to WebP.
- Convert PNG to WebP.
- Convert PNG to JPG.
- Inspect transparent PNG conversion output.
- Confirm Image Optimizer navigation opens the image workflow page.

Follow-up:

- Add filename cleanup before AI naming so generated files are web-safe.

### Phase 4: Filename Cleanup

Normalize filenames for web and SEO compatibility.

Backend tasks:

- Create filename slugification utility.
- Lowercase names.
- Trim whitespace.
- Replace spaces with hyphens.
- Remove special characters.
- Remove duplicate hyphens.
- Limit base filename length to 60 characters.
- Preserve extension.
- Deduplicate filenames by appending counters.

Frontend tasks:

- Add filename mode selector.
- Show original filename.
- Show cleaned filename.
- Allow manual filename edits.

Manual verification:

- Upload files with spaces and special characters.
- Confirm safe filenames are generated.
- Upload duplicate names and confirm counters are added.
- Edit a filename manually in the UI.

Follow-up:

- Add AI metadata after deterministic filename cleanup is working.

### Phase 5: AI Image Metadata

Use a local vision model to generate image filenames, alt text, and captions.

Backend tasks:

- Add Ollama client.
- Add image preview generator.
- Add image metadata prompt.
- Send preview image to Ollama.
- Parse JSON response.
- Validate `filename`, `alt_text`, `caption`, and `confidence`.
- Retry once on invalid JSON.
- Store AI result per image.

Frontend tasks:

- Add AI settings toggle.
- Show AI generation progress.
- Show generated filename, alt text, and caption.
- Add regenerate action.

Manual verification:

- Start Ollama locally.
- Pull `llama3.2-vision`.
- Generate metadata for one image.
- Confirm generated JSON fields appear in the UI.
- Confirm invalid AI responses fail visibly.

Follow-up:

- Build review workflow before final exports.

### Phase 6: Review UI

Allow users to review, edit, approve, or regenerate image metadata.

Frontend tasks:

- Add TanStack Table review UI.
- Show preview, original filename, suggested filename, alt text, caption, status, and actions.
- Add inline editable fields.
- Add row action menu.
- Add bulk selection.
- Add accept selected and accept all.
- Add regenerate selected.

Backend tasks:

- Add update image result endpoint.
- Add regenerate image metadata endpoint.
- Add accept image result endpoint.
- Add accept all endpoint.
- Persist edited values.

Manual verification:

- Edit generated metadata.
- Accept one row.
- Accept selected rows.
- Accept all rows.
- Regenerate a single row.

Follow-up:

- Add exports once review state is reliable.

### Phase 7: Export System

Export processed images and metadata reports.

Backend tasks:

- Generate CSV report.
- Generate JSON report.
- Generate XLSX report.
- Package processed images into ZIP.
- Include reports in ZIP.
- Return downloadable files.

Frontend tasks:

- Add export buttons.
- Add export format selector.
- Add download link.
- Show export status.

Manual verification:

- Download CSV report.
- Download JSON report.
- Download XLSX report.
- Download ZIP package.
- Confirm ZIP contains `images/`, `report.csv`, and `report.json`.

Follow-up:

- Start website workflow after image workflow is usable end to end.

### Phase 8: Website Crawler

Crawl websites and extract page content.

Backend tasks:

- Create website job endpoint.
- Support website URL, Basic Auth username/password, max pages, max depth, include paths, and exclude paths.
- Fetch start URL.
- Parse HTML with BeautifulSoup.
- Extract internal links.
- Normalize URLs.
- Restrict crawl to same domain.
- Store page title, meta description, headings, status code, and main text.

Frontend tasks:

- Add website checker form.
- Add auth settings section.
- Add crawl settings section.
- Show crawl progress.
- Display crawled pages table.

Manual verification:

- Crawl a public website.
- Crawl a Basic Auth protected site if available.
- Confirm pages are discovered.
- Confirm page content is extracted.

Follow-up:

- Add broken link checking using crawled pages.

### Phase 9: Broken Link Checker

Detect broken links across crawled pages.

Backend tasks:

- Extract links from crawled pages.
- Classify links as internal or external.
- Deduplicate target URL checks where possible.
- Check HTTP status with timeout handling.
- Detect redirects, unauthorized, forbidden, not found, server errors, timeouts, and invalid URLs.
- Store source page for each link result.

Frontend tasks:

- Add broken links table.
- Add status badges.
- Add filters for broken only, redirects, internal, external, timeouts, and status code.
- Add export broken links action.

Manual verification:

- Run link check on crawled pages.
- Confirm broken links show source page.
- Filter by broken only.
- Export broken link report.

Follow-up:

- Add AI SEO metadata generation after crawl and link data are stable.

### Phase 10: AI SEO Metadata Generator

Generate page summaries, SEO titles, and meta descriptions.

Backend tasks:

- Prepare clean page content for AI.
- Truncate content safely for local model constraints.
- Send SEO metadata prompt to Ollama.
- Parse JSON response.
- Validate `summary`, `seo_title`, `meta_description`, and `confidence`.
- Enforce SEO title under 60 characters.
- Enforce meta description under 160 characters.
- Store generated metadata.

Frontend tasks:

- Add SEO metadata review table.
- Show URL, current title, suggested title, meta description, summary, status, and actions.
- Allow inline editing.
- Add regenerate action.
- Add accept action.

Manual verification:

- Generate SEO metadata for crawled pages.
- Confirm title and meta description length limits.
- Edit generated metadata.
- Accept generated metadata.
- Export SEO metadata report.

Follow-up:

- Harden the POC for demo use.

### Phase 11: POC Hardening

Prepare the POC for demo and stakeholder review.

Backend tasks:

- Improve error handling.
- Add clearer failed job states.
- Add temporary file cleanup.
- Add configurable model name.
- Add configurable Ollama endpoint.
- Improve logging.

Frontend tasks:

- Improve loading states.
- Improve empty states.
- Improve failed states.
- Add settings screen for local defaults.
- Polish dashboard metrics and job history.

Manual verification:

- Run full image workflow from upload to ZIP export.
- Run website workflow from crawl to broken link export.
- Run SEO metadata workflow from crawl to metadata export.
- Confirm failures are visible and understandable.
- Confirm temporary files can be cleaned up.

Follow-up:

- Decide whether to move into beta readiness work.

### Phase 12: Beta Data Persistence

Move metadata persistence from JSON files to a relational database while keeping binary files in file/object storage.

Backend tasks:

- Add PostgreSQL as the beta metadata database.
- Add SQLAlchemy or SQLModel for database models.
- Add Alembic migrations.
- Persist jobs, uploaded files, image results, page results, broken link results, and export records.
- Store file paths or object-storage keys in the database, not binary image contents.
- Keep local file storage as the default file backend until object storage is introduced.
- Add repository/service boundaries so file storage and database writes are coordinated.
- Add startup/config checks for database connectivity.
- Add migration and rollback instructions.

Frontend tasks:

- Keep using existing API contracts where possible.
- Add persistent job history views once backend job records survive restarts.
- Add clearer empty/error states for database-backed history.

Manual verification:

- Run database migrations.
- Upload images and confirm job/file rows are created.
- Restart the backend and confirm job history persists.
- Generate image/page metadata and confirm result rows persist.
- Delete or move a stored file and confirm the API reports a clear missing-file state.

Follow-up:

- Add Redis/background workers for long-running processing after metadata persistence is stable.

## Milestones

### Milestone 1: Basic Image Tool

Includes:

- Project setup
- Image upload
- ZIP upload
- Image validation
- Image compression
- Image conversion
- Filename cleanup
- ZIP export
- CSV report

Acceptance criteria:

- User can upload images.
- User can compress images.
- User can convert images to WebP or JPG.
- User can download processed images.
- User can download a basic CSV report.

### Milestone 2: AI Image Metadata

Includes:

- Ollama integration
- Image preview generation
- AI filename generation
- AI alt text generation
- AI caption generation
- AI JSON validation
- Regenerate metadata action

Acceptance criteria:

- AI returns filename, alt text, and caption.
- Results are displayed in the UI.
- User can regenerate metadata.
- User can edit metadata.

### Milestone 3: Review and Export UI

Includes:

- Editable image metadata table
- Accept and regenerate actions
- Bulk approval
- CSV, JSON, XLSX, and ZIP exports

Acceptance criteria:

- User can review generated metadata.
- User can manually edit fields.
- User can approve selected rows.
- User can export images and reports.

### Milestone 4: Website Crawler

Includes:

- Website URL form
- Basic Auth username/password
- Max pages setting
- Max depth setting
- Internal link discovery
- Page content extraction

Acceptance criteria:

- User can crawl a website.
- Protected websites can be accessed with Basic Auth.
- Crawled pages are listed in the UI.
- Page content is stored for later AI processing.

### Milestone 5: Broken Link Checker

Includes:

- Link extraction
- Internal and external link classification
- HTTP status checking
- Timeout handling
- Broken link report
- Filters
- CSV export

Acceptance criteria:

- Broken links are detected.
- Status codes are displayed.
- Source pages are shown.
- User can filter broken links.
- User can export broken link report.

### Milestone 6: AI SEO Metadata Generator

Includes:

- AI page summary generation
- AI SEO title generation
- AI meta description generation
- Editable review table
- Regeneration action
- Accept action
- Export report

Acceptance criteria:

- AI generates summary, title, and meta description.
- User can edit generated metadata.
- User can approve generated metadata.
- User can export SEO metadata report.

### Milestone 7: POC Hardening

Includes:

- Better error handling
- Loading states
- Failed job states
- Temporary file cleanup
- Configurable model name
- Configurable Ollama endpoint
- Improved UI polish
- Basic logging

Acceptance criteria:

- POC runs consistently on a local machine.
- Failures are visible and understandable.
- Demo workflow works end to end.
- Temporary files are cleaned up.

### Milestone 8: Beta Data Persistence

Includes:

- PostgreSQL
- SQLAlchemy or SQLModel
- Alembic migrations
- Persistent jobs
- Persistent uploaded file records
- Persistent image metadata results
- Persistent website crawl and broken link results
- Persistent export records
- File paths or object keys stored in database rows

Acceptance criteria:

- Jobs persist across backend restarts.
- Uploaded file metadata persists across backend restarts.
- Generated image and SEO metadata persists across backend restarts.
- Binary files remain in file/object storage, not PostgreSQL.
- Database migrations can create and upgrade the schema reliably.

## Build Sequence

1. Create monorepo.
2. Create FastAPI backend.
3. Create Next.js frontend.
4. Build image upload.
5. Build compression.
6. Build conversion.
7. Build filename cleanup.
8. Build ZIP and CSV export.
9. Integrate Ollama.
10. Generate AI image metadata.
11. Build review UI.
12. Build website crawler.
13. Add Basic Auth support.
14. Build broken link checker.
15. Build AI page metadata generator.
16. Add JSON and XLSX exports.
17. Add cleanup and logging.
18. Add PostgreSQL metadata persistence.
19. Prepare Redis/background worker architecture.

## Assumptions

- Project folder and app name: `seo-studio`.
- The POC supports ZIP upload, not direct folder upload.
- AI-generated filenames do not overwrite processed files until user approval.
- Basic Auth credentials are used for crawling only and are not persisted.
- JavaScript-rendered page crawling is out of scope for the POC.
- The SEO metadata generator initially uses the same configured Ollama runtime.
- Brand tone rules are out of scope for the first POC.
- Client-specific export templates are out of scope for the first POC.
- Local file storage plus JSON metadata is enough for the POC.
- PostgreSQL is planned for beta metadata persistence.
- Redis, auth, background workers, and object storage are later beta-readiness items.

## Initial Setup Commands

Backend:

```bash
cd seo-studio/backend
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn python-multipart pillow httpx beautifulsoup4 pandas openpyxl pytest
```

Frontend:

```bash
cd seo-studio
npx create-next-app@latest frontend
cd frontend
npm install @tanstack/react-table react-hook-form zod lucide-react
```

Ollama:

```bash
ollama pull llama3.2-vision
```

## Phase Completion Format

At the end of each phase, provide:

- What changed.
- Commands that were run.
- Automated checks that passed or failed.
- Manual verification steps.
- Known limitations.
- Recommended next phase.
