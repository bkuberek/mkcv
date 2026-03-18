# mkcv — Architecture Specification

**Version:** 0.1.0
**Date:** 2026-03-18

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          mkcv CLI                                │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐ │
│  │  CLI Layer    │──▶│  Pipeline    │──▶│  Renderer            │ │
│  │  (click)      │   │  Orchestrator│   │  (RenderCV/Weasy)    │ │
│  └──────────────┘   └──────┬───────┘   └──────────────────────┘ │
│                            │                                     │
│         ┌──────────────────┼──────────────────┐                  │
│         ▼                  ▼                  ▼                  │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────────┐        │
│  │  Provider   │  │  Prompt      │  │  Model           │        │
│  │  Adapters   │  │  Templates   │  │  Validators      │        │
│  │  (AI APIs)  │  │  (Jinja2)    │  │  (Pydantic)      │        │
│  └────────────┘  └──────────────┘  └──────────────────┘        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Artifact Store                          │   │
│  │  (filesystem: .mkcv/ directory per generation run)        │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. CLI Layer (`cli.py`)

Responsibilities:
- Parse CLI arguments and flags
- Load configuration (config file → env vars → CLI flags)
- Orchestrate commands: `generate`, `render`, `validate`, `init`
- Display progress and results to the user
- Handle errors with user-friendly messages

Technology: `click` (preferred over argparse for nested commands and rich help)

### 2. Pipeline Orchestrator (`pipeline/`)

Responsibilities:
- Execute the 5-stage pipeline in sequence
- Manage intermediate artifact persistence
- Support resuming from a specific stage
- Pass context (previous stage outputs) forward through the pipeline
- Enforce stage dependencies

```python
class Pipeline:
    stages: list[PipelineStage]  # ordered list of stages

    async def run(
        self,
        jd: str,
        kb: str,
        from_stage: int = 1,
        output_dir: Path = Path(".mkcv"),
    ) -> PipelineResult:
        """Execute pipeline stages sequentially, persisting artifacts."""
```

Each stage implements a common interface:

```python
class PipelineStage(Protocol):
    name: str
    stage_number: int

    async def execute(self, context: PipelineContext) -> StageOutput:
        """Run this stage and return structured output."""

    def load_cached(self, output_dir: Path) -> StageOutput | None:
        """Load previously computed output, if available."""
```

### 3. Provider Adapters (`providers/`)

Abstract interface for AI model calls:

```python
class Provider(Protocol):
    async def complete(
        self,
        messages: list[Message],
        model: str,
        temperature: float = 0.3,
        response_format: type[BaseModel] | None = None,
    ) -> str | BaseModel:
        """Send a completion request and return the response."""
```

Implementations:
- `AnthropicProvider` — Claude API via `anthropic` SDK
- `OpenAIProvider` — GPT-4o via `openai` SDK
- `OllamaProvider` — Local models via Ollama HTTP API
- `OpenRouterProvider` — Multi-model proxy via OpenRouter API

Provider selection is per-stage via configuration:

```yaml
# ~/.config/mkcv/config.yaml
pipeline:
  stages:
    analyze:
      provider: anthropic
      model: claude-sonnet-4-20250514
      temperature: 0.2
    select:
      provider: anthropic
      model: claude-sonnet-4-20250514
      temperature: 0.3
    tailor:
      provider: anthropic
      model: claude-sonnet-4-20250514
      temperature: 0.5
    structure:
      provider: openai
      model: gpt-4o
      temperature: 0.1
    review:
      provider: anthropic
      model: claude-sonnet-4-20250514
      temperature: 0.3
```

### 4. Prompt Templates (`prompts/`)

All prompts are Jinja2 templates stored as `.j2` files:

```
prompts/
├── analyze_jd.j2         # Stage 1: JD → structured analysis
├── select_experience.j2  # Stage 2: KB + analysis → selected items
├── tailor_bullets.j2     # Stage 3a: selected items → tailored bullets
├── write_mission.j2      # Stage 3b: context → mission statement
├── structure_yaml.j2     # Stage 4: content → RenderCV YAML
├── review.j2             # Stage 5: resume + KB → review report
└── _voice_anchor.j2      # Partial: voice consistency guidelines (included in all writing prompts)
```

Templates receive typed context objects and produce text that is then parsed/validated:

```python
def render_prompt(template_name: str, context: dict) -> str:
    env = Environment(loader=PackageLoader("mkcv", "prompts"))
    template = env.get_template(template_name)
    return template.render(**context)
```

### 5. Model Validators (`models/`)

Every AI output is validated against a Pydantic model before being used downstream:

```python
class JDAnalysis(BaseModel):
    company: str
    role_title: str
    seniority_level: Literal["junior", "mid", "senior", "staff", "principal"]
    core_requirements: list[Requirement]
    technical_stack: list[str]
    ats_keywords: list[str]
    role_summary: str

class TailoredBullet(BaseModel):
    original: str
    rewritten: str
    keywords_incorporated: list[str]
    confidence: Literal["high", "medium", "low"]
```

Validation failures are caught and retried (with the error message fed back to the model):

