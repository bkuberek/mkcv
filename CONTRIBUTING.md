# Contributing to mkcv

Thank you for your interest in contributing to mkcv! This guide will help you get started.

## How to Contribute

1. **Fork** the repository on GitHub
2. **Clone** your fork locally
3. **Create a branch** for your changes (`git checkout -b my-feature`)
4. **Make your changes** following the code style guidelines below
5. **Run tests and linters** to make sure everything passes
6. **Commit** your changes with a descriptive message
7. **Push** to your fork and open a **Pull Request**

## Development Setup

### Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** for package management

### Getting Started

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/mkcv.git
cd mkcv

# Install dependencies
uv sync

# Verify the installation
uv run mkcv --help
```

## Code Style

mkcv uses strict tooling to maintain code quality:

- **Formatter/Linter:** [Ruff](https://docs.astral.sh/ruff/) (line length 88, Python 3.12+ target)
- **Type checker:** [mypy](https://mypy-lang.org/) in strict mode
- **Imports:** Absolute only (`from mkcv.core.models...`), never relative or wildcard
- **Models:** All structured data uses [Pydantic v2](https://docs.pydantic.dev/) `BaseModel`
- **One class per file** for models, exceptions, ports, and adapters
- **No `print()`** -- use `logging` internally, `rich.console.Console` for CLI output
- **Error handling:** Use the custom `MkcvError` hierarchy, never catch bare `Exception`

## Running Tests

```bash
# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_cli/test_app.py

# Run a specific test by name
uv run pytest -k test_version_flag

# Run with coverage report
uv run pytest --cov=mkcv
```

Tests mirror the source layout: `src/mkcv/cli/app.py` maps to `tests/test_cli/test_app.py`. All external calls (LLM providers, filesystem, etc.) must be mocked -- tests never hit real APIs.

## Running Linters

```bash
# Check for lint issues
uv run ruff check src/ tests/

# Auto-format code
uv run ruff format src/ tests/

# Type check (strict mode)
uv run mypy src/
```

All three must pass cleanly before submitting a PR.

## Architecture Overview

mkcv follows **hexagonal architecture** with strict dependency rules:

```
cli/ --> core/services/ --> core/ports/ (Protocol interfaces)
                            adapters/   <-- implements ports
```

| Layer | Path | Role |
|-------|------|------|
| **CLI** | `src/mkcv/cli/` | Command definitions, argument parsing, Rich output -- no business logic |
| **Core** | `src/mkcv/core/` | Services, Pydantic models, Protocol ports, exception hierarchy |
| **Adapters** | `src/mkcv/adapters/` | LLM providers, filesystem, RenderCV renderer |
| **Config** | `src/mkcv/config/` | Dynaconf 5-layer config resolution |

Key rules:
- **`core/`** never imports from `cli/`, `adapters/`, or `config/`
- **Services depend only on Protocols** (ports), never concrete adapters
- **`adapters/factory.py`** wires dependency injection manually -- no framework

For a deeper dive into the architecture and development workflow, see [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Pull Request Guidelines

- **Descriptive title** summarizing the change
- **All tests pass** (`uv run pytest`)
- **Lint clean** (`uv run ruff check src/ tests/`)
- **Format clean** (`uv run ruff format --check src/ tests/`)
- **Type check clean** (`uv run mypy src/`)
- **New features** should include tests
- **Bug fixes** should include a test that demonstrates the fix

## Questions?

If you have questions or need guidance before starting, feel free to open an issue on GitHub.
