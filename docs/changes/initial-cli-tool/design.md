# Design: Initial CLI Tool

## Technical Approach

Bootstrap the mkcv repository from a docs-only state into an installable Python CLI
application using a pragmatic hexagonal architecture. The source layout follows the
`src/` convention managed by `uv`. Cyclopts provides the CLI framework with native
async support. Dynaconf manages layered configuration. All commands are stubbed out
with the correct signatures, wired through factory functions to service classes that
depend on port protocols -- but no AI pipeline logic is implemented.

The workspace model is a first-class concept: `mkcv init PATH` creates a workspace
directory with `mkcv.toml`, `knowledge-base/`, `applications/`, and `templates/`.
The CLI auto-discovers workspaces by walking up from CWD, and all commands adapt
their behavior based on whether a workspace is active. Without a workspace, only
`mkcv generate` works (with explicit `--jd` and `--kb` flags).

The goal is a skeleton that passes `uv run mkcv --help`, `uv run pytest`, `uv run
ruff check`, and `uv run mypy src/` on the very first change -- establishing the
contracts that every subsequent change will implement against.

---

## Architecture Decisions

### Decision: CLI Framework -- Cyclopts over Click

**Choice**: Cyclopts
**Alternatives considered**: Click (as specified in AGENTS.md), Typer
**Rationale**: Cyclopts offers native async command support (auto-creates event
loop for `async def` commands), built-in Pydantic/Literal type coercion, docstring-
driven help text, and `Meta App` for global parameter handling. Click would require
a custom async wrapper and Typer is largely deprecated in favor of Cyclopts.
AGENTS.md will be updated to reflect this decision.

### Decision: Configuration -- Dynaconf over plain YAML

**Choice**: Dynaconf with TOML settings files
**Alternatives considered**: Plain YAML + pydantic-settings, raw env vars
**Rationale**: Dynaconf provides layered config (defaults < file < env < runtime),
built-in validation, env var prefix support (`MKCV_`), secrets separation, and
merge semantics. The reference project demonstrates a proven pattern. TOML is used
for settings files (bundled defaults and user config) because Dynaconf natively
supports it and it avoids the YAML-parsing dependency for config.

### Decision: DI Wiring -- Manual factory functions over container

**Choice**: Manual factory functions in `mkcv/factories.py`
**Alternatives considered**: dependency-injector, python-inject, kink
**Rationale**: The project has a small number of services (3) and ports (4). A DI
container adds complexity, a learning curve, and a runtime dependency for no
measurable benefit at this scale. Factory functions are explicit, testable, and
type-checkable. If the project grows to need more sophisticated DI, the factory
pattern migrates cleanly to a container.

### Decision: Package Layout -- Single `mkcv` package with subpackages

**Choice**: `src/mkcv/` with `core/`, `adapters/`, `cli/`, `config/` subpackages
**Alternatives considered**: Flat modules, separate packages per layer
**Rationale**: The hexagonal architecture maps cleanly to subpackages within a
single installable package. `core/` holds ports, services, models, and exceptions;
`adapters/` holds implementations; `cli/` holds Cyclopts commands; `config/` holds
Dynaconf wiring. Imports flow inward: `cli` and `adapters` import from `core`, but
`core` never imports from `cli` or `adapters`.

### Decision: Prompt Templates -- Jinja2 bundled as package data

**Choice**: Jinja2 templates in `src/mkcv/prompts/` loaded via `importlib.resources`
**Alternatives considered**: String constants, external template directory only
**Rationale**: Templates ship with the package (no separate install step), but a
user-override path from config allows customization. `importlib.resources` is the
modern stdlib way to access package data and works correctly with wheels and editable
installs.

### Decision: Test Directory -- `tests/` at repo root (not `test/`)

**Choice**: `tests/` mirroring source layout
**Alternatives considered**: `test/` (reference project pattern)
**Rationale**: AGENTS.md specifies `tests/test_pipeline/test_analyze.py` as the
convention. The `tests/` directory name is more common in the Python ecosystem and
matches the existing documentation.

### Decision: Workspace Model -- Workspace-centric file management

**Choice**: `mkcv.toml` marker file at workspace root; `knowledge-base/` directory;
`applications/{company}/{date-position}/` hierarchy; tool manages all file placement
**Alternatives considered**: Single config file + flat output directories; XDG-only
config without workspace concept; project-per-application model
**Rationale**: A workspace provides a single location for all career materials and
applications, making it easy to version-control, back up, and review history. The
company-first grouping (`applications/deepl/2026-03-senior-staff/`) reflects how
users think about applications. The tool managing file placement (JD copying,
directory creation, `application.toml` generation) reduces user friction and enforces
consistency. Without a workspace, the tool degrades gracefully to simple file-in,
file-out behavior.

---

## A. Package Layout

```
mkcv/
├── .gitignore
├── AGENTS.md                          # AI agent instructions (exists, update)
├── README.md                          # Project readme (stub)
├── pyproject.toml                     # Package metadata, deps, tool config
├── uv.lock                           # Generated by uv sync
│
├── docs/                              # Existing documentation (unchanged)
│   ├── product/
│   │   ├── PRD.md
│   │   └── roadmap.md
│   ├── specs/
│   │   ├── architecture.md
│   │   ├── cli-interface.md
│   │   └── data-models.md
│   └── changes/
│       └── initial-cli-tool/
│           ├── design.md              # This document
│           └── specs/
│
├── src/
│   └── mkcv/
│       ├── __init__.py                # Package root: __version__, package docstring
│       ├── __main__.py                # `python -m mkcv` entry point
│       │
│       ├── cli/                       # CLI layer (Cyclopts)
│       │   ├── __init__.py
│       │   ├── app.py                 # Root App, meta app, global params, main()
│       │   ├── console.py             # Rich console singleton, output helpers
│       │   └── commands/              # One module per subcommand
│       │       ├── __init__.py
│       │       ├── generate.py        # `mkcv generate` command (workspace-aware)
│       │       ├── render.py          # `mkcv render` command
│       │       ├── validate.py        # `mkcv validate` command
│       │       ├── init_cmd.py        # `mkcv init` command (workspace creation)
│       │       └── themes.py          # `mkcv themes` command
│       │
│       ├── config/                    # Configuration layer (Dynaconf)
│       │   ├── __init__.py            # Exports `settings` singleton
│       │   ├── configuration.py       # Configuration(Dynaconf) class
│       │   ├── workspace.py           # Workspace discovery + loading functions
│       │   ├── settings.toml          # Bundled default settings
│       │   └── .secrets.toml          # Secrets template (dev defaults only)
│       │
│       ├── core/                      # Domain core (no external deps except pydantic)
│       │   ├── __init__.py
│       │   ├── ports.py               # Protocol interfaces (LLM, Renderer, etc.)
│       │   ├── services.py            # PipelineService, RenderService, ValidationService
│       │   ├── exceptions.py          # MkcvError hierarchy (incl. WorkspaceError)
│       │   └── models/                # Pydantic data models
│       │       ├── __init__.py        # Re-exports all model classes
│       │       ├── jd_analysis.py     # Stage 1 models
│       │       ├── experience.py      # Stage 2 models
│       │       ├── content.py         # Stage 3 models
│       │       ├── resume.py          # Stage 4 models (RenderCV YAML)
│       │       ├── review.py          # Stage 5 models
│       │       ├── pipeline.py        # Pipeline metadata models
│       │       ├── workspace_config.py  # WorkspaceConfig model
│       │       └── application_metadata.py  # ApplicationMetadata model
│       │
│       ├── adapters/                  # Port implementations
│       │   ├── __init__.py
│       │   ├── prompt_loader.py       # FileSystemPromptLoader (Jinja2)
│       │   ├── artifact_store.py      # FileSystemArtifactStore (workspace-aware)
│       │   ├── filesystem/            # Filesystem operation adapters
│       │   │   ├── __init__.py
│       │   │   └── workspace_manager.py  # WorkspaceManager (dir operations)
│       │   └── llm/                   # LLM provider adapters
│       │       ├── __init__.py
│       │       ├── base.py            # Base adapter utilities
│       │       └── stub.py            # StubLLMAdapter (for this change)
│       │
│       ├── factories.py               # DI wiring: create_*_service() functions
│       │
│       └── prompts/                   # Jinja2 prompt templates (package data)
│           ├── analyze_jd.j2          # Stage 1 template (stub)
│           ├── select_experience.j2   # Stage 2 template (stub)
│           ├── tailor_bullets.j2      # Stage 3a template (stub)
│           ├── write_mission.j2       # Stage 3b template (stub)
│           ├── structure_yaml.j2      # Stage 4 template (stub)
│           ├── review.j2             # Stage 5 template (stub)
│           └── _voice_anchor.j2       # Shared partial: voice guidelines
│
└── tests/
    ├── __init__.py
    ├── conftest.py                    # Shared fixtures (incl. workspace fixtures)
    ├── test_cli/
    │   ├── __init__.py
    │   ├── test_app.py                # Root app, --help, --version
    │   └── test_commands/
    │       ├── __init__.py
    │       ├── test_generate.py       # generate: workspace + non-workspace modes
    │       ├── test_render.py         # render command smoke tests
    │       ├── test_validate.py       # validate command smoke tests
    │       ├── test_init_cmd.py       # init command: workspace creation tests
    │       └── test_themes.py         # themes command smoke tests
    ├── test_config/
    │   ├── __init__.py
    │   ├── test_configuration.py      # Config loading, validation, overrides
    │   └── test_workspace_config.py   # Workspace discovery + layered config
    ├── test_core/
    │   ├── __init__.py
    │   ├── test_exceptions.py         # Exception hierarchy
    │   ├── test_services.py           # Service classes with mocked ports
    │   └── test_models/
    │       ├── __init__.py
    │       ├── test_jd_analysis.py    # JDAnalysis model validation
    │       ├── test_resume.py         # RenderCVResume model validation
    │       ├── test_pipeline.py       # Pipeline metadata models
    │       ├── test_workspace_config.py  # WorkspaceConfig model validation
    │       └── test_application_metadata.py  # ApplicationMetadata validation
    └── test_adapters/
        ├── __init__.py
        ├── test_prompt_loader.py      # Template loading and rendering
        ├── test_artifact_store.py     # .mkcv/ save/load (both modes)
        └── test_workspace_manager.py  # Workspace dir creation, slugification
```

### Key Changes from v1

- **Renamed**: `cli/commands/init.py` -> `cli/commands/init_cmd.py` (avoids shadowing
  the `init` builtin; corresponding test file is `test_init_cmd.py`)
