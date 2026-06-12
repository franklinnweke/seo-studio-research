# Sprint Milestone Plan

This plan maps SEO Studio work to the Sprint Milestone Evaluation rubric for Sprints 1-3. It is designed to be mirrored in GitHub Issues, Milestones, and a GitHub Project board.

## Rubric Targets

### Goal Achievement and Quality

Target: every sprint has demoable user workflows, acceptance criteria, and recorded evidence.

Evidence to attach to issues:

- Screenshots or short screen recordings of completed flows.
- API responses or Swagger screenshots for backend work.
- Test command output.
- PR links showing reviewed, merged work.
- Known limitations listed before the demo.

### Process, Documentation, and Version Control

Target: GitHub shows steady progress from all team members.

Team rules:

- Each sprint task must be represented by a GitHub issue.
- Every issue must have an owner, sprint milestone, labels, acceptance criteria, and demo evidence.
- Each PR should reference its issue with `Closes #issue-number`.
- Commit messages should describe the change, not only the file touched.
- At least one documentation update should land per sprint.
- Sprint review notes should be added to the sprint milestone issue before the demo.

### Technical Complexity and Effort

Target: sprint goals should show full-stack work, AI integration, file processing, API design, and export/reporting complexity.

Evidence to highlight:

- FastAPI route contracts and OpenAPI docs.
- Image processing behavior with Pillow.
- AI metadata generation and retry handling.
- Brand context extraction from TXT/DOCX/PDF.
- CSV/ZIP export generation.
- Frontend state management, review UI, and error handling.

## GitHub Project Setup

Create one GitHub Project named:

```text
SEO Studio Sprint Board
```

Recommended fields:

| Field | Type | Values |
|---|---|---|
| Status | Single select | Backlog, Ready, In Progress, Review, Done, Blocked |
| Sprint | Single select | Sprint 1, Sprint 2, Sprint 3 |
| Area | Single select | Frontend, Backend, AI, Docs, QA |
| Rubric | Single select | Goal Quality, Process Docs VC, Technical Complexity |
| Priority | Single select | P0, P1, P2 |
| Story Points | Number | 1, 2, 3, 5, 8 |
| Demo Evidence | Text | Link to screenshot, video, PR, or notes |

Recommended views:

- Board by `Status`.
- Table grouped by `Sprint`.
- Table grouped by `Area`.
- Table filtered to `Rubric = Process Docs VC`.
- Done view filtered to `Status = Done`.

## Labels

Create these labels in GitHub:

| Label | Purpose |
|---|---|
| `sprint-1` | Sprint 1 work |
| `sprint-2` | Sprint 2 work |
| `sprint-3` | Sprint 3 work |
| `area:frontend` | Frontend implementation |
| `area:backend` | Backend implementation |
| `area:ai` | AI model and prompt work |
| `area:docs` | Documentation and planning |
| `area:qa` | Testing and demo validation |
| `type:feature` | New user-facing capability |
| `type:bug` | Defect or regression |
| `type:chore` | Maintenance/setup work |
| `type:docs` | Documentation-only work |
| `priority:p0` | Required for sprint demo |
| `priority:p1` | Important for sprint goal |
| `priority:p2` | Nice-to-have |
| `rubric:goal-quality` | Supports completed goals and polished demo |
| `rubric:process-docs-vc` | Supports Scrum, docs, commits, GitHub evidence |
| `rubric:technical-complexity` | Supports challenging technical work |

## Milestones

Create these GitHub milestones:

### Sprint 1 - Image Optimization Foundation

Demo goal: show a reliable image optimization workflow from upload to processed download.

Rubric focus:

- Goal quality: image upload, validation, compression, conversion, filename cleanup, ZIP export.
- Process: documented API and committed OpenAPI contract.
- Technical complexity: multipart upload, ZIP extraction, Pillow processing, file persistence.

### Sprint 2 - AI Metadata and Brand Context

Demo goal: show brand-aware AI image metadata generation and CSV export from the metadata table.

Rubric focus:

- Goal quality: generated filenames, alt text, captions, regenerate flow, CSV export.
- Process: issue-driven frontend/backend/AI work with test evidence.
- Technical complexity: Ollama integration, prompt design, JSON validation/retry, TXT/DOCX/PDF extraction.

### Sprint 3 - Crop Review and Website Quality Tools

Demo goal: show fixed-size image resizing/crop review and the first website quality workflow.

Rubric focus:

- Goal quality: crop review, editable review UI, website crawl/broken-link path.
- Process: sprint review notes and demo checklist attached to milestone.
- Technical complexity: crop math, AI crop suggestions, crawler/link checking, export hardening.

## Sprint 1 Issue Plan