```python
async def call_with_validation(
    provider: Provider,
    prompt: str,
    model_class: type[T],
    max_retries: int = 2,
) -> T:
    """Call provider and validate output. Retry on validation failure."""
```

### 6. Renderers (`renderers/`)

```python
class Renderer(Protocol):
    def render(self, yaml_path: Path, output_dir: Path) -> RenderedOutput:
        """Render resume YAML to PDF and other formats."""

class RenderedOutput(BaseModel):
    pdf_path: Path
    png_path: Path | None
    md_path: Path | None
    html_path: Path | None
```

Implementations:
- `RenderCVRenderer` — Calls `rendercv render` as subprocess. Primary renderer.
- `WeasyPrintRenderer` — Renders HTML/CSS template with WeasyPrint. Secondary/custom designs.

### 7. Artifact Store

Each pipeline run creates a timestamped directory:

```
.mkcv/
├── 2026-03-18T10-30-00_deepl/
│   ├── input/
│   │   ├── jd.txt                  # Original JD
│   │   └── kb.md                   # Knowledge base used
│   ├── stage1_analysis.json        # JD analysis output
│   ├── stage2_selection.json       # Experience selection
│   ├── stage3_content.json         # Tailored content
│   ├── stage4_resume.yaml          # Structured RenderCV YAML
│   ├── stage5_review.json          # Review report
│   ├── output/
│   │   ├── resume.pdf              # Final PDF
│   │   ├── resume.png              # PNG preview
│   │   └── resume.md               # Markdown version
│   └── meta.json                   # Run metadata (models, timing, cost)
```

---

## Data Flow

```
JD (text) ──┐
             ├──▶ Stage 1 (Analyze) ──▶ jd_analysis.json
KB (md) ────┘                              │
                                           ▼
KB (md) + jd_analysis.json ──▶ Stage 2 (Select) ──▶ selection.json
                                                        │
                                                        ▼
selection.json + jd_analysis.json ──▶ Stage 3 (Tailor) ──▶ tailored_content.json
                                                               │
                                                               ▼
tailored_content.json ──▶ Stage 4 (Structure) ──▶ resume.yaml
                                                      │
                                                      ▼
resume.yaml + KB + jd_analysis ──▶ Stage 5 (Review) ──▶ review_report.json
                                                             │
                                                             ▼
resume.yaml ──▶ Stage 6 (Render) ──▶ resume.pdf + resume.png
```

---

## Error Handling Strategy

### Provider Errors

```python
class MkcvError(Exception): ...
class ProviderError(MkcvError): ...
class RateLimitError(ProviderError): ...    # → exponential backoff retry
class AuthenticationError(ProviderError): ... # → fail fast, show config help
class ContextLengthError(ProviderError): ...  # → truncate KB or switch model
class ValidationError(MkcvError): ...        # → retry with error feedback
class RenderError(MkcvError): ...            # → show YAML validation errors
```

### Retry Strategy

- API rate limits: exponential backoff, 3 retries, max 60s wait
- Validation failures: feed error back to model, 2 retries
- Network errors: 3 retries with 5s delay
- Rendering errors: fail fast (these are deterministic)

---

## Configuration Hierarchy

Resolution order (later overrides earlier):

1. Built-in defaults (in code)
2. Config file (`~/.config/mkcv/config.yaml`)
3. Environment variables (`MKCV_*`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`)
4. CLI flags (`--provider`, `--model`, `--theme`)

```yaml
# ~/.config/mkcv/config.yaml
defaults:
  kb_path: ~/career/knowledge-base.md
  theme: sb2nov
  output_dir: .mkcv

providers:
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}    # env var reference
  openai:
    api_key: ${OPENAI_API_KEY}
  ollama:
    base_url: http://localhost:11434

pipeline:
  stages:
    analyze:
      provider: anthropic
      model: claude-sonnet-4-20250514
    # ... per-stage config

voice:
  guidelines: |
    Direct, not flowery. No "passionate" or "leveraged."
    Concrete over abstract. Technical but accessible.
    Confident but not arrogant.

profiles:
  budget:
    stages:
      analyze: { provider: ollama, model: qwen2.5:32b }
      select: { provider: ollama, model: qwen2.5:72b }
      tailor: { provider: anthropic, model: claude-sonnet-4-20250514 }
      structure: { provider: ollama, model: qwen2.5-coder:32b }
      review: { provider: anthropic, model: claude-sonnet-4-20250514 }
  premium:
    stages:
      analyze: { provider: anthropic, model: claude-sonnet-4-20250514 }
      select: { provider: anthropic, model: claude-sonnet-4-20250514 }
      tailor: { provider: anthropic, model: claude-sonnet-4-20250514 }
      structure: { provider: openai, model: gpt-4o }
      review: { provider: anthropic, model: claude-sonnet-4-20250514 }
```

---

## Security Considerations

1. **API keys** are never stored in the artifact directory or logged
2. **Knowledge base** may contain PII — local-only mode (Ollama) processes KB without sending to cloud
3. **Intermediate artifacts** may contain sensitive data — `.mkcv/` should be in `.gitignore`
4. **Provider calls** use HTTPS only
5. **No telemetry** without explicit opt-in