- **New**: `config/workspace.py` -- workspace discovery and config loading
- **New**: `core/models/workspace_config.py` -- WorkspaceConfig Pydantic model
- **New**: `core/models/application_metadata.py` -- ApplicationMetadata Pydantic model
- **New**: `adapters/filesystem/workspace_manager.py` -- workspace directory operations
- **New**: `tests/test_config/test_workspace_config.py` -- workspace discovery tests
- **New**: `tests/test_core/test_models/test_workspace_config.py` -- model tests
- **New**: `tests/test_core/test_models/test_application_metadata.py` -- model tests
- **New**: `tests/test_adapters/test_workspace_manager.py` -- workspace manager tests
- **Modified**: `exceptions.py` gains `WorkspaceError`, `WorkspaceNotFoundError`
- **Modified**: `artifact_store.py` gains workspace-aware output paths
- **Modified**: `factories.py` gains `create_workspace_manager()`

---

## B. pyproject.toml Design

*Unchanged from v1* -- no new dependencies needed for workspace support. The `toml`
stdlib module (Python 3.11+) handles `mkcv.toml` and `application.toml` parsing.
The `tomli-w` package is added for writing TOML files.

```toml
[project]
name = "mkcv"
version = "0.1.0"
description = "AI-powered CLI tool that generates ATS-compliant PDF resumes tailored to specific job applications"
readme = "README.md"
requires-python = ">=3.12"
license = { text = "MIT" }
authors = [
    { name = "Bastian Kuberek", email = "bastian@bkuberek.com" },
]
keywords = ["resume", "cv", "cli", "ai", "ats"]
classifiers = [
    "Development Status :: 2 - Pre-Alpha",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Office/Business",
]

dependencies = [
    "cyclopts>=3.6",
    "pydantic>=2.0",
    "dynaconf>=3.2",
    "jinja2>=3.1",
    "httpx>=0.27",
    "rich>=13.0",
    "pyyaml>=6.0",
    "tomli-w>=1.0",
]

[project.scripts]
mkcv = "mkcv.cli.app:main"

[project.optional-dependencies]
anthropic = ["anthropic>=0.40"]
openai = ["openai>=1.50"]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "ruff>=0.4",
    "mypy>=1.10",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/mkcv"]

# Include prompt templates as package data
[tool.hatch.build.targets.wheel.force-include]
"src/mkcv/prompts" = "mkcv/prompts"
"src/mkcv/config/settings.toml" = "mkcv/config/settings.toml"

# ---------- Ruff ----------
[tool.ruff]
src = ["src"]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "F",      # pyflakes
    "I",      # isort
    "UP",     # pyupgrade
    "B",      # flake8-bugbear
    "SIM",    # flake8-simplify
    "TCH",    # flake8-type-checking
    "RET",    # flake8-return
    "ARG",    # flake8-unused-arguments
    "C4",     # flake8-comprehensions
    "PIE",    # flake8-pie
    "PERF",   # perflint
    "LOG",    # flake8-logging
    "G",      # flake8-logging-format
]
ignore = [
    "ARG001",  # Unused function argument (common in stubs)
    "ARG002",  # Unused method argument
]

[tool.ruff.lint.isort]
known-first-party = ["mkcv"]
force-sort-within-sections = true

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

# ---------- Mypy ----------
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
mypy_path = "src"
packages = ["mkcv"]

[[tool.mypy.overrides]]
module = ["dynaconf.*"]
ignore_missing_imports = true

# ---------- Pytest ----------
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = "test_*.py"
python_functions = "test_*"
addopts = "-v --tb=short"
```

### Key Change from v1

- **Added**: `tomli-w>=1.0` to dependencies for writing TOML files (`mkcv.toml`,
  `application.toml`). Python 3.11+ includes `tomllib` for reading TOML, but the
  stdlib has no TOML writer.

---

## C. CLI Architecture (Cyclopts)

### C.1 Root App and Meta App

The root app uses Cyclopts' **Meta App** pattern to handle global parameters that
apply before any command is dispatched. The `--workspace` flag and workspace
auto-discovery are processed here, making workspace context available to all commands.

```python
# src/mkcv/cli/app.py

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import cyclopts
from cyclopts import App, Group, Parameter

from mkcv import __version__

app = App(
    name="mkcv",
    help="AI-powered resume generator. Tailors ATS-compliant PDFs to job descriptions.",
    version=__version__,
    version_flags=["--version"],
)

# -- Register subcommands --
# Note: init_cmd (not init) to avoid shadowing the builtin
from mkcv.cli.commands.generate import generate
from mkcv.cli.commands.init_cmd import init
from mkcv.cli.commands.render import render
from mkcv.cli.commands.themes import themes
from mkcv.cli.commands.validate import validate

app.command(generate)
app.command(render)
app.command(validate)
app.command(init)
app.command(themes)

# -- Meta app for global parameters --
app.meta.group_parameters = Group("Global Options", sort_key=0)


@app.meta.default
def launcher(
    *tokens: Annotated[str, Parameter(show=False, allow_leading_hyphen=True)],
    verbose: Annotated[
        bool,
        Parameter(
            name=["--verbose", "-v"],
            help="Enable verbose output.",
        ),
    ] = False,
    log_format: Annotated[
        str,
        Parameter(
            name="--log-format",
            help="Log format: text or json.",
        ),
    ] = "text",
    config_path: Annotated[
        Path | None,
        Parameter(
            name="--config",
            help="Path to config file.",
        ),
    ] = None,
    workspace: Annotated[
        Path | None,
        Parameter(
            name="--workspace",
            help="Path to workspace root (overrides auto-discovery).",
        ),
    ] = None,
) -> None:
    """Process global options, then dispatch to the actual command."""
    # 1. Configure logging based on verbose / log_format
    _configure_logging(verbose=verbose, log_format=log_format)

    # 2. If a custom config path was given, load it
    if config_path is not None:
        _load_custom_config(config_path)

    # 3. Discover and load workspace config
    _setup_workspace(workspace_override=workspace)

    # 4. Dispatch to the actual command
    app(tokens)


def main() -> None:
    """Entry point for `mkcv` console script."""
    app.meta()


def _configure_logging(*, verbose: bool, log_format: str) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = (
        "%(asctime)s %(name)s %(levelname)s %(message)s"
        if log_format == "text"
        else '{"ts":"%(asctime)s","logger":"%(name)s","level":"%(levelname)s","msg":"%(message)s"}'
    )
    logging.basicConfig(level=level, format=fmt, force=True)


def _load_custom_config(config_path: Path) -> None:
    from mkcv.config import settings

    settings.load_file(path=str(config_path))


def _setup_workspace(*, workspace_override: Path | None) -> None:
    """Discover workspace and inject its config into the Dynaconf settings chain.

    Resolution order:
      1. --workspace CLI flag (explicit)
      2. MKCV_WORKSPACE env var
      3. Walk up from CWD looking for mkcv.toml

    If a workspace is found, its mkcv.toml is loaded into the settings chain
    and the workspace root is stored as settings.WORKSPACE_ROOT.
    If no workspace is found, settings.WORKSPACE_ROOT is set to None.
    """
    import os

    from mkcv.config import settings
    from mkcv.config.workspace import find_workspace_root, load_workspace_into_settings

    workspace_root: Path | None = None

    if workspace_override is not None:
        workspace_root = workspace_override.resolve()
    else:
        env_workspace = os.environ.get("MKCV_WORKSPACE")
        if env_workspace:
            workspace_root = Path(env_workspace).resolve()
        else:
            workspace_root = find_workspace_root(Path.cwd())

    if workspace_root is not None:
        load_workspace_into_settings(workspace_root, settings)
    else:
        settings.set("WORKSPACE_ROOT", None)
```

### C.2 `__main__.py`

*Unchanged from v1.*

```python
# src/mkcv/__main__.py
from mkcv.cli.app import main

main()
```

### C.3 Command Module Pattern

*Unchanged from v1 for render, validate, themes. Updated for generate and init.*

See **Section F** for updated `generate` and `init` command designs.

### C.4 Console Module

*Unchanged from v1.*

```python
# src/mkcv/cli/console.py

from rich.console import Console

from mkcv.core.exceptions import MkcvError

# Singleton consoles -- stdout for output, stderr for errors/logs
console = Console()
error_console = Console(stderr=True)


def print_error(exc: MkcvError) -> None:
    """Format and print an MkcvError to stderr."""
    error_console.print(f"[bold red]Error:[/bold red] {exc}")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]{message}[/green]")


def print_warning(message: str) -> None:
    """Print a warning message."""
    error_console.print(f"[yellow]Warning:[/yellow] {message}")
```

### C.5 Error Handling Flow

*Unchanged from v1.*

### C.6 Config Defaults for CLI Parameters

*Unchanged from v1.* Workspace-aware defaults are resolved at call time inside
command bodies, not at import time.

---

## D. Configuration Design (Dynaconf)

### D.1 Configuration Class

```python
# src/mkcv/config/configuration.py

from __future__ import annotations

from pathlib import Path

from dynaconf import Dynaconf, Validator


class Configuration(Dynaconf):
    """mkcv configuration backed by Dynaconf.

    Resolution order (5 layers):
      1. Bundled settings.toml (defaults)
      2. Global user config (~/.config/mkcv/settings.toml)
      3. Workspace config ({workspace}/mkcv.toml) -- injected at runtime
      4. Environment variables (MKCV_ prefix)
      5. CLI flags (applied at runtime via settings.set())
    """

    def __init__(self, **kwargs: object) -> None:
        bundled_dir = Path(__file__).parent
        bundled_settings = str(bundled_dir / "settings.toml")
        bundled_secrets = str(bundled_dir / ".secrets.toml")

        user_config_dir = Path.home() / ".config" / "mkcv"
        user_settings = str(user_config_dir / "settings.toml")

        super().__init__(
            envvar_prefix="MKCV",
            settings_files=[bundled_settings, bundled_secrets, user_settings],
            environments=False,  # No dev/prod layers -- single flat namespace
            load_dotenv=True,
            merge_enabled=True,
            **kwargs,
        )
        self._register_validators()

    def _register_validators(self) -> None:
        """Register validation rules for configuration settings."""
        self.validators.register(
            # Defaults
            Validator("defaults.theme", default="sb2nov"),
            Validator("defaults.output_dir", default=".mkcv"),
            # Pipeline
            Validator(
                "pipeline.default_provider",
                default="anthropic",
                is_in=["anthropic", "openai", "ollama", "openrouter"],
            ),
            Validator("pipeline.default_model", default="claude-sonnet-4-20250514"),
            Validator("pipeline.default_temperature", default=0.3, gte=0.0, lte=2.0),
            # Rendering
            Validator("render.engine", default="rendercv", is_in=["rendercv", "weasyprint"]),
            # Logging
            Validator("logging.level", default="INFO", is_in=["DEBUG", "INFO", "WARNING", "ERROR"]),
            Validator("logging.format", default="text", is_in=["text", "json"]),
        )

    def validate_all(self) -> None:
        """Validate all settings. Raises on failure."""
        self.validators.validate()

    def get_provider_api_key(self, provider: str) -> str | None:
        """Get API key for a provider, checking env vars first."""
        import os

        env_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
        }
        env_var = env_map.get(provider)
        if env_var:
            key = os.environ.get(env_var)
            if key:
                return key
        return self.get(f"providers.{provider}.api_key")

    @property
    def workspace_root(self) -> Path | None:
        """Return the resolved workspace root, or None if no workspace."""
        val = self.get("WORKSPACE_ROOT")
        if val is None:
            return None
        return Path(val) if not isinstance(val, Path) else val

    @property
    def in_workspace(self) -> bool:
        """Check whether a workspace is active."""
        return self.workspace_root is not None
```

