# AGENTS.md — mkcv

> Instructions for AI coding agents operating in this repository.

## Project Overview

**mkcv** is an AI-powered CLI tool that generates ATS-compliant PDF resumes
tailored to specific job applications. It takes a career knowledge base (Markdown)
+ job description (text) and produces a polished PDF through a 5-stage AI pipeline:
analyze JD, select experience, tailor content, structure YAML, review.

Organized around a **workspace model**: `mkcv init PATH` creates a workspace with
a knowledge base, config, and `applications/{company}/{YYYY-MM-position}/` dirs.

## Tech Stack

- **Python >=3.12** with `uv` for package management
- **Cyclopts** for CLI (native async, modern type-based API)
- **Dynaconf** for configuration (TOML, env vars with `MKCV_` prefix, workspace layering)
- **Pydantic v2** for all data models — never raw dicts
- **asyncio + httpx** for async AI provider calls
- **Jinja2** for prompt templates (`.j2` files in `src/mkcv/prompts/`)
- **RenderCV** (Typst) for PDF rendering, WeasyPrint as secondary
- **pytest + pytest-asyncio** for tests, **ruff** for lint/format, **mypy --strict** for types
- AI providers: Anthropic, OpenAI, Ollama, OpenRouter (provider-agnostic)

## Build / Run / Test

```bash
uv sync                                          # Install dependencies
uv run mkcv --help                               # CLI help
uv run mkcv init ./my-workspace                  # Create workspace
uv run mkcv generate --jd job.txt --kb career.md # Generate resume
uv run pytest                                    # All tests
uv run pytest tests/test_cli/test_app.py         # Single file
uv run pytest -k test_version_flag               # Single test by name
uv run pytest --cov=mkcv                         # With coverage
uv run ruff check src/ tests/                    # Lint
uv run ruff format src/ tests/                   # Format
uv run mypy src/                                 # Type check
```

## Package Structure

```
src/mkcv/
├── cli/                  # Cyclopts commands — no business logic
│   ├── app.py            # App entry point, global options, meta handler
│   └── commands/         # generate, render, validate, init_cmd, themes
├── core/                 # Pure business logic — never imports from adapters
│   ├── exceptions/       # MkcvError hierarchy (one class per file)
│   ├── models/           # Pydantic data models (one class per file)
│   ├── ports/            # Protocol interfaces: LLMPort, RendererPort, etc.
│   └── services/         # Pipeline, Render, Validation, Workspace services
├── config/               # Dynaconf configuration + workspace discovery
│   ├── configuration.py  # 5-layer Configuration class
│   ├── workspace.py      # find_workspace_root(), is_workspace()
│   └── settings.toml     # Built-in defaults
└── adapters/             # Implementations of core ports
    ├── factory.py        # DI wiring — creates fully-assembled services
    ├── filesystem/       # ArtifactStore, PromptLoader, WorkspaceManager
    ├── llm/              # LLM provider adapters (stub, future: anthropic, openai)
    └── renderers/        # PDF rendering adapters (stub, future: rendercv)
```

## Code Style

### Architecture Rules

- **Hexagonal architecture**: core never imports from adapters or cli
- **Services depend only on ports** (Protocol interfaces), never concrete adapters
- **CLI has no business logic** — delegates to services via factory-created instances
- **One class per file** — each model, exception, port, and adapter in its own file
- **Manual DI via factory functions** in `adapters/factory.py`

### General Rules

- Python 3.12+ syntax: `match`/`case`, `X | Y` unions, `type` statements
- Complete type annotations on all functions; `mypy --strict` must pass
- `Pydantic v2 BaseModel` for all structured data
- All AI provider calls and pipeline stages are `async`
- No `print()` — use `logging` for internals, `rich.console.Console` for CLI output
- Line length: ruff defaults (88 chars)

### Imports

```python
# 1. Standard library
from pathlib import Path

# 2. Third party
import cyclopts
from pydantic import BaseModel

# 3. Local
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.ports.llm import LLMPort
```

- Group: stdlib, third-party, local — separated by blank lines
- Absolute imports only (`from mkcv.core.models...`), never relative or wildcard

### Naming

| Element           | Convention         | Example                       |
|-------------------|--------------------|-------------------------------|
| Files/modules     | `snake_case`       | `jd_analysis.py`              |
| Classes           | `PascalCase`       | `JDAnalysis`, `PipelineService` |
| Functions/methods | `snake_case`       | `analyze_jd`, `render_pdf`    |
| Constants         | `UPPER_SNAKE_CASE` | `DEFAULT_TEMPERATURE`         |
| Private members   | `_` prefix         | `_build_prompt`               |

### Error Handling

Custom hierarchy rooted at `MkcvError` (each with `exit_code`):
- `ProviderError` (4) → `RateLimitError`, `AuthenticationError`, `ContextLengthError`
- `PipelineStageError` (5), `ValidationError` (5)
- `RenderError` (6), `TemplateError` (6)
- `WorkspaceError` (7) → `WorkspaceNotFoundError`, `WorkspaceExistsError`

Never catch bare `Exception` — always catch specific types.

### Configuration (5-layer resolution)

1. Built-in defaults (`config/settings.toml` bundled with package)
2. Global user config (`~/.config/mkcv/settings.toml`)
3. Workspace config (`mkcv.toml` in workspace root)
4. Environment variables (`MKCV_` prefix)
5. CLI flags (applied at runtime)

Secrets via env vars: `MKCV_ANTHROPIC_API_KEY`, `MKCV_OPENAI_API_KEY`, etc.

### Testing

- Mirror source layout: `src/mkcv/cli/app.py` → `tests/test_cli/test_app.py`
- Mock all external calls — never hit real providers
- Fixtures in `conftest.py` for shared test data
- One assertion per test where practical
- Descriptive names: `test_version_flag_prints_version`

## Key Design Principles

1. **Hexagonal architecture** — core logic is framework-free and testable in isolation
2. **Workspace-centric** — `mkcv init` creates a project, applications are organized per-company
3. **Pipeline stages are independent** — each can be run, tested, retried in isolation
4. **Provider-agnostic** — switching AI providers is a config change, not a code change
5. **Schema-validated** — all AI outputs validated against Pydantic models before use
6. **Config layering** — 5 layers from built-in defaults to CLI flags

## Reference Documentation

- Architecture: `docs/specs/architecture.md`
- Data models: `docs/specs/data-models.md`
- CLI interface: `docs/specs/cli-interface.md`
- ADRs: `docs/decisions/`
- Product requirements: `docs/product/PRD.md`
