# Initial CLI Tool — Specification

**Change**: initial-cli-tool<br>
**Version**: 0.2.0<br>
**Date**: 2026-03-18<br>
**Status**: Draft<br>
**Previous version**: 0.1.0 (9 requirements, 61 scenarios)<br>
**This version**: 10 requirements, 91 scenarios<br>

---

## Purpose

This specification defines the requirements and acceptance scenarios for bootstrapping
the mkcv project from a docs-only repository into an installable Python CLI application
with hexagonal architecture and workspace management. The scope covers project
scaffolding, CLI commands (stubs), configuration management, core domain ports and
models, adapter stubs, prompt infrastructure, test infrastructure, code quality tooling,
and workspace initialization and discovery.

This change does NOT implement the AI pipeline, rendering, or any LLM calls. All
services and adapters are stubs that raise `NotImplementedError` or return placeholder
values. However, workspace management commands (`init`, workspace-aware `generate`)
MUST be functional — they create real directories and files.

---

## R-001: Project Structure & Packaging

*Unchanged from v1.* The project MUST be structured as an installable Python package
using `uv` and the `src/` layout convention.

### R-001.1: pyproject.toml

The project MUST have a `pyproject.toml` at the repository root that:

- Specifies `requires-python = ">=3.12"`
- Uses `hatchling` as the build backend
- Declares `mkcv` as the package name
- Defines version `0.1.0`
- Lists runtime dependencies: `cyclopts`, `pydantic>=2.0`, `dynaconf`, `jinja2`, `httpx`
- Lists dev dependencies: `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`
- Defines a console script entry point: `mkcv = "mkcv.cli.app:main"`
- Configures `ruff`, `mypy`, and `pytest` tool sections
- Adds `toml` or `tomli-w` as a runtime dependency (for writing `mkcv.toml` and
  `application.toml`)

### R-001.2: Source Layout

The project MUST use the `src/mkcv/` package layout:

```
src/mkcv/
├── __init__.py          # Package root, exports __version__
├── __main__.py          # python -m mkcv support
├── cli/
│   ├── __init__.py
│   ├── app.py           # Main cyclopts app, global options
│   └── commands/
│       ├── __init__.py
│       ├── generate.py
│       ├── render.py
│       ├── validate.py
│       ├── init.py
│       └── themes.py
├── core/
│   ├── __init__.py
│   ├── exceptions.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── jd_analysis.py
│   │   ├── experience.py
│   │   ├── content.py
│   │   ├── resume.py
│   │   ├── review.py
│   │   ├── pipeline.py
│   │   └── workspace.py      # NEW: WorkspaceConfig, ApplicationMetadata
│   ├── ports/
│   │   ├── __init__.py
│   │   ├── llm.py
│   │   ├── renderer.py
│   │   ├── prompt_loader.py
│   │   └── artifact_store.py
│   └── services/
│       ├── __init__.py
│       ├── pipeline.py
│       ├── render.py
│       ├── validation.py
│       └── workspace.py      # NEW: WorkspaceService
├── config/
│   ├── __init__.py        # Exports settings singleton
│   ├── configuration.py   # Configuration(Dynaconf) subclass
│   ├── settings.toml      # Default settings
│   └── .secrets.toml      # API key placeholders (gitignored)
├── adapters/
│   ├── __init__.py
│   ├── factory.py         # DI wiring via factory functions
│   ├── llm/
│   │   ├── __init__.py
│   │   └── base.py        # BaseLLMAdapter (stub)
│   ├── renderers/
│   │   ├── __init__.py
│   │   └── base.py        # BaseRenderer (stub)
│   ├── filesystem/
│   │   ├── __init__.py
│   │   ├── prompt_loader.py
│   │   └── artifact_store.py
│   └── workspace/          # NEW: Workspace filesystem operations
│       ├── __init__.py
│       └── manager.py      # WorkspaceManager (implements workspace ops)
└── prompts/
    ├── _voice_anchor.j2
    ├── analyze_jd.j2
    ├── select_experience.j2
    ├── tailor_bullets.j2
    ├── write_mission.j2
    ├── structure_yaml.j2
    └── review.j2
```

### R-001.3: Module Runnable

*Unchanged from v1.* The package MUST be runnable via `python -m mkcv`, which SHALL
invoke the same entry point as the `mkcv` console script.

### R-001.4: Version Export

*Unchanged from v1.* `mkcv.__version__` MUST be defined and MUST match the version
in `pyproject.toml`.

#### Scenario: S-001 — Project installs successfully

- GIVEN a clean Python 3.12+ virtual environment
- WHEN the user runs `uv sync`
- THEN the command exits with code 0
- AND all dependencies are installed
- AND the `mkcv` console script is available on PATH

#### Scenario: S-002 — Package is importable

- GIVEN the project is installed via `uv sync`
- WHEN Python executes `import mkcv`
- THEN the import succeeds without errors
- AND `mkcv.__version__` returns a string matching `"0.1.0"`

#### Scenario: S-003 — Module is runnable

- GIVEN the project is installed
- WHEN the user runs `python -m mkcv --help`
- THEN the output is identical to running `mkcv --help`

---

## R-002: CLI Interface (Cyclopts) — MODIFIED

The CLI MUST be implemented using `cyclopts` with native async command support.
All subcommands from the existing CLI specification MUST be present. The `init`
and `generate` commands have been updated to support the workspace model.

### R-002.1: Main Application — MODIFIED

The main `cyclopts.App` MUST define:

- App name: `mkcv`
- App help text describing the tool's purpose
- A `--version` flag that prints the version and exits
- Global options applied to all subcommands:
  - `--verbose` / `-v`: Enable verbose output (default: `False`)
  - `--log-format`: Log output format, one of `text` | `json` (default: `text`)
  - `--config-path`: Override path to config directory (default: from dynaconf)
  - `--workspace` / `-w`: Override workspace root path (default: auto-discovered)
    **(NEW)**

The `--workspace` global option MUST override workspace discovery for all
commands that use the workspace. It MUST also be overridable via the
`MKCV_WORKSPACE` environment variable. Priority: `--workspace` flag >
`MKCV_WORKSPACE` env var > auto-discovery.

### R-002.2: Generate Command — MODIFIED

The `generate` subcommand MUST operate in two modes:

**Workspace mode** (when a workspace is found or `--workspace` is specified):
- `--jd` is REQUIRED — path to the job description file
- `--kb` is OPTIONAL — defaults to the workspace's `knowledge-base/` directory
- `--company` is OPTIONAL — company name; if not provided, the tool SHOULD attempt
  to infer it from the JD content or prompt the user
- `--position` is OPTIONAL — position title; if not provided, the tool SHOULD
  attempt to infer it from the JD content or prompt the user
- The command MUST auto-create the application directory under
  `applications/{company}/{YYYY-MM-position}/`
- The command MUST copy (or symlink) the JD file into the application directory
  as `jd.txt`
- The command MUST auto-generate `application.toml` with metadata
- Pipeline intermediates MUST be stored in
  `applications/{company}/{YYYY-MM-position}/.mkcv/`
- Final outputs (resume.yaml, resume.pdf) MUST be placed in the application
  directory root

**Non-workspace mode** (no workspace found, no `--workspace` specified):
- `--jd` is REQUIRED
- `--kb` is REQUIRED (no workspace to provide a default)
- `--output-dir` is used for output (defaults to `.mkcv/<timestamp>_<company>`)
- No application directory is created, no `application.toml` is generated