### D.2 Settings Singleton

*Unchanged from v1.*

```python
# src/mkcv/config/__init__.py

from mkcv.config.configuration import Configuration

settings = Configuration()

__all__ = ["settings"]
```

### D.3 Bundled `settings.toml`

Updated to include workspace-related defaults:

```toml
# src/mkcv/config/settings.toml
# Default configuration for mkcv. Overridden by user config, workspace, and env vars.

[defaults]
theme = "sb2nov"
output_dir = ".mkcv"
# kb_path = ""  # No default -- user must provide

[workspace]
# Default workspace settings (overridden by mkcv.toml in workspace)
applications_dir = "applications"
templates_dir = "templates"
knowledge_base_dir = "knowledge-base"
application_pattern = "{date}-{position}"
company_slug = true

[pipeline]
default_provider = "anthropic"
default_model = "claude-sonnet-4-20250514"
default_temperature = 0.3

[pipeline.stages.analyze]
provider = "anthropic"
model = "claude-sonnet-4-20250514"
temperature = 0.2

[pipeline.stages.select]
provider = "anthropic"
model = "claude-sonnet-4-20250514"
temperature = 0.3

[pipeline.stages.tailor]
provider = "anthropic"
model = "claude-sonnet-4-20250514"
temperature = 0.5

[pipeline.stages.structure]
provider = "anthropic"
model = "claude-sonnet-4-20250514"
temperature = 0.1

[pipeline.stages.review]
provider = "anthropic"
model = "claude-sonnet-4-20250514"
temperature = 0.3

[render]
engine = "rendercv"
font = "SourceSansPro"
font_size = "10pt"
page_size = "letterpaper"

[render.colors]
primary = "003366"

[providers.anthropic]
# api_key set via ANTHROPIC_API_KEY env var

[providers.openai]
# api_key set via OPENAI_API_KEY env var

[providers.ollama]
base_url = "http://localhost:11434"

[providers.openrouter]
# api_key set via OPENROUTER_API_KEY env var

[voice]
guidelines = """
Direct, not flowery. No "passionate" or "leveraged."
Concrete over abstract. Technical but accessible.
Confident but not arrogant.
"""

[logging]
level = "INFO"
format = "text"

[profiles.budget.stages]
analyze = { provider = "ollama", model = "qwen2.5:32b" }
select = { provider = "ollama", model = "qwen2.5:72b" }
tailor = { provider = "anthropic", model = "claude-sonnet-4-20250514" }
structure = { provider = "ollama", model = "qwen2.5-coder:32b" }
review = { provider = "anthropic", model = "claude-sonnet-4-20250514" }

[profiles.premium.stages]
analyze = { provider = "anthropic", model = "claude-sonnet-4-20250514" }
select = { provider = "anthropic", model = "claude-sonnet-4-20250514" }
tailor = { provider = "anthropic", model = "claude-sonnet-4-20250514" }
structure = { provider = "openai", model = "gpt-4o" }
review = { provider = "anthropic", model = "claude-sonnet-4-20250514" }
```

### D.4 Bundled `.secrets.toml`

*Unchanged from v1.*

### D.5 Env Var Override Semantics

*Unchanged from v1.* One addition:

| Config Key                    | Env Var                             |
|-------------------------------|-------------------------------------|
| `defaults.theme`              | `MKCV_DEFAULTS__THEME`              |
| `pipeline.default_provider`   | `MKCV_PIPELINE__DEFAULT_PROVIDER`   |
| `providers.ollama.base_url`   | `MKCV_PROVIDERS__OLLAMA__BASE_URL`  |
| `logging.level`               | `MKCV_LOGGING__LEVEL`               |
| **`WORKSPACE_ROOT`**          | **`MKCV_WORKSPACE`** (special)      |

`MKCV_WORKSPACE` is handled specially in `_setup_workspace()` -- it provides a
path override, not a Dynaconf settings value.

### D.6 Thread-Safety / Async-Safety

*Unchanged from v1.*

---

## E. Workspace Discovery Design

### E.1 `config/workspace.py`

```python
# src/mkcv/config/workspace.py

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mkcv.config.configuration import Configuration

logger = logging.getLogger(__name__)

WORKSPACE_MARKER = "mkcv.toml"


def find_workspace_root(start: Path) -> Path | None:
    """Walk up from start looking for mkcv.toml.

    Returns the directory containing mkcv.toml, or None if not found.
    Stops at the filesystem root.
    """
    current = start.resolve()
    while True:
        candidate = current / WORKSPACE_MARKER
        if candidate.is_file():
            logger.debug("Found workspace at: %s", current)
            return current
        parent = current.parent
        if parent == current:
            # Reached filesystem root
            return None
        current = parent


def load_workspace_toml(workspace_root: Path) -> dict[str, Any]:
    """Parse mkcv.toml into a raw dict.

    Raises FileNotFoundError if mkcv.toml doesn't exist.
    Raises tomllib.TOMLDecodeError on malformed TOML.
    """
    toml_path = workspace_root / WORKSPACE_MARKER
    with toml_path.open("rb") as f:
        return tomllib.load(f)


def load_workspace_into_settings(
    workspace_root: Path,
    settings: Configuration,
) -> None:
    """Load mkcv.toml from workspace_root into the Dynaconf settings chain.

    This injects the workspace config at the correct layer in the resolution
    order (after global user config, before env vars). Dynaconf's load_file()
    with merge enabled handles this correctly.

    Also sets WORKSPACE_ROOT so all components can locate workspace paths.
    """
    toml_path = workspace_root / WORKSPACE_MARKER
    if not toml_path.is_file():
        logger.warning("Workspace marker not found: %s", toml_path)
        settings.set("WORKSPACE_ROOT", None)
        return

    # Dynaconf's load_file merges settings from the file on top of existing.
    # With merge_enabled=True on the Configuration, nested dicts are merged
    # rather than replaced.
    settings.load_file(path=str(toml_path))

    # Store workspace root as a settings value for components to use
    settings.set("WORKSPACE_ROOT", str(workspace_root))

    logger.info("Loaded workspace: %s", workspace_root)
```

### E.2 How Workspace Config Integrates with Dynaconf

The 5-layer config resolution works as follows:

```
Layer 1: src/mkcv/config/settings.toml     (loaded at Configuration.__init__)
Layer 2: ~/.config/mkcv/settings.toml       (loaded at Configuration.__init__)
Layer 3: {workspace}/mkcv.toml              (loaded at runtime via load_file)
Layer 4: MKCV_* environment variables       (always active via envvar_prefix)
Layer 5: CLI flags                          (applied via settings.set() in commands)
```

Dynaconf's `load_file()` method with `merge_enabled=True` causes values from
`mkcv.toml` to be merged on top of layers 1-2. Since env vars are always evaluated
at access time, they naturally override file-based settings. CLI flags are applied
last via `settings.set()`.

The key insight: we do NOT need a custom config loader. Dynaconf's existing
`load_file()` + `merge_enabled` handles the workspace layer correctly. We just
need to call it at the right time (in the meta app launcher, after workspace
discovery but before command dispatch).

---

## F. Updated CLI Commands

### F.1 `mkcv init [PATH]` -- Workspace Initialization

```python
# src/mkcv/cli/commands/init_cmd.py

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from cyclopts import Parameter

logger = logging.getLogger(__name__)


async def init(
    path: Annotated[
        Path | None,
        Parameter(help="Directory to initialize as workspace. Defaults to CWD."),
    ] = None,
    *,
    name: Annotated[
        str | None,
        Parameter(help="Your name (for KB template)."),
    ] = None,
) -> None:
    """Initialize a new mkcv workspace.

    Creates the workspace directory structure with mkcv.toml, knowledge-base/,
    applications/, templates/, and .gitignore. Idempotent: skips existing files.
    """
    from mkcv.cli.console import console, print_success, print_warning
    from mkcv.core.exceptions import MkcvError, WorkspaceError
    from mkcv.factories import create_workspace_manager

    try:
        target = (path or Path.cwd()).resolve()
        manager = create_workspace_manager()

        # Check if already initialized
        if (target / "mkcv.toml").exists():
            print_warning(f"Workspace already initialized at {target}")
            print_warning("Ensuring directory structure is complete...")

        workspace_root = manager.create_workspace(target, name=name)

        print_success(f"Workspace initialized at {workspace_root}")
        console.print()
        console.print("  Created:")
        console.print(f"    {workspace_root / 'mkcv.toml'}")
        console.print(f"    {workspace_root / 'knowledge-base/'}")
        console.print(f"    {workspace_root / 'applications/'}")
        console.print(f"    {workspace_root / 'templates/'}")
        console.print(f"    {workspace_root / '.gitignore'}")
        console.print()
        console.print("  Next steps:")
        console.print("    1. Edit knowledge-base/career.md with your career history")
        console.print("    2. Run: mkcv generate --jd <job-description.txt>")

    except WorkspaceError as exc:
        from mkcv.cli.console import print_error

        print_error(exc)
        raise SystemExit(exc.exit_code) from exc
```

### F.2 `mkcv generate` -- Workspace-Aware Generation

