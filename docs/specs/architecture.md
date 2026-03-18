# mkcv — Architecture Specification

**Version:** 0.2.0
**Date:** 2026-03-18

---

## System Overview

mkcv uses **hexagonal architecture** (ports and adapters) to keep business
logic isolated from infrastructure. Four top-level packages enforce
dependency rules:

```
┌──────────────────────────────────────────────────────────────────────┐
│                         mkcv CLI (Cyclopts)                          │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐  │
│  │  cli/           │  │  config/        │  │  adapters/             │  │
│  │  app.py         │  │  configuration  │  │  factory.py (DI)       │  │
│  │  commands/      │  │  workspace      │  │  filesystem/           │  │
│  │   generate      │  │  settings.toml  │  │  llm/                  │  │
│  │   render        │  │                 │  │  renderers/            │  │
│  │   validate      │  └────────────────┘  └──────────┬─────────────┘  │
│  │   init          │                                  │               │
│  │   themes        │                                  │ implements    │
│  └───────┬────────┘                                  ▼               │
│          │ delegates    ┌──────────────────────────────────────────┐  │
│          └─────────────▶│            core/                         │  │
│                         │  ports/     (LLMPort, RendererPort, ...) │  │
│                         │  services/  (Pipeline, Render, ...)      │  │
│                         │  models/    (Pydantic data models)       │  │
│                         │  exceptions/ (MkcvError hierarchy)       │  │
│                         └──────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

**Dependency rule:** `core/` never imports from `cli/`, `config/`, or
`adapters/`. Services depend only on port Protocols.

---

## Package Architecture

### 1. `cli/` — Command Layer (Cyclopts)

Responsibilities:
- Parse arguments via Cyclopts type annotations
- Apply global options (--verbose, --workspace, --version) in the meta handler
- Discover workspace via `find_workspace_root()` or `--workspace` flag
- Delegate to services created by `adapters/factory.py`
- Handle `MkcvError` with exit codes and user-friendly messages

Commands: `generate`, `render`, `validate`, `init`, `themes`

The CLI contains **no business logic** — it validates inputs and calls services.

### 2. `core/` — Business Logic

Four sub-packages, all framework-free:

**`core/ports/`** — Protocol interfaces that define how services talk to the
outside world:
- `LLMPort` — AI provider calls (`complete`, `complete_structured`)
- `RendererPort` — PDF rendering (`render`)
- `ArtifactStorePort` — Pipeline artifact persistence (`save`, `load`, `create_run_dir`)
- `PromptLoaderPort` — Jinja2 template loading (`load`, `render`, `list_templates`)

**`core/services/`** — Business logic orchestration:
- `PipelineService` — 5-stage resume generation pipeline
- `RenderService` — YAML-to-PDF rendering
- `ValidationService` — ATS compliance checking
- `WorkspaceService` — Workspace initialization and application setup

Services accept port interfaces via constructor injection. They never
instantiate adapters directly.

**`core/models/`** — Pydantic v2 data models. One class per file:
- Pipeline: `JDAnalysis`, `Requirement`, `ExperienceSelection`, `TailoredContent`, `TailoredBullet`, `ReviewReport`, `PipelineResult`
- Resume: `RenderCVResume`, `ResumeCV`, `ResumeDesign`, `ExperienceEntry`, `SkillGroup`
- Workspace: `WorkspaceConfig`, `ApplicationMetadata`

**`core/exceptions/`** — Error hierarchy rooted at `MkcvError`. One class per file.
Each exception carries an `exit_code` for the CLI layer.

### 3. `config/` — Configuration (Dynaconf)

`Configuration` extends `Dynaconf` and loads settings from 5 layers
(later overrides earlier):

1. **Built-in defaults** — `config/settings.toml` bundled with the package
2. **Global user config** — `~/.config/mkcv/settings.toml`
3. **Workspace config** — `mkcv.toml` at workspace root (loaded dynamically)
4. **Environment variables** — `MKCV_` prefix (e.g. `MKCV_RENDERING__THEME`)
5. **CLI flags** — applied at runtime via `settings.set()`

`workspace.py` provides `find_workspace_root()` which walks up from CWD
looking for `mkcv.toml` (similar to how git finds `.git/`).

The `settings` singleton is created on import:
```python
from mkcv.config import settings
theme = settings.rendering.theme
```

### 4. `adapters/` — Infrastructure Implementations

Concrete implementations of core ports:

**`adapters/filesystem/`**:
- `FileSystemArtifactStore` — implements `ArtifactStorePort` (JSON file I/O)
- `FileSystemPromptLoader` — implements `PromptLoaderPort` (Jinja2 templates)
- `WorkspaceManager` — filesystem operations for workspace/application creation

**`adapters/llm/`**:
- `StubLLMAdapter` — test stub (future: `AnthropicAdapter`, `OpenAIAdapter`, etc.)

**`adapters/renderers/`**:
- `StubRenderer` — test stub (future: `RenderCVRenderer`, `WeasyPrintRenderer`)

**`adapters/factory.py`** — Manual DI wiring. Factory functions assemble
fully-wired service instances:
```python
def create_pipeline_service(config) -> PipelineService:
    llm = StubLLMAdapter()  # future: select based on config
    prompts = FileSystemPromptLoader(override_dir=...)
    artifacts = FileSystemArtifactStore()
    return PipelineService(llm=llm, prompts=prompts, artifacts=artifacts)