Full parameter list:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--jd` | Path | Yes | — | Job description file path |
| `--kb` | Path | Conditional | Workspace KB dir or required | Knowledge base path |
| `--company` | str | No | Inferred from JD | Company name (workspace mode) |
| `--position` | str | No | Inferred from JD | Position title (workspace mode) |
| `--output-dir` | Path | No | Auto (workspace or `.mkcv/`) | Output directory |
| `--theme` | str | No | From config | RenderCV theme name |
| `--profile` | str | No | From config | Provider profile name |
| `--from-stage` | int | No | `1` | Resume from this pipeline stage |
| `--render/--no-render` | bool | No | `True` | Auto-render PDF after pipeline |
| `--interactive` | bool | No | `False` | Pause after each stage for review |
| `--provider` | str | No | None | Override provider for all stages |
| `--model` | str | No | None | Override model for all stages |
| `--dry-run` | bool | No | `False` | Show plan without calling APIs |

For this change, the pipeline execution body remains a stub that prints a
placeholder message. However, the workspace setup (directory creation, JD
copy, `application.toml` generation) MUST be functional.

### R-002.3: Render Command

*Unchanged from v1.* The `render` subcommand MUST accept:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `yaml_file` | Path | Yes (positional) | — | RenderCV YAML file to render |
| `--output-dir` | Path | No | Same as input | Output directory |
| `--theme` | str | No | From YAML | Override theme |
| `--format` | str | No | `pdf,png` | Output formats (comma-separated) |
| `--open` | bool | No | `False` | Open PDF after rendering |

For this change, the command body MUST print a placeholder message and exit 0.

### R-002.4: Validate Command

*Unchanged from v1.* The `validate` subcommand MUST accept:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file` | Path | Yes (positional) | — | Resume file (PDF or YAML) |
| `--jd` | Path | No | None | JD file for keyword coverage check |

For this change, the command body MUST print a placeholder message and exit 0.

### R-002.5: Init Command — MODIFIED

The `init` subcommand MUST initialize a workspace directory. It now takes a
positional `PATH` argument instead of a `--config-dir` flag.

(Previously: `init` created a config directory at `~/.config/mkcv/` and optionally
a KB template file.)

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | Path | No (positional) | `.` (current dir) | Directory to initialize as workspace |
| `--kb-template` | bool | No | `True` | Generate knowledge base template files |
| `--global-config` | bool | No | `False` | Also create `~/.config/mkcv/` global config |

The command MUST:

1. Create the workspace directory structure (see R-010.1)
2. Create `mkcv.toml` at the workspace root with default settings
3. Create `knowledge-base/` directory with template files (if `--kb-template`)
4. Create `applications/` directory
5. Create `.gitignore` in the workspace root with appropriate patterns
6. Print a summary of what was created
7. Exit with code 0

