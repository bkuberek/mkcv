# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-06-01

### Added

- **5-stage AI resume pipeline** -- analyze JD, select experience, tailor content, structure YAML, review for ATS compliance
- **`mkcv generate`** command -- end-to-end resume generation from job description and career knowledge base
- **`mkcv render`** command -- render resume YAML to PDF, PNG, Markdown, or HTML via RenderCV/Typst
- **`mkcv validate`** command -- LLM-powered ATS compliance check for resumes and knowledge base validation
- **`mkcv themes`** command -- list and preview available resume themes
- **`mkcv status`** command -- workspace overview showing applications and their status
- **`mkcv init`** command -- create organized workspace with knowledge base templates and config
- **`mkcv cover-letter`** command -- generate tailored cover letters from job description and resume
- **Interactive mode** (`--interactive`) -- pause and review after each pipeline stage
- **Multi-provider AI support** -- Anthropic (Claude), OpenAI (GPT), Ollama (local/free), OpenRouter (200+ models)
- **Provider profiles** (`--profile`) -- switch between premium (Anthropic) and budget (Ollama) configurations
- **Per-stage model configuration** -- configure different providers and models for each pipeline stage
- **Smart per-stage model defaults** -- optimized default model selection per pipeline stage
- **Multiple resume themes** -- sb2nov, classic, moderncv, engineeringresumes
- **5-layer configuration resolution** -- built-in defaults, global config, workspace config, environment variables, CLI flags
- **Workspace model** -- organized directory structure with knowledge base, applications per company/role, and templates
- **JD input flexibility** -- accept job descriptions from file path, URL, or stdin
- **Resume re-generation** (`--from-stage`) -- restart pipeline from a specific stage reusing previous artifacts
- **Cover letter layout customization** -- configurable page size, margins, fonts, and spacing
- **Resume layout customization** -- configurable theme properties, page geometry, header spacing, section titles, and typography

[0.1.0]: https://github.com/bkuberek/mkcv/releases/tag/v0.1.0
