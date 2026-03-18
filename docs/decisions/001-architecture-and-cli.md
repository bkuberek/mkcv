# ADR-001: Architecture and CLI Framework

## Status

Accepted

## Context

mkcv needs to generate resumes through a multi-stage AI pipeline that calls
external LLM providers, renders PDFs, and manages artifacts on disk. We needed
to choose:

1. How to structure the codebase so core logic is testable without real API calls
2. A CLI framework that supports async, modern Python typing, and subcommands
3. A configuration system that layers workspace, user, and environment settings
4. A file organization pattern that scales as the project grows

The initial spec used click for CLI and YAML for configuration. During
implementation, we re-evaluated based on actual needs.

## Decision

### Hexagonal architecture (ports and adapters)

Four top-level packages with a strict dependency rule:

- **`core/`** — Business logic, Pydantic models, Protocol port interfaces,
  custom exceptions. Never imports from `adapters/`, `cli/`, or `config/`.
- **`adapters/`** — Concrete implementations of core ports (filesystem,
  LLM providers, renderers). Depends on `core/`.
- **`cli/`** — Cyclopts command definitions. Delegates to services. No
  business logic.
- **`config/`** — Dynaconf-based configuration. Independent of core.

### Cyclopts for CLI

Chosen over click because:
- Native async support (pipeline stages are async)
- Type-based API using `Annotated` and `cyclopts.Parameter` — aligns with
  Pydantic-first codebase
- Built-in `--version` and `--help` handling
- Meta handler pattern for global options (--verbose, --workspace)

### Dynaconf for configuration

Chosen over plain YAML because:
- Native TOML support (consistent with `pyproject.toml` ecosystem)
- Built-in env var support with `MKCV_` prefix
- Dynamic file loading (for workspace config discovery)
- Validator framework for setting defaults and type checks
- 5-layer resolution: built-in → global user → workspace → env vars → CLI

### Workspace-centric model

`mkcv init PATH` creates a project workspace with:
- `mkcv.toml` for workspace-level configuration
- `knowledge-base/` for career data
- `applications/{company}/{YYYY-MM-position}/` for job applications
- `templates/` for user prompt overrides

Workspace discovery walks up from CWD looking for `mkcv.toml`, similar to git.

### One class per file

Every model, exception, port, and adapter lives in its own file. This keeps
files short, makes git diffs clear, and avoids circular import issues.

### Manual DI via factory functions

`adapters/factory.py` contains factory functions that assemble services with
their adapter dependencies. No DI framework — just functions that create
objects and wire them together. This keeps the dependency graph explicit
and easy to follow.

## Consequences

### Benefits

- Core logic is fully testable with stub adapters — no mocking frameworks needed
- Adding a new LLM provider means implementing `LLMPort` and updating the factory
- CLI changes don't affect business logic
- Workspace model organizes multiple job applications cleanly
- Config layering lets users customize at the right scope

### Trade-offs

- More files than a flat structure (mitigated by consistent naming)
- Factory functions must be updated when adding new adapters
- Workspace discovery adds a small startup cost (walking up directories)
- One-class-per-file can feel verbose for simple types — accepted for consistency
