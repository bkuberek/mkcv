# mkcv

[![CI](https://github.com/bkuberek/mkcv/actions/workflows/test.yml/badge.svg)](https://github.com/bkuberek/mkcv/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

AI-powered CLI tool that generates ATS-compliant PDF resumes tailored to specific job applications.

## What is mkcv?

mkcv takes your career knowledge base and a job description, then produces a polished, keyword-optimized resume through a 5-stage AI pipeline. Every resume is tailored to the specific role -- the AI analyzes requirements, selects the most relevant experience, rewrites bullets using the XYZ impact formula, and optimizes for applicant tracking systems.

## Features

- **5-stage AI pipeline** -- analyze JD, select experience, tailor content, structure YAML, review for ATS compliance
- **Multi-provider AI** -- Anthropic (Claude), OpenAI (GPT), Ollama (local/free), OpenRouter (200+ models)
- **Interactive mode** -- pause and review after each pipeline stage
- **Cover letters** -- generate tailored cover letters alongside your resume
- **Multiple themes** -- choose from built-in RenderCV themes (sb2nov, classic, moderncv, engineeringresumes)
- **PDF + more** -- render to PDF, PNG, Markdown, or HTML via Typst
- **Workspace model** -- organize knowledge base, config, and applications per company/role
- **Smart defaults** -- per-stage model selection with budget and premium profiles
- **Configurable** -- 5-layer config resolution (defaults, global, workspace, env vars, CLI flags)

## Quick Start

```bash
# Install
pip install git+https://github.com/bkuberek/mkcv.git

# Set up an API key (at least one provider)
export ANTHROPIC_API_KEY=sk-ant-...

# Create a workspace
mkcv init ~/Documents/cv

# Edit your knowledge base with your career history
$EDITOR ~/Documents/cv/knowledge-base/career.md

# Generate a resume tailored to a job description
cd ~/Documents/cv
mkcv generate --jd https://example.com/job-posting.txt \
  --company Acme --position "Senior Engineer"
```

## Installation

Requires **Python 3.12+**.

### pip

```bash
pip install git+https://github.com/bkuberek/mkcv.git
```

### pipx (isolated environment)

```bash
pipx install git+https://github.com/bkuberek/mkcv.git
```

### uv

```bash
uv tool install git+https://github.com/bkuberek/mkcv.git
```

### From source

```bash
git clone https://github.com/bkuberek/mkcv.git
cd mkcv
uv sync
uv run mkcv --help
```

Verify the installation:

```bash
mkcv --version
mkcv --help
```

## Usage

### Set Up API Credentials

mkcv needs at least one AI provider configured:

```bash
# Anthropic (default provider -- recommended)
export ANTHROPIC_API_KEY=sk-ant-...

# OpenAI
export OPENAI_API_KEY=sk-...

# OpenRouter (access 200+ models with one key)
export OPENROUTER_API_KEY=sk-or-...

# Ollama (free, local -- no key needed, just have Ollama running)
```

Add these to your shell profile (`~/.zshrc`, `~/.bashrc`) so they persist.

### Create a Workspace

```bash
mkcv init ~/Documents/cv
```

This creates an organized directory with your knowledge base, config, and a place for generated applications:

```
~/Documents/cv/
├── mkcv.toml                    # Workspace configuration
├── knowledge-base/
│   ├── career.md                # Your career history (fill this in!)
│   └── voice.md                 # Writing tone/style guidelines
├── applications/                # Generated resumes go here
└── templates/                   # Custom prompt overrides
```

### Generate a Resume

```bash
# Basic -- from a file
mkcv generate --jd job_description.txt --kb career.md

# From a URL
mkcv generate --jd https://example.com/posting.txt --kb career.md

# From clipboard (macOS)
pbpaste | mkcv generate --jd - --kb career.md

# Workspace mode (KB from config, organized by company)
cd ~/Documents/cv
mkcv generate --jd job.txt --company DeepL --position "Senior Engineer"

# Interactive mode -- review each stage before proceeding
mkcv generate --jd job.txt --kb career.md --interactive

# Budget mode -- use free local Ollama models
mkcv generate --jd job.txt --kb career.md --profile budget

# Resume from a specific stage (reuse previous artifacts)
mkcv generate --jd job.txt --from-stage 3

# Skip PDF rendering
mkcv generate --jd job.txt --kb career.md --no-render
```

**Pipeline stages:**
1. **Analyze JD** -- extract requirements, keywords, and priorities
2. **Select Experience** -- choose the most relevant items from your knowledge base
3. **Tailor Content** -- rewrite bullets with XYZ formula, weave in keywords
4. **Structure YAML** -- produce RenderCV-compatible YAML
5. **Review** -- ATS compliance check with scoring and suggestions

### Generate a Cover Letter

```bash
# From a job description and resume
mkcv cover-letter --jd job.txt --company Acme --position "Senior Engineer"

# Using an existing application directory
mkcv cover-letter --jd job.txt --app-dir applications/acme/senior-engineer/2025-01-15
```

### Render to PDF

```bash
mkcv render resume.yaml
mkcv render resume.yaml --theme classic
mkcv render resume.yaml --format pdf,png,md,html
mkcv render resume.yaml --open    # Open PDF after rendering
```

### Validate Quality

```bash
# Validate a resume YAML (LLM-powered ATS check)
mkcv validate resume.yaml

# Validate against a specific JD for keyword coverage
mkcv validate resume.yaml --jd job.txt

# Validate knowledge base structure (no LLM needed)
mkcv validate --kb knowledge-base/career.md
```

### Browse Themes

```bash
mkcv themes                      # List all available themes
mkcv themes --preview sb2nov     # Detailed theme preview
```

### Workspace Status

```bash
mkcv status                      # Overview of workspace and applications
```

## Configuration

Configuration is resolved in 5 layers (later overrides earlier):

1. **Built-in defaults** -- bundled with the package
2. **Global user config** -- `~/.config/mkcv/settings.toml`
3. **Workspace config** -- `mkcv.toml` in workspace root
4. **Environment variables** -- `MKCV_` prefix
5. **CLI flags** -- applied at runtime

See [`examples/mkcv.toml`](examples/mkcv.toml) for a fully-commented configuration reference.

### Provider Profiles

Use `--profile` to quickly switch provider configurations:

| Profile | Provider | Best For |
|---------|----------|----------|
| `premium` (default) | Anthropic Claude | Highest quality output |
| `budget` | Ollama (local) | Free, no API key needed |

### Per-Stage Configuration

Configure different providers and models for each pipeline stage in `mkcv.toml`:

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

### Environment Variables

Use the `MKCV_` prefix with double underscores for nested keys:

```bash
export MKCV_RENDERING__THEME=classic
export MKCV_PIPELINE__STAGES__ANALYZE__MODEL=claude-sonnet-4-20250514
```

## LLM Providers

| Provider | Setup | Notes |
|----------|-------|-------|
| **Anthropic** | `export ANTHROPIC_API_KEY=sk-ant-...` | Default provider, Claude models |
| **OpenAI** | `export OPENAI_API_KEY=sk-...` | GPT models |
| **Ollama** | [Install Ollama](https://ollama.ai), run `ollama serve` | Free, local, no API key |
| **OpenRouter** | `export OPENROUTER_API_KEY=sk-or-...` | 200+ models via single API key |

[OpenRouter](https://openrouter.ai) is a good choice if you want access to Claude, GPT, Gemini, DeepSeek, and more through a single API key. Set `provider = "openrouter"` in your config and use OpenRouter model identifiers (e.g., `anthropic/claude-sonnet-4`).

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to get started.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Development

For detailed development setup, architecture documentation, and coding conventions, see [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).
