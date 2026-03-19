# mkcv — CLI Interface Specification

**Version:** 0.3.0
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
├── validate    # ATS compliance check on existing resume or KB
├── init        # Initialize a new mkcv workspace
├── themes      # List and preview available themes
└── status      # Show workspace overview and application listing
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
Usage: mkcv generate --jd SOURCE [OPTIONS]

Required:
  --jd SOURCE            Job description source: file path, URL (http/https),
                         or "-" for stdin.

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

**JD sources:** `--jd` accepts a local file path, an HTTP/HTTPS URL (fetched
via httpx), or `"-"` to read from stdin. URL content is fetched
automatically. KB validation runs before the pipeline starts and blocks
generation if errors are found.

**Profile presets:** `--profile budget` uses Ollama (local models, free);
`--profile premium` uses Anthropic Claude. Each profile sets per-stage
provider, model, and temperature.

**Progress:** A Rich spinner shows progress during each pipeline stage.
In `--interactive` mode, the pipeline pauses after each stage and prompts
the user to continue or stop.

**Workspace mode** (when `mkcv.toml` is found): creates
`applications/{company}/{YYYY-MM-position}/` with `application.toml`,
`jd.txt`, and `.mkcv/` for artifacts. `--company` and `--position` are
required.

**Standalone mode** (no workspace): requires `--kb`. Creates `.mkcv/` in CWD.

**Examples:**

```bash
# Standalone — explicit KB
mkcv generate --jd jobs/deepl.txt --kb career.md

# From a URL
mkcv generate --jd https://example.com/job-posting.txt --kb career.md

# From stdin
cat jobs/deepl.txt | mkcv generate --jd - --kb career.md

# Workspace mode — KB from config, app dir created
mkcv generate --jd jobs/deepl.txt --company DeepL --position "Senior Engineer"

# Resume from stage 3
mkcv generate --jd jobs/deepl.txt --from-stage 3

# Generate YAML only, skip rendering
mkcv generate --jd jobs/deepl.txt --kb career.md --no-render

# Use budget profile (local Ollama models)
mkcv generate --jd jobs/deepl.txt --kb career.md --profile budget

# Interactive mode — review after each stage
mkcv generate --jd jobs/deepl.txt --kb career.md --interactive
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

Check a resume or knowledge base for quality issues.

```
Usage: mkcv validate [FILE] [OPTIONS]

Arguments:
  FILE                   Resume file to validate (YAML or PDF). Optional if
                         using --kb.

Options:
  --kb PATH              Knowledge base file to validate (Markdown).
  --jd PATH              Job description to check keyword coverage against.
```

**Resume validation** uses an LLM to review the resume for ATS compliance,
bullet quality, keyword coverage, and overall presentation. Accepts both
YAML resume files and rendered PDFs (text is extracted via pypdf).

**KB validation** (`--kb`) checks a knowledge base Markdown file for
expected sections (contact info, summary, experience, education, skills),
date patterns, bullet points, and reasonable length. Runs without an LLM.

**Examples:**

```bash
mkcv validate resume.yaml
mkcv validate resume.pdf
mkcv validate resume.pdf --jd jobs/deepl.txt
mkcv validate --kb knowledge-base/career.md
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
  --preview TEXT          Show a styled preview for a specific theme.
```

Lists all available RenderCV themes with name, description, and font family.
Uses `--preview` to display a detailed Rich panel with colors, font info,
page size, and a sample layout rendering in the terminal.

Theme metadata is extracted from the RenderCV built-in theme classes at
runtime (font family, primary/accent colors, page size).

**Examples:**

```bash
mkcv themes                        # List all themes in a table
mkcv themes --preview sb2nov       # Show detailed preview panel
```

---

### `mkcv status`

Show workspace overview and application listing.

```
Usage: mkcv status
```

Displays the current workspace root, config path, knowledge base status,
and a table of all applications with company, position, date, status,
and whether resume YAML and PDF files exist.

If no workspace is found, suggests running `mkcv init`.

**Examples:**

```bash
mkcv status                        # Show workspace overview
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