```python
# src/mkcv/cli/commands/generate.py

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from cyclopts import Parameter

logger = logging.getLogger(__name__)


async def generate(
    *,
    jd: Annotated[Path, Parameter(help="Job description file (text/markdown).")],
    kb: Annotated[
        Path | None,
        Parameter(help="Knowledge base file. In workspace: auto-resolved from knowledge-base/."),
    ] = None,
    output_dir: Annotated[
        Path | None,
        Parameter(name="--output-dir", help="Output directory."),
    ] = None,
    theme: Annotated[str, Parameter(help="RenderCV theme name.")] = "sb2nov",
    profile: Annotated[str, Parameter(help="Provider profile (budget/premium).")] = "premium",
    from_stage: Annotated[int, Parameter(name="--from-stage", help="Resume from this stage (1-5).")] = 1,
    render: Annotated[bool, Parameter(help="Auto-render PDF after pipeline.")] = True,
    interactive: Annotated[bool, Parameter(help="Pause after each stage for review.")] = False,
    provider: Annotated[str | None, Parameter(help="Override provider for all stages.")] = None,
    model: Annotated[str | None, Parameter(help="Override model for all stages.")] = None,
    dry_run: Annotated[bool, Parameter(name="--dry-run", help="Show plan without calling APIs.")] = False,
) -> None:
    """Run the AI pipeline to generate a tailored resume from a JD and knowledge base.

    In a workspace: auto-resolves KB from knowledge-base/, creates application
    directory after Stage 1 analysis. --kb overrides the default KB.

    Without a workspace: requires explicit --jd and --kb. Outputs to CWD/.mkcv/.
    """
    from mkcv.cli.console import console, print_error, print_warning
    from mkcv.config import settings
    from mkcv.core.exceptions import MkcvError

    try:
        # --- Resolve KB ---
        resolved_kb: Path
        if kb is not None:
            resolved_kb = kb
        elif settings.in_workspace:
            # Auto-resolve KB from workspace
            ws_root = settings.workspace_root
            assert ws_root is not None  # guarded by in_workspace
            kb_dir = settings.get("workspace.knowledge_base_dir", "knowledge-base")
            resolved_kb = ws_root / kb_dir / "career.md"
            if not resolved_kb.exists():
                raise MkcvError(
                    f"Knowledge base not found: {resolved_kb}\n"
                    f"Create it or pass --kb explicitly.",
                    exit_code=2,
                )
        else:
            raise MkcvError(
                "No workspace found. Pass --kb to specify a knowledge base file.\n"
                "Or run 'mkcv init' to create a workspace.",
                exit_code=2,
            )

        # --- Resolve output directory ---
        # In workspace mode: output is deferred to after Stage 1 (when we know
        # company and position). For now, just validate inputs.
        # Without workspace: output to CWD/.mkcv/
        if output_dir is None and not settings.in_workspace:
            output_dir = Path(settings.get("defaults.output_dir", ".mkcv"))

        # --- Stub: Pipeline not yet implemented ---
        if settings.in_workspace:
            console.print(f"[dim]Workspace mode: {settings.workspace_root}[/dim]")
        else:
            console.print("[dim]Non-workspace mode[/dim]")

        console.print(f"[dim]Pipeline not yet implemented. JD: {jd}, KB: {resolved_kb}[/dim]")
        # Future: service = create_pipeline_service()
        # Future: await service.run(...)

    except MkcvError as exc:
        print_error(exc)
        raise SystemExit(exc.exit_code) from exc
```

### F.3 Global Options

The `--workspace PATH` flag is defined in the meta app launcher (Section C.1).
It overrides both `MKCV_WORKSPACE` env var and CWD-based auto-discovery.

---

## G. mkcv.toml Schema Design

### G.1 Complete Schema

```toml
# ~/Documents/cv/mkcv.toml
# Workspace configuration for mkcv

[workspace]
version = "0.1.0"           # mkcv workspace format version

[paths]
knowledge_base_dir = "knowledge-base"   # Directory containing KB files
applications_dir = "applications"       # Directory for application outputs
templates_dir = "templates"             # Directory for custom render templates

[naming]
company_slug = true                     # Group applications by company directory
application_pattern = "{date}-{position}"  # Pattern for application dir names
# Available variables: {date} (YYYY-MM), {company}, {position}

[defaults]
theme = "sb2nov"
profile = "premium"
# kb_file = "career.md"     # Relative to knowledge_base_dir (default: career.md)

[voice]
guidelines = """
Direct, not flowery. No "passionate" or "leveraged."
Concrete over abstract. Technical but accessible.
Confident but not arrogant.
"""
```

### G.2 Schema Notes

- **`workspace.version`**: Allows future schema migrations. The tool checks this
  and warns if the workspace was created by a newer version.
- **`paths.*`**: All relative to workspace root. No absolute paths allowed.
- **`naming.company_slug`**: When `true`, applications are grouped under
  `applications/{company}/{date-position}/`. When `false`, applications are flat:
  `applications/{date-position}/`.
- **`naming.application_pattern`**: Template string for directory naming. Variables
  are slugified before interpolation.
- **`defaults.*`**: Merged into the Dynaconf settings chain. These override bundled
  defaults and global user config, but are overridden by env vars and CLI flags.
- **`voice.*`**: Workspace-specific voice guidelines. Merged with (overrides) global
  voice settings.

### G.3 Template `mkcv.toml` Generated by `mkcv init`

```toml
# mkcv workspace configuration
# https://github.com/bkuberek/mkcv

[workspace]
version = "0.1.0"

[paths]
knowledge_base_dir = "knowledge-base"
applications_dir = "applications"
templates_dir = "templates"

[naming]
company_slug = true
application_pattern = "{date}-{position}"

[defaults]
theme = "sb2nov"
profile = "premium"

# [voice]
# guidelines = """
# Direct, not flowery. Concrete over abstract.
# Technical but accessible. Confident but not arrogant.
# """
```

---

## H. Application Management Design

### H.1 `application.toml` Schema

```toml
# applications/deepl/2026-03-senior-staff-engineer/application.toml
# Auto-generated by mkcv. Safe to edit.

[application]
company = "DeepL"
position = "Senior Staff Software Engineer (API)"
date = "2026-03-18"
status = "draft"                  # draft | applied | interviewing | offered | rejected | withdrawn
url = ""                          # Job posting URL
created_at = "2026-03-18T10:30:00Z"

[source]
jd_file = "jd.txt"               # Relative to application dir
kb_file = "../../knowledge-base/career.md"  # Relative to application dir
```

### H.2 WorkspaceManager

```python
# src/mkcv/adapters/filesystem/workspace_manager.py

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import tomli_w

from mkcv.core.exceptions import WorkspaceError
from mkcv.core.models.application_metadata import ApplicationMetadata
from mkcv.core.models.workspace_config import WorkspaceConfig

logger = logging.getLogger(__name__)

# Template content for new workspace files
_MKCV_TOML_TEMPLATE = """\
# mkcv workspace configuration
# https://github.com/bkuberek/mkcv

[workspace]
version = "0.1.0"

[paths]
knowledge_base_dir = "knowledge-base"
applications_dir = "applications"
templates_dir = "templates"

[naming]
company_slug = true
application_pattern = "{date}-{position}"

[defaults]
theme = "sb2nov"
profile = "premium"
"""

_GITIGNORE_TEMPLATE = """\
# mkcv workspace ignores
.mkcv/
*.pdf
*.png

# OS files
.DS_Store
Thumbs.db
"""

_CAREER_MD_TEMPLATE = """\
# {name} -- Career Knowledge Base

## Personal Information

| Field    | Value              |
|----------|--------------------|
| Name     | {name}             |
| Email    |                    |
| Phone    |                    |
| Location |                    |
| LinkedIn |                    |
| GitHub   |                    |
| Website  |                    |

## Languages

- English (native)

## Professional Summary

<!-- 2-3 paragraphs summarizing your career -->

## Technical Skills -- Master List

### Programming Languages
### Frontend
### Backend Frameworks
### AI / ML / LLM
### Databases & Data Stores
### Infrastructure & DevOps

## Career History -- Complete and Detailed

### Company Name -- Job Title
**YYYY-MM to YYYY-MM** | Location

- Achievement bullet using XYZ formula
- Tech stack: Python, FastAPI, PostgreSQL

## Key Achievements

## Strengths

## Passions & Interests
"""

_VOICE_MD_TEMPLATE = """\
# Voice Guidelines

<!-- These guidelines shape how your resume content is written. -->
<!-- Edit to match your personal voice and tone preferences. -->

## Tone
- Direct, not flowery
- Concrete over abstract
- Technical but accessible
- Confident but not arrogant

## Avoid
- "Passionate about..."
- "Leveraged..."
- "Spearheaded..."
- Buzzwords without substance

## Prefer
- Specific metrics and outcomes
- Active voice
- Clear cause-and-effect
"""


class WorkspaceManager:
    """Manages workspace directory structure and application lifecycle.

    Responsible for:
    - Creating workspace directories and template files
    - Creating application directories from pipeline output
    - Slugifying names for filesystem safety
    - Placing JD files and generating application.toml
    - Handling directory collisions
    """

    def create_workspace(
        self,
        path: Path,
        *,
        name: str | None = None,
    ) -> Path:
        """Create a new workspace at the given path.

        Creates: mkcv.toml, knowledge-base/, applications/, templates/, .gitignore

        Idempotent: skips files that already exist, creates missing directories.
        Returns the workspace root path.

        Raises WorkspaceError if path is not a writable directory.
        """
        workspace_root = path.resolve()

        # Create root directory if needed
        try:
            workspace_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise WorkspaceError(
                f"Cannot create workspace directory: {workspace_root}: {exc}"
            ) from exc

        # Create mkcv.toml (skip if exists)
        toml_path = workspace_root / "mkcv.toml"
        if not toml_path.exists():
            toml_path.write_text(_MKCV_TOML_TEMPLATE, encoding="utf-8")
            logger.info("Created %s", toml_path)
        else:
            logger.debug("Skipped existing %s", toml_path)

        # Create directories
        for dir_name in ("knowledge-base", "applications", "templates"):
            dir_path = workspace_root / dir_name
            dir_path.mkdir(exist_ok=True)
            logger.debug("Ensured directory: %s", dir_path)

        # Create knowledge-base/career.md (skip if exists)
        career_path = workspace_root / "knowledge-base" / "career.md"
        if not career_path.exists():
            display_name = name or "Your Name"
            career_path.write_text(
                _CAREER_MD_TEMPLATE.format(name=display_name),
                encoding="utf-8",
            )
            logger.info("Created %s", career_path)

        # Create knowledge-base/voice.md (skip if exists)
        voice_path = workspace_root / "knowledge-base" / "voice.md"
        if not voice_path.exists():
            voice_path.write_text(_VOICE_MD_TEMPLATE, encoding="utf-8")
            logger.info("Created %s", voice_path)

        # Create .gitignore (skip if exists)
        gitignore_path = workspace_root / ".gitignore"
        if not gitignore_path.exists():
            gitignore_path.write_text(_GITIGNORE_TEMPLATE, encoding="utf-8")
            logger.info("Created %s", gitignore_path)

        return workspace_root

    def create_application(
        self,
        *,
        workspace_root: Path,
        company: str,
        position: str,
        jd_source: Path,
        url: str | None = None,
        application_date: date | None = None,
        application_pattern: str = "{date}-{position}",
        company_slug_enabled: bool = True,
        applications_dir: str = "applications",
    ) -> Path:
        """Create an application directory and populate it.

        Creates:
          applications/{company_slug}/{date}-{position_slug}/
          ├── application.toml
          ├── jd.txt
          └── .mkcv/

        Returns the application directory path.

        Collision handling: if directory exists, appends -2, -3, etc.
        """
        app_date = application_date or date.today()
        date_str = app_date.strftime("%Y-%m")

        company_slug = self.slugify(company)
        position_slug = self.slugify(position)

        # Build directory name from pattern
        dir_name = application_pattern.format(
            date=date_str,
            company=company_slug,
            position=position_slug,
        )

        # Build full path
        apps_base = workspace_root / applications_dir
        if company_slug_enabled:
            app_dir = apps_base / company_slug / dir_name
        else:
            app_dir = apps_base / dir_name

        # Handle collisions
        app_dir = self._resolve_collision(app_dir)

        # Create directories
        app_dir.mkdir(parents=True, exist_ok=True)
        (app_dir / ".mkcv").mkdir(exist_ok=True)

        # Copy JD file
        jd_content = jd_source.read_text(encoding="utf-8")
        jd_dest = app_dir / "jd.txt"
        jd_dest.write_text(jd_content, encoding="utf-8")
        logger.info("Placed JD: %s", jd_dest)

        # Generate application.toml
        metadata = ApplicationMetadata(
            company=company,
            position=position,
            date=app_date,
            status="draft",
            url=url,
            created_at=datetime.now(tz=timezone.utc),
        )
        self._write_application_toml(app_dir, metadata)

        logger.info("Created application: %s", app_dir)
        return app_dir

    def slugify(self, text: str) -> str:
        """Convert text to a filesystem-safe slug.

        Rules:
        - Lowercase
        - Unicode normalized (NFKD) and ASCII-transliterated
        - Spaces, underscores, and non-alphanumeric chars replaced with hyphens
        - Consecutive hyphens collapsed
        - Leading/trailing hyphens stripped
        - Max length: 64 characters

        Examples:
            "DeepL" -> "deepl"
            "Senior Staff Software Engineer (API)" -> "senior-staff-software-engineer-api"
            "Café & Co." -> "cafe-co"
        """
        # Normalize unicode
        text = unicodedata.normalize("NFKD", text)
        # Remove non-ASCII (accents become separate chars after NFKD)
        text = text.encode("ascii", "ignore").decode("ascii")
        # Lowercase
        text = text.lower()
        # Replace non-alphanumeric with hyphens
        text = re.sub(r"[^a-z0-9]+", "-", text)
        # Collapse consecutive hyphens
        text = re.sub(r"-{2,}", "-", text)
        # Strip leading/trailing hyphens
        text = text.strip("-")
        # Truncate
        if len(text) > 64:
            text = text[:64].rstrip("-")
        return text

    def _resolve_collision(self, path: Path) -> Path:
        """If path exists, append -2, -3, etc. until a free name is found."""
        if not path.exists():
            return path
        base = path
        for i in range(2, 100):
            candidate = base.parent / f"{base.name}-{i}"
            if not candidate.exists():
                logger.warning(
                    "Directory collision: %s exists. Using %s",
                    base.name,
                    candidate.name,
                )
                return candidate
        raise WorkspaceError(
            f"Too many collisions for directory: {base}. Clean up old applications."
        )

    def _write_application_toml(
        self,
        app_dir: Path,
        metadata: ApplicationMetadata,
    ) -> None:
        """Write application.toml from metadata."""
        data: dict[str, Any] = {
            "application": {
                "company": metadata.company,
                "position": metadata.position,
                "date": metadata.date.isoformat(),
                "status": metadata.status,
                "url": metadata.url or "",
                "created_at": metadata.created_at.isoformat(),
            },
        }
        toml_path = app_dir / "application.toml"
        with toml_path.open("wb") as f:
            tomli_w.dump(data, f)
        logger.debug("Wrote %s", toml_path)
```

