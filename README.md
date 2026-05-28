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

### Optional AI Metadata

Phase 5 uses Ollama with `moondream` by default:

```bash
ollama pull moondream
ollama serve
```

The backend reads these optional environment variables:

```text
SEO_STUDIO_AI_PROVIDER=ollama
SEO_STUDIO_OLLAMA_BASE_URL=http://localhost:11434
SEO_STUDIO_OLLAMA_MODEL=moondream
SEO_STUDIO_AI_PREVIEW_MAX_WIDTH=1024
```

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
- Ollama/moondream AI image metadata backend
- SEO Metadata page for job-based image metadata generation and review

Next phase: brand document context for AI metadata, followed by dual-model AI metadata and focus-aware crop/resize.
