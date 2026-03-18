# AGENTS.md — mkcv

> Instructions for AI coding agents operating in this repository.

## Project Overview

**mkcv** is an AI-powered resume generation tool that produces stunning, ATS-compliant PDF resumes tailored to specific job applications. It takes a career knowledge base + job description as input and outputs a polished PDF through a multi-stage AI pipeline.

**Current phase:** CLI tool (Phase 1)
**Future phases:** Web service API (Phase 2), Web app (Phase 3), Mobile app (Phase 4)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12+ |
| Package manager | `uv` (preferred) or `pip` |
| CLI framework | `click` |
| AI providers | Anthropic (Claude), OpenAI (GPT-4o), Ollama (local), OpenRouter |
| PDF rendering | RenderCV (Typst engine) via subprocess, WeasyPrint as secondary |
| Data format | YAML (RenderCV schema) and JSON (intermediate pipeline stages) |
| Validation | Pydantic v2 for all data models |
| Configuration | YAML config file + environment variables |
| Testing | pytest, pytest-asyncio |
| Linting | ruff |
| Type checking | mypy (strict mode) |
| Async | asyncio + httpx for API calls |

## Directory Structure

```
mkcv/
├── AGENTS.md                  # This file
├── README.md                  # User-facing documentation
├── pyproject.toml             # Project config, dependencies, scripts
├── docs/
│   ├── product/               # Product requirements, research, roadmap
│   │   ├── PRD.md
│   │   ├── research.md
│   │   └── roadmap.md
│   └── specs/                 # Technical specifications
│       ├── architecture.md
│       ├── cli-interface.md
│       └── data-models.md
├── src/
│   └── mkcv/
│       ├── __init__.py
│       ├── cli.py             # Click CLI entrypoint
│       ├── pipeline/          # 5-stage AI pipeline
│       │   ├── __init__.py
│       │   ├── analyze.py     # Stage 1: JD analysis
│       │   ├── select.py      # Stage 2: Experience selection
│       │   ├── tailor.py      # Stage 3: Content tailoring
│       │   ├── structure.py   # Stage 4: YAML assembly
│       │   └── review.py      # Stage 5: Quality review
│       ├── providers/         # AI model provider adapters
│       │   ├── __init__.py
│       │   ├── base.py        # Abstract provider interface
│       │   ├── anthropic.py   # Claude API
│       │   ├── openai.py      # OpenAI API
│       │   ├── ollama.py      # Local Ollama
│       │   └── openrouter.py  # OpenRouter proxy
│       ├── renderers/         # PDF rendering backends
│       │   ├── __init__.py
│       │   ├── rendercv.py    # RenderCV/Typst renderer
│       │   └── weasyprint.py  # HTML/CSS renderer (secondary)
│       ├── models/            # Pydantic data models
│       │   ├── __init__.py
│       │   ├── knowledge_base.py
│       │   ├── jd_analysis.py
│       │   ├── resume.py
│       │   └── review.py
│       ├── prompts/           # Prompt templates (Jinja2)
│       │   ├── analyze_jd.j2
│       │   ├── select_experience.j2
│       │   ├── tailor_bullets.j2
│       │   ├── write_mission.j2
│       │   ├── structure_yaml.j2
│       │   └── review.j2
│       └── config.py          # Configuration loading
├── tests/
│   ├── conftest.py
│   ├── test_pipeline/
│   ├── test_providers/
│   ├── test_renderers/
│   └── test_models/
└── templates/                 # RenderCV theme templates
    └── default/
```

## Build / Run / Test Commands

```bash
# Install dependencies
uv sync

# Run CLI
uv run mkcv --help
uv run mkcv generate --jd job.txt --kb career.md
uv run mkcv render resume.yaml

# Run all tests
uv run pytest

# Run a single test
uv run pytest tests/test_pipeline/test_analyze.py::test_extracts_requirements

# Run tests with coverage
uv run pytest --cov=mkcv

# Lint
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type check
uv run mypy src/
```

## Code Style Guidelines

### General

- **Python 3.12+** — use modern syntax (match/case, type unions with `|`, etc.)
- **Strict typing** — all functions have type annotations; `mypy --strict` must pass
- **Pydantic v2** for all data models — never use raw dicts for structured data
- **async by default** — all AI provider calls are async; pipeline stages are async
- **No print statements** — use `logging` or `click.echo` for CLI output

### Imports

```python
# Standard library
from pathlib import Path

# Third party
import click
from pydantic import BaseModel

# Local
from mkcv.models.resume import Resume
from mkcv.pipeline.analyze import analyze_jd
```

- Group imports: stdlib → third-party → local, separated by blank lines
- Use absolute imports from `mkcv.*`
- Never use wildcard imports (`from x import *`)

### Naming Conventions

- Files/modules: `snake_case.py`
- Classes: `PascalCase` (e.g., `JDAnalysis`, `ResumeBuilder`)
- Functions/methods: `snake_case` (e.g., `analyze_jd`, `render_pdf`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_TEMPERATURE`, `MAX_BULLET_LENGTH`)
- Type aliases: `PascalCase` (e.g., `ProviderConfig = dict[str, Any]`)
- Private: prefix with `_` (e.g., `_build_prompt`)

### Error Handling

- Use custom exception hierarchy rooted at `MkcvError`
- Provider errors: `ProviderError`, `RateLimitError`, `AuthenticationError`
- Pipeline errors: `PipelineStageError`, `ValidationError`
- Rendering errors: `RenderError`, `TemplateError`
- Never catch bare `Exception` — always catch specific types
- All errors should include actionable messages for CLI users

### Testing

- Test files mirror source structure: `src/mkcv/pipeline/analyze.py` → `tests/test_pipeline/test_analyze.py`
- Use pytest fixtures for common test data (sample JDs, KBs, resumes)
- Mock all external API calls — never hit real providers in tests
- One assertion per test function where practical
- Test names describe behavior: `test_extracts_skills_from_bulleted_jd`

### Configuration

- **Environment variables** for secrets: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OLLAMA_BASE_URL`
- **YAML config file** (`~/.config/mkcv/config.yaml`) for preferences: default models, temperature, theme
- **CLI flags** override config file; config file overrides env vars
- Never hardcode API keys, model names, or file paths

### Prompts

- All prompts live in `src/mkcv/prompts/` as Jinja2 templates (`.j2` files)
- Prompts are never hardcoded in Python files
- Each prompt template has a corresponding Pydantic model for its expected output
- Include a voice consistency anchor in all writing-stage prompts

### Key Design Principles

1. **Pipeline stages are independent** — each can be run, tested, and retried in isolation
2. **Intermediate outputs are persisted** — every stage writes its output to disk for debugging
3. **Provider-agnostic** — switching from Claude to GPT-4o is a config change, not a code change
4. **Schema-validated** — all AI outputs are validated against Pydantic models before proceeding
5. **Human-in-the-loop friendly** — pipeline can pause after any stage for human review
6. **ATS compliance is a first-class concern** — rendering rules are enforced, not just documented