### H.3 Slugification Details

The `slugify()` method handles:
- Unicode: NFKD normalization + ASCII transliteration ("Cafe" from "Cafe")
- Special chars: parentheses, ampersands, dots stripped ("api" from "(API)")
- Spaces: collapsed to single hyphens
- Length: truncated at 64 chars (filesystem safety)

### H.4 Collision Handling

When `applications/deepl/2026-03-senior-staff-engineer/` already exists:
1. The tool tries `2026-03-senior-staff-engineer-2`
2. Then `-3`, `-4`, etc. up to `-99`
3. Logs a warning when a collision is resolved
4. Raises `WorkspaceError` if 99 collisions are exhausted (pathological case)

This preserves existing application data while allowing re-runs against the same JD.

---

## I. Updated Config Architecture (5-Layer Resolution)

### I.1 Resolution Order

```
 Priority    Layer                          Source
 (lowest)
    1        Built-in defaults              src/mkcv/config/settings.toml
    2        Global user config             ~/.config/mkcv/settings.toml
    3        Workspace config               {workspace}/mkcv.toml
    4        Environment variables           MKCV_* prefix
    5        CLI flags                       --theme, --profile, etc.
 (highest)
```

### I.2 How Dynaconf Handles This

```python
# At Configuration.__init__():
#   settings_files = [bundled_settings, bundled_secrets, user_settings]
#   → Layers 1 and 2 are loaded

# At _setup_workspace() in meta app launcher:
#   settings.load_file(path=str(workspace_root / "mkcv.toml"))
#   → Layer 3 is loaded (merge_enabled=True merges nested dicts)

# Dynaconf envvar_prefix="MKCV" handles layer 4 automatically

# In command bodies:
#   settings.set("defaults.theme", theme_from_cli)
#   → Layer 5 applied on demand
```

### I.3 Example Resolution

Given:
- Bundled: `defaults.theme = "sb2nov"`
- User: `defaults.theme = "classic"`
- Workspace: `[defaults] theme = "moderncv"`
- Env: (not set)
- CLI: (not set)

Result: `settings.defaults.theme` == `"moderncv"` (workspace overrides user).

If the user also passes `--theme engineering`:
- CLI sets `settings.set("defaults.theme", "engineering")`
- Result: `"engineering"` (CLI overrides all).

---

## J. Core Domain Design (Hexagonal)

### J.1 Port Interfaces (Protocols)

*Unchanged from v1.* The `ArtifactStorePort` interface does not change -- the
workspace-awareness is an implementation detail of `FileSystemArtifactStore`, not a
contract change.

### J.2 Service Classes

*Unchanged from v1.* `PipelineService` still depends only on ports. The workspace
manager is not a port -- it's used by CLI commands directly (or via factories). The
pipeline does not need to know about workspaces; the CLI resolves workspace context
and passes concrete paths to the pipeline.

### J.3 Exception Hierarchy

Updated with workspace-specific errors:

```python
# src/mkcv/core/exceptions.py

from __future__ import annotations


class MkcvError(Exception):
    """Base exception for all mkcv errors."""

    exit_code: int = 1

    def __init__(self, message: str, *, exit_code: int | None = None) -> None:
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code


# -- Configuration Errors (exit code 3) --

class ConfigurationError(MkcvError):
    """Raised for configuration problems (missing keys, bad config file)."""
    exit_code: int = 3


# -- Workspace Errors (exit code 7) --

class WorkspaceError(MkcvError):
    """Base class for workspace-related errors."""
    exit_code: int = 7


class WorkspaceNotFoundError(WorkspaceError):
    """No workspace found when one was expected."""
    pass


class WorkspaceExistsError(WorkspaceError):
    """Workspace already exists at the target path (non-idempotent operation)."""
    pass


# -- Provider Errors (exit code 4) --

class ProviderError(MkcvError):
    """Base class for AI provider errors."""
    exit_code: int = 4


class RateLimitError(ProviderError):
    """API rate limit exceeded. Eligible for retry with backoff."""
    pass


class AuthenticationError(ProviderError):
    """Invalid or missing API key."""
    pass


class ContextLengthError(ProviderError):
    """Input exceeds model context window."""
    pass


class ProviderConnectionError(ProviderError):
    """Network error communicating with provider."""
    pass


# -- Pipeline Errors (exit code 5) --

class PipelineError(MkcvError):
    """Base class for pipeline execution errors."""
    exit_code: int = 5


class PipelineStageError(PipelineError):
    """A specific pipeline stage failed."""

    def __init__(
        self,
        message: str,
        *,
        stage: int,
        stage_name: str,
        exit_code: int | None = None,
    ) -> None:
        super().__init__(message, exit_code=exit_code)
        self.stage = stage
        self.stage_name = stage_name


class ValidationError(PipelineError):
    """AI output failed Pydantic validation."""
    pass


# -- Render Errors (exit code 6) --

class RenderError(MkcvError):
    """Rendering failed (YAML -> PDF)."""
    exit_code: int = 6


class TemplateError(MkcvError):
    """Jinja2 template loading or rendering error."""
    exit_code: int = 1
```

### J.4 Updated Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments / missing required options |
| 3 | Configuration error |
| 4 | Provider error |
| 5 | Pipeline/Validation error |
| 6 | Render error |
| **7** | **Workspace error (new)** |

### J.5 Pydantic Models

All models from v1 are preserved. Two new models are added:

#### `WorkspaceConfig`

```python
# src/mkcv/core/models/workspace_config.py

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkspaceNaming(BaseModel):
    """Naming configuration for workspace directories."""

    company_slug: bool = Field(
        default=True,
        description="Group applications by company directory.",
    )
    application_pattern: str = Field(
        default="{date}-{position}",
        description="Pattern for application directory names. Variables: {date}, {company}, {position}.",
    )


class WorkspacePaths(BaseModel):
    """Path configuration for workspace directories. All relative to workspace root."""

    knowledge_base_dir: str = Field(
        default="knowledge-base",
        description="Directory containing knowledge base files.",
    )
    applications_dir: str = Field(
        default="applications",
        description="Directory for application outputs.",
    )
    templates_dir: str = Field(
        default="templates",
        description="Directory for custom render templates.",
    )


class WorkspaceDefaults(BaseModel):
    """Default settings for the workspace."""

    theme: str = "sb2nov"
    profile: str = "premium"
    kb_file: str = Field(
        default="career.md",
        description="Default KB filename within knowledge_base_dir.",
    )


class WorkspaceConfig(BaseModel):
    """Complete workspace configuration parsed from mkcv.toml.

    This model validates the workspace config file. It is NOT used
    directly at runtime -- the parsed values are loaded into Dynaconf
    settings for unified config access. This model exists for validation
    and documentation purposes.
    """

    version: str = Field(
        default="0.1.0",
        description="Workspace format version.",
    )
    paths: WorkspacePaths = Field(default_factory=WorkspacePaths)
    naming: WorkspaceNaming = Field(default_factory=WorkspaceNaming)
    defaults: WorkspaceDefaults = Field(default_factory=WorkspaceDefaults)
```

