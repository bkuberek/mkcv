# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- version list -->

## v1.2.0 (2026-03-20)

### Bug Fixes

- **cli**: Add -i short alias for --interactive flag
  ([`7759fab`](https://github.com/bkuberek/mkcv/commit/7759fab7e517ea7c467ae05b69e3e355760167d5))

### Chores

- Merge openspec SDD artifacts into docs/changes
  ([`f7dc098`](https://github.com/bkuberek/mkcv/commit/f7dc0983d0d7f5cb4f89fb44f025017a72067864))

### Code Style

- Fix ruff formatting in new and modified files
  ([`a0228a8`](https://github.com/bkuberek/mkcv/commit/a0228a8ec8d651c82dff979a902431c99fca8062))

### Documentation

- Add changelog entries for v1.0.0–v1.1.2 and fix semantic-release integration
  ([`f7a59e5`](https://github.com/bkuberek/mkcv/commit/f7a59e5bee9a4ec4c1ba43f12f07932fcfedeade))

- **sdd**: Add interactive-regeneration change artifacts
  ([`f5c6af0`](https://github.com/bkuberek/mkcv/commit/f5c6af056210b9ef1942f26b94cb07a98aa39cd5))

### Features

- **cli**: Default --interactive to on when stdin is a TTY
  ([`adc5c9e`](https://github.com/bkuberek/mkcv/commit/adc5c9ef9d4ca27ee70fcbeead60daace7c76407))

- **interactive**: Add /edit, free-text regeneration, and tab completion
  ([`515ba0e`](https://github.com/bkuberek/mkcv/commit/515ba0e5ce117679d0cf853261e9b4be1ca0c5a0))


## [1.1.2] - 2026-03-20

### Fixed

- Escape Typst special characters in cover letter rendering
- Add project-level agent skills and lock file

## [1.1.1] - 2026-03-20

### Fixed

- Use valid phone number format in example knowledge base

### Added

- Sample knowledge base and job description examples
- Version badge to README

## [1.1.0] - 2026-03-20

### Added

- Theme system overhaul — fix `--theme` flag, add config defaults, custom themes, and design overrides

### Fixed

- Version step checks out latest main before bumping
- Opt into Node.js 24 for GitHub Actions to suppress warnings
- Resolve test failures for dynamic version and env-dependent factory
- Single CI pipeline with conditional version step

### Changed

- Split CI into quality checks and release pipelines

## [1.0.0] - 2026-03-20

### Added

- **5-stage AI resume pipeline** — analyze JD, select experience, tailor content, structure YAML, review for ATS compliance
- **`mkcv generate`** command — end-to-end resume generation from job description and career knowledge base
- **`mkcv render`** command — render resume YAML to PDF, PNG, Markdown, or HTML via RenderCV/Typst
- **`mkcv validate`** command — LLM-powered ATS compliance check for resumes and knowledge base validation
- **`mkcv themes`** command — list and preview available resume themes
- **`mkcv status`** command — workspace overview showing applications and their status
- **`mkcv init`** command — create organized workspace with knowledge base templates and config
- **`mkcv cover-letter`** command — generate tailored cover letters from job description and resume
- **Interactive mode** (`--interactive`) — pause and review after each pipeline stage
- **Multi-provider AI support** — Anthropic (Claude), OpenAI (GPT), Ollama (local/free), OpenRouter (200+ models)
- **Provider profiles** (`--profile`) — switch between premium (Anthropic) and budget (Ollama) configurations
- **Per-stage model configuration** — configure different providers and models for each pipeline stage
- **Smart per-stage model defaults** — optimized default model selection per pipeline stage
- **Multiple resume themes** — sb2nov, classic, moderncv, engineeringresumes
- **5-layer configuration resolution** — built-in defaults, global config, workspace config, environment variables, CLI flags
- **Workspace model** — organized directory structure with knowledge base, applications per company/role, and templates
- **JD input flexibility** — accept job descriptions from file path, URL, or stdin
- **Resume re-generation** (`--from-stage`) — restart pipeline from a specific stage reusing previous artifacts
- **Cover letter layout customization** — configurable page size, margins, fonts, and spacing
- **Resume layout customization** — configurable theme properties, page geometry, header spacing, section titles, and typography
- **Automatic semantic versioning** on merge to main
- **Token usage tracking** across all LLM adapters
- **Exponential backoff retry** for LLM rate limits
- Unified preset system with content density, artifact relocation, and versioned output
- Generic resume mode, output organization, and init safety
- OpenRouter provider support with 200+ models
- Ollama adapter for local model support
- Multi-theme preview — render same resume across multiple themes

[1.1.2]: https://github.com/bkuberek/mkcv/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/bkuberek/mkcv/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/bkuberek/mkcv/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/bkuberek/mkcv/releases/tag/v1.0.0