| Issue title | Owner | Area | Points | Acceptance criteria |
|---|---|---:|---:|---|
| Project setup and local dev script | Backend | Backend | 3 | Backend and frontend start locally from documented commands. Health endpoint returns OK. |
| FastAPI OpenAPI baseline | Backend | Backend | 5 | `/docs`, `/redoc`, and `/openapi.json` are available. Routes have summaries and typed responses. |
| Dashboard shell and navigation | Frontend | Frontend | 3 | App shell loads, dashboard displays implementation queue, active tools link to pages. |
| Image and ZIP upload API | Backend | Backend | 8 | JPG/PNG/WebP and ZIP uploads create image jobs. Unsupported files fail clearly. |
| Image upload UI with progress | Frontend | Frontend | 5 | Users can upload images/ZIP files and see accepted files, progress, and validation errors. |
| Compression, conversion, and filename cleanup | Full stack | Backend | 8 | Users can process images with quality, resize, output format, metadata stripping, and safe filenames. |
| Processed image ZIP export | Backend | Backend | 3 | Processed images download as a ZIP archive. |
| Sprint 1 demo checklist and notes | QA/Docs | Docs | 2 | Demo steps, screenshots, known limitations, and test output are documented. |

## Sprint 2 Issue Plan

| Issue title | Owner | Area | Points | Acceptance criteria |
|---|---|---:|---:|---|
| Ollama image metadata service | AI/Backend | AI | 8 | Backend generates filename, alt text, caption, and confidence for an uploaded image. Invalid JSON retries once. |
| SEO Metadata page and review table | Frontend | Frontend | 8 | Users can load a job, generate metadata, view statuses, inspect details, and regenerate one image. |
| Brand context document upload | Backend | Backend | 5 | TXT, DOCX, and PDF brand files are accepted, extracted, truncated, and stored with the job. |
| Brand context UI | Frontend | Frontend | 5 | Users can upload brand documents, see attached files, and preview extracted context. |
| Metadata image download with SEO filename | Backend | Backend | 3 | Download uses processed image if available and applies generated or requested SEO filename. |
| AI metadata CSV export | Full stack | Frontend | 5 | Users can choose visible metadata table columns and download a CSV export. |
| Hydration-safe workspace state | Frontend | Frontend | 2 | Workspace active job state no longer causes hydration mismatch. |
| Sprint 2 demo checklist and notes | QA/Docs | Docs | 2 | Demo includes brand context, AI generation, CSV export, test output, and limitations. |

## Sprint 3 Issue Plan

| Issue title | Owner | Area | Points | Acceptance criteria |
|---|---|---:|---:|---|
| Natural-language resize instruction parser | Backend | Backend | 5 | Backend converts common resize instructions into editable settings. |
| Exact crop and fit-inside processing | Backend | Backend | 8 | Backend supports exact target dimensions, fit-inside padding, crop boxes, and no-upscale behavior. |
| AI crop suggestion endpoint | AI/Backend | AI | 8 | Backend can request subject-aware crop suggestions and returns warnings on AI failure. |
| Image resizer UI | Frontend | Frontend | 8 | Users can upload/load image jobs, parse instructions, review crop needs, and process resized outputs. |
| Persist edited metadata and approvals | Full stack | Backend | 8 | Users can save metadata edits, approve rows, and reload persisted review state. |
| Website crawler skeleton | Backend | Backend | 5 | Website job endpoint and same-domain crawl data model are in place. |
| Broken link checker skeleton | Backend | Backend | 5 | Link status checking path exists with clear placeholder/demo behavior or basic implementation. |
| Export hardening for reports | Backend | Backend | 5 | CSV/JSON/XLSX report direction is documented or partially implemented with clear API contracts. |
| Sprint 3 demo checklist and notes | QA/Docs | Docs | 2 | Demo script covers crop workflow, website-quality progress, test results, and risks. |

## Definition of Ready

An issue is ready for sprint work when it has:

- Sprint milestone.
- Owner.
- Area label.
- Rubric label.
- Acceptance criteria.
- Demo evidence expectation.
- Clear dependency notes.

## Definition of Done

An issue is done when:

- Acceptance criteria are met.
- Relevant tests or manual verification are documented.
- Screenshots/API evidence are attached when user-facing.
- The PR is linked to the issue.
- Any known limitations are recorded.
- The issue is moved to `Done` before sprint review.

## Sprint Review Template

Use this template in each sprint milestone issue or project notes field:

```md
## Sprint Goal

## Completed Work

## Demo Script

## Rubric Evidence

### Goal Achievement and Quality

### Process, Documentation, and Version Control

### Technical Complexity and Effort

## Test Evidence

## Known Limitations

## Next Sprint Carryover
```

## Current Status Snapshot

As of June 12, 2026:

- Sprint 1 foundation work is largely complete.
- Sprint 2 AI metadata and brand context work is largely complete.
- AI metadata CSV export is implemented on branch `codex/ai-metadata-csv-export`.
- Sprint 3 should focus on crop review completion, persisted review approvals, and the first website quality workflow.
- GitHub CLI authentication currently needs refresh before automated Project/Milestone creation can run from the terminal.
