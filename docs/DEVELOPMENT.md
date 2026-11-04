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
│   ├── llm/                  # Anthropic, OpenAI, Google, OpenAI-compatible, Stub adapters; provider registry, stage resolver, retry
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

API keys go in the global user config (`[default.providers.<name>] api_key = "..."` in `~/.config/mkcv/settings.toml`), never in a committed workspace `mkcv.toml`. A key in config takes precedence over the provider's environment variable (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` or `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`), which stays available for CI and one-off overrides. A provider you define in config names its own variable with `api_key_env`. See [API keys](models.md#api-keys).

In `mkcv.toml` every section header needs the `default.` prefix (for example `[default.pipeline.stages.tailor]`); without it the setting is silently ignored. The models behind each stage are decided by the stage resolver (CLI flags, then per-stage config, then a model profile); see [Models and providers](models.md).

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

Providers are data. Nothing in `adapters/factory.py` dispatches on a provider name.

1. If the endpoint speaks the OpenAI Chat Completions API, add a `ProviderSpec` to `BUILTIN_PROVIDERS` in `src/mkcv/adapters/llm/builtin_providers.py` (kind `openai-compatible`, a `base_url`, and `api_key_env`). Users can do the same in `mkcv.toml` with `[default.providers.<name>]`, with no code change.
2. For a new API, add a `ProviderKind`, an adapter in `src/mkcv/adapters/llm/` implementing `LLMPort`, the kind's defaults in `KIND_DEFAULTS`, and a builder in `_BUILDERS` in `provider_registry.py`. Import the vendor SDK inside the builder so it loads lazily.
3. Describe its models in `src/mkcv/core/catalog/builtin_models.py` (tier, prices, how requests are shaped) and, if it should have a recommended model per stage, add a profile to `builtin_model_profiles.py`. Every profile model needs a catalog entry.
4. Cover it with tests that mock the SDK client; never call a real provider.

### Changing Recommended Models

Profiles in `src/mkcv/core/catalog/builtin_model_profiles.py` are provisional
until an eval run backs them. Document any change in [`models.md`](models.md).

### Evaluating Models

The `evals/` directory holds an offline harness that scores models on each
pipeline stage and suggests profile changes. It is not part of the installed
package and never runs in CI beyond its unit tests, which use stub providers.
Run it with `uv run python -m evals --help`; `evals/README.md` explains the
keys it needs, what a run costs, how to read the report, and how to apply the
results.

## Releases and the Homebrew Tap

Versions come from [Conventional Commits](https://www.conventionalcommits.org) on
`main`: `fix:` and `perf:` bump the patch, `feat:` the minor, a breaking change the
major. `docs:`, `ci:`, `build:`, `chore:`, `refactor:`, `style:` and `test:` do not
release. Nothing is uploaded to PyPI.

`.github/workflows/ci.yml` lints and tests every push and pull request. On `main`,
only after lint and tests pass for that commit, three more jobs run in order:

| Job | Does |
|-----|------|
| `version` | `semantic-release` bumps `pyproject.toml`, refreshes `uv.lock` (its `build_command`), updates `CHANGELOG.md`, commits `chore(release): vX.Y.Z` and tags `vX.Y.Z`, when a commit warrants it |
| `release` | Builds the wheel (`uv build --wheel`) and a hashed `requirements.txt` (`uv export --no-dev --no-emit-project`) from the tag and attaches them to the GitHub release `vX.Y.Z`, whose notes are that version's `CHANGELOG.md` section |
| `homebrew` | Renders `packaging/homebrew/mkcv.rb.template` against those two files and pushes `Formula/mkcv.rb` to `main` of [`bkuberek/homebrew-tap`](https://github.com/bkuberek/homebrew-tap) |

Publishing is part of this workflow, not a workflow triggered by the tag, because
events caused by `GITHUB_TOKEN` (the tag push) never start other workflow runs.
Both publish jobs skip what is already done: a release that has both files is left
alone, and an unchanged formula is not committed.

The formula installs `requirements.txt` as binary wheels only (`pip install
--require-hashes --only-binary=:all: --no-deps`), then the mkcv wheel, inside a
virtual environment on Homebrew's `python@3.13`. Every dependency in `uv.lock` has a
cp313 wheel for macOS arm64 and Linux x86_64/aarch64, but `cryptography` (via
`google-genai`) has none for macOS x86_64, so the formula requires Apple silicon on
macOS. Change the formula in the template, never in the tap: the next publish
overwrites the tap's copy.

### Secret

The `homebrew` job pushes with `HOMEBREW_TAP_GITHUB_TOKEN`, an environment secret of
the `production` environment of this repository. Only the `homebrew` job declares
`environment: production`, so no other job can read it. The token is a fine-grained
personal access token whose only repository is `bkuberek/homebrew-tap`, with
**Contents** read and write. When it expires, the `homebrew` job fails at its
checkout of the tap: renew the secret and run the workflow by hand.

### Publishing again

A manual run on `main` publishes the newest tag reachable from `main`, skipping the
steps already done, so it repairs a publish that failed or never ran, or publishes a
release without waiting for a new one:

```bash
gh workflow run ci.yml --ref main
```

The run first lints and tests that commit, then cuts a release if an unreleased
commit warrants one, then publishes the newest tag. To replace the files of a
published release, delete them from the GitHub release first; the next manual run
uploads them again and updates the formula. A manual run on another branch publishes
nothing.

### Testing the formula locally

Before merging a template change, install it from a local build through a throwaway
tap, from the repository root:

```bash
uv build --wheel --out-dir /tmp/mkcv-dist
uv export --frozen --no-dev --no-emit-project --no-header --format requirements.txt \
  --output-file /tmp/mkcv-dist/requirements.txt
brew tap-new --no-git bkuberek/mkcvtest
python3 packaging/homebrew/render_formula.py --base-url file:///tmp/mkcv-dist \
  --wheel /tmp/mkcv-dist/mkcv-*-py3-none-any.whl --requirements /tmp/mkcv-dist/requirements.txt \
  --output "$(brew --repository bkuberek/mkcvtest)/Formula/mkcv.rb"
HOMEBREW_NO_INSTALL_FROM_API=1 brew install --formula bkuberek/mkcvtest/mkcv
brew test bkuberek/mkcvtest/mkcv
brew audit --strict --formula bkuberek/mkcvtest/mkcv
HOMEBREW_NO_AUTOREMOVE=1 brew uninstall --formula mkcv
brew untap bkuberek/mkcvtest
```

The release tooling has its own tests: `uv run pytest packaging`.

## Reference Documentation

- [Architecture spec](specs/architecture.md)
- [CLI interface spec](specs/cli-interface.md)
- [Data models spec](specs/data-models.md)
- [Architecture decisions](decisions/)