#### `ApplicationMetadata`

```python
# src/mkcv/core/models/application_metadata.py

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ApplicationMetadata(BaseModel):
    """Metadata for a single job application.

    Auto-generated by the tool when creating an application directory.
    Stored as application.toml. Users may edit status and url manually.
    """

    company: str = Field(description="Company name (original, not slugified).")
    position: str = Field(description="Job title (original, not slugified).")
    date: date = Field(description="Application date.")
    status: Literal[
        "draft",
        "applied",
        "interviewing",
        "offered",
        "rejected",
        "withdrawn",
    ] = Field(
        default="draft",
        description="Application lifecycle status.",
    )
    url: str | None = Field(
        default=None,
        description="Job posting URL.",
    )
    created_at: datetime = Field(
        description="Timestamp when this application record was created.",
    )
```

### J.6 Updated Model Re-exports

```python
# src/mkcv/core/models/__init__.py

from mkcv.core.models.application_metadata import ApplicationMetadata
from mkcv.core.models.content import (
    MissionStatement,
    SkillGroup,
    TailoredBullet,
    TailoredContent,
    TailoredRole,
)
from mkcv.core.models.experience import ExperienceSelection, SelectedExperience
from mkcv.core.models.jd_analysis import JDAnalysis, Requirement
from mkcv.core.models.pipeline import PipelineResult, StageMetadata
from mkcv.core.models.resume import (
    ExperienceEntry,
    RenderCVResume,
    ResumeCV,
    ResumeDesign,
    SkillEntry,
    SocialNetwork,
)
from mkcv.core.models.review import ATSCheck, BulletReview, KeywordCoverage, ReviewReport
from mkcv.core.models.workspace_config import (
    WorkspaceConfig,
    WorkspaceDefaults,
    WorkspaceNaming,
    WorkspacePaths,
)

__all__ = [
    "ATSCheck",
    "ApplicationMetadata",
    "BulletReview",
    "ExperienceEntry",
    "ExperienceSelection",
    "JDAnalysis",
    "KeywordCoverage",
    "MissionStatement",
    "PipelineResult",
    "RenderCVResume",
    "Requirement",
    "ResumeCV",
    "ResumeDesign",
    "ReviewReport",
    "SelectedExperience",
    "SkillEntry",
    "SkillGroup",
    "StageMetadata",
    "TailoredBullet",
    "TailoredContent",
    "TailoredRole",
    "SocialNetwork",
    "WorkspaceConfig",
    "WorkspaceDefaults",
    "WorkspaceNaming",
    "WorkspacePaths",
    "ApplicationMetadata",
]
```

---

## K. Updated ArtifactStore

### K.1 Workspace-Aware `FileSystemArtifactStore`

```python
# src/mkcv/adapters/artifact_store.py

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path(".mkcv")


class FileSystemArtifactStore:
    """Persists pipeline artifacts to the filesystem.

    Supports two modes:

    1. Workspace mode:
       Pipeline artifacts (.mkcv/) are written inside the application dir:
         applications/{company}/{date-position}/.mkcv/
       Final outputs (resume.yaml, resume.pdf) go at the application root:
         applications/{company}/{date-position}/resume.yaml

    2. Non-workspace mode:
       Everything goes to .mkcv/ in CWD (original behavior):
         .mkcv/<timestamp>_<company>/
    """

    def create_run_dir(
        self,
        *,
        company: str,
        output_dir: Path | None = None,
    ) -> Path:
        """Create a timestamped run directory.

        In workspace mode, output_dir should be the .mkcv/ subdir
        of the application directory (set by the CLI layer).
        In non-workspace mode, output_dir defaults to .mkcv/ in CWD.
        """
        base = output_dir or DEFAULT_OUTPUT_DIR
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        safe_company = "".join(
            c if c.isalnum() or c in "-_" else "_" for c in company.lower()
        )
        run_dir = base / f"{timestamp}_{safe_company}"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "input").mkdir(exist_ok=True)
        (run_dir / "output").mkdir(exist_ok=True)
        logger.debug("Created run directory: %s", run_dir)
        return run_dir

    def save_artifact(
        self,
        *,
        run_dir: Path,
        name: str,
        data: BaseModel | dict[str, Any] | str,
        format: str = "json",
    ) -> Path:
        """Save an artifact. Returns the file path."""
        file_path = run_dir / f"{name}.{format}"
        content: str
        if isinstance(data, BaseModel):
            if format == "yaml":
                content = yaml.dump(
                    data.model_dump(mode="json"), default_flow_style=False
                )
            else:
                content = data.model_dump_json(indent=2)
        elif isinstance(data, dict):
            if format == "yaml":
                content = yaml.dump(data, default_flow_style=False)
            else:
                content = json.dumps(data, indent=2)
        else:
            content = data

        file_path.write_text(content, encoding="utf-8")
        logger.debug("Saved artifact: %s", file_path)
        return file_path

    def save_final_output(
        self,
        *,
        application_dir: Path,
        name: str,
        data: BaseModel | dict[str, Any] | str,
        format: str = "yaml",
    ) -> Path:
        """Save a final output file at the application directory root.

        Used for resume.yaml and resume.pdf -- the files the user cares about.
        In non-workspace mode, application_dir is the run_dir itself.
        """
        return self.save_artifact(
            run_dir=application_dir,
            name=name,
            data=data,
            format=format,
        )

    def load_artifact(
        self,
        *,
        run_dir: Path,
        name: str,
        model: type[BaseModel] | None = None,
        format: str = "json",
    ) -> BaseModel | dict[str, Any] | str:
        """Load an artifact from disk."""
        file_path = run_dir / f"{name}.{format}"
        if not file_path.exists():
            msg = f"Artifact not found: {file_path}"
            raise FileNotFoundError(msg)

        raw = file_path.read_text(encoding="utf-8")

        if format == "json":
            parsed = json.loads(raw)
            if model is not None:
                return model.model_validate(parsed)
            return parsed
        elif format == "yaml":
            parsed = yaml.safe_load(raw)
            if model is not None:
                return model.model_validate(parsed)
            return parsed
        else:
            return raw

    def save_input(
        self,
        *,
        run_dir: Path,
        name: str,
        content: str,
    ) -> Path:
        """Save an input file to the run's input/ subdirectory."""
        input_dir = run_dir / "input"
        input_dir.mkdir(exist_ok=True)
        file_path = input_dir / name
        file_path.write_text(content, encoding="utf-8")
        return file_path
```

### K.2 Directory Layout Comparison

**Non-workspace mode** (no mkcv.toml found):
```
<cwd>/
└── .mkcv/
    └── 2026-03-18T10-30-00_deepl/
        ├── input/
        │   ├── jd.txt
        │   └── kb.md
        ├── stage1_analysis.json
        ├── ...
        ├── output/
        │   ├── resume.pdf
        │   └── resume.yaml
        └── meta.json
```

**Workspace mode** (mkcv.toml found):
```
~/Documents/cv/
├── mkcv.toml
├── knowledge-base/
│   ├── career.md
│   └── voice.md
├── applications/
│   └── deepl/
│       └── 2026-03-senior-staff-engineer/
│           ├── application.toml          # Auto-generated
│           ├── jd.txt                    # Placed by tool
│           ├── resume.yaml               # Final output (at app root)
│           ├── resume.pdf                # Final output (at app root)
│           └── .mkcv/                    # Pipeline artifacts
│               └── 2026-03-18T10-30-00_deepl/
│                   ├── input/
│                   ├── stage1_analysis.json
│                   ├── ...
│                   └── meta.json
└── ...
```

---

## L. Updated Factory Functions

```python
# src/mkcv/factories.py

from __future__ import annotations

from mkcv.adapters.artifact_store import FileSystemArtifactStore
from mkcv.adapters.filesystem.workspace_manager import WorkspaceManager
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.adapters.prompt_loader import FileSystemPromptLoader
from mkcv.config import settings
from mkcv.core.services import PipelineService, RenderService, ValidationService


def create_prompt_loader() -> FileSystemPromptLoader:
    """Create a prompt loader with bundled templates + optional user override."""
    user_prompt_dir = settings.get("prompts.override_dir", None)
    return FileSystemPromptLoader(user_override_dir=user_prompt_dir)


def create_artifact_store() -> FileSystemArtifactStore:
    """Create a filesystem artifact store."""
    return FileSystemArtifactStore()


def create_workspace_manager() -> WorkspaceManager:
    """Create a workspace manager for directory operations."""
    return WorkspaceManager()


def create_llm_adapter() -> StubLLMAdapter:
    """Create an LLM adapter based on configuration.

    For this change, always returns StubLLMAdapter.
    Future: reads settings.pipeline.default_provider to select adapter.
    """
    return StubLLMAdapter()


def create_pipeline_service() -> PipelineService:
    """Wire up the PipelineService with all dependencies."""
    return PipelineService(
        llm=create_llm_adapter(),
        prompt_loader=create_prompt_loader(),
        artifact_store=create_artifact_store(),
    )


def create_render_service() -> RenderService:
    """Wire up the RenderService.

    Stub: uses a placeholder renderer for this change.
    """
    raise NotImplementedError(
        "RenderService requires a renderer adapter (RenderCV integration). "
        "This will be implemented in a future change."
    )


def create_validation_service() -> ValidationService:
    """Wire up the ValidationService."""
    return ValidationService(
        prompt_loader=create_prompt_loader(),
    )
```

---

## M. Updated Dependency Flow

