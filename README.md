# seo-studio

AI-powered image and website optimization platform POC.

## Local Development

Start both backend and frontend from the project root:

```bash
./scripts/dev.sh
```

This script:

- Creates the backend virtual environment if missing.
- Installs backend dependencies when requirements change.
- Installs frontend dependencies if `node_modules` is missing.
- Starts FastAPI on `http://127.0.0.1:8000`.
- Starts Next.js on `http://127.0.0.1:3000`.
- Stops both servers when you press `Ctrl+C`.

### Backend

```bash
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

### Frontend

```bash
cd frontend
npm install
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open:

```text
http://127.0.0.1:3000
```

## Docker

Run both services with Docker Compose:

```bash
docker compose up --build
```

This starts:

- FastAPI backend on `http://localhost:11502`
- Next.js frontend on `http://localhost:11501`

Build a single service image directly:

```bash
docker build --target backend -t seo-studio-backend .
docker build --target frontend -t seo-studio-frontend .
```

### Optional AI Metadata

Phase 5+ can use Ollama with a dual-model setup:

```bash
ollama pull qwen2.5vl:3b
ollama serve
```

The backend reads these optional environment variables:

```text
SEO_STUDIO_AI_PROVIDER=ollama
SEO_STUDIO_OLLAMA_BASE_URL=http://localhost:11434
SEO_STUDIO_OLLAMA_MODEL=qwen2.5vl:3b
SEO_STUDIO_VISION_MODEL=qwen2.5vl:3b
SEO_STUDIO_LANGUAGE_MODEL=qwen2.5vl:3b
SEO_STUDIO_OLLAMA_TIMEOUT_SECONDS=600
SEO_STUDIO_AI_LANGUAGE_TIMEOUT_SECONDS=120
SEO_STUDIO_AI_CROP_TIMEOUT_SECONDS=120
SEO_STUDIO_AI_PREVIEW_MAX_WIDTH=1024
```

The vision model inspects image content and crop targets. The language model turns verified visual facts and optional brand context into filenames, alt text, and captions.

## Checks

Backend:

```bash
cd backend
.venv/bin/pytest
```

Export the canonical OpenAPI contract:

```bash
cd backend
.venv/bin/python scripts/export_openapi.py
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

## Current Phase

Implemented phases:

- FastAPI backend scaffold
- Health endpoint
- CORS configuration
- Swagger UI at `/docs`
- ReDoc at `/redoc`
- Canonical OpenAPI contract at `/openapi.json`
- Exported contract at `shared/api-contracts/openapi.json`
- Storage folders
- Base backend module structure
- Next.js frontend scaffold
- Dashboard shell
- Sidebar navigation
- Frontend API health utility
- Axios API client
- TanStack Query provider
- Image and ZIP upload endpoint
- Image upload UI with progress
- Safe ZIP extraction and image validation
- Compression settings UI with quality slider
- Image compression endpoint
- Processed image output under `backend/app/storage/processed/{job_id}`
- Working Image Optimizer page
- Output format conversion selector
- JPG/WebP/PNG conversion support
- PNG transparency flattening for JPG output
- Filename cleanup with editable output filename stems
- Processed image ZIP download
- Ollama dual-model AI image metadata backend
- SEO Metadata page for job-based image metadata generation and review
- Selected metadata ZIP download with renamed images and `report.csv`

Next phase: continue focus-aware crop/resize hardening, then review and export flows.
