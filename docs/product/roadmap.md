# mkcv — Product Roadmap

**Date:** 2026-03-18<br>

---

## Phase Overview

```
Phase 1: CLI Tool        ← WE ARE HERE (core complete, iterating)
Phase 2: Web Service API
Phase 3: Web Application
Phase 4: Mobile App
```

---

## Phase 1: CLI Tool (MVP)

**Goal:** A working CLI that generates tailored, ATS-compliant PDF resumes from a knowledge base + job description.

### Milestones

#### M1.1: Rendering Pipeline ✅
- [x] Project scaffolding (pyproject.toml, uv, src layout)
- [x] Hexagonal architecture (core/ports/adapters, one class per file)
- [x] RenderCV integration: YAML → PDF rendering (Typst engine)
- [x] `mkcv render` command working end-to-end (PDF, PNG, MD, HTML)
- [x] Theme selection (sb2nov and RenderCV built-in themes)

#### M1.2: AI Pipeline — Core ✅
- [x] Provider abstraction layer (Anthropic, OpenAI, configurable StubLLM)
- [x] Stage 1: JD analysis (structured extraction via tool_use/JSON mode)
- [x] Stage 2: Experience selection
- [x] Stage 3: Content tailoring + mission statement
- [x] Stage 4: YAML structuring
- [x] `mkcv generate` command working end-to-end
- [x] Workspace model (`mkcv init`, applications/{company}/{YYYY-MM-position}/)

#### M1.3: Quality & Polish ✅
- [x] Stage 5: Review + ATS compliance check
- [x] Confidence scoring on generated bullets (high/medium/low)
- [x] Intermediate artifact persistence (JSON files per stage)
- [x] Dynaconf config (5-layer: built-in → global → workspace → env → CLI)
- [x] Error handling hierarchy (MkcvError + 12 specific exception types)
- [x] Exponential backoff retry for rate-limited API calls
- [x] Per-stage provider/model/temperature selection

#### M1.4: Iteration & UX ✅
- [x] Resume from specific stage (`--from-stage 3`)
- [x] Interactive mode (`--interactive` — pause after each stage for review)
- [x] Prompt tuning — XYZ bullet formula, voice guidelines, ATS keyword strategy
- [x] `mkcv validate` command — LLM-powered resume quality review
- [x] Test suite: 284 tests with mocked API calls, ruff + mypy --strict clean

#### M1.5: Remaining Work (Next)
- [ ] Ollama adapter — local model support for offline/budget usage
- [ ] Cost tracking — token counts from adapters, cost calculation in pipeline
- [ ] Prompt iteration with real JDs (ongoing quality improvement)
- [ ] Update outdated docs (research.md references old architecture)

### Deliverables
- `mkcv generate --jd <file> --kb <file>` → `resume.yaml` + `review_report.json` + auto-rendered PDF
- `mkcv render <file>` → `resume.pdf` + `resume.png` + `resume.md` + `resume.html`
- `mkcv validate <file> [--jd <file>]` → ATS compliance + quality report
- `mkcv init [path]` → workspace with KB templates, config, application dirs

---

## Phase 2: Web Service API

**Goal:** Expose mkcv as a REST/GraphQL API that can power multiple frontends.

**Timeline:** 4-6 weeks after Phase 1

### Key Features
- FastAPI service wrapping the CLI pipeline
- Async job processing (pipeline runs as background task)
- Webhook/SSE for pipeline progress updates
- File upload for KB and JD documents
- PDF download endpoint
- API key authentication
- Rate limiting and usage metering
- Docker Compose deployment (API + Typst renderer)

### API Surface (Draft)

```
POST   /api/v1/generate          # Start pipeline: JD + KB → job ID
GET    /api/v1/jobs/{id}         # Poll job status + progress
GET    /api/v1/jobs/{id}/result  # Download artifacts (YAML, PDF, review)
POST   /api/v1/render            # Render a YAML file to PDF
POST   /api/v1/validate          # ATS compliance check
GET    /api/v1/themes            # List available themes
```

### Infrastructure
- FastAPI + uvicorn
- Redis for job queue (or PostgreSQL with pg_notify)
- S3-compatible storage for artifacts (MinIO for self-hosted)
- Docker Compose for local dev and deployment

---

## Phase 3: Web Application

**Goal:** A polished web UI for non-CLI users to generate and manage resumes.

**Timeline:** 6-8 weeks after Phase 2

### Key Features
- Knowledge base editor (rich Markdown editor)
- JD input (paste, upload, or URL)
- Real-time pipeline progress visualization
- Side-by-side: YAML editor + live PDF preview
- Inline bullet editing with AI suggestions
- Theme gallery and customization
- Resume history and versioning
- Job application tracker (link resumes to applications)
- Export: PDF, DOCX, PNG, Markdown

### Tech Stack (Tentative)
- Next.js or React + Vite
- TailwindCSS
- Monaco editor (for YAML/Markdown editing)
- PDF.js for in-browser preview
- Auth: Auth0 or Clerk
- Database: PostgreSQL

---

## Phase 4: Mobile App

**Goal:** Generate and manage resumes on the go; quick-apply workflow.

**Timeline:** TBD (after Phase 3 is stable)

### Key Features
- View and share existing resumes
- Quick-generate from saved KB + pasted JD
- Push notifications when pipeline completes
- Camera: photograph a job posting → OCR → generate resume
- Share directly to email or job board apps

### Tech Stack (Tentative)
- React Native or Expo
- Shared API backend from Phase 2

---

## Future Features (Backlog)

| Feature | Phase | Notes |
|---------|-------|-------|
| Cover letter generation | 2+ | Same pipeline, different output template |
| LinkedIn profile optimizer | 3+ | Analyze LinkedIn vs KB, suggest improvements |
| Job board integrations | 3+ | Auto-fill applications on Greenhouse, Lever, etc. |
| A/B resume testing | 3+ | Generate variants, track which gets more callbacks |
| Multi-user / team support | 3+ | Recruiters managing multiple candidate resumes |
| Analytics dashboard | 3+ | Track applications, response rates, keyword trends |
| Community themes | 2+ | User-contributed RenderCV/Typst themes |
| Automatic JD scraping | 2+ | Paste URL → extract JD text automatically |
| Interview prep generation | 2+ | Generate tailored interview prep from JD + KB |
| Salary benchmarking | 3+ | Levels.fyi integration for comp data |