```
                     ┌─────────────────────────┐
                     │      CLI Commands        │
                     │  (cli/commands/*.py)      │
                     └─────────┬───────────────┘
                               │ imports
                               ▼
                     ┌─────────────────────────┐
                     │      factories.py        │
                     │  create_*_service()      │
                     │  create_workspace_manager│
                     └─────────┬───────────────┘
                               │ creates
              ┌────────────────┼────────────────┬──────────────┐
              ▼                ▼                ▼              ▼
   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
   │ Pipeline     │ │ Render       │ │ Validation   │ │ Workspace    │
   │ Service      │ │ Service      │ │ Service      │ │ Manager      │
   └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
          │                │                │                │
          │ depends on     │ depends on     │ depends on     │ uses
          ▼                ▼                ▼                ▼
   ┌─────────────────────────────────────────────┐  ┌──────────────┐
   │              Port Protocols                  │  │ Filesystem   │
   │  (core/ports.py: LLMPort, RendererPort,     │  │ (pathlib)    │
   │   PromptLoaderPort, ArtifactStorePort)      │  └──────────────┘
   └─────────────────────┬───────────────────────┘
                         │
                         │ implemented by
                         ▼
   ┌─────────────────────────────────────────────────────────────┐
   │                        Adapters                              │
   │  (adapters/: prompt_loader.py, artifact_store.py,           │
   │   llm/stub.py, filesystem/workspace_manager.py)             │
   └─────────────────────┬───────────────────────────────────────┘
                         │
                         │ reads from
                         ▼
                   ┌─────────────────┐
                   │   Config        │
                   │ (Dynaconf)      │
                   │                 │
                   │ Layers:         │
                   │ 1. bundled      │
                   │ 2. global user  │
                   │ 3. workspace    │◄── workspace.py discovery
                   │ 4. env vars     │
                   │ 5. CLI flags    │
                   └─────────────────┘

   Direction of dependency: ───►
   Core (ports/services/models) has ZERO imports from adapters or CLI.
   WorkspaceManager is an adapter, NOT a port -- it is not abstracted
   behind a protocol because there's only one implementation and it's
   a filesystem-only operation with no need for test substitution.
```

**Key difference from v1**: `WorkspaceManager` is a direct adapter (not behind a
port protocol) because:
1. There's only one implementation (filesystem)
2. Tests use real filesystem via `tmp_path`
3. No network or external service involved
4. Adding a protocol would be over-engineering for directory operations

---

## N. Adapter Design

### N.1 FileSystemPromptLoader

*Unchanged from v1.*

### N.2 LLM Adapter Stub

*Unchanged from v1.*

### N.3 LLM Adapter Base

*Unchanged from v1.*

---

## O. Data Flow (Stub)

Updated to show workspace-aware flow:

```
User ──► `mkcv generate --jd deepl.txt`  (in workspace)
           │
           ▼
       meta.launcher
           │ 1. --verbose, --config, --workspace
           │ 2. find_workspace_root(cwd) → ~/Documents/cv/
           │ 3. load_workspace_into_settings(~/Documents/cv/, settings)
           │    → settings.WORKSPACE_ROOT = ~/Documents/cv/
           │    → workspace defaults merged into settings
           │
           ▼
       generate command
           │ 1. settings.in_workspace == True
           │ 2. resolved_kb = ~/Documents/cv/knowledge-base/career.md
           │ 3. (future: run pipeline → Stage 1 → get company/position)
           │ 4. (future: workspace_manager.create_application(...))
           │ 5. (future: artifact_store writes to application/.mkcv/)
           │
           └── NotImplementedError ("Pipeline not yet implemented")
           ▼
       print stub message + exit

User ──► `mkcv generate --jd deepl.txt --kb career.md`  (no workspace)
           │
           ▼
       meta.launcher
           │ 1. find_workspace_root(cwd) → None
           │ 2. settings.WORKSPACE_ROOT = None
           │
           ▼
       generate command
           │ 1. settings.in_workspace == False
           │ 2. resolved_kb = career.md (from --kb)
           │ 3. output_dir = .mkcv/ (in CWD)
           │
           └── NotImplementedError ("Pipeline not yet implemented")

User ──► `mkcv init ~/Documents/cv`
           │
           ▼
       init command
           │ workspace_manager.create_workspace(~/Documents/cv)
           │ → Creates: mkcv.toml, knowledge-base/, applications/, .gitignore
           ▼
       print success message
```

---

## P. Test Architecture

### P.1 Directory Structure

*See Section A for the full test tree.* Key additions:

| Test File | What It Validates |
|-----------|-------------------|
| `test_commands/test_init_cmd.py` | Workspace creation, idempotency, file contents |
| `test_commands/test_generate.py` | Workspace mode vs non-workspace mode, KB resolution |
| `test_config/test_workspace_config.py` | Workspace discovery, config layering |
| `test_core/test_models/test_workspace_config.py` | WorkspaceConfig model validation |
| `test_core/test_models/test_application_metadata.py` | ApplicationMetadata validation |
| `test_adapters/test_workspace_manager.py` | create_workspace, create_application, slugify, collisions |

### P.2 `conftest.py` Fixtures

Updated with workspace fixtures:

```python
# tests/conftest.py

from __future__ import annotations

from pathlib import Path

import pytest

from mkcv.adapters.artifact_store import FileSystemArtifactStore
from mkcv.adapters.filesystem.workspace_manager import WorkspaceManager
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.adapters.prompt_loader import FileSystemPromptLoader
from mkcv.core.services import PipelineService, ValidationService


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for test artifacts."""
    return tmp_path / ".mkcv"


@pytest.fixture
def sample_jd() -> str:
    """A minimal job description for testing."""
    return (
        "Senior Software Engineer at ExampleCorp.\n"
        "Requirements: Python, FastAPI, PostgreSQL, 5+ years experience.\n"
        "Nice to have: Kubernetes, CI/CD.\n"
    )


@pytest.fixture
def sample_kb() -> str:
    """A minimal knowledge base for testing."""
    return (
        "# Jane Doe -- Knowledge Base\n\n"
        "## Personal Information\n"
        "Name: Jane Doe\nEmail: jane@example.com\n\n"
        "## Career History\n"
        "### ExampleCorp -- Senior Engineer\n"
        "- Built scalable Python APIs\n"
    )


@pytest.fixture
def sample_jd_file(tmp_path: Path, sample_jd: str) -> Path:
    """Write sample JD to a temp file."""
    jd_file = tmp_path / "test_jd.txt"
    jd_file.write_text(sample_jd)
    return jd_file


@pytest.fixture
def sample_kb_file(tmp_path: Path, sample_kb: str) -> Path:
    """Write sample KB to a temp file."""
    kb_file = tmp_path / "test_kb.md"
    kb_file.write_text(sample_kb)
    return kb_file


@pytest.fixture
def stub_llm() -> StubLLMAdapter:
    """A stub LLM adapter."""
    return StubLLMAdapter()


@pytest.fixture
def prompt_loader() -> FileSystemPromptLoader:
    """A prompt loader using bundled templates."""
    return FileSystemPromptLoader()


@pytest.fixture
def artifact_store() -> FileSystemArtifactStore:
    """A filesystem artifact store."""
    return FileSystemArtifactStore()


@pytest.fixture
def workspace_manager() -> WorkspaceManager:
    """A workspace manager."""
    return WorkspaceManager()


@pytest.fixture
def pipeline_service(
    stub_llm: StubLLMAdapter,
    prompt_loader: FileSystemPromptLoader,
    artifact_store: FileSystemArtifactStore,
) -> PipelineService:
    """A PipelineService wired with test dependencies."""
    return PipelineService(
        llm=stub_llm,
        prompt_loader=prompt_loader,
        artifact_store=artifact_store,
    )


@pytest.fixture
def validation_service(
    prompt_loader: FileSystemPromptLoader,
) -> ValidationService:
    """A ValidationService wired with test dependencies."""
    return ValidationService(prompt_loader=prompt_loader)


# -- Workspace fixtures --


@pytest.fixture
def workspace_root(tmp_path: Path, workspace_manager: WorkspaceManager) -> Path:
    """Create a temporary workspace for testing."""
    ws = tmp_path / "test-workspace"
    workspace_manager.create_workspace(ws, name="Test User")
    return ws


@pytest.fixture
def workspace_with_kb(workspace_root: Path) -> Path:
    """A workspace with a populated career.md KB."""
    kb_path = workspace_root / "knowledge-base" / "career.md"
    kb_path.write_text(
        "# Test User -- Knowledge Base\n\n"
        "## Personal Information\n"
        "Name: Test User\n\n"
        "## Career History\n"
        "### TestCorp -- Engineer\n"
        "- Did things\n",
        encoding="utf-8",
    )
    return workspace_root
```

### P.3 Smoke Test Descriptions

Updated:

| Test File | What It Validates |
|-----------|-------------------|
| `test_app.py` | `mkcv --help` exits 0; `mkcv --version` prints version; `--workspace` option accepted |
| `test_commands/test_generate.py` | `--help` exits 0; workspace mode resolves KB; non-workspace mode requires `--kb` |
| `test_commands/test_init_cmd.py` | Creates workspace structure; idempotent on re-run; `--name` populates KB |
| `test_commands/test_render.py` | `--help` exits 0 |
| `test_commands/test_validate.py` | `--help` exits 0 |
| `test_commands/test_themes.py` | `--help` exits 0 |
| `test_configuration.py` | Default settings load; env var overrides; validators pass |
| `test_workspace_config.py` (config/) | `find_workspace_root` walks up; `load_workspace_into_settings` merges; 5-layer resolution |
| `test_exceptions.py` | Exit codes correct; hierarchy correct; WorkspaceError included |
| `test_services.py` | Services accept mocked ports; stub methods raise NotImplementedError |
| `test_models/test_workspace_config.py` | WorkspaceConfig accepts valid data; rejects invalid |
| `test_models/test_application_metadata.py` | ApplicationMetadata validates; status enum enforced |
| `test_models/test_jd_analysis.py` | JDAnalysis accepts valid data; rejects invalid |
| `test_models/test_resume.py` | RenderCVResume accepts valid data; rejects invalid |
| `test_models/test_pipeline.py` | StageMetadata, PipelineResult roundtrip |
| `test_prompt_loader.py` | Bundled templates load; render produces text |
| `test_artifact_store.py` | create_run_dir; save/load roundtrip; workspace mode paths |
| `test_workspace_manager.py` | create_workspace; create_application; slugify edge cases; collision handling |

### P.4 Two-Mode Testing Strategy

Every command that behaves differently with/without a workspace is tested in both modes:

