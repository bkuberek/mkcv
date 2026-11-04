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
├── status      # Show workspace overview and application listing
├── cover-letter # Generate a tailored cover letter
├── kb          # Generate or update a career knowledge base
└── models      # Show which model each stage uses, with recommendations and cost
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
  --preset TEXT          Resume density: concise, standard, comprehensive.
                         [default: standard]
  --model-profile TEXT   Model profile for all stages: anthropic,
                         anthropic-economy, openai, openai-economy, google,
                         google-economy, local. Run 'mkcv models --profiles'.
  --provider TEXT        Run every stage on this provider with its recommended
                         models (anthropic/openai/google/ollama/openrouter or
                         a provider from your config).
  --profile TEXT         Deprecated: use --preset. budget = concise + ollama.
  --cover-letter         Chain cover letter generation after the resume.
  --from-stage INT       Resume from this pipeline stage (1-5). [default: 1]
  --render / --no-render Auto-render PDF after pipeline. [default: --render]
  --interactive          Pause after each stage for review. [default: False]
```

**JD sources:** `--jd` accepts a local file path, an HTTP/HTTPS URL (fetched
via httpx), or `"-"` to read from stdin. URL content is fetched
automatically. KB validation runs before the pipeline starts and blocks
generation if errors are found.

**Presets and model profiles:** two independent choices. `--preset` sets how
much the resume says (`concise`, `standard`, `comprehensive`); it does not
choose models, except that `concise` selects the economy variant of the active
profile. `--model-profile` and `--provider` choose the models. They are
mutually exclusive: combining them exits with code 3. `--profile budget` is a
deprecated alias for `--preset concise` with `--provider ollama`.

**Model selection:** per-stage `provider`, `model`, and `temperature` in
`mkcv.toml` (`[default.pipeline.stages.<stage>]`) **are honoured by
`generate`**. Earlier versions replaced them with the preset's models, so
existing keys now take effect. The full precedence order is: command-line
flags (`--model-profile`, else `--provider`), then per-stage config, then
`pipeline.model_profile`, then the profile of `pipeline.provider`, then the
`anthropic` profile. Under `--provider X`, a stage keeps its own entry only if
that entry names both `provider = "X"` and a `model`; all other stages use X's
recommended model. A provider with no profile (`openrouter`, or one you define)
needs a `model` for every stage, or the command exits with code 3 before any
LLM call. See [`docs/models.md`](../models.md).

**Model warnings:** before the pipeline starts, `generate` prints
non-blocking warnings (below recommended tier, unknown model, deprecated model,
missing API key) and a pointer to `mkcv models`. Disable them with
`pipeline.model_warnings = false`.

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

# Run every stage on another provider's recommended models
mkcv generate --jd jobs/deepl.txt --kb career.md --model-profile google
mkcv generate --jd jobs/deepl.txt --kb career.md --provider openai

# Cheaper models (economy variant of the active profile)
mkcv generate --jd jobs/deepl.txt --kb career.md --preset concise

# Local Ollama models
mkcv generate --jd jobs/deepl.txt --kb career.md --model-profile local

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

### `mkcv cover-letter`

Generate a tailored cover letter from a job description and a resume or
knowledge base.

```
Usage: mkcv cover-letter --jd SOURCE [OPTIONS]

Required:
  --jd SOURCE            Job description: file path, URL, or "-" for stdin.

Options:
  --app-dir PATH         Application directory containing resume.yaml.
  --company TEXT         Auto-resolve the latest application for a company.
  --resume PATH          A resume.yaml file to use as context.
  --kb PATH              Knowledge base file.
  --output-dir PATH      Output directory for the cover letter files.
  --preset TEXT          Preset name (concise/standard/comprehensive).
  --model-profile TEXT   Model profile for both stages (see `mkcv generate`).
  --provider TEXT        Run both stages on this provider with its
                         recommended models.
  --render / --no-render Render the cover letter to PDF. [default: --render]
```

The cover letter uses the `cover_letter.generate` and `cover_letter.review`
stages. Model selection, precedence, and warnings work as for `mkcv generate`.

---

### `mkcv models`

Show which model each stage will use, what mkcv recommends, and an estimated
cost. Calls no provider and needs no API key.

```
Usage: mkcv models [OPTIONS]

