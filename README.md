# mkcv

AI-powered CLI tool that generates ATS-compliant PDF resumes tailored to specific job applications.

Feed it your career knowledge base + a job description, and it produces a polished, keyword-optimized resume through a 5-stage AI pipeline.

## Quick Start

```bash
# Install
uv tool install -e .

# Set up an API key (at least one)
export ANTHROPIC_API_KEY=sk-ant-...
# or
export OPENAI_API_KEY=sk-...

# Create a workspace
mkcv init ~/Documents/cv

# Edit your knowledge base
$EDITOR ~/Documents/cv/knowledge-base/career.md

# Generate a resume
cd ~/Documents/cv
mkcv generate --jd https://example.com/job-posting.txt \
  --company Acme --position "Senior Engineer"
```

## Installation

Requires **Python 3.12+** and [uv](https://docs.astral.sh/uv/).

```bash
# Clone the repo
git clone https://github.com/bkuberek/mkcv.git
cd mkcv

# Install as a global CLI tool
uv tool install -e .

# Verify
mkcv --version
mkcv --help
```

Alternative install methods:

```bash
# pip (editable)
pip install -e .

# Just sync deps (for development)
uv sync
uv run mkcv --help
```

## API Credentials

mkcv needs at least one AI provider configured. Set API keys as environment variables:

```bash
# Anthropic (default provider — recommended)
export ANTHROPIC_API_KEY=sk-ant-...

# OpenAI (used for some pipeline stages by default)
export OPENAI_API_KEY=sk-...

# OpenRouter (access 200+ models with one key — https://openrouter.ai)
export OPENROUTER_API_KEY=sk-or-...

# Ollama (free, local — no key needed, just have Ollama running)
# ollama serve
```

Add these to your shell profile (`~/.zshrc`, `~/.bashrc`, etc.) so they persist.

You only need **one** provider. OpenRouter is a good choice if you want access to multiple models (Claude, GPT, Gemini, DeepSeek, etc.) through a single API key.

### Provider Profiles

Use `--profile` to control which providers are used:

| Profile | Provider | Model | Cost |
|---------|----------|-------|------|
| `premium` (default) | Anthropic | Claude Sonnet 4 | ~$0.10-0.50/resume |
| `budget` | Ollama | Llama 3.1 8B | Free (local) |
| `default` | Mixed | Per-stage config | Varies |

```bash
# Use local models (free, requires Ollama running)
mkcv generate --jd job.txt --kb career.md --profile budget

# Use best models (requires Anthropic API key)
mkcv generate --jd job.txt --kb career.md --profile premium
```

You can also configure providers per-stage in your workspace `mkcv.toml`:

```toml
[pipeline.stages.analyze]
provider = "anthropic"
model = "claude-sonnet-4-20250514"
temperature = 0.2

[pipeline.stages.structure]
provider = "openai"
model = "gpt-4o"
temperature = 0.1
```

### Using OpenRouter

[OpenRouter](https://openrouter.ai) gives you access to Claude, GPT, Gemini, DeepSeek, and many other models through a single API key. Set `provider = "openrouter"` in your config and use the OpenRouter model identifiers:

```toml
# mkcv.toml — all stages via OpenRouter
[pipeline.stages.analyze]
provider = "openrouter"
model = "anthropic/claude-sonnet-4"
temperature = 0.2

[pipeline.stages.select]
provider = "openrouter"
model = "anthropic/claude-sonnet-4"
temperature = 0.3

[pipeline.stages.tailor]
provider = "openrouter"
model = "anthropic/claude-sonnet-4"
temperature = 0.5

[pipeline.stages.structure]
provider = "openrouter"
model = "openai/gpt-4o"
temperature = 0.1

[pipeline.stages.review]
provider = "openrouter"
model = "anthropic/claude-sonnet-4"
temperature = 0.3
```

You can mix and match — use DeepSeek for cheap drafting and Claude for final review:

```toml
[pipeline.stages.tailor]
provider = "openrouter"
model = "deepseek/deepseek-chat-v3"
temperature = 0.5

[pipeline.stages.review]
provider = "openrouter"
model = "anthropic/claude-sonnet-4"
temperature = 0.3
```

## Workspace Setup

A workspace keeps your knowledge base, configuration, and all applications organized:

```bash
mkcv init ~/Documents/cv
```

This creates:

```
~/Documents/cv/
├── mkcv.toml                    # Workspace configuration
├── knowledge-base/
│   ├── career.md                # Your career history (fill this in!)
│   └── voice.md                 # Writing tone/style guidelines
├── applications/                # Generated resumes go here
│   └── {company}/
│       └── {date-position}/
│           ├── jd.txt           # Job description
│           ├── resume.yaml      # Generated resume data
│           └── resume.pdf       # Rendered PDF
└── templates/                   # Custom prompt overrides
```

### Knowledge Base

The knowledge base (`career.md`) is the single source of truth about your career. Fill it in with:

- **Contact info** — name, email, phone, location, LinkedIn, GitHub
- **Summary** — professional profile / objective
- **Experience** — all roles with dates, companies, and detailed bullet points
- **Education** — degrees, institutions, dates
- **Skills** — technical skills, tools, frameworks, languages
- **Projects** — notable projects (optional)
- **Certifications** — professional certifications (optional)

The more detail you put in, the better the AI can tailor your resume. Include metrics, technologies, and outcomes in your bullet points.

## Commands

### `mkcv generate` — Generate a Resume

The main command. Takes a job description + knowledge base and produces a tailored resume.

```bash
# Basic — file path
mkcv generate --jd job_description.txt --kb career.md

# From a URL
mkcv generate --jd https://example.com/posting.txt --kb career.md

# From stdin
cat job.txt | mkcv generate --jd - --kb career.md
pbpaste | mkcv generate --jd - --kb career.md

# Workspace mode (KB from config, creates application directory)
cd ~/Documents/cv
mkcv generate --jd job.txt --company DeepL --position "Senior Engineer"

# Resume from a specific stage (reuses previous artifacts)
mkcv generate --jd job.txt --from-stage 3

# Generate YAML only, skip PDF rendering
mkcv generate --jd job.txt --kb career.md --no-render

# Interactive mode — pause and review after each stage
mkcv generate --jd job.txt --kb career.md --interactive

# Budget mode — use local Ollama models
mkcv generate --jd job.txt --kb career.md --profile budget
```

**Pipeline stages:**
1. **Analyze JD** — Extract requirements, keywords, priorities from the job description
2. **Select Experience** — Choose the most relevant items from your knowledge base
3. **Tailor Content** — Rewrite bullets with XYZ formula, weave in keywords
4. **Structure YAML** — Produce RenderCV-compatible YAML
5. **Review** — ATS compliance check, scoring, improvement suggestions

### `mkcv render` — Render to PDF

Render an existing resume YAML to PDF (and optionally PNG, Markdown, HTML).

```bash
mkcv render resume.yaml
mkcv render resume.yaml --theme classic
mkcv render resume.yaml --format pdf,png,md,html
mkcv render resume.yaml --open    # Open PDF after rendering
```

### `mkcv validate` — Check Quality

Validate a resume or knowledge base for issues.

```bash
# Validate a resume YAML (LLM-powered)
mkcv validate resume.yaml

# Validate a rendered PDF
mkcv validate resume.pdf

# Validate against a specific JD for keyword coverage
mkcv validate resume.yaml --jd job.txt

# Validate your knowledge base structure (no LLM needed)
mkcv validate --kb knowledge-base/career.md
```

### `mkcv themes` — Browse Themes

List available resume themes and preview them.

```bash
mkcv themes                      # List all themes
mkcv themes --preview sb2nov     # Detailed preview with colors and layout
```

### `mkcv status` — Workspace Overview

See what's in your workspace.

```bash
mkcv status
```

Shows: workspace root, config path, KB status, and a table of all applications with their resume/PDF status.

### `mkcv init` — Create a Workspace

```bash
mkcv init                        # Current directory
mkcv init ~/Documents/cv         # Specific path
```

## Configuration

Configuration is resolved in 5 layers (later overrides earlier):

1. **Built-in defaults** — bundled with the package
2. **Global user config** — `~/.config/mkcv/settings.toml`
3. **Workspace config** — `mkcv.toml` in workspace root
4. **Environment variables** — `MKCV_` prefix
5. **CLI flags** — applied at runtime

### Workspace Config (`mkcv.toml`)

```toml
[general]
verbose = false

[pipeline]
auto_render = true
interactive = false

[pipeline.stages.analyze]
provider = "anthropic"
model = "claude-sonnet-4-20250514"
temperature = 0.2

[pipeline.stages.select]
provider = "anthropic"
model = "claude-sonnet-4-20250514"
temperature = 0.3

[pipeline.stages.tailor]
provider = "anthropic"
model = "claude-sonnet-4-20250514"
temperature = 0.5

[pipeline.stages.structure]
provider = "openai"
model = "gpt-4o"
temperature = 0.1

[pipeline.stages.review]
provider = "anthropic"
model = "claude-sonnet-4-20250514"
temperature = 0.3

[rendering]
theme = "sb2nov"

[workspace]
knowledge_base = "knowledge-base/career.md"
```

### Environment Variables

Use the `MKCV_` prefix. Double underscores for nested keys:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export MKCV_RENDERING__THEME=classic
export MKCV_PIPELINE__STAGES__ANALYZE__MODEL=claude-sonnet-4-20250514
export MKCV_GENERAL__VERBOSE=true
```

## Development

```bash
uv sync                                          # Install dependencies
uv run pytest                                    # Run all tests
uv run pytest -k test_name                       # Single test
uv run ruff check src/ tests/                    # Lint
uv run ruff format src/ tests/                   # Format
uv run mypy src/                                 # Type check
```

## License

MIT
