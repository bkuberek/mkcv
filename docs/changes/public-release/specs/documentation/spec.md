# Documentation Specification

## Purpose

Provides the public-facing documentation artifacts required for a credible open-source release: overhauled README, contributor guide, developer setup guide, changelog, and example configuration reference.

## Requirements

### Requirement: README Overhaul

`README.md` MUST include badges (CI status, license, Python version), a concise product pitch, quick-start TL;DR, multiple install methods (pip, pipx, uv), and a link to CONTRIBUTING.md.

#### Scenario: Badges render on GitHub

- GIVEN the README.md is viewed on GitHub
- WHEN the page loads
- THEN badge images for CI status, license ("MIT"), and Python version ("3.12+") are visible in the header area

#### Scenario: Quick-start is self-contained

- GIVEN a new user reads only the Quick Start section
- WHEN they follow the listed commands
- THEN they can install mkcv, set an API key, create a workspace, and generate a resume without reading other sections

#### Scenario: Multiple install methods documented

- GIVEN the Installation section of README
- WHEN a user reads it
- THEN at least three install methods are shown: `pip install`, `pipx install`, and `uv tool install`

#### Scenario: Contributing link present

- GIVEN the README
- WHEN scanned for contributor guidance
- THEN a link or section pointing to `CONTRIBUTING.md` exists

### Requirement: CONTRIBUTING.md

The repository MUST contain `CONTRIBUTING.md` at the root covering: fork/PR workflow, code style expectations, how to run tests, how to run linters, and a brief architecture overview.

#### Scenario: Fork-PR workflow documented

- GIVEN a potential contributor reads CONTRIBUTING.md
- WHEN they look for contribution steps
- THEN the document describes: fork, branch, make changes, run tests, submit PR

#### Scenario: Testing instructions included

- GIVEN CONTRIBUTING.md
- WHEN a contributor looks for test commands
- THEN `uv run pytest`, `uv run ruff check`, and `uv run mypy src/` commands are documented

### Requirement: DEVELOPMENT.md

A `docs/DEVELOPMENT.md` file MUST consolidate developer setup instructions from CLAUDE.md and AGENTS.md into a public-facing guide. It SHOULD cover: prerequisites, environment setup, project structure, running tests, and coding conventions.

#### Scenario: Dev environment setup covered

- GIVEN a new developer reads docs/DEVELOPMENT.md
- WHEN they follow the setup instructions
- THEN they can clone the repo, install dependencies with `uv sync`, and run the test suite

#### Scenario: No internal agent references

- GIVEN docs/DEVELOPMENT.md
- WHEN its content is reviewed
- THEN it contains no references to Claude Code, SDD workflows, engram, or other internal AI agent tooling

### Requirement: CHANGELOG.md

The repository MUST contain a `CHANGELOG.md` at the root with an initial entry for v0.1.0. It SHOULD follow Keep a Changelog format.

#### Scenario: Initial v0.1.0 entry

- GIVEN CHANGELOG.md exists
- WHEN read by a user
- THEN it contains an entry for version `0.1.0` with the release date and a summary of initial features (generate, render, validate, themes, status, init commands)

#### Scenario: Keep a Changelog format

- GIVEN CHANGELOG.md
- WHEN parsed
- THEN it uses sections like Added, Changed, Fixed, Removed under each version heading

### Requirement: Example Config Documentation

An `examples/mkcv.toml` file MUST exist containing a fully-commented example configuration referencing all available settings from `settings.toml`. Every setting SHOULD have an inline comment explaining its purpose and valid values.

#### Scenario: Example config covers all settings

- GIVEN `src/mkcv/config/settings.toml` defines default settings
- WHEN compared to `examples/mkcv.toml`
- THEN every user-configurable setting from settings.toml has a corresponding entry (commented or uncommented) in the example

#### Scenario: Example config is valid TOML

- GIVEN `examples/mkcv.toml`
- WHEN parsed by a TOML parser
- THEN parsing succeeds without errors