```

---

## Workspace Model

`mkcv init PATH` creates a workspace:

```
my-workspace/
├── mkcv.toml                    # Workspace config (loaded as layer 3)
├── knowledge-base/
│   ├── career.md                # Career knowledge base
│   └── voice.md                 # Voice/tone guidelines
├── applications/                # One dir per company, one subdir per application
│   └── acme-corp/
│       └── 2026-03-senior-engineer/
│           ├── application.toml # Application metadata
│           ├── jd.txt           # Job description (copied)
│           └── .mkcv/           # Pipeline artifacts
├── templates/                   # User prompt template overrides
└── .gitignore
```

Application directories follow the pattern:
`applications/{company-slug}/{YYYY-MM-position-slug}/`

When `generate` runs inside a workspace, it auto-discovers the workspace
root, loads `mkcv.toml` config, resolves the KB from config, and creates
the application directory structure.

---

## Data Flow

```
JD (text) ──┐
             ├──▶ Stage 1 (Analyze) ──▶ JDAnalysis
KB (md) ────┘                              │
                                           ▼
KB + JDAnalysis ──▶ Stage 2 (Select) ──▶ ExperienceSelection
                                                │
                                                ▼
Selection + JDAnalysis ──▶ Stage 3 (Tailor) ──▶ TailoredContent
                                                       │
                                                       ▼
TailoredContent ──▶ Stage 4 (Structure) ──▶ RenderCVResume (YAML)
                                                  │
                                                  ▼
Resume + KB + JDAnalysis ──▶ Stage 5 (Review) ──▶ ReviewReport
                                                       │
                                                       ▼
Resume YAML ──▶ Render ──▶ resume.pdf + resume.png
```

Each stage output is a Pydantic model validated before passing downstream.
Artifacts are persisted to the `.mkcv/` directory for caching and debugging.

---

## Error Handling

```
MkcvError (exit_code=1)
├── ProviderError (4)
│   ├── RateLimitError (4)     → exponential backoff retry
│   ├── AuthenticationError (4) → fail fast, show config help
│   └── ContextLengthError (4)  → truncate KB or switch model
├── PipelineStageError (5)
├── ValidationError (5)
├── RenderError (6)
├── TemplateError (6)
└── WorkspaceError (7)
    ├── WorkspaceNotFoundError (7)
    └── WorkspaceExistsError (7)
```

The CLI meta handler catches `MkcvError` and exits with the appropriate code.
`KeyboardInterrupt` exits with code 130.

---

## Security

1. **API keys** via env vars (`MKCV_ANTHROPIC_API_KEY`, etc.) — never in config files or logs
2. **Knowledge base** may contain PII — Ollama provides local-only processing
3. **Artifacts** may contain sensitive data — `.mkcv/` is in `.gitignore`
4. **Provider calls** use HTTPS only
5. **No telemetry** without explicit opt-in