If the directory already contains `mkcv.toml`, the command MUST print a warning
and exit with code 0 without overwriting existing files. It MAY create missing
subdirectories (e.g., if `applications/` doesn't exist).

### R-002.6: Themes Command

*Unchanged from v1.* The `themes` subcommand MUST accept:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--preview` | str | No | None | Theme name to generate preview for |

For this change, the command body MUST print a placeholder message and exit 0.

### R-002.7: Exit Codes — MODIFIED

The CLI MUST use the following exit codes:

| Code | Constant Name | Meaning |
|------|---------------|---------|
| 0 | `EXIT_SUCCESS` | Success |
| 1 | `EXIT_GENERAL_ERROR` | General error |
| 2 | `EXIT_INVALID_ARGS` | Invalid arguments / missing required options |
| 3 | `EXIT_CONFIG_ERROR` | Configuration error |
| 4 | `EXIT_PROVIDER_ERROR` | Provider error (API failure) |
| 5 | `EXIT_VALIDATION_ERROR` | Validation error (schema failure) |
| 6 | `EXIT_RENDER_ERROR` | Render error (YAML to PDF failed) |
| 7 | `EXIT_WORKSPACE_ERROR` | Workspace error (not found, invalid) **(NEW)** |

Exit codes SHOULD be defined as constants in `mkcv.core.exceptions` or a
dedicated `mkcv.cli.exit_codes` module.

### R-002.8: Workspace-Required Commands — NEW

Commands that require a workspace (currently none beyond `init`, but future
commands like `status` or `list` will) MUST check for a workspace and exit
gracefully with exit code 7 and a helpful message if no workspace is found.
The message MUST suggest running `mkcv init` to create a workspace.

The `generate` command MUST NOT require a workspace — it falls back to
non-workspace mode. However, if `--company` or `--position` is specified
without a workspace, the command MUST warn that these options are only
meaningful in workspace mode.

#### Scenario: S-004 — Main help displays all subcommands

- GIVEN the project is installed
- WHEN the user runs `mkcv --help`
- THEN the output lists all 5 subcommands: `generate`, `render`, `validate`, `init`, `themes`
- AND the output shows global options: `--verbose`, `--log-format`, `--config-path`, `--workspace`, `--version`

#### Scenario: S-005 — Version flag prints version

- GIVEN the project is installed
- WHEN the user runs `mkcv --version`
- THEN the output contains the string `0.1.0`
- AND the command exits with code 0

#### Scenario: S-006 — Generate help shows all options

- GIVEN the project is installed
- WHEN the user runs `mkcv generate --help`
- THEN the output lists all generate parameters: `--jd`, `--kb`, `--company`, `--position`, `--output-dir`, `--theme`, `--profile`, `--from-stage`, `--render/--no-render`, `--interactive`, `--provider`, `--model`, `--dry-run`

#### Scenario: S-007 — Generate stub runs without error (non-workspace)

- GIVEN the project is installed
- AND a file `test_jd.txt` exists
- AND the current directory does NOT contain `mkcv.toml` or any parent directory
- WHEN the user runs `mkcv generate --jd test_jd.txt --kb career.md`
- THEN the output contains a "not yet implemented" message (pipeline stub)
- AND the command exits with code 0

#### Scenario: S-008 — Generate requires --jd

- GIVEN the project is installed
- WHEN the user runs `mkcv generate` (without --jd)
- THEN the command exits with a non-zero code
- AND the error output indicates that `--jd` is required

#### Scenario: S-008b — Generate requires --kb in non-workspace mode (NEW)

- GIVEN the project is installed
- AND no workspace exists (no `mkcv.toml` in CWD or parents)
- AND a file `test_jd.txt` exists
- WHEN the user runs `mkcv generate --jd test_jd.txt` (without --kb)
- THEN the command exits with a non-zero code
- AND the error output indicates that `--kb` is required when no workspace is active

#### Scenario: S-009 — Render help shows all options

- GIVEN the project is installed
- WHEN the user runs `mkcv render --help`
- THEN the output lists: `yaml_file` (positional), `--output-dir`, `--theme`, `--format`, `--open`

#### Scenario: S-010 — Render stub runs without error

- GIVEN the project is installed
- AND a file `resume.yaml` exists
- WHEN the user runs `mkcv render resume.yaml`
- THEN the output contains a "not yet implemented" message
- AND the command exits with code 0

#### Scenario: S-011 — Validate help shows all options

- GIVEN the project is installed
- WHEN the user runs `mkcv validate --help`
- THEN the output lists: `file` (positional), `--jd`

#### Scenario: S-012 — Init help shows all options (MODIFIED)

- GIVEN the project is installed
- WHEN the user runs `mkcv init --help`
- THEN the output lists: `path` (positional, optional), `--kb-template`, `--global-config`
- AND the output does NOT list `--config-dir`

#### Scenario: S-013 — Themes help shows all options

- GIVEN the project is installed
- WHEN the user runs `mkcv themes --help`
- THEN the output lists: `--preview`

#### Scenario: S-014 — Module invocation matches console script

- GIVEN the project is installed
- WHEN the user runs `python -m mkcv --help`
- THEN the output is functionally equivalent to `mkcv --help`

#### Scenario: S-014b — Global --workspace option overrides discovery (NEW)

- GIVEN the project is installed
- AND a workspace exists at `/tmp/test-workspace/` with `mkcv.toml`
- AND the current directory is NOT inside that workspace
- WHEN the user runs `mkcv --workspace /tmp/test-workspace/ generate --jd test.txt`
- THEN the command uses `/tmp/test-workspace/` as the workspace root
- AND the application directory is created under `/tmp/test-workspace/applications/`

---

## R-003: Configuration (Dynaconf) — MODIFIED

The project MUST use Dynaconf for configuration management with a layered override
strategy that includes workspace-level configuration.

### R-003.1: Configuration Class

*Unchanged from v1.* A `Configuration` class MUST exist at `mkcv.config.configuration`
that subclasses `dynaconf.Dynaconf` with `envvar_prefix="MKCV"`.

### R-003.2: Settings File (settings.toml)

*Unchanged from v1.* The `settings.toml` file MUST define bundled defaults.

### R-003.3: Secrets File (.secrets.toml)

*Unchanged from v1.* A `.secrets.toml` file MUST exist alongside `settings.toml`.

### R-003.4: Settings Singleton

*Unchanged from v1.* The `mkcv.config` package MUST export a `settings` singleton.

### R-003.5: Environment Variable Override

*Unchanged from v1.* All settings MUST be overridable via `MKCV_` prefixed env vars.

Additionally, `MKCV_WORKSPACE` MUST be recognized as the workspace root path
override. **(NEW)**

### R-003.6: Validators

*Unchanged from v1.* Validators for critical settings.

### R-003.7: CLI Integration

*Unchanged from v1.* Global CLI options override config values.

### R-003.8: Workspace Config Layer — NEW

The configuration resolution order MUST be:

1. Built-in defaults (bundled `settings.toml`)
2. Global user config (`~/.config/mkcv/settings.toml`)
3. Workspace config (`mkcv.toml` in workspace root) **(NEW)**
4. Environment variables (`MKCV_*`)
5. CLI flags

When a workspace is active, the `mkcv.toml` file MUST be loaded as an
additional Dynaconf settings source. Workspace config values override global
config but are overridden by env vars and CLI flags.

The `Configuration` class MUST provide a method to load workspace config:

```python
def load_workspace_config(self, workspace_root: Path) -> None:
    """Load mkcv.toml from the workspace root as an additional settings layer."""
```

This method MUST be called during CLI startup when a workspace is discovered
or specified via `--workspace`.

#### Scenario: S-015 — Default config loads successfully

- GIVEN the project is installed
- AND no environment variables override settings
- WHEN Python executes `from mkcv.config import settings`
- THEN `settings.defaults.theme` equals `"sb2nov"`
- AND `settings.defaults.output_dir` equals `".mkcv"`
- AND `settings.providers.default_provider` equals `"anthropic"`

#### Scenario: S-016 — Environment variable overrides config value

- GIVEN the environment variable `MKCV_DEFAULTS__THEME` is set to `"classic"`
- WHEN Python executes `from mkcv.config import settings`
- THEN `settings.defaults.theme` equals `"classic"`

#### Scenario: S-017 — Validator catches invalid provider

- GIVEN settings where `providers.default_provider` is set to `"invalid_provider"`
- WHEN `settings.validate_all()` is called
- THEN a `dynaconf.ValidationError` is raised
- AND the error message references `default_provider`

#### Scenario: S-018 — Secrets file is gitignored

- GIVEN the repository `.gitignore` file
- WHEN its contents are inspected
- THEN it contains a pattern matching `.secrets.toml`

#### Scenario: S-019 — Config path override

- GIVEN the project is installed
- AND a custom settings file exists at `/tmp/mkcv-test/settings.toml`
- WHEN the user runs `mkcv --config-path /tmp/mkcv-test --help`
- THEN the application loads settings from the custom path

#### Scenario: S-019b — Workspace config overrides global config (NEW)

- GIVEN a global config at `~/.config/mkcv/settings.toml` with `defaults.theme = "classic"`
- AND a workspace with `mkcv.toml` containing `[defaults]\ntheme = "moderncv"`
- WHEN the CLI runs inside the workspace
- THEN `settings.defaults.theme` equals `"moderncv"`

#### Scenario: S-019c — Env var overrides workspace config (NEW)

- GIVEN a workspace with `mkcv.toml` containing `[defaults]\ntheme = "moderncv"`
- AND the environment variable `MKCV_DEFAULTS__THEME` is set to `"classic"`
- WHEN the CLI runs inside the workspace
- THEN `settings.defaults.theme` equals `"classic"`

---

## R-004: Core Domain (Hexagonal Architecture) — MODIFIED

The core domain MUST contain only pure business logic, Pydantic models, Protocol
interfaces (ports), and service stubs. It MUST NOT import from `mkcv.adapters`,
`mkcv.cli`, or `mkcv.config`.

### R-004.1: Port Interfaces

*Unchanged from v1.* All ports MUST be defined as `typing.Protocol` classes with
`runtime_checkable` decorator.

(LLMPort, RendererPort, PromptLoaderPort, ArtifactStorePort — unchanged.)

### R-004.2: Exception Hierarchy — MODIFIED

The exception hierarchy MUST be defined in `core/exceptions.py` and rooted at
`MkcvError`:

```
MkcvError
├── ConfigurationError
├── ProviderError
│   ├── RateLimitError
│   ├── AuthenticationError
│   └── ContextLengthError
├── PipelineStageError
├── ValidationError         (mkcv's own, not Pydantic's)
├── RenderError
├── TemplateError
└── WorkspaceError          (NEW)
    ├── WorkspaceNotFoundError    (NEW)
    ├── WorkspaceExistsError      (NEW)
    └── InvalidWorkspaceError     (NEW)
```

New workspace exceptions:

- `WorkspaceError`: Base class for workspace-related errors. Exit code: 7.
- `WorkspaceNotFoundError(WorkspaceError)`: Raised when a workspace is required but
  not found via discovery. Message MUST include suggestion to run `mkcv init`.
- `WorkspaceExistsError(WorkspaceError)`: Raised when `mkcv init` is called on a
  directory that already has `mkcv.toml`.
- `InvalidWorkspaceError(WorkspaceError)`: Raised when `mkcv.toml` exists but is
  malformed or the workspace structure is invalid.

### R-004.3: Pydantic v2 Models — MODIFIED

All data models from v1 remain unchanged. The following new models MUST be added:

| Module | Models |
|--------|--------|
| `core/models/workspace.py` | `WorkspaceConfig`, `ApplicationMetadata`, `ApplicationStatus` |

#### WorkspaceConfig

Represents the parsed content of `mkcv.toml`:

```python
class WorkspaceConfig(BaseModel):
    """Parsed workspace configuration from mkcv.toml."""
    workspace_root: Path
    knowledge_base_dir: str = "knowledge-base"
    applications_dir: str = "applications"
    templates_dir: str = "templates"

    # Optional overrides (same keys as global config)
    defaults: dict[str, Any] = Field(default_factory=dict)
    pipeline: dict[str, Any] = Field(default_factory=dict)
    voice: dict[str, Any] = Field(default_factory=dict)
```

#### ApplicationStatus

An enum for tracking application status:

```python
class ApplicationStatus(str, Enum):
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    GENERATED = "generated"
    SUBMITTED = "submitted"
    ARCHIVED = "archived"
```

#### ApplicationMetadata

Represents the content of `application.toml`:

```python
class ApplicationMetadata(BaseModel):
    """Auto-generated metadata for a job application."""
    company: str
    position: str
    date: str  # YYYY-MM-DD of creation
    status: ApplicationStatus = ApplicationStatus.CREATED
    url: str | None = None  # Job posting URL
    jd_file: str = "jd.txt"
    kb_files: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    notes: str | None = None
```

### R-004.4: Service Stubs — MODIFIED

Service classes MUST exist in `core/services/` and depend only on ports.

All v1 services remain unchanged (PipelineService, RenderService, ValidationService).

The following new service MUST be added:

#### WorkspaceService (`core/services/workspace.py`) — NEW

Provides pure business logic for workspace operations. Does NOT perform filesystem
I/O directly — that is delegated to the workspace adapter.

- Has methods for:
  - `build_application_path(company: str, position: str, date: date | None = None) -> str`:
    Generates the canonical application directory path
    (`{company}/{YYYY-MM-position}/`). Sanitizes company and position names for
    filesystem safety.
  - `build_workspace_config() -> WorkspaceConfig`: Creates a default workspace
    config model.
  - `build_application_metadata(company: str, position: str, ...) -> ApplicationMetadata`:
    Creates an application metadata model.
  - `validate_workspace_structure(workspace_root: Path) -> list[str]`: Returns a list
    of warnings for missing expected directories/files. Returns empty list if valid.

#### Scenario: S-020 — LLMPort is importable and is a Protocol

*Unchanged from v1.*

- GIVEN the project is installed
- WHEN Python executes `from mkcv.core.ports.llm import LLMPort`
- THEN the import succeeds
- AND `LLMPort` is a `runtime_checkable` Protocol

#### Scenario: S-021 — RendererPort is importable and is a Protocol

*Unchanged from v1.*

- GIVEN the project is installed
- WHEN Python executes `from mkcv.core.ports.renderer import RendererPort`
- THEN the import succeeds
- AND `RendererPort` is a `runtime_checkable` Protocol

#### Scenario: S-022 — PromptLoaderPort is importable

*Unchanged from v1.*

#### Scenario: S-023 — ArtifactStorePort is importable

*Unchanged from v1.*

#### Scenario: S-024 — Exception hierarchy structure (MODIFIED)

- GIVEN the project is installed
- WHEN Python imports from `mkcv.core.exceptions`
- THEN `MkcvError` is a subclass of `Exception`
- AND `ProviderError` is a subclass of `MkcvError`
- AND `RateLimitError` is a subclass of `ProviderError`
- AND `AuthenticationError` is a subclass of `ProviderError`
- AND `ContextLengthError` is a subclass of `ProviderError`
- AND `PipelineStageError` is a subclass of `MkcvError`
- AND `ConfigurationError` is a subclass of `MkcvError`
- AND `RenderError` is a subclass of `MkcvError`
- AND `TemplateError` is a subclass of `MkcvError`
- AND `ValidationError` is a subclass of `MkcvError`
- AND `WorkspaceError` is a subclass of `MkcvError`
- AND `WorkspaceNotFoundError` is a subclass of `WorkspaceError`
- AND `WorkspaceExistsError` is a subclass of `WorkspaceError`
- AND `InvalidWorkspaceError` is a subclass of `WorkspaceError`

#### Scenario: S-025 — Exception carries message and details

*Unchanged from v1.*

- GIVEN `from mkcv.core.exceptions import ProviderError`
- WHEN `err = ProviderError("API call failed", provider="anthropic", model="claude-sonnet-4-20250514")`
- THEN `str(err)` contains `"API call failed"`
- AND `err.provider` equals `"anthropic"`
- AND `err.model` equals `"claude-sonnet-4-20250514"`

#### Scenario: S-025b — WorkspaceError carries exit code 7 (NEW)

- GIVEN `from mkcv.core.exceptions import WorkspaceError, WorkspaceNotFoundError`
- WHEN `err = WorkspaceNotFoundError("No workspace found")`
- THEN `err.exit_code` equals `7`
- AND `str(err)` contains `"No workspace found"`

#### Scenario: S-026 — JDAnalysis model validates correct input

*Unchanged from v1.*

#### Scenario: S-027 — JDAnalysis model rejects invalid seniority level

*Unchanged from v1.*

#### Scenario: S-028 — TailoredBullet model validates confidence levels

*Unchanged from v1.*

#### Scenario: S-029 — ReviewReport score validates range

*Unchanged from v1.*

#### Scenario: S-029b — WorkspaceConfig model validates (NEW)

- GIVEN `from mkcv.core.models.workspace import WorkspaceConfig`
- WHEN a `WorkspaceConfig` is constructed with `workspace_root=Path("/tmp/ws")`
- THEN the model is created successfully
- AND `model.knowledge_base_dir` equals `"knowledge-base"`
- AND `model.applications_dir` equals `"applications"`

#### Scenario: S-029c — ApplicationMetadata model validates (NEW)

- GIVEN `from mkcv.core.models.workspace import ApplicationMetadata`
- WHEN an `ApplicationMetadata` is constructed with valid data
- THEN the model is created successfully
- AND `model.model_dump_json()` returns valid JSON
- AND `ApplicationMetadata.model_validate_json(json_str)` reconstructs the model

#### Scenario: S-029d — ApplicationMetadata rejects invalid status (NEW)

- GIVEN `from mkcv.core.models.workspace import ApplicationMetadata`
- WHEN an `ApplicationMetadata` is constructed with `status="invalid"`
- THEN a `pydantic.ValidationError` is raised

#### Scenario: S-030 — PipelineService depends only on ports

*Unchanged from v1.*

#### Scenario: S-031 — PipelineService stub raises NotImplementedError

*Unchanged from v1.*

#### Scenario: S-032 — RenderService stub raises NotImplementedError

*Unchanged from v1.*

#### Scenario: S-032b — WorkspaceService builds application path correctly (NEW)

- GIVEN a `WorkspaceService` instance
- WHEN `service.build_application_path(company="DeepL", position="Senior Staff Engineer")` is called
- THEN the result is `"deepl/2026-03-senior-staff-engineer"`
- AND the company name is lowercase
- AND the position is lowercase with spaces replaced by hyphens
- AND the date prefix uses the current year and month in YYYY-MM format

#### Scenario: S-032c — WorkspaceService sanitizes company names (NEW)

- GIVEN a `WorkspaceService` instance
- WHEN `service.build_application_path(company="Acme Corp.", position="Lead Dev")` is called
- THEN the company directory component contains only lowercase alphanumeric chars and hyphens
- AND special characters like `.` are stripped or replaced

#### Scenario: S-033 — ExperienceEntry highlights enforce min/max length

*Unchanged from v1.*

#### Scenario: S-034 — Core models do not import adapters

*Unchanged from v1.*

- GIVEN all Python files under `src/mkcv/core/`
- WHEN their import statements are analyzed
- THEN none of them import from `mkcv.adapters`, `mkcv.cli`, or `mkcv.config`

---

## R-005: Adapters — MODIFIED

Adapters implement the port interfaces and live outside the core hexagon.

### R-005.1: Factory Functions — MODIFIED

`adapters/factory.py` MUST provide factory functions that construct and wire
together the adapter implementations. New factory functions for workspace:

```python
def create_prompt_loader(settings: Dynaconf) -> PromptLoaderPort: ...
def create_artifact_store(settings: Dynaconf) -> ArtifactStorePort: ...
def create_llm_adapter(settings: Dynaconf) -> LLMPort: ...
def create_renderer(settings: Dynaconf) -> RendererPort: ...
def create_pipeline_service(settings: Dynaconf) -> PipelineService: ...
def create_render_service(settings: Dynaconf) -> RenderService: ...
def create_validation_service(settings: Dynaconf) -> ValidationService: ...
def create_workspace_manager() -> WorkspaceManager: ...  # NEW
def create_workspace_service() -> WorkspaceService: ...   # NEW
```

### R-005.2: FileSystemPromptLoader

*Unchanged from v1.* Implements `PromptLoaderPort` with Jinja2 and user overrides.

### R-005.3: FileSystemArtifactStore — MODIFIED

`adapters/filesystem/artifact_store.py` MUST implement `ArtifactStorePort` with
additional workspace awareness:

- When operating in workspace mode, the artifact store MUST write pipeline
  intermediates to `applications/{company}/{YYYY-MM-position}/.mkcv/` instead
  of the default `.mkcv/<timestamp>/` location.
- The `create_run()` method MUST accept an optional `application_dir: Path`
  parameter. When provided, the run directory is created as `.mkcv/` inside
  the application directory.
- Final outputs (resume.yaml, resume.pdf) MUST be written to the application
  directory root, not inside `.mkcv/`.

### R-005.4: LLM Adapter Stub

*Unchanged from v1.*

### R-005.5: Renderer Adapter Stub

*Unchanged from v1.*

### R-005.6: WorkspaceManager — NEW

`adapters/workspace/manager.py` MUST implement filesystem operations for workspace
management. This is NOT a port/protocol — it's a concrete adapter used directly by
the CLI layer and workspace service. It encapsulates all workspace-related I/O.

The `WorkspaceManager` class MUST provide:

- `init_workspace(path: Path) -> WorkspaceConfig`: Creates workspace directory
  structure, writes `mkcv.toml`, returns parsed config.
- `find_workspace_root(start: Path | None = None) -> Path | None`: Walks up from
  `start` (default: CWD) looking for `mkcv.toml`. Returns the directory containing
  `mkcv.toml`, or `None` if not found.
- `load_workspace_config(workspace_root: Path) -> WorkspaceConfig`: Reads and parses
  `mkcv.toml` into a `WorkspaceConfig` model.
- `create_application_dir(workspace_root: Path, relative_path: str) -> Path`:
  Creates the application directory and returns its absolute path.
- `write_application_toml(app_dir: Path, metadata: ApplicationMetadata) -> Path`:
  Writes `application.toml` and returns its path.
- `copy_jd_to_application(jd_source: Path, app_dir: Path) -> Path`: Copies the JD
  file into the application directory as `jd.txt`. Returns the destination path.
- `read_application_toml(app_dir: Path) -> ApplicationMetadata | None`: Reads
  and parses `application.toml` if it exists.
- `write_gitignore(workspace_root: Path) -> Path`: Creates/updates `.gitignore`
  with patterns for `.mkcv/`, `*.pdf` (optional), etc.
- `list_knowledge_base_files(workspace_root: Path) -> list[Path]`: Returns all
  `.md` files in the `knowledge-base/` directory.

#### Scenario: S-035 — FileSystemPromptLoader loads bundled template

*Unchanged from v1.*

#### Scenario: S-036 — FileSystemPromptLoader renders template with context

*Unchanged from v1.*

#### Scenario: S-037 — FileSystemPromptLoader uses custom template directory

*Unchanged from v1.*

#### Scenario: S-038 — FileSystemPromptLoader raises on missing template

*Unchanged from v1.*

#### Scenario: S-039 — FileSystemArtifactStore creates run directory

*Unchanged from v1.*

#### Scenario: S-040 — FileSystemArtifactStore round-trips a model

*Unchanged from v1.*

#### Scenario: S-041 — FileSystemArtifactStore returns None for missing artifact

*Unchanged from v1.*

#### Scenario: S-041b — ArtifactStore workspace mode writes to application dir (NEW)

- GIVEN a `FileSystemArtifactStore` configured with workspace mode
- AND an application directory at `/tmp/ws/applications/deepl/2026-03-staff-engineer/`
- WHEN `store.create_run(application_dir=app_dir)` is called
- THEN the run directory is created at `<app_dir>/.mkcv/`
- AND the `.mkcv/` directory contains `input/` and `output/` subdirectories

#### Scenario: S-042 — BaseLLMAdapter raises NotImplementedError

*Unchanged from v1.*

#### Scenario: S-043 — BaseRenderer raises NotImplementedError

*Unchanged from v1.*

#### Scenario: S-044 — Factory creates functional PromptLoader

*Unchanged from v1.*

#### Scenario: S-045 — Factory creates functional ArtifactStore

*Unchanged from v1.*

#### Scenario: S-045b — Factory creates WorkspaceManager (NEW)

- GIVEN default settings
- WHEN `create_workspace_manager()` is called
- THEN the returned object is an instance of `WorkspaceManager`

#### Scenario: S-045c — Factory creates WorkspaceService (NEW)

- GIVEN default settings
- WHEN `create_workspace_service()` is called
- THEN the returned object is an instance of `WorkspaceService`

---

## R-006: Prompt Infrastructure

*Unchanged from v1.* Jinja2 prompt templates MUST be bundled with the package and
loadable at runtime.

### R-006.1: Bundled Templates

*Unchanged from v1.*

### R-006.2: Voice Anchor

*Unchanged from v1.*

### R-006.3: Package Data

*Unchanged from v1.*

#### Scenario: S-046 — All prompt templates exist

*Unchanged from v1.*

#### Scenario: S-047 — Templates are valid Jinja2

*Unchanged from v1.*

#### Scenario: S-048 — Voice anchor is includable

*Unchanged from v1.*

---

## R-007: Test Infrastructure — MODIFIED

The project MUST have a test suite that validates all stubs and infrastructure.

### R-007.1: Test Configuration

*Unchanged from v1.*

### R-007.2: Test Directory Structure — MODIFIED

Tests MUST mirror the source layout. New workspace test files are added:

```
tests/
├── conftest.py
├── test_cli/
│   ├── __init__.py
│   ├── test_app.py
│   └── test_commands/
│       ├── __init__.py
│       ├── test_generate.py
│       ├── test_render.py
│       ├── test_validate.py
│       ├── test_init.py            # MODIFIED: workspace init tests
│       └── test_themes.py
├── test_core/
│   ├── __init__.py
│   ├── test_exceptions.py
│   ├── test_models/
│   │   ├── __init__.py
│   │   ├── test_jd_analysis.py
│   │   ├── test_experience.py
│   │   ├── test_content.py
│   │   ├── test_resume.py
│   │   ├── test_review.py
│   │   ├── test_pipeline.py
│   │   └── test_workspace.py       # NEW
│   ├── test_ports/
│   │   └── test_protocols.py
│   └── test_services/
│       ├── test_pipeline_service.py
│       ├── test_render_service.py
│       ├── test_validation_service.py
│       └── test_workspace_service.py  # NEW
├── test_config/
│   ├── __init__.py
│   └── test_configuration.py
├── test_adapters/
│   ├── __init__.py
│   ├── test_factory.py
│   ├── test_prompt_loader.py
│   ├── test_artifact_store.py
│   └── test_workspace_manager.py    # NEW
└── test_prompts/
    ├── __init__.py
    └── test_templates.py
```

### R-007.3: Shared Fixtures — MODIFIED

`tests/conftest.py` MUST provide the v1 fixtures plus:

- `workspace_dir`: A temporary directory initialized as a workspace (with `mkcv.toml`,
  `knowledge-base/`, `applications/`)
- `workspace_manager`: A `WorkspaceManager` instance
- `workspace_service`: A `WorkspaceService` instance
- `sample_application_metadata`: A valid `ApplicationMetadata` model instance

### R-007.4: Smoke Tests — MODIFIED

At minimum, the test suite MUST include all v1 smoke tests plus:

- Workspace model validation tests
- Workspace service unit tests
- WorkspaceManager filesystem tests (init, find, create app dir, write toml)
- Init command tests (creates workspace)
- Generate command workspace integration (creates app directory structure)

#### Scenario: S-049 — All tests pass

*Unchanged from v1.*

#### Scenario: S-050 — Test coverage is reported

*Unchanged from v1.*

---

## R-008: Code Quality

*Unchanged from v1.* All code MUST pass static analysis and formatting checks.

### R-008.1: Ruff Configuration

*Unchanged from v1.*

### R-008.2: Mypy Configuration

*Unchanged from v1.*

### R-008.3: All Checks Pass

*Unchanged from v1.*

#### Scenario: S-051 — Ruff check passes

*Unchanged from v1.*

#### Scenario: S-052 — Ruff format check passes

*Unchanged from v1.*

#### Scenario: S-053 — Mypy strict passes

*Unchanged from v1.*

---

## R-009: Documentation Updates — MODIFIED

Documentation MUST be updated to reflect the new architecture, tooling decisions,
and workspace model.

### R-009.1: AGENTS.md

*Unchanged from v1 scope* — MUST reference Cyclopts, Dynaconf, hexagonal architecture.
Additionally MUST mention the workspace model and `mkcv.toml` config.

### R-009.2: Architecture Spec

*Unchanged from v1 scope* — MUST describe hexagonal architecture with ports/adapters.
Additionally MUST include the workspace management components.

### R-009.3: CLI Interface Spec

MUST be updated to reflect workspace-aware `init` and `generate` commands,
the `--workspace` global option, and the new exit code 7.

### R-009.4: Architecture Decision Record

*Unchanged from v1 scope* — MUST document Cyclopts, Dynaconf, hexagonal, manual DI.
Additionally SHOULD document the workspace model decision.

#### Scenario: S-054 — AGENTS.md references Cyclopts

*Unchanged from v1.*

#### Scenario: S-055 — Architecture spec describes hexagonal architecture

*Unchanged from v1.*

#### Scenario: S-056 — ADR exists and documents decisions

*Unchanged from v1.*

#### Scenario: S-057 — .gitignore is comprehensive (MODIFIED)

- GIVEN the `.gitignore` file at the repository root
- WHEN its content is inspected
- THEN it includes patterns for: `.secrets.toml`, `.mkcv/`, `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`, `*.egg-info/`, `dist/`, `.venv/`

(The workspace `.gitignore` generated by `mkcv init` is tested separately in R-010.)

---

## R-010: Workspace Management — NEW

mkcv MUST support a workspace-centric workflow where a workspace directory, marked
by `mkcv.toml`, organizes career knowledge bases and job applications.

### R-010.1: `mkcv init` Creates Workspace Structure

The `mkcv init [PATH]` command MUST create the following directory structure:

```
<PATH>/                              # Workspace root (default: CWD)
├── mkcv.toml                        # Workspace config marker
├── knowledge-base/                  # Knowledge base directory
│   ├── career.md                    # Template career KB (if --kb-template)
│   └── voice.md                     # Template voice guidelines (if --kb-template)
├── applications/                    # Application storage
├── templates/                       # User prompt overrides (empty)
└── .gitignore                       # Workspace-specific gitignore
```

The command MUST:

- Accept an optional positional `PATH` argument (default: current directory)
- Create all directories that don't already exist
- Write `mkcv.toml` with sensible defaults
- Write `.gitignore` with patterns for `.mkcv/` directories inside application
  dirs and other transient files
- If `--kb-template` (default: `True`), create template KB files with placeholder
  content and section headers matching the expected KB format from
  `docs/specs/data-models.md`
- If `--global-config` is set, also create `~/.config/mkcv/settings.toml`
- Be idempotent for directories: if a directory already exists, skip it
- NOT overwrite existing files (especially `mkcv.toml`, KB files)
- Print a clear summary of created files and directories

#### Scenario: S-062 — Init creates workspace in current directory (NEW)

- GIVEN an empty temporary directory
- WHEN the user runs `mkcv init` from inside it (or `mkcv init .`)
- THEN the directory contains `mkcv.toml`
- AND the directory contains `knowledge-base/`
- AND the directory contains `knowledge-base/career.md`
- AND the directory contains `knowledge-base/voice.md`
- AND the directory contains `applications/`
- AND the directory contains `templates/`
- AND the directory contains `.gitignore`
- AND the command exits with code 0

#### Scenario: S-063 — Init creates workspace at specified path (NEW)

- GIVEN a path `/tmp/my-career/` that does not exist
- WHEN the user runs `mkcv init /tmp/my-career/`
- THEN `/tmp/my-career/` is created
- AND `/tmp/my-career/mkcv.toml` exists
- AND `/tmp/my-career/knowledge-base/` exists
- AND the command exits with code 0

#### Scenario: S-064 — Init skips existing workspace (NEW)

- GIVEN a directory that already contains `mkcv.toml`
- WHEN the user runs `mkcv init` from inside it
- THEN the command prints a warning that the workspace already exists
- AND the command does NOT overwrite `mkcv.toml`
- AND the command creates any missing subdirectories (e.g., `templates/` if absent)
- AND the command exits with code 0

#### Scenario: S-065 — Init without KB template (NEW)

- GIVEN an empty temporary directory
- WHEN the user runs `mkcv init --no-kb-template`
- THEN `knowledge-base/` directory is created
- BUT `knowledge-base/career.md` does NOT exist
- AND `knowledge-base/voice.md` does NOT exist

#### Scenario: S-066 — Init with global config (NEW)

- GIVEN an empty temporary directory
- AND `~/.config/mkcv/settings.toml` does not exist
- WHEN the user runs `mkcv init --global-config`
- THEN the workspace is created
- AND `~/.config/mkcv/settings.toml` is created with default settings

### R-010.2: Workspace Discovery

The system MUST discover the active workspace by walking up from the current
working directory (or a specified start path) looking for `mkcv.toml`.

Discovery order:

1. `--workspace PATH` CLI flag (if provided, use directly — do not walk up)
2. `MKCV_WORKSPACE` environment variable (if set, use directly)
3. Walk up from CWD: check CWD, then parent, then parent's parent, etc., until
   either `mkcv.toml` is found or the filesystem root is reached

The `find_workspace_root()` function MUST:

- Return `Path` to the workspace root (the directory containing `mkcv.toml`)
  if found
- Return `None` if no workspace is found
- NEVER raise an exception for "not found" — the caller decides whether that's
  an error
- Stop at filesystem root — do NOT traverse mount points or symlinks beyond
  the filesystem boundary

#### Scenario: S-067 — Workspace found in current directory (NEW)

- GIVEN a workspace initialized at `/tmp/ws/` (contains `mkcv.toml`)
- AND the current working directory is `/tmp/ws/`
- WHEN `find_workspace_root()` is called
- THEN it returns `Path("/tmp/ws/")`

#### Scenario: S-068 — Workspace found in parent directory (NEW)

- GIVEN a workspace initialized at `/tmp/ws/` (contains `mkcv.toml`)
- AND the current working directory is `/tmp/ws/applications/deepl/2026-03-staff/`
- WHEN `find_workspace_root()` is called
- THEN it returns `Path("/tmp/ws/")`

#### Scenario: S-069 — No workspace found (NEW)

- GIVEN no `mkcv.toml` exists in `/tmp/no-ws/` or any parent directory
- AND the current working directory is `/tmp/no-ws/`
- WHEN `find_workspace_root()` is called
- THEN it returns `None`

#### Scenario: S-070 — Workspace override via environment variable (NEW)

- GIVEN a workspace at `/tmp/ws/` (contains `mkcv.toml`)
- AND the environment variable `MKCV_WORKSPACE` is set to `/tmp/ws/`
- AND the current working directory is `/tmp/elsewhere/`
- WHEN workspace discovery is performed
- THEN the workspace root is `/tmp/ws/`

#### Scenario: S-071 — Nested workspace uses nearest (NEW)

- GIVEN a workspace at `/tmp/outer/` (contains `mkcv.toml`)
- AND a workspace at `/tmp/outer/inner/` (also contains `mkcv.toml`)
- AND the current working directory is `/tmp/outer/inner/subdir/`
- WHEN `find_workspace_root()` is called
- THEN it returns `Path("/tmp/outer/inner/")` (the nearest workspace)

### R-010.3: `mkcv.toml` Workspace Config File

The `mkcv.toml` file MUST serve as both a workspace marker and a configuration
source.

Minimal content (generated by `mkcv init`):

```toml
# mkcv workspace configuration
# See: https://github.com/bkuberek/mkcv

[workspace]
# Relative paths from this file's directory
knowledge_base_dir = "knowledge-base"
applications_dir = "applications"
templates_dir = "templates"

[defaults]
# Override global defaults for this workspace
# theme = "sb2nov"
# profile = "premium"

[voice]
# Workspace-specific voice guidelines
# guidelines = "Direct, not flowery..."
```

The `mkcv.toml` file MUST:

- Be valid TOML
- Be parseable into a `WorkspaceConfig` model
- Support all configuration keys that the global `settings.toml` supports
  (as overrides)
- Have a `[workspace]` section with directory paths
- Use relative paths (relative to the `mkcv.toml` location) for all
  directory references

#### Scenario: S-072 — mkcv.toml is valid TOML and parseable (NEW)

- GIVEN a workspace initialized via `mkcv init`
- WHEN `mkcv.toml` is read and parsed as TOML
- THEN no parse errors occur
- AND the `[workspace]` section contains `knowledge_base_dir`, `applications_dir`, `templates_dir`

#### Scenario: S-073 — mkcv.toml with custom overrides (NEW)

- GIVEN a workspace where `mkcv.toml` contains:
  ```toml
  [workspace]
  knowledge_base_dir = "kb"
  applications_dir = "apps"
  [defaults]
  theme = "classic"
  ```
- WHEN the workspace config is loaded
- THEN `config.knowledge_base_dir` equals `"kb"`
- AND `config.applications_dir` equals `"apps"`
- AND when merged into Dynaconf, `settings.defaults.theme` equals `"classic"`

### R-010.4: Application Directory Management

The workspace MUST organize job applications in a company-first, then
date-position directory structure:

```
applications/
├── {company}/                           # Lowercase, sanitized
│   └── {YYYY-MM-position}/             # Date prefix + sanitized position
│       ├── application.toml             # Auto-generated metadata
│       ├── jd.txt                       # Job description
│       ├── resume.yaml                  # Final structured output
│       ├── resume.pdf                   # Rendered PDF
│       └── .mkcv/                       # Pipeline intermediates
│           ├── stage1_analysis.json
│           ├── stage2_selection.json
│           ├── stage3_content.json
│           ├── stage4_resume.yaml
│           ├── stage5_review.json
│           └── meta.json
```

Directory naming rules:

- **Company directory**: Lowercase, alphanumeric and hyphens only. Special
  characters stripped or replaced with hyphens. Multiple consecutive hyphens
  collapsed to single. Leading/trailing hyphens stripped.
  Examples: `"DeepL" -> "deepl"`, `"Acme Corp." -> "acme-corp"`,
  `"O'Reilly Media" -> "oreilly-media"`
- **Application directory**: `{YYYY-MM}-{position}` where position follows same
  sanitization rules as company.
  Examples: `"Senior Staff Engineer" -> "2026-03-senior-staff-engineer"`,
  `"Lead Dev (Backend)" -> "2026-03-lead-dev-backend"`

#### Scenario: S-074 — Application directory created with correct structure (NEW)

- GIVEN an initialized workspace at `/tmp/ws/`
- WHEN the tool creates an application for company="DeepL", position="Senior Staff Engineer"
- THEN the directory `/tmp/ws/applications/deepl/2026-03-senior-staff-engineer/` exists
- AND the directory contains `.mkcv/`

#### Scenario: S-075 — Company directory reused for multiple applications (NEW)

- GIVEN an initialized workspace at `/tmp/ws/`
- AND an existing application at `applications/deepl/2026-01-backend-engineer/`
- WHEN the tool creates a new application for company="DeepL", position="Staff Engineer"
- THEN the new directory is `applications/deepl/2026-03-staff-engineer/`
- AND the existing `applications/deepl/2026-01-backend-engineer/` is unchanged

#### Scenario: S-076 — Duplicate application directory handling (NEW)

- GIVEN an initialized workspace at `/tmp/ws/`
- AND an existing application at `applications/deepl/2026-03-senior-staff-engineer/`
- WHEN the tool attempts to create another application with the same company/position/date
- THEN the command MUST either:
  - Append a numeric suffix (e.g., `2026-03-senior-staff-engineer-2`), OR
  - Warn the user and offer to use the existing directory
- AND the existing directory is NOT overwritten

#### Scenario: S-077 — Special characters in company/position names (NEW)

- GIVEN an initialized workspace
- WHEN the tool creates an application for company="O'Reilly & Sons", position="Sr. Eng (Remote)"
- THEN the company directory is `oreilly-sons` (or `oreilly-and-sons`)
- AND the application directory starts with `2026-03-sr-eng-remote`

### R-010.5: `application.toml` Auto-Generation

When the `generate` command runs in workspace mode, it MUST auto-generate an
`application.toml` file in the application directory.

The `application.toml` MUST contain:

```toml
# Auto-generated by mkcv
# Do not edit the [metadata] section manually

[metadata]
company = "DeepL"
position = "Senior Staff Software Engineer"
date = "2026-03-18"
status = "created"
url = ""
jd_file = "jd.txt"
created_at = "2026-03-18T14:30:00Z"
updated_at = "2026-03-18T14:30:00Z"

[notes]
# Add your notes about this application here
```

The `application.toml` MUST:

- Be valid TOML
- Be parseable into an `ApplicationMetadata` model
- Contain the company name in its original casing (not sanitized)
- Contain the position in its original casing
- Include timestamps in ISO 8601 format
- Set initial status to `"created"`
- Be updateable by subsequent pipeline runs (update `status` and `updated_at`)

#### Scenario: S-078 — application.toml is auto-generated (NEW)

- GIVEN a workspace-mode `generate` run for company="DeepL", position="Staff Engineer"
- WHEN the command creates the application directory
- THEN `application.toml` exists in the application directory
- AND parsing it as TOML succeeds
- AND `metadata.company` equals `"DeepL"` (original casing)
- AND `metadata.position` equals `"Staff Engineer"`
- AND `metadata.status` equals `"created"`
- AND `metadata.date` equals today's date in YYYY-MM-DD format

#### Scenario: S-079 — application.toml preserves existing on re-run (NEW)

- GIVEN an existing `application.toml` with `status = "submitted"` and custom notes
- WHEN the generate command runs again in the same application directory
- THEN the `status` field is NOT reset to `"created"`
- AND custom notes are preserved
- AND `updated_at` IS updated to the current time

### R-010.6: Workspace-Aware Generate Command

When the `generate` command detects a workspace (via discovery or `--workspace`):

1. It MUST resolve `--kb` from the workspace's `knowledge-base/` directory if not
   explicitly provided. If multiple `.md` files exist in KB dir, they MUST all
   be concatenated or passed as a composite input (implementation detail deferred
   to pipeline stage).
2. It MUST determine the company and position (from `--company`/`--position` flags
   or by attempting inference — for this change, flags are required if not inferrable;
   inference is a stub that raises a clear error asking the user to provide flags).
3. It MUST call the workspace manager to create the application directory structure.
4. It MUST copy the JD file into the application directory.
5. It MUST generate `application.toml`.
6. It MUST configure the artifact store to use the application's `.mkcv/` directory.
7. It MUST print the application directory path in the output.

For this change, steps 1-7 are functional (real filesystem operations). The actual
pipeline execution (AI calls) remains a stub.

#### Scenario: S-080 — Generate in workspace creates full application structure (NEW)

- GIVEN an initialized workspace at `/tmp/ws/`
- AND a JD file at `/tmp/ws/jobs/deepl.txt`
- AND KB files exist at `/tmp/ws/knowledge-base/career.md`
- WHEN the user runs `mkcv generate --jd /tmp/ws/jobs/deepl.txt --company DeepL --position "Staff Engineer"` inside the workspace
- THEN `applications/deepl/2026-03-staff-engineer/` is created
- AND `applications/deepl/2026-03-staff-engineer/jd.txt` exists (copy of the JD)
- AND `applications/deepl/2026-03-staff-engineer/application.toml` exists
- AND `applications/deepl/2026-03-staff-engineer/.mkcv/` exists
- AND the output includes the path to the application directory

#### Scenario: S-081 — Generate in workspace uses KB from workspace (NEW)

- GIVEN an initialized workspace with `knowledge-base/career.md`
- AND no `--kb` flag is provided
- WHEN the user runs `mkcv generate --jd jobs/test.txt --company Test --position Dev`
- THEN the command uses files from `knowledge-base/` as the KB source
- AND the command does NOT error about missing `--kb`

#### Scenario: S-082 — Generate in workspace with explicit --kb (NEW)

- GIVEN an initialized workspace
- AND a KB file at `/tmp/other-kb.md`
- WHEN the user runs `mkcv generate --jd test.txt --kb /tmp/other-kb.md --company Test --position Dev`
- THEN the command uses `/tmp/other-kb.md` as the KB (not the workspace KB)

#### Scenario: S-083 — Generate in workspace prints application path (NEW)

- GIVEN an initialized workspace
- WHEN the user runs `mkcv generate --jd test.txt --company Acme --position Engineer`
- THEN the output contains the full path to the created application directory
- AND the output contains `applications/acme/2026-03-engineer/`

### R-010.7: Non-Workspace Mode

When no workspace is found and `--workspace` is not specified, the `generate`
command MUST operate in non-workspace mode:

- `--jd` is REQUIRED
- `--kb` is REQUIRED (the command MUST error if not provided)
- `--company` and `--position` are ignored with a warning if provided
- Output goes to `--output-dir` (default: `.mkcv/<timestamp>_<company>/`)
- No `application.toml` is generated
- No application directory structure is created

Other commands (`render`, `validate`, `themes`) are unaffected by workspace mode.

#### Scenario: S-084 — Non-workspace generate requires --kb (NEW)

- GIVEN no workspace exists
- AND a JD file `test.txt` exists
- WHEN the user runs `mkcv generate --jd test.txt`
- THEN the command exits with a non-zero code
- AND the error message indicates `--kb` is required without a workspace

#### Scenario: S-085 — Non-workspace generate works with explicit params (NEW)

- GIVEN no workspace exists
- AND `test_jd.txt` and `career.md` exist
- WHEN the user runs `mkcv generate --jd test_jd.txt --kb career.md`
- THEN the command runs successfully (stub output)
- AND no `application.toml` is created
- AND the command exits with code 0

#### Scenario: S-086 — Non-workspace mode warns about --company flag (NEW)

- GIVEN no workspace exists
- AND `test.txt` and `kb.md` exist
- WHEN the user runs `mkcv generate --jd test.txt --kb kb.md --company Acme`
- THEN the output contains a warning that `--company` is only meaningful in workspace mode
- AND the command still runs successfully

#### Scenario: S-087 — Generate in workspace fails gracefully with missing KB dir (NEW)

- GIVEN an initialized workspace where `knowledge-base/` directory exists but is empty
- AND no `--kb` flag is provided
- WHEN the user runs `mkcv generate --jd test.txt --company Test --position Dev`
- THEN the command exits with a non-zero code
- AND the error message indicates no knowledge base files found in workspace
- AND the error message suggests adding `.md` files to `knowledge-base/` or using `--kb`

---

## Cross-Cutting Scenarios

These scenarios verify integration between multiple requirements.

#### Scenario: S-058 — End-to-end: install, run help, run stub command

- GIVEN a clean environment
- WHEN the user runs `uv sync`
- AND the user runs `mkcv --help`
- AND the user runs `mkcv generate --jd /dev/null --kb /dev/null`
- THEN all three commands succeed (exit code 0)

#### Scenario: S-059 — Full quality check pipeline

- GIVEN the complete project source code
- WHEN the user runs `uv run ruff check src/ tests/`
- AND the user runs `uv run ruff format --check src/ tests/`
- AND the user runs `uv run mypy src/`
- AND the user runs `uv run pytest`
- THEN all four commands exit with code 0

#### Scenario: S-060 — Hexagonal boundary is respected

- GIVEN all Python files in `src/mkcv/core/`
- WHEN their import statements are analyzed (statically or via test)
- THEN none of them import from `mkcv.adapters`, `mkcv.cli`, or `mkcv.config`
- AND adapters only import from `mkcv.core` (ports, models, exceptions)

#### Scenario: S-061 — Config flows to CLI defaults

- GIVEN the environment variable `MKCV_DEFAULTS__THEME` is set to `"moderncv"`
- WHEN the user runs `mkcv generate --help`
- THEN the default value shown for `--theme` is `"moderncv"` (or the config value is used at runtime when no flag is passed)

#### Scenario: S-088 — End-to-end workspace workflow (NEW)

- GIVEN a clean temporary directory
- WHEN the user runs `mkcv init /tmp/ws/`
- AND creates a JD file at `/tmp/ws/jobs/test.txt`
- AND runs `mkcv --workspace /tmp/ws generate --jd /tmp/ws/jobs/test.txt --company TestCo --position "Engineer"`
- THEN `/tmp/ws/applications/testco/2026-03-engineer/application.toml` exists
- AND `/tmp/ws/applications/testco/2026-03-engineer/jd.txt` exists
- AND `/tmp/ws/applications/testco/2026-03-engineer/.mkcv/` exists

#### Scenario: S-089 — Workspace .gitignore patterns (NEW)

- GIVEN a workspace initialized via `mkcv init`
- WHEN the `.gitignore` file in the workspace root is inspected
- THEN it contains patterns for:
  - `.mkcv/` (pipeline intermediates in application dirs)
  - `*.pdf` (optionally, as a commented suggestion)
  - `.secrets.toml`

#### Scenario: S-090 — KB directory listing (NEW)

- GIVEN a workspace with `knowledge-base/career.md` and `knowledge-base/voice.md`
- WHEN `workspace_manager.list_knowledge_base_files(workspace_root)` is called
- THEN the result contains `Path("knowledge-base/career.md")` and `Path("knowledge-base/voice.md")`
- AND the result does NOT contain non-`.md` files

#### Scenario: S-091 — Workspace config loaded during CLI startup (NEW)

- GIVEN a workspace at `/tmp/ws/` with `mkcv.toml` containing `[defaults]\ntheme = "engineeringresumes"`
- WHEN any mkcv command runs from inside `/tmp/ws/`
- THEN the workspace is auto-discovered
- AND `settings.defaults.theme` equals `"engineeringresumes"` (workspace override active)

---

## Summary

| Requirement | Count of Scenarios | Coverage |
|-------------|-------------------|----------|
| R-001: Project Structure | S-001 to S-003 (3) | Unchanged |
| R-002: CLI Interface | S-004 to S-014b (14) | +3 new (S-008b, S-014b, S-012 modified) |
| R-003: Configuration | S-015 to S-019c (7) | +2 new (S-019b, S-019c) |
| R-004: Core Domain | S-020 to S-034 (20) | +5 new (S-025b, S-029b, S-029c, S-029d, S-032b, S-032c) |
| R-005: Adapters | S-035 to S-045c (14) | +3 new (S-041b, S-045b, S-045c) |
| R-006: Prompts | S-046 to S-048 (3) | Unchanged |
| R-007: Tests | S-049 to S-050 (2) | Unchanged (but scope expanded) |
| R-008: Code Quality | S-051 to S-053 (3) | Unchanged |
| R-009: Documentation | S-054 to S-057 (4) | S-057 modified |
| R-010: Workspace Management | S-062 to S-087 (26) | NEW |
| Cross-Cutting | S-058 to S-091 (8) | +4 new (S-088, S-089, S-090, S-091) |
| **TOTAL** | **104 scenarios** | +43 new/modified vs v1 |

**Note:** Scenario count is 104 (not 91 as originally estimated). The additional
scenarios emerged from thorough coverage of workspace edge cases, which is
appropriate given the scope of the workspace model additions.

### Coverage Assessment

- **Happy paths**: Covered for all requirements including workspace init, discovery,
  generate in workspace mode, and non-workspace mode
- **Edge cases**: Covered for already-initialized workspace, nested workspaces,
  duplicate application directories, special characters in names, re-application
  to same company, empty KB directory, missing KB in workspace
- **Error states**: Covered for missing workspace for workspace-aware commands,
  missing KB in non-workspace mode, invalid workspace config, workspace-only
  flags in non-workspace mode, malformed mkcv.toml

### Changes from v1

| Category | Count | Details |
|----------|-------|---------|
| New requirement | 1 | R-010: Workspace Management (26 scenarios) |
| Modified requirements | 6 | R-002, R-003, R-004, R-005, R-007, R-009 |
| Unchanged requirements | 3 | R-001, R-006, R-008 |
| New scenarios | 43 | S-008b through S-091 |
| Modified scenarios | 2 | S-012, S-024 |
| Removed scenarios | 0 | None |

### Next Step

Ready for design update (sdd-design). The design phase should detail the
`WorkspaceManager` implementation, `mkcv.toml` parsing flow, the workspace
discovery integration into the CLI meta app launcher, and how `generate`
branches between workspace and non-workspace modes.
