# CI/CD Specification

## Purpose

Defines the GitHub Actions workflows that automate linting, testing, and release publishing for the mkcv project, ensuring code quality gates on every PR and automated releases on version tags.

## Requirements

### Requirement: Lint Workflow

A `.github/workflows/lint.yml` workflow MUST run `ruff check` and `mypy --strict` on every push and pull request targeting the main branch. It MUST use Python 3.12 and install dependencies via `uv sync`.

#### Scenario: Lint passes on clean code

- GIVEN a PR with code that passes ruff and mypy
- WHEN the lint workflow runs
- THEN both `ruff check src/ tests/` and `mypy src/` exit with code 0
- AND the workflow reports success

#### Scenario: Lint fails on violation

- GIVEN a PR introducing a ruff lint violation or mypy type error
- WHEN the lint workflow runs
- THEN the workflow exits with non-zero status
- AND the PR check shows failure

#### Scenario: Ruff format check included

- GIVEN the lint workflow
- WHEN it runs
- THEN it also runs `ruff format --check src/ tests/` to enforce formatting

### Requirement: Test Workflow

A `.github/workflows/test.yml` workflow MUST run `pytest` on every push and pull request targeting the main branch. It MUST test on Python 3.12 and 3.13 using a matrix strategy. It MUST install dependencies via `uv sync`.

#### Scenario: Tests pass on both Python versions

- GIVEN the test suite passes locally
- WHEN the test workflow runs on GitHub Actions
- THEN `uv run pytest` passes on both Python 3.12 and Python 3.13

#### Scenario: Test failure blocks merge

- GIVEN a PR with a failing test
- WHEN the test workflow runs
- THEN the workflow reports failure for the affected Python version
- AND the PR cannot be merged (assuming branch protection)

### Requirement: Release Workflow

A `.github/workflows/release.yml` workflow MUST trigger on pushes of tags matching `v*` (e.g., `v0.1.0`). It MUST create a GitHub Release with auto-generated release notes. It SHOULD build the distribution package (`sdist` + `wheel`).

#### Scenario: Tag push creates GitHub Release

- GIVEN a tag `v0.1.0` is pushed
- WHEN the release workflow runs
- THEN a GitHub Release is created with the tag name as the title
- AND the release body contains auto-generated release notes

#### Scenario: Distribution artifacts attached

- GIVEN the release workflow completes
- WHEN the GitHub Release is inspected
- THEN `.tar.gz` (sdist) and `.whl` (wheel) artifacts are attached as release assets

#### Scenario: Non-tag pushes do not trigger release

- GIVEN a regular commit is pushed to main
- WHEN workflows are evaluated
- THEN the release workflow does NOT run

### Requirement: Workflow Consistency

All workflows MUST pin action versions to full SHA or major version tags. All workflows MUST use `uv` for dependency installation to match the project's tooling.

#### Scenario: Actions are version-pinned

- GIVEN any workflow YAML file
- WHEN `uses:` directives are inspected
- THEN each action reference uses a pinned version (e.g., `actions/checkout@v4`, `astral-sh/setup-uv@v4`)