```python
# tests/test_cli/test_commands/test_generate.py (sketch)

class TestGenerateWorkspaceMode:
    """Tests for generate command when a workspace is active."""

    def test_resolves_kb_from_workspace(self, workspace_with_kb, sample_jd_file):
        """KB is auto-resolved from knowledge-base/career.md."""
        ...

    def test_kb_flag_overrides_workspace_default(self, workspace_root, sample_jd_file, sample_kb_file):
        """--kb flag takes precedence over workspace KB."""
        ...

    def test_fails_if_workspace_kb_missing(self, workspace_root, sample_jd_file):
        """Error if workspace KB doesn't exist and --kb not provided."""
        ...


class TestGenerateNonWorkspaceMode:
    """Tests for generate command without a workspace."""

    def test_requires_kb_flag(self, sample_jd_file):
        """Error if --kb not provided and no workspace."""
        ...

    def test_explicit_kb_works(self, sample_jd_file, sample_kb_file):
        """Explicit --jd and --kb work without workspace."""
        ...
```

### P.5 CLI Test Pattern (Cyclopts)

*Unchanged from v1.*

---

## Q. File Changes

| File | Action | Description |
|------|--------|-------------|
| `pyproject.toml` | Create | Package metadata, deps (incl. tomli-w), tool config |
| `.gitignore` | Create | Python/IDE/`.mkcv/` ignores |
| `README.md` | Create | Basic project readme |
| `src/mkcv/__init__.py` | Create | `__version__`, package docstring |
| `src/mkcv/__main__.py` | Create | `python -m mkcv` entry |
| `src/mkcv/cli/__init__.py` | Create | CLI package marker |
| `src/mkcv/cli/app.py` | Create | Root Cyclopts app, meta app with `--workspace`, `main()` |
| `src/mkcv/cli/console.py` | Create | Rich console helpers |
| `src/mkcv/cli/commands/__init__.py` | Create | Commands package marker |
| `src/mkcv/cli/commands/generate.py` | Create | `generate` command (workspace-aware) |
| `src/mkcv/cli/commands/render.py` | Create | `render` command stub |
| `src/mkcv/cli/commands/validate.py` | Create | `validate` command stub |
| `src/mkcv/cli/commands/init_cmd.py` | Create | `init` command (workspace creation) |
| `src/mkcv/cli/commands/themes.py` | Create | `themes` command |
| `src/mkcv/config/__init__.py` | Create | Exports `settings` singleton |
| `src/mkcv/config/configuration.py` | Create | `Configuration(Dynaconf)` with workspace support |
| `src/mkcv/config/workspace.py` | Create | **NEW** Workspace discovery + config loading |
| `src/mkcv/config/settings.toml` | Create | Bundled defaults (incl. workspace section) |
| `src/mkcv/config/.secrets.toml` | Create | Secrets template (empty keys) |
| `src/mkcv/core/__init__.py` | Create | Core package marker |
| `src/mkcv/core/ports.py` | Create | Protocol interfaces |
| `src/mkcv/core/services.py` | Create | Service classes (stub methods) |
| `src/mkcv/core/exceptions.py` | Create | Exception hierarchy (incl. WorkspaceError) |
| `src/mkcv/core/models/__init__.py` | Create | Model re-exports (incl. workspace models) |
| `src/mkcv/core/models/jd_analysis.py` | Create | Stage 1 models |
| `src/mkcv/core/models/experience.py` | Create | Stage 2 models |
| `src/mkcv/core/models/content.py` | Create | Stage 3 models |
| `src/mkcv/core/models/resume.py` | Create | Stage 4 models |
| `src/mkcv/core/models/review.py` | Create | Stage 5 models |
| `src/mkcv/core/models/pipeline.py` | Create | Pipeline metadata models |
| `src/mkcv/core/models/workspace_config.py` | Create | **NEW** WorkspaceConfig model |
| `src/mkcv/core/models/application_metadata.py` | Create | **NEW** ApplicationMetadata model |
| `src/mkcv/adapters/__init__.py` | Create | Adapters package marker |
| `src/mkcv/adapters/prompt_loader.py` | Create | `FileSystemPromptLoader` |
| `src/mkcv/adapters/artifact_store.py` | Create | `FileSystemArtifactStore` (workspace-aware) |
| `src/mkcv/adapters/filesystem/__init__.py` | Create | **NEW** Filesystem adapters package marker |
| `src/mkcv/adapters/filesystem/workspace_manager.py` | Create | **NEW** `WorkspaceManager` |
| `src/mkcv/adapters/llm/__init__.py` | Create | LLM adapters package marker |
| `src/mkcv/adapters/llm/base.py` | Create | Provider registry, retry config |
| `src/mkcv/adapters/llm/stub.py` | Create | `StubLLMAdapter` |
| `src/mkcv/factories.py` | Create | DI factory functions (incl. `create_workspace_manager`) |
| `src/mkcv/prompts/analyze_jd.j2` | Create | Stage 1 prompt template (stub) |
| `src/mkcv/prompts/select_experience.j2` | Create | Stage 2 prompt template (stub) |
| `src/mkcv/prompts/tailor_bullets.j2` | Create | Stage 3a prompt template (stub) |
| `src/mkcv/prompts/write_mission.j2` | Create | Stage 3b prompt template (stub) |
| `src/mkcv/prompts/structure_yaml.j2` | Create | Stage 4 prompt template (stub) |
| `src/mkcv/prompts/review.j2` | Create | Stage 5 prompt template (stub) |
| `src/mkcv/prompts/_voice_anchor.j2` | Create | Shared voice guidelines partial |
| `tests/__init__.py` | Create | Tests root marker |
| `tests/conftest.py` | Create | Shared fixtures (incl. workspace fixtures) |
| `tests/test_cli/__init__.py` | Create | Test CLI package marker |
| `tests/test_cli/test_app.py` | Create | Root app tests |
| `tests/test_cli/test_commands/__init__.py` | Create | Test commands package marker |
| `tests/test_cli/test_commands/test_generate.py` | Create | Generate: workspace + non-workspace modes |
| `tests/test_cli/test_commands/test_render.py` | Create | Render command smoke tests |
| `tests/test_cli/test_commands/test_validate.py` | Create | Validate command smoke tests |
| `tests/test_cli/test_commands/test_init_cmd.py` | Create | Init command: workspace creation tests |
| `tests/test_cli/test_commands/test_themes.py` | Create | Themes command smoke tests |
| `tests/test_config/__init__.py` | Create | Test config package marker |
| `tests/test_config/test_configuration.py` | Create | Config loading and validation tests |
| `tests/test_config/test_workspace_config.py` | Create | **NEW** Workspace discovery + layered config tests |
| `tests/test_core/__init__.py` | Create | Test core package marker |
| `tests/test_core/test_exceptions.py` | Create | Exception hierarchy tests |
| `tests/test_core/test_services.py` | Create | Service class tests |
| `tests/test_core/test_models/__init__.py` | Create | Test models package marker |
| `tests/test_core/test_models/test_jd_analysis.py` | Create | JD analysis model tests |
| `tests/test_core/test_models/test_resume.py` | Create | Resume model tests |
| `tests/test_core/test_models/test_pipeline.py` | Create | Pipeline metadata model tests |
| `tests/test_core/test_models/test_workspace_config.py` | Create | **NEW** WorkspaceConfig model tests |
| `tests/test_core/test_models/test_application_metadata.py` | Create | **NEW** ApplicationMetadata model tests |
| `tests/test_adapters/__init__.py` | Create | Test adapters package marker |
| `tests/test_adapters/test_prompt_loader.py` | Create | Prompt loader tests |
| `tests/test_adapters/test_artifact_store.py` | Create | Artifact store tests (both modes) |
| `tests/test_adapters/test_workspace_manager.py` | Create | **NEW** Workspace manager tests |
| `AGENTS.md` | Modify | Update CLI library, config format, workspace commands |

**Total: 72 files created, 1 file modified, 0 deleted.**

---

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Pydantic models validate/reject correctly | Direct construction with valid/invalid data |
| Unit | WorkspaceConfig, ApplicationMetadata models | Valid/invalid data, enum constraints |
| Unit | Exception hierarchy, exit codes | `isinstance` checks, attribute assertions |
| Unit | Prompt loader finds and renders templates | Real Jinja2 environment, bundled templates |
| Unit | Artifact store save/load roundtrip | Real filesystem in `tmp_path` |
| Unit | `slugify()` edge cases | Unicode, special chars, length, empty input |
| Unit | Workspace collision resolution | Create dirs then check `-2` suffix |
| Unit | Services accept port implementations | Constructor with mock/stub ports |
| Integration | CLI `--help` for every command | `app(["command", "--help"])` via Cyclopts |
| Integration | CLI `--version` prints correct version | `app(["--version"])` + capsys |
| Integration | `mkcv init` creates workspace structure | Real filesystem, verify all files |
| Integration | `mkcv generate` workspace mode | Workspace fixture + mock pipeline |
| Integration | `mkcv generate` non-workspace mode | No workspace, explicit flags |
| Integration | Config defaults load, env vars override | Dynaconf in test mode |
| Integration | Workspace config merges into settings | `load_workspace_into_settings()` + assertions |
| Integration | 5-layer config resolution | Bundled < user < workspace < env < CLI |
| Integration | `find_workspace_root` walks up | Nested tmp dirs with mkcv.toml |
| Integration | Factory functions create valid objects | Call factory, check return types |
| Smoke | `uv run mkcv --help` exits 0 | Subprocess (manual, not in pytest) |

---

## Migration / Rollout

No migration required. This is a greenfield scaffolding change on a docs-only
repository. No data, users, or deployments exist.

---

## Open Questions

- [x] ~~CLI library: Click vs Cyclopts~~ **Resolved: Cyclopts**
- [x] ~~Config format: YAML vs TOML~~ **Resolved: TOML via Dynaconf**
- [x] ~~DI: Container vs manual~~ **Resolved: Manual factory functions**
- [x] ~~`mkcv init` scope~~ **Resolved: Creates workspace, not just global config**
- [ ] Should we include a `py.typed` marker file for PEP 561? **Recommended: yes,
  add `src/mkcv/py.typed` empty file.** Deferred to implementation as it's trivial.
- [ ] Should `mkcv init` prompt interactively for name/email, or only accept
  `--name` flag? **Current design: `--name` flag only.** Interactive prompting
  can be added later. Rationale: CLI tools should be scriptable by default.

---

## Summary

| Metric | Value |
|--------|-------|
| **Approach** | Pragmatic hexagonal with Cyclopts + Dynaconf + workspace model |
| **Key Decisions** | 7 documented (6 original + workspace model) |
| **Files Affected** | 72 new, 1 modified, 0 deleted |
| **Testing Strategy** | Unit + integration covering all layers, both workspace modes |
| **New Components** | WorkspaceManager, WorkspaceConfig, ApplicationMetadata, workspace discovery |

### Next Step
Ready for task breakdown (`sdd-tasks`).
