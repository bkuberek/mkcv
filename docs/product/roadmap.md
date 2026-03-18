# mkcv — Product Roadmap

**Date:** 2026-03-18

---

## Phase Overview

```
Phase 1: CLI Tool        ← WE ARE HERE
Phase 2: Web Service API
Phase 3: Web Application
Phase 4: Mobile App
```

---

## Phase 1: CLI Tool (MVP)

**Goal:** A working CLI that generates tailored, ATS-compliant PDF resumes from a knowledge base + job description.

**Timeline:** 2-4 weeks

### Milestones

#### M1.1: Rendering Pipeline (Week 1)
- [ ] Project scaffolding (pyproject.toml, uv, src layout)
- [ ] RenderCV integration: YAML → PDF rendering
- [ ] Base YAML template with the creator's career data
- [ ] `mkcv render` command working end-to-end
- [ ] Theme selection (sb2nov, classic, moderncv)

#### M1.2: AI Pipeline — Core (Week 2)
- [ ] Provider abstraction layer (Anthropic, OpenAI, Ollama, OpenRouter)
- [ ] Stage 1: JD analysis
- [ ] Stage 2: Experience selection
- [ ] Stage 3: Content tailoring + mission statement
- [ ] Stage 4: YAML structuring
- [ ] `mkcv generate` command working end-to-end

#### M1.3: Quality & Polish (Week 3)
- [ ] Stage 5: Review + ATS compliance check
- [ ] Confidence scoring on generated bullets
- [ ] Intermediate artifact persistence (JSON files per stage)
- [ ] Config file support (~/.config/mkcv/config.yaml)
- [ ] Error handling and retry logic for API calls

#### M1.4: Iteration & UX (Week 4)
- [ ] Resume from specific stage (`--from-stage 3`)
- [ ] Interactive mode (review and edit between stages)
- [ ] Provider profiles (budget vs premium)
- [ ] Documentation and README
- [ ] Test suite with mocked API calls

### Deliverables
- `mkcv generate --jd <file> --kb <file>` → `resume.yaml` + `review_report.json`
- `mkcv render <file>` → `resume.pdf` + `resume.png`
- `mkcv validate <file>` → ATS compliance report

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
