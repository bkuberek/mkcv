# mkcv — CLI Interface Specification

**Version:** 0.2.0
**Date:** 2026-03-18

---

## Overview

mkcv uses **Cyclopts** for CLI parsing. Global options are handled by a
meta handler that runs before any subcommand. Workspace discovery happens
automatically (walk up from CWD looking for `mkcv.toml`) or via `--workspace`.

```
mkcv
├── generate    # Run AI pipeline: JD + KB → resume.yaml + review
├── render      # Render resume.yaml → PDF/PNG/MD
├── validate    # ATS compliance check on existing resume
├── init        # Initialize a new mkcv workspace
└── themes      # List available themes
```

---

## Global Options

These apply to all commands via the Cyclopts meta handler:

```
--verbose / -v     Enable verbose (DEBUG) logging. [default: False]
--workspace PATH   Path to workspace root (overrides auto-discovery).
--version          Display application version.
--help / -h        Display help and exit.
```

---

## Commands

### `mkcv generate`

Run the AI pipeline to generate a tailored resume.

```
Usage: mkcv generate --jd PATH [OPTIONS]

Required:
  --jd PATH              Path to job description file (text/markdown).

Options:
  --kb PATH              Path to knowledge base file.
                         In workspace mode, defaults to config value.
  --company TEXT         Company name (required in workspace mode).
  --position TEXT        Position title (required in workspace mode).
  --output-dir PATH      Output directory (default: auto-generated).
  --theme TEXT           RenderCV theme name. [default: sb2nov]
  --profile TEXT         Provider profile (budget/premium). [default: premium]
  --from-stage INT       Resume from this pipeline stage (1-5). [default: 1]
  --render / --no-render Auto-render PDF after pipeline. [default: --render]
  --interactive          Pause after each stage for review. [default: False]
```

**Workspace mode** (when `mkcv.toml` is found): creates
`applications/{company}/{YYYY-MM-position}/` with `application.toml`,
`jd.txt`, and `.mkcv/` for artifacts. `--company` and `--position` are
required.

**Standalone mode** (no workspace): requires `--kb`. Creates `.mkcv/` in CWD.

**Examples:**

```bash
# Standalone — explicit KB
mkcv generate --jd jobs/deepl.txt --kb career.md

# Workspace mode — KB from config, app dir created
mkcv generate --jd jobs/deepl.txt --company DeepL --position "Senior Engineer"

# Resume from stage 3
mkcv generate --jd jobs/deepl.txt --from-stage 3

# Generate YAML only, skip rendering
mkcv generate --jd jobs/deepl.txt --kb career.md --no-render
```

---

### `mkcv render`

Render an existing YAML file to PDF and other formats.

```
Usage: mkcv render YAML-FILE [OPTIONS]

Required:
  YAML-FILE              RenderCV YAML file to render.

Options:
  --output-dir PATH      Output directory (default: same as input file).
  --theme TEXT           Override theme (default: from YAML).
  --format TEXT          Output formats, comma-separated (pdf,png,md,html).
                         [default: pdf,png]
  --open / --no-open     Open PDF after rendering. [default: False]
```

**Examples:**

```bash
mkcv render resume.yaml
mkcv render resume.yaml --theme classic --open
mkcv render resume.yaml --format pdf,png,md,html
```

---

### `mkcv validate`

Check a resume for ATS compliance.

```
Usage: mkcv validate FILE [OPTIONS]

Required:
  FILE                   Resume file to validate (PDF or YAML).

Options:
  --jd PATH              Job description to check keyword coverage against.
```

**Examples:**

```bash
mkcv validate resume.pdf
mkcv validate resume.pdf --jd jobs/deepl.txt
```

---

### `mkcv init`

Initialize a new mkcv workspace.

```
Usage: mkcv init [PATH]

Arguments:
  PATH                   Directory to initialize. [default: current directory]
```

Creates the workspace directory structure:
- `mkcv.toml` — workspace configuration
- `knowledge-base/career.md` — starter knowledge base template
- `knowledge-base/voice.md` — voice/tone guidelines
- `applications/` — empty applications directory
- `templates/` — user prompt template overrides
- `.gitignore`

**Examples:**

```bash
mkcv init                          # Initialize in current directory
mkcv init ./my-workspace           # Initialize at a specific path
```

---

### `mkcv themes`

List and preview available resume themes.

```
Usage: mkcv themes [OPTIONS]

Options:
  --preview TEXT          Generate a preview PDF for a specific theme.
```

**Examples:**

```bash
mkcv themes                        # List all themes
mkcv themes --preview sb2nov       # Preview a specific theme
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments / missing required options |
| 3 | Configuration error (missing API key, bad config file) |
| 4 | Provider error (API failure after retries) |
| 5 | Pipeline stage error / validation error |
| 6 | Render error / template error |
| 7 | Workspace error (not found, already exists) |
| 130 | Keyboard interrupt |

---

## Environment Variables

All env vars use the `MKCV_` prefix (Dynaconf convention):

| Variable | Description |
|----------|-------------|
| `MKCV_ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `MKCV_OPENAI_API_KEY` | OpenAI API key |
| `MKCV_OPENROUTER_API_KEY` | OpenRouter API key |
| `MKCV_RENDERING__THEME` | Default theme |
| `MKCV_GENERAL__VERBOSE` | Enable verbose logging |

Dynaconf uses double underscores for nested keys:
`MKCV_PIPELINE__STAGES__ANALYZE__MODEL=claude-sonnet-4-20250514`
