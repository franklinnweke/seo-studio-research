# Sprint 1 Demo Checklist and Evidence

## Sprint Goal

Show a reliable local image optimization workflow from upload to processed download.

## Completed Work

- FastAPI backend scaffold with health check, CORS, settings, logging, and storage folders.
- Swagger UI, ReDoc, and canonical OpenAPI contract.
- Next.js dashboard shell with navigation to active image workflows.
- Image and ZIP upload endpoint with safe ZIP extraction.
- Frontend image upload UI with validation and progress feedback.
- Image compression, output format conversion, metadata stripping, and filename cleanup.
- Processed image ZIP export.
- Dockerfile and Docker Compose local runtime.

## Demo Script

1. Start the local app with `./scripts/dev.sh`.
2. Open `http://127.0.0.1:3000`.
3. Open Image Optimizer.
4. Upload one PNG/JPG/WebP image and one ZIP archive containing images.
5. Confirm unsupported files are rejected with a clear error.
6. Process images with default quality `80`, metadata stripping enabled, and original format.
7. Switch output format to WebP or JPG and process again.
8. Confirm cleaned filenames and processed file sizes appear in the results table.
9. Download one processed image.
10. Download the processed image ZIP export.
11. Open `http://127.0.0.1:8000/docs` and confirm the documented API routes.

## Rubric Evidence

### Goal Achievement and Quality

- Upload, validation, processing, conversion, filename cleanup, and ZIP export are implemented.
- User-facing flows exist in the dashboard and Image Optimizer page.
- Backend returns typed API responses and clear validation errors.

### Process, Documentation, and Version Control

- Project plan, sprint milestone plan, and capstone proposal are committed under `docs/`.
- GitHub PR history shows incremental merged work for metadata, brand context, CSV export, sprint planning, and Docker support.
- Sprint progress is summarized in `docs/project-sprint-progress.csv`.

### Technical Complexity and Effort

- Multipart uploads and ZIP extraction are validated server-side.
- Pillow handles image processing, resizing, conversion, transparency flattening, and metadata stripping.
- FastAPI exposes typed OpenAPI contracts.
- Frontend uses Next.js, TanStack Query, Axios progress events, and typed API helpers.

## Test Evidence

- Backend: `cd backend && .venv/bin/pytest` returned `48 passed`.
- Frontend lint: `cd frontend && npm run lint` passes after cleanup.
- Frontend build: `cd frontend && npm run build` passes when run outside the sandbox.

## Known Limitations

- Website crawler and broken-link workflows are planned for Sprint 3 and remain placeholder-only.
- Persisted review approvals are planned for Sprint 3.
- GitHub Project board access requires refreshing the GitHub CLI token with `read:project` scope before project-board verification.

## Next Sprint Carryover

- Persist metadata edits and approvals.
- Complete crop review persistence.
- Implement website job creation, crawler, and broken-link checking.
- Harden CSV/JSON/XLSX report exports.
