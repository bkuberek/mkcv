# Foundation Specification

## Purpose

Establishes the legal, packaging, and repository hygiene prerequisites for a public GitHub release: license file, single-source versioning, enriched package metadata, and gitignore coverage for internal tooling.

## Requirements

### Requirement: MIT License File

The repository MUST contain a `LICENSE` file in the project root with the full MIT license text, copyright year 2025, and author "Bastian Kuberek <bastian@bkuberek.com>".

#### Scenario: LICENSE file present and valid

- GIVEN the repository root
- WHEN a user or tool inspects `LICENSE`
- THEN the file contains "MIT License", "Copyright (c) 2025 Bastian Kuberek", and the full MIT permission/disclaimer text

#### Scenario: LICENSE matches pyproject.toml declaration

- GIVEN `pyproject.toml` declares `license = {text = "MIT"}`
- WHEN the repository is packaged or inspected by GitHub
- THEN the LICENSE file content and the pyproject.toml declaration are consistent

### Requirement: Single-Source Version

The package version MUST be defined in exactly one place (`pyproject.toml`) and read at runtime via `importlib.metadata.version("mkcv")`. Hardcoded `"0.1.0"` strings in `src/mkcv/__init__.py`, `workspace_config.py`, and `workspace_manager.py` MUST be removed.

#### Scenario: Runtime version from installed package

- GIVEN mkcv is installed (pip, uv, or editable)
- WHEN `mkcv --version` is invoked
- THEN the output matches the version in `pyproject.toml`
- AND `__version__` in `__init__.py` equals that same value

#### Scenario: Dev fallback when not installed as package

- GIVEN mkcv source is run without package installation (e.g., raw `python -m`)
- WHEN `importlib.metadata.version("mkcv")` raises `PackageNotFoundError`
- THEN `__version__` falls back to `"0.1.0-dev"`

#### Scenario: No duplicate version strings in source

- GIVEN the full source tree under `src/`
- WHEN searching for hardcoded `"0.1.0"` strings
- THEN zero matches are found (only `pyproject.toml` contains the version literal)

### Requirement: Enriched pyproject.toml Metadata

`pyproject.toml` MUST include `[project.urls]` with Homepage, Repository, Issues, and Changelog links. It MUST include relevant PyPI classifiers and keywords. The `authors` field SHOULD use the correct name "Bastian Kuberek".

#### Scenario: Project URLs present

- GIVEN the published `pyproject.toml`
- WHEN parsed by a packaging tool
- THEN `[project.urls]` contains keys: Homepage, Repository, Issues, Changelog
- AND all URLs point to `https://github.com/bkuberek/mkcv` or subpaths

#### Scenario: Classifiers and keywords present

- GIVEN `pyproject.toml`
- WHEN inspected
- THEN `classifiers` includes at minimum: License, Python version, topic, and development status trove classifiers
- AND `keywords` includes terms like "resume", "cv", "ai", "cli", "ats"

### Requirement: Gitignore Agent Tooling Dirs

`.gitignore` MUST include entries for `.claude/`, `.atl/`, and `openspec/` so that internal agent tooling artifacts are never committed.

#### Scenario: Agent dirs ignored

- GIVEN a repository clone with `.claude/`, `.atl/`, or `openspec/` directories present locally
- WHEN `git status` is run
- THEN those directories do not appear as untracked files

#### Scenario: Existing gitignore rules preserved

- GIVEN the current `.gitignore` content
- WHEN agent tooling entries are added
- THEN all previously existing ignore rules remain intact
