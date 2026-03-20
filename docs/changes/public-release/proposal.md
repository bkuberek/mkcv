# Proposal: Public Release Readiness

## Intent

mkcv is feature-complete for v0.1.0 but lacks the artifacts required for a credible public GitHub release: no LICENSE file, no CI/CD, no contributor docs, version hardcoded in multiple places, and .gitignore missing entries for agent tooling directories. This change prepares the repository for its first public release.

## Scope

### In Scope

1. **LICENSE file** -- MIT, copyright Bastian Kuberek
2. **GitHub Actions CI/CD** -- 3 workflows: `lint.yml` (ruff + mypy), `test.yml` (pytest, Python 3.12 + 3.13), `release.yml` (tag-triggered GitHub Release)
3. **Single-source versioning** -- `importlib.metadata` in `__init__.py`; remove hardcoded `"0.1.0"` from `workspace_config.py`, `workspace_manager.py`
4. **README overhaul** -- Badges (CI, license, Python version), product pitch, quick-start TL;DR, multiple install methods (pip, pipx, uv), contributing link
5. **CONTRIBUTING.md** -- Fork/PR workflow, code style, testing, architecture overview
6. **pyproject.toml updates** -- `[project.urls]` (repo, issues), keywords, classifiers, `license-files`
7. **CHANGELOG.md** -- Initial entry for v0.1.0
8. **Example mkcv.toml** -- Documented config reference (`examples/mkcv.toml`)
9. **.gitignore updates** -- Add `.claude/`, `.atl/`, `openspec/`
10. **DEVELOPMENT.md** -- Consolidate dev setup from CLAUDE.md + AGENTS.md into public-facing guide

### Out of Scope

- MkDocs / Sphinx documentation site
- PyPI trusted publishing automation
- Homebrew formula / Docker image
- Code of Conduct
- API reference docs
- Commitizen / bump2version release automation

## Approach

Sequential implementation in 3 phases:

1. **Foundation** -- LICENSE, .gitignore, pyproject.toml metadata, single-source version
2. **Documentation** -- README overhaul, CONTRIBUTING.md, DEVELOPMENT.md, CHANGELOG.md, example config
3. **CI/CD** -- GitHub Actions workflows (lint, test, release)

Each phase is independently shippable. No architectural changes to core code.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `LICENSE` | New | MIT license file |
| `.github/workflows/` | New | 3 CI/CD workflow files |
| `src/mkcv/__init__.py` | Modified | Use `importlib.metadata.version()` |
| `src/mkcv/core/models/workspace_config.py` | Modified | Remove hardcoded version default |
| `src/mkcv/adapters/filesystem/workspace_manager.py` | Modified | Remove hardcoded version string |
| `README.md` | Modified | Badges, expanded install, product pitch |
| `CONTRIBUTING.md` | New | Contributor guide |
| `DEVELOPMENT.md` | New | Developer setup guide |
| `CHANGELOG.md` | New | Initial v0.1.0 changelog |
| `pyproject.toml` | Modified | URLs, classifiers, keywords |
| `.gitignore` | Modified | Add agent tooling dirs |
| `examples/mkcv.toml` | New | Documented config example |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `importlib.metadata` fails when not installed as package | Med | Fallback to `__version__ = "0.1.0-dev"` for editable/dev installs |
| CI workflows fail on first run (permissions, secrets) | Low | Test workflows in a branch PR before merge |
| README changes misrepresent features | Low | Review against actual CLI --help output |

## Rollback Plan

All changes are additive files or metadata edits. Revert the merge commit to restore pre-release state. No database migrations, no API changes, no breaking modifications.

## Dependencies

- GitHub repository write access for Actions workflows
- No external service dependencies for implementation

## Success Criteria

- [ ] `LICENSE` file exists and matches pyproject.toml declaration
- [ ] `mkcv --version` reads from package metadata (single source)
- [ ] `grep -r '"0.1.0"' src/` returns only `pyproject.toml`
- [ ] GitHub Actions: lint, test, release workflows pass on PR
- [ ] README renders correctly on GitHub with badges
- [ ] CONTRIBUTING.md covers fork/PR/test/style workflow
- [ ] `.claude/`, `.atl/`, `openspec/` are gitignored
- [ ] All existing tests still pass (`uv run pytest`)
- [ ] `mypy --strict` still passes