Options:
  --model-profile TEXT   Show this profile's models.
  --provider TEXT        Show every stage on this provider; with --catalog,
                         list only this provider's entries.
  --preset TEXT          Preset to resolve models for. [default: standard]
  --profiles             List the built-in model profiles and their stage models.
  --catalog              List the model catalog (capabilities, tiers, prices),
                         including [[default.model_catalog]] overrides.
  --json                 Print JSON instead of tables.
```

**Default view:** the resolved profile (marked `provisional` until an eval
run backs it), where that choice came from, and a table with one row per
stage: `analyze`, `select`, `tailor`, `structure`, `review`,
`cover_letter.generate`, `cover_letter.review`, `kb`, `validate`. The columns
are `Stage`, `Provider`, `Model`, `Source` (`profile`, `config`, or `cli`),
`Recommended`, `Tier`, and `Est. cost`. A line below the table gives the
estimated cost per resume run (the five pipeline stages), and a `Warnings:`
section follows when there is something to warn about.

**`--json`:** the default view prints a `ModelReport`; `--profiles` prints a
list of profiles; `--catalog` prints a list of catalog entries.
`--profiles` and `--catalog` cannot be combined (exit code 2).

Configuration errors (an unknown profile or provider, conflicting flags, a
stage with no model) exit with code 3.

**Examples:**

```bash
mkcv models                              # What would a run use?
mkcv models --model-profile openai       # What would the openai profile use?
mkcv models --preset concise             # The economy variant
mkcv models --profiles                   # The seven built-in profiles
mkcv models --catalog --provider google  # Everything mkcv knows about Gemini
mkcv models --json | jq '.estimated_total_usd'
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments / missing required options |
| 3 | Configuration error: unknown provider or model profile, `--model-profile` combined with `--provider`, a stage with no model, an invalid `[default.providers.*]` or `[[default.model_catalog]]` entry, or an invalid setting. A missing API key is a warning, not an error. |
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
| `MKCV_PIPELINE__MODEL_PROFILE` | Default model profile (for example `google`) |
| `MKCV_PIPELINE__STAGES__ANALYZE__MODEL` | Model for one stage (any stage section works the same way) |
| `MKCV_RENDERING__THEME` | Default theme |
| `MKCV_GENERAL__VERBOSE` | Enable verbose logging |

Dynaconf uses double underscores for nested keys:
`MKCV_PIPELINE__STAGES__ANALYZE__MODEL=claude-sonnet-5-5`

API keys are read from the providers' own variable names, without the `MKCV_`
prefix:

| Variable | Provider |
|----------|----------|
| `ANTHROPIC_API_KEY` | Anthropic |
| `OPENAI_API_KEY` | OpenAI |
| `GEMINI_API_KEY`, `GOOGLE_API_KEY` | Google Gemini (`GEMINI_API_KEY` wins when both are set) |
| `OPENROUTER_API_KEY` | OpenRouter |

Google Gemini can also run on Vertex AI with Application Default Credentials
instead of a key (run `gcloud auth application-default login` once):

```toml
[default.providers.google]
vertexai = true
project = "my-gcp-project"
location = "global"
```

| Variable | Meaning |
|----------|---------|
| `GOOGLE_GENAI_USE_VERTEXAI` | `true` or `1` turns Vertex mode on (`vertexai` in config wins) |
| `GOOGLE_CLOUD_PROJECT` | Project for Vertex AI (`project` in config wins; falls back to the ADC project) |
| `GOOGLE_CLOUD_LOCATION` | Location for Vertex AI (`location` in config wins; default `global`) |

To pin one account for a workspace, set `credentials_file` in the same table
(for example `"~/.config/gcloud-mkcv/application_default_credentials.json"`,
created with `CLOUDSDK_CONFIG=~/.config/gcloud-mkcv gcloud auth
application-default login`). It takes precedence over ADC lookup, including
`GOOGLE_APPLICATION_CREDENTIALS` and `CLOUDSDK_CONFIG`; a missing file is a
configuration error naming the path.

In Vertex mode an API key is ignored. Missing ADC or an unknown project stops
the command with a configuration error (exit code 3).

A provider you define under `[default.providers.<name>]` names its own
variable with `api_key_env`. Ollama needs no key. A missing key stops the command
with a configuration error (exit code 3); use `--provider stub` for offline runs.
