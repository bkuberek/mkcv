# mkcv — CLI Interface Specification

**Version:** 0.1.0
**Date:** 2026-03-18

---

## Command Overview

```
mkcv
├── generate    # Run AI pipeline: JD + KB → resume.yaml + review
├── render      # Render resume.yaml → PDF/PNG/MD
├── validate    # ATS compliance check on existing resume
├── init        # Initialize config and KB template
└── themes      # List available themes
```

---

## Commands

### `mkcv generate`

Run the AI pipeline to generate a tailored resume.

```
Usage: mkcv generate [OPTIONS]

Options:
  --jd PATH              Job description file (text/markdown)  [required]
  --kb PATH              Knowledge base file                   [default: from config]
  --output-dir PATH      Output directory                      [default: .mkcv/<timestamp>_<company>]
  --theme TEXT            RenderCV theme name                   [default: sb2nov]
  --profile TEXT          Provider profile (budget/premium)     [default: premium]
  --from-stage INT        Resume from this stage (1-5)          [default: 1]
  --render / --no-render  Auto-render PDF after pipeline        [default: --render]
  --interactive           Pause after each stage for review     [default: false]
  --provider TEXT         Override provider for all stages
  --model TEXT            Override model for all stages
  --verbose / -v          Show detailed progress
  --dry-run              Show what would be done without calling APIs
  --help                 Show this message
```

**Examples:**

```bash
# Basic usage
mkcv generate --jd jobs/deepl.txt --kb career.md

# Budget mode with Ollama
mkcv generate --jd jobs/deepl.txt --kb career.md --profile budget

# Resume from stage 3 (reuse existing analysis and selection)
mkcv generate --jd jobs/deepl.txt --kb career.md --from-stage 3

# Interactive mode — review after each stage
mkcv generate --jd jobs/deepl.txt --kb career.md --interactive

# Just generate YAML, don't render
mkcv generate --jd jobs/deepl.txt --kb career.md --no-render
```

**Output:**

```
mkcv generate --jd jobs/deepl.txt --kb career.md

  ✓ Stage 1: Analyzed JD — DeepL, Senior Staff Software Engineer (API)
  ✓ Stage 2: Selected 4 experiences, 18 bullets (3 gaps identified)
  ✓ Stage 3: Tailored content — 15 bullets (2 flagged low confidence)
  ✓ Stage 4: Structured resume.yaml (validated)
  ✓ Stage 5: Review score: 87/100, ATS keyword coverage: 82%
  ✓ Stage 6: Rendered → resume.pdf

  Output: .mkcv/2026-03-18T10-30_deepl/
  ├── resume.pdf          (2 pages)
  ├── resume.yaml         (edit and re-render with: mkcv render)
  ├── review_report.json  (2 items need attention)
  └── resume.png          (preview)

  ⚠ 2 low-confidence bullets flagged — review in review_report.json
```

---

### `mkcv render`

Render an existing YAML file to PDF (and optionally PNG/MD).

```
Usage: mkcv render [OPTIONS] YAML_FILE

Arguments:
  YAML_FILE              RenderCV YAML file to render           [required]

Options:
  --output-dir PATH      Output directory                       [default: same as input]
  --theme TEXT            Override theme                         [default: from YAML]
  --format TEXT           Output formats (pdf,png,md,html)       [default: pdf,png]
  --open                 Open PDF after rendering                [default: false]
  --help                 Show this message
```

**Examples:**

```bash
# Render to PDF
mkcv render .mkcv/2026-03-18T10-30_deepl/resume.yaml

# Render with a different theme
mkcv render resume.yaml --theme classic

# Render and open in default PDF viewer
mkcv render resume.yaml --open

# Render all formats
mkcv render resume.yaml --format pdf,png,md,html
```

---

### `mkcv validate`

Check an existing resume (PDF or YAML) for ATS compliance.

```
Usage: mkcv validate [OPTIONS] FILE

Arguments:
  FILE                   Resume file (PDF or YAML)              [required]

Options:
  --jd PATH              Job description to check keyword coverage against
  --verbose / -v         Show detailed findings
  --help                 Show this message
```

**Output:**

```
mkcv validate resume.pdf

  ATS Compliance Report
  ─────────────────────
  ✓ Text extractable — all content present in text layer
  ✓ Reading order correct — no column interleaving
  ✓ Standard section headings detected
  ✓ Contact info in body (not header/footer)
  ✓ No icon fonts or special characters detected
  ✓ Standard bullet characters
  ✗ Font: SourceSansPro — not a standard system font (medium risk)

  Score: 95/100 — PASS

mkcv validate resume.pdf --jd jobs/deepl.txt

  Keyword Coverage: 82% (41/50 keywords matched)
  Missing: "AWS Marketplace", "data residency", "billing integration"
  Suggestion: Add missing keywords to skills or bullet points
```

---

### `mkcv init`

Initialize mkcv configuration and optionally create a knowledge base template.

```
Usage: mkcv init [OPTIONS]

Options:
  --config-dir PATH      Config directory                       [default: ~/.config/mkcv]
  --kb-template          Generate a knowledge base template     [default: false]
  --help                 Show this message
```

**Output:**

```
mkcv init

  Created: ~/.config/mkcv/config.yaml
  Created: ~/.config/mkcv/voice.md

  Configure your API keys:
    export ANTHROPIC_API_KEY=sk-ant-...
    export OPENAI_API_KEY=sk-...

  Or add them to ~/.config/mkcv/config.yaml

mkcv init --kb-template

  Created: knowledge-base-template.md
  Fill in your career details and use with: mkcv generate --kb knowledge-base-template.md
```

---

### `mkcv themes`

List and preview available themes.

```
Usage: mkcv themes [OPTIONS]

Options:
  --preview TEXT          Generate a preview PDF for a specific theme
  --help                 Show this message
```

**Output:**

```
mkcv themes

  Available Themes:
  ─────────────────
  sb2nov              Single-column, minimal, industry standard for tech
  classic             Traditional professional layout
  moderncv            Classic academic/professional CV style
  engineeringresumes  Optimized for engineering roles
  markdown            Plain text with minimal formatting

  Preview: mkcv themes --preview sb2nov
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
| 5 | Validation error (AI output failed schema validation) |
| 6 | Render error (YAML → PDF failed) |

---

## Environment Variables

| Variable | Description |
|----------|------------|
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `OLLAMA_BASE_URL` | Ollama server URL (default: `http://localhost:11434`) |
| `MKCV_CONFIG` | Override config file path |
| `MKCV_KB` | Default knowledge base path |
| `MKCV_THEME` | Default theme |
| `MKCV_PROFILE` | Default provider profile |
