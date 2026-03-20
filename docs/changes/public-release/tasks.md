# Tasks: Public Release Readiness

## Phase 1: Foundation

- [ ] 1.1 Create `LICENSE` in project root with MIT text, copyright 2025 Bastian Kuberek
- [ ] 1.2 Update `src/mkcv/__init__.py`: replace hardcoded `__version__ = "0.1.0"` with `importlib.metadata.version("mkcv")` + `PackageNotFoundError` fallback to `"0.0.0-dev"`
- [ ] 1.3 Update `src/mkcv/core/models/workspace_config.py` line 31: import `__version__` from `mkcv` and use it as default for `version` field
- [ ] 1.4 Update `src/mkcv/adapters/filesystem/workspace_manager.py` line 36: replace hardcoded `version = "0.1.0"` in TOML template with f-string interpolation using `__version__`
- [ ] 1.5 Update `pyproject.toml`: add `[project.urls]` (Homepage, Repository, Issues, Changelog), `keywords` (resume, cv, ai, cli, ats), `classifiers` (license, python version, topic, dev status), fix author name to "Bastian Kuberek"
- [ ] 1.6 Update `.gitignore`: add `.claude/`, `.atl/`, `openspec/` under a new "Agent tooling" section

## Phase 2: Documentation

- [ ] 2.1 Overhaul `README.md`: add badges (CI status, license, Python version), refine product pitch, ensure install section shows pip/pipx/uv methods, add contributing link
- [ ] 2.2 Create `CONTRIBUTING.md`: fork/PR workflow, code style (ruff, mypy --strict), test commands (`uv run pytest`, `uv run ruff check`, `uv run mypy src/`), brief architecture overview
- [ ] 2.3 Create `docs/DEVELOPMENT.md`: prerequisites (Python 3.12+, uv), env setup (`uv sync`), project structure, running tests/lint/typecheck, config system overview; no internal agent tooling references
- [ ] 2.4 Create `CHANGELOG.md`: Keep a Changelog format, initial `## [0.1.0]` entry with Added section listing core features (generate, render, validate, themes, status, init, cover-letter)
- [ ] 2.5 Create `examples/mkcv.toml`: fully-commented config reference derived from `src/mkcv/config/settings.toml`, covering all user-configurable settings with inline explanations

## Phase 3: CI/CD

- [ ] 3.1 Create `.github/workflows/lint.yml`: triggers on push/PR to main, ubuntu-latest, Python 3.12, `uv sync`, runs `ruff check`, `ruff format --check`, `mypy src/`; pin actions (checkout@v4, setup-python, setup-uv)
- [ ] 3.2 Create `.github/workflows/test.yml`: triggers on push/PR to main, matrix Python 3.12+3.13, `uv sync`, `uv run pytest --tb=short`; pin actions
- [ ] 3.3 Create `.github/workflows/release.yml`: triggers on `v*` tags, `permissions: contents: write`, creates GitHub Release via `softprops/action-gh-release@v2` with auto-generated notes

## Phase 4: Verification

- [ ] 4.1 Run `uv run pytest` — all existing tests pass after version changes
- [ ] 4.2 Run `uv run mypy src/` — strict mode still passes
- [ ] 4.3 Run `uv run ruff check src/ tests/` — no lint violations
- [ ] 4.4 Verify `mkcv --version` outputs the correct version from package metadata
- [ ] 4.5 Verify `grep -r '"0.1.0"' src/` returns no matches (only `pyproject.toml` has the literal)
- [ ] 4.6 Verify all new files exist: LICENSE, CONTRIBUTING.md, CHANGELOG.md, docs/DEVELOPMENT.md, examples/mkcv.toml, .github/workflows/{lint,test,release}.yml
