# Development Guide

Comprehensive guide for developers working on mkcv.

## Prerequisites

- **Python 3.12+** -- mkcv uses modern Python syntax (`match`/`case`, `X | Y` unions)
- **[uv](https://docs.astral.sh/uv/)** -- fast Python package manager

## Environment Setup

```bash
# Clone the repository
git clone https://github.com/bkuberek/mkcv.git
cd mkcv

# Install all dependencies (including dev tools)
uv sync

# Verify the CLI works
uv run mkcv --help
uv run mkcv --version
```

You can also install mkcv as a global tool for development:

```bash
uv tool install -e .
mkcv --help
```

## Project Structure

```
src/mkcv/
├── __init__.py               # Package version (via importlib.metadata)
├── cli/                      # CLI layer (Cyclopts)
│   ├── app.py                # App entry point, global options, meta handler
│   └── commands/             # Subcommands: generate, render, validate, init, themes, status, cover-letter
├── core/                     # Pure business logic (framework-free)
│   ├── exceptions/           # MkcvError hierarchy (one class per file)
│   ├── models/               # Pydantic data models (one class per file)
│   ├── ports/                # Protocol interfaces: LLMPort, RendererPort, etc.
│   └── services/             # Pipeline, Render, Validation, Workspace, Theme, CoverLetter, etc.
├── config/                   # Configuration (Dynaconf)
│   ├── configuration.py      # 5-layer Configuration class
│   ├── workspace.py          # Workspace discovery (find_workspace_root)
│   └── settings.toml         # Built-in defaults
├── adapters/                 # Implementations of core ports
│   ├── factory.py            # DI wiring -- creates fully-assembled services
│   ├── filesystem/           # ArtifactStore, PromptLoader, WorkspaceManager, PyPdfReader
│   ├── llm/                  # Anthropic, OpenAI, Ollama, OpenRouter, Stub adapters + retry
│   └── renderers/            # RenderCV (Typst -> PDF)
└── prompts/                  # Jinja2 templates for each pipeline stage (.j2 files)
```

## Architecture

mkcv uses **hexagonal architecture** (ports and adapters) with strict dependency rules.

### Dependency Flow

```
cli/ --> adapters/factory.py --> core/services/ --> core/ports/ (Protocols)
                                 adapters/       <-- implements ports
```

### Rules

1. **`core/`** is framework-free and never imports from `cli/`, `adapters/`, or `config/`
2. **Services depend only on Protocols** (defined in `core/ports/`), never on concrete adapters
3. **CLI has zero business logic** -- it delegates everything through factory-created services
4. **`adapters/factory.py`** wires dependency injection manually (no DI framework)
5. **One class per file** throughout models, exceptions, ports, and adapters

### Data Flow (Resume Generation)

```
JD + KB --> analyze_jd --> select_experience --> tailor_bullets --> structure_yaml --> review --> render PDF
```

Each pipeline stage uses a configurable LLM provider/model and produces a typed Pydantic model consumed by the next stage.

## Configuration System

Configuration is resolved through 5 layers (later overrides earlier):

| Priority | Source | Location |
|----------|--------|----------|
| 1 (lowest) | Built-in defaults | `src/mkcv/config/settings.toml` |
| 2 | Global user config | `~/.config/mkcv/settings.toml` |
| 3 | Workspace config | `mkcv.toml` in workspace root |
| 4 | Environment variables | `MKCV_` prefix (double underscores for nesting) |
| 5 (highest) | CLI flags | Applied at runtime |

API keys are always set via environment variables: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`.

## Testing

```bash
# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_cli/test_app.py

# Run a specific test by name
uv run pytest -k test_version_flag

# Run with coverage
uv run pytest --cov=mkcv
```

### Test Conventions

- Tests mirror the source layout: `src/mkcv/cli/app.py` --> `tests/test_cli/test_app.py`
- **Mock all external calls** -- tests never hit real LLM providers or external services
- Shared fixtures go in `conftest.py`
- One assertion per test where practical
- Descriptive names: `test_version_flag_prints_version`

## Lint and Type Check

```bash
# Lint (check for issues)
uv run ruff check src/ tests/

# Auto-format
uv run ruff format src/ tests/

# Type check (strict mode)
uv run mypy src/
```

All three must pass before code is merged.

## Code Conventions

### Python Style

- **Python 3.12+** syntax: `match`/`case`, `X | Y` type unions, `type` statements
- Complete type annotations on all functions; `mypy --strict` must pass
- `Pydantic v2 BaseModel` for all structured data
- All AI provider calls and pipeline stages are `async`
- No `print()` -- use `logging` for internals, `rich.console.Console` for CLI output
- Line length: 88 characters (Ruff default)

### Imports

```python
# 1. Standard library
from pathlib import Path

# 2. Third party
import cyclopts
from pydantic import BaseModel

# 3. Local (absolute only, never relative or wildcard)
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.ports.llm import LLMPort
```

### Naming

| Element | Convention | Example |
|---------|-----------|---------|
| Files/modules | `snake_case` | `jd_analysis.py` |
| Classes | `PascalCase` | `JDAnalysis`, `PipelineService` |
| Functions/methods | `snake_case` | `analyze_jd`, `render_pdf` |
| Constants | `UPPER_SNAKE_CASE` | `DEFAULT_TEMPERATURE` |
| Private members | `_` prefix | `_build_prompt` |

### Error Handling

Custom hierarchy rooted at `MkcvError` (each with an `exit_code`):

- `ProviderError` (4) --> `RateLimitError`, `AuthenticationError`, `ContextLengthError`
- `PipelineStageError` (5), `ValidationError` (5)
- `RenderError` (6), `TemplateError` (6)
- `WorkspaceError` (7) --> `WorkspaceNotFoundError`, `WorkspaceExistsError`
- `JDReadError` (2)

Never catch bare `Exception` -- always catch specific exception types.

## Adding New Features

### Adding a CLI Command

1. Create `src/mkcv/cli/commands/your_command.py` with a function decorated for Cyclopts
2. Register it in `src/mkcv/cli/app.py` via `app.command()`
3. Keep the command thin -- delegate all logic to a service

### Adding a Service

1. Define the Protocol (port) in `src/mkcv/core/ports/` if a new interface is needed
2. Create the service in `src/mkcv/core/services/` -- depend only on ports, never adapters
3. Create adapter implementation(s) in `src/mkcv/adapters/`
4. Wire it up in `src/mkcv/adapters/factory.py`

### Adding a Model

1. Create a new file in `src/mkcv/core/models/` (one class per file)
2. Use `pydantic.BaseModel` with full type annotations
3. Add validation via Pydantic validators where appropriate

### Adding an LLM Provider

1. Create a new adapter in `src/mkcv/adapters/llm/` implementing `LLMPort`
2. Register it in the factory's provider resolution logic
3. Add any required config defaults to `src/mkcv/config/settings.toml`

## Reference Documentation

- [Architecture spec](specs/architecture.md)
- [CLI interface spec](specs/cli-interface.md)
- [Data models spec](specs/data-models.md)
- [Architecture decisions](decisions/)
