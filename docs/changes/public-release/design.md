# Design: Public Release Readiness

## Technical Approach

Prepare mkcv for its first public GitHub release through three independent phases: foundation (versioning, license, metadata), documentation (README, contributor guides, changelog), and CI/CD (GitHub Actions). All changes are additive or metadata-only — no core architecture modifications.

## Architecture Decisions

### Decision: Single-Source Versioning via importlib.metadata

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `importlib.metadata.version("mkcv")` with fallback | Standard Python pattern, works with hatchling build, requires try/except for dev/editable installs | **Chosen** |
| `__version__` hardcoded in `__init__.py` | Simple but creates duplicate version sources (pyproject.toml + code) | Rejected |
| `hatch-vcs` (git tag versioning) | Eliminates manual version bumps but adds build dependency and complexity | Rejected — out of scope per proposal |

**Implementation pattern:**

```python
# src/mkcv/__init__.py
"""mkcv — AI-powered resume generator."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mkcv")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"
```

The fallback `"0.0.0-dev"` fires only when running from source without `pip install -e .` or `uv sync`. This is safe because `uv sync` (the documented dev setup) always installs the package metadata.

**Version consumers to update:**
- `workspace_config.py` line 31: change default from `"0.1.0"` to import from `mkcv.__version__`
- `workspace_manager.py` line 36: the embedded TOML template has `version = "0.1.0"` — replace with `version = "{__version__}"` using f-string interpolation at template render time (already imports `__version__` at line 287)

### Decision: GitHub Actions Workflow Structure

| Option | Tradeoff | Decision |
|--------|----------|----------|
| 3 separate workflows (lint, test, release) | Clear separation, independent triggers, easy to disable one | **Chosen** |
| Single CI workflow with matrix | Fewer files but harder to reason about, release logic mixed with CI | Rejected |

### Decision: DEVELOPMENT.md Location

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `docs/DEVELOPMENT.md` | Keeps repo root clean, grouped with other docs | **Chosen** |
| Root `DEVELOPMENT.md` | More discoverable but adds clutter alongside README, CONTRIBUTING, CHANGELOG | Rejected |

## Data Flow

No runtime data flow changes. Version resolution at import time:

```
pyproject.toml [version = "X.Y.Z"]
       │
       ▼  (hatchling build / uv sync)
  Package metadata
       │
       ▼  (importlib.metadata.version)
  __version__ in __init__.py
       │
       ├──→ cli/app.py (--version flag)
       ├──→ workspace_config.py (default value)
       └──→ workspace_manager.py (README template)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `LICENSE` | Create | MIT license, copyright 2025 Bastian Kuberek |
| `src/mkcv/__init__.py` | Modify | Replace hardcoded `__version__` with `importlib.metadata.version()` + fallback |
| `src/mkcv/core/models/workspace_config.py` | Modify | Import `__version__` for `version` field default instead of hardcoded `"0.1.0"` |
| `src/mkcv/adapters/filesystem/workspace_manager.py` | Modify | Replace hardcoded `version = "0.1.0"` in TOML template with f-string using `__version__` |
| `pyproject.toml` | Modify | Add `[project.urls]`, `keywords`, `classifiers`, update `authors` name to "Bastian Kuberek" |
| `.gitignore` | Modify | Add `.claude/`, `.atl/`, `openspec/` under new "Agent tooling" section |
| `README.md` | Modify | Add badges (CI, license, Python), refine install section (pip, pipx, uv), add contributing link |
| `CONTRIBUTING.md` | Create | Fork/PR workflow, code style summary, test instructions, architecture overview |
| `docs/DEVELOPMENT.md` | Create | Dev environment setup, build/test/lint commands, project structure, config system |
| `CHANGELOG.md` | Create | Initial `## [0.1.0]` entry summarizing features |
| `examples/mkcv.toml` | Create | Annotated config reference derived from `settings.toml` defaults |
| `.github/workflows/lint.yml` | Create | Ruff check + mypy strict on push/PR |
| `.github/workflows/test.yml` | Create | pytest matrix (Python 3.12, 3.13) on push/PR |
| `.github/workflows/release.yml` | Create | Tag-triggered GitHub Release with changelog body |

## GitHub Actions Workflow Designs

### `.github/workflows/lint.yml`

- **Triggers:** push to `main`, pull_request to `main`
- **Jobs:** single `lint` job
- **Steps:** checkout → setup-python 3.12 → install uv → `uv sync` → `uv run ruff check src/ tests/` → `uv run ruff format --check src/ tests/` → `uv run mypy src/`
- **Runs-on:** `ubuntu-latest`

### `.github/workflows/test.yml`

- **Triggers:** push to `main`, pull_request to `main`
- **Jobs:** single `test` job with matrix
- **Matrix:** `python-version: ["3.12", "3.13"]`
- **Steps:** checkout → setup-python ${{ matrix.python-version }} → install uv → `uv sync` → `uv run pytest --tb=short`
- **Runs-on:** `ubuntu-latest`

### `.github/workflows/release.yml`

- **Triggers:** push tags matching `v*` (e.g., `v0.1.0`)
- **Jobs:** single `release` job
- **Steps:** checkout → create GitHub Release via `softprops/action-gh-release@v2` with auto-generated release notes
- **Runs-on:** `ubuntu-latest`
- **Permissions:** `contents: write`

## Interfaces / Contracts

No new interfaces. The only contract change is `__version__` resolution:

```python
# Before: static string
__version__ = "0.1.0"

# After: dynamic from metadata with fallback
from importlib.metadata import PackageNotFoundError, version
try:
    __version__ = version("mkcv")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"
```

All existing consumers (`cli/app.py`, `workspace_manager.py`) import `__version__` unchanged — the interface is identical.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `__version__` resolves to a valid semver string | Assert `__version__` matches `r"\d+\.\d+\.\d+"` pattern (existing `test_version_flag` covers CLI output) |
| Unit | `WorkspaceConfig.version` default matches `__version__` | Assert `WorkspaceConfig().version == __version__` |
| Integration | `mkcv --version` outputs package version | Already tested in `test_cli/test_app.py` — verify still passes |
| CI | Workflows execute successfully | Push to branch, verify all 3 workflows pass on the PR |

No new test files needed — existing tests cover the version flow. Verify they still pass after the `importlib.metadata` change.

## Migration / Rollout

No migration required. All changes are additive or metadata-only. The version resolution change is backward-compatible — `__version__` remains a module-level string.

## Open Questions

- None — all decisions are straightforward with clear rationale.
