# SEO Studio Capstone Project Proposal

Team members:

- Aladenoye Ayobami
- Abel Michael
- Nweke Chigozie

Course: PROG8751 Capstone (Web Development)

Date of submission: May 29, 2026

Instructor: Davneet Chawla

## 1. Problem Statement

Many content teams, web developers, and small businesses need to prepare large sets of images and website metadata before publishing pages. The work is repetitive and error-prone: images must be compressed, converted, renamed, resized, and given useful alt text; websites must be checked for broken links; and pages need clear summaries, titles, and meta descriptions. These tasks are often handled manually across separate tools, which slows down delivery and produces inconsistent SEO and accessibility results.

The problem is especially important for teams that manage brand-sensitive websites. A generic AI caption or filename may describe the image, but it may not match the company's tone, service area, product language, or website context. SEO Studio addresses this by combining image optimization, website checking, and AI-assisted metadata generation in one workflow, with review steps that keep the user in control before exports are finalized.

## 2. Proposed Solution and Key Benefits

SEO Studio is a web-based optimization platform for preparing website images and metadata. Users can upload images or ZIP archives, compress and convert them, clean filenames, generate AI-powered filenames, alt text, captions, and descriptions, review the generated results, and export processed images and reports. The platform also supports website workflows such as crawling pages, checking broken links, generating page summaries, creating SEO titles and meta descriptions, taking website screenshots, and checking bulk URL lists.

A key part of the solution is brand-aware AI generation. Before generating image metadata, users can upload a brand document in `.docx`, `.txt`, or `.pdf` format. The platform extracts useful context from the document and uses it alongside image analysis so generated names, alt text, captions, and descriptions better match the company's website and brand language.

The project will also include an AI focus-aware image resizer. When a user requests a target crop size, the platform should identify the important subject in the image and propose a crop around that focal area. For example, if a brand is about dogs and the uploaded image contains a dog in the bottom-left corner, the crop preview should preserve the dog instead of blindly cropping from the center. Users will preview and approve AI crop suggestions before exporting.

## 3. Project Goals and Scope

High-level goals:

1. Build a usable local POC for image upload, compression, conversion, filename cleanup, and export.
2. Generate AI-powered image metadata that can use brand document context.
3. Implement review workflows so users can edit, approve, regenerate, and download optimized outputs.
4. Add AI focus-aware crop and resize behavior for fixed-dimension website image requirements.
5. Add website quality tools, including crawling, Basic Auth support, broken link checking, screenshots, bulk URL checking, and AI SEO metadata generation.

Out of scope for the first POC:

- Multi-tenant user accounts and permissions.
- Billing and subscriptions.
- Direct CMS publishing.
- Kubernetes or distributed microservices.
- Enterprise-scale crawling and high-volume image processing.
- Automated deployment to customer websites.

## 4. Proposed Technology Stack and Market Relevance

Frontend: Next.js, TypeScript, Tailwind CSS, shadcn/ui-style components, TanStack Query, TanStack Table, and lucide-react. This stack is relevant because React and Next.js are widely used in modern web development, while TanStack Query and Table support production-quality data workflows and review screens.

Backend: FastAPI with Python 3.11+, Pillow, httpx, BeautifulSoup4, pandas, and openpyxl. FastAPI provides strong API documentation through OpenAPI/Swagger, while Python has mature image processing, web crawling, data export, and AI integration libraries.

AI runtime: Ollama for local development, with support for vision and language models. The architecture will allow a vision model to analyze images and focal points, while a language model generates brand-aligned filenames, alt text, captions, and descriptions.

Data and storage: Local file storage and JSON metadata for the POC, with PostgreSQL planned for beta persistence. This keeps the POC lightweight while leaving a clear path toward persistent job history, uploaded file records, and generated metadata records.

## 5. Preliminary Timeline by Sprint Milestones

| Sprint | Internal focus | Official due date |
|---|---|---|
| Sprint 1 | Project setup, documented FastAPI APIs, dashboard shell, image upload, image validation, ZIP upload, compression, conversion, filename cleanup, and initial exports. | June 20, 2026 at 4:59 AM |
| Sprint 2 | Brand document upload and extraction, local AI integration, AI image metadata generation, metadata review UI, regenerate actions, and improved image export flow. | July 11, 2026 at 4:59 AM |
| Sprint 3 | AI focus-aware crop and resize workflow, crop preview and approval, website crawler, Basic Auth support, broken link checker, and bulk URL checker. | August 1, 2026 at 4:59 AM |
| Sprint 4 | Website screenshot tool, AI SEO metadata generator, CSV/JSON/XLSX/ZIP export hardening, demo reliability, cleanup, logging, technical summary, and final showcase preparation. | August 15, 2026 at 4:59 AM |

The team plans to complete the main implementation work between June and the end of July, while using the official sprint dates as checkpoints for demonstration, grading, and final showcase readiness.

## 6. Team Charter

Roles and responsibilities:

| Area | Owner(s) |
|---|---|
| Frontend | Ayobami |
| Backend | Michael |
| Database management | Michael and Chigozie |
| Documentation | Chigozie |
| Quality assurance | Ayobami and Chigozie |

Communication plan: The team will use WhatsApp for regular communication and quick coordination. Tasks will be tracked in a GitHub Projects board so sprint work, blockers, and completed items are visible to the full team.

Conflict resolution: The team will first discuss disagreements in WhatsApp and compare options against project scope, sprint goals, technical risk, and user value. If a decision is still unresolved, the team will use majority agreement and document the rationale in the relevant GitHub issue or task.

## 7. Links

GitHub repository: https://github.com/iobami/seo-studio
