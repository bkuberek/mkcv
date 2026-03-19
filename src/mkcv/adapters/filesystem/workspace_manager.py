"""Filesystem adapter for workspace and application directory management."""

import logging
import re
import shutil
import unicodedata
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import tomli_w

from mkcv.core.exceptions.workspace import WorkspaceError, WorkspaceExistsError
from mkcv.core.models.application_metadata import ApplicationMetadata

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Template constants
# ---------------------------------------------------------------------------

_MKCV_TOML_TEMPLATE: dict[str, Any] = {
    "workspace": {"version": "0.1.0"},
    "paths": {
        "knowledge_base_dir": "knowledge-base",
        "applications_dir": "applications",
        "templates_dir": "templates",
    },
    "naming": {
        "company_slug": True,
        "application_pattern": "{date}-{position}",
    },
    "defaults": {
        "theme": "sb2nov",
        "profile": "premium",
    },
}

_CAREER_MD_TEMPLATE = """\
# {name} -- Career Knowledge Base

## Personal Information

| Field    | Value              |
|----------|--------------------|
| Name     | {name}             |
| Email    |                    |
| Phone    |                    |
| Location |                    |
| LinkedIn |                    |
| GitHub   |                    |
| Website  |                    |

## Languages

- English (native)

## Professional Summary

<!-- 2-3 paragraphs summarizing your career -->

## Technical Skills -- Master List

### Programming Languages
### Frontend
### Backend Frameworks
### AI / ML / LLM
### Databases & Data Stores
### Infrastructure & DevOps

## Career History -- Complete and Detailed

### Company Name -- Job Title
**YYYY-MM to YYYY-MM** | Location

- Achievement bullet using XYZ formula
- Tech stack: Python, FastAPI, PostgreSQL

## Key Achievements

## Strengths

## Passions & Interests
"""

_VOICE_MD_TEMPLATE = """\
# Voice Guidelines

<!-- These guidelines shape how your resume content is written. -->
<!-- Edit to match your personal voice and tone preferences. -->

## Tone
- Direct, not flowery
- Concrete over abstract
- Technical but accessible
- Confident but not arrogant

## Avoid
- "Passionate about..."
- "Leveraged..."
- "Spearheaded..."
- Buzzwords without substance

## Prefer
- Specific metrics and outcomes
- Active voice
- Clear cause-and-effect
"""

_GITIGNORE_TEMPLATE = """\
# mkcv workspace ignores
.mkcv/
*.pdf
*.png

# OS files
.DS_Store
Thumbs.db
"""

_EXAMPLE_THEME_TEMPLATE = """\
# Example custom theme for mkcv
# Rename this file to use it: mv example.yaml mytheme.yaml
#
# Custom themes extend a built-in RenderCV theme with property overrides.
# Available base themes: classic, engineeringclassic, engineeringresumes,
#                        moderncv, sb2nov
#
# applies_to controls which documents use this theme:
#   "all" (default) - both resumes and cover letters
#   "resume"        - resumes only
#   "cover_letter"  - cover letters only
#
# To use: mkcv generate --theme mytheme

name: example
extends: classic
description: "Example custom theme"
applies_to: all
overrides:
  # font: "Charter"
  # font_size: "11pt"
  # page_size: "a4paper"
  # primary_color: "004080"
"""


def _build_readme() -> str:
    """Generate the workspace README from current mkcv state.

    Pulls version, supported providers, and registered CLI commands
    so the README always matches the installed mkcv version.
    """
    from mkcv import __version__
    from mkcv.adapters.factory import _PROVIDER_ENV_KEYS

    # Build credentials block from actual provider registry
    provider_hints: dict[str, str] = {
        "anthropic": "# Anthropic (recommended)\nexport ANTHROPIC_API_KEY=sk-ant-...",
        "openai": "# OpenAI\nexport OPENAI_API_KEY=sk-...",
        "openrouter": (
            "# OpenRouter (access Claude, GPT, Gemini, DeepSeek, etc. "
            "with one key)\nexport OPENROUTER_API_KEY=sk-or-..."
        ),
        "ollama": "# Ollama (free, local — no key needed)\n# Just run: ollama serve",
    }
    credential_lines = "\n\n".join(
        provider_hints.get(p, f"# {p}\nexport {env}=...")
        for p, env in _PROVIDER_ENV_KEYS.items()
        if p != "ollama"
    )
    # Ollama always last (no key needed)
    if "ollama" in _PROVIDER_ENV_KEYS:
        credential_lines += "\n\n" + provider_hints["ollama"]

    # Build command list from actual CLI registrations
    try:
        from mkcv.cli.app import app as cli_app

        command_names = sorted(
            name for name, _ in cli_app._commands.items() if not name.startswith("-")
        )
    except Exception:
        command_names = [
            "generate",
            "init",
            "render",
            "status",
            "themes",
            "validate",
        ]

    command_help: dict[str, str] = {
        "generate": "Generate a tailored resume",
        "init": "Initialize a new workspace",
        "render": "Render resume YAML to PDF",
        "status": "Show workspace overview",
        "themes": "List and preview themes",
        "validate": "Check resume or KB quality",
    }
    commands_table = "\n".join(
        f"| `mkcv {name}` | {command_help.get(name, '')} |" for name in command_names
    )

    return f"""\
# My CV Workspace

> Generated by [mkcv](https://github.com/bkuberek/mkcv) v{__version__}

This is an mkcv workspace for generating ATS-compliant resumes tailored
to specific job applications.

## Setup

### 1. Install mkcv

```bash
pip install mkcv
# or
uv tool install mkcv
```

### 2. Set up an API key

You need at least one AI provider. Pick one:

```bash
{credential_lines}
```

Add the export to your shell profile (`~/.zshrc` or `~/.bashrc`) so it persists.

### 3. Fill in your knowledge base

Edit `knowledge-base/career.md` with your complete career history. The more
detail you include (metrics, technologies, outcomes), the better the AI can
tailor your resume.

## Commands

| Command | Description |
|---------|-------------|
{commands_table}

## Usage

### Generate a resume

```bash
# From a file
mkcv generate --jd path/to/job_description.txt \\
  --company "Company Name" --position "Job Title"

# From a URL
mkcv generate --jd https://example.com/job-posting \\
  --company "Company Name" --position "Job Title"

# From clipboard (macOS)
pbpaste | mkcv generate --jd - \\
  --company "Company Name" --position "Job Title"

# Generic resume (no JD needed)
mkcv generate --kb career.md
mkcv generate --kb career.md --target "Senior Software Engineer"
```

This creates `applications/{{company}}/{{date-position}}/` with your tailored
resume YAML and rendered PDF.

### Other commands

```bash
mkcv status                        # See workspace overview
mkcv render resume.yaml            # Re-render a resume to PDF
mkcv validate resume.yaml          # Check resume quality
mkcv validate resume.yaml --jd job.txt  # Check keyword coverage
mkcv validate --kb knowledge-base/career.md  # Check KB structure
mkcv themes                        # List available themes
mkcv themes --preview sb2nov       # Preview a theme
```

### Provider profiles

```bash
mkcv generate --jd job.txt --profile budget   # Ollama (free, local)
mkcv generate --jd job.txt --profile premium  # Anthropic Claude (best quality)
```

### Using OpenRouter

To use [OpenRouter](https://openrouter.ai), set the API key and configure
your `mkcv.toml`:

```toml
[pipeline.stages.analyze]
provider = "openrouter"
model = "anthropic/claude-sonnet-4"

[pipeline.stages.review]
provider = "openrouter"
model = "anthropic/claude-sonnet-4"
```

## Workspace Structure

```
.
├── mkcv.toml                     # Workspace configuration
├── knowledge-base/
│   ├── career.md                 # Your career history
│   └── voice.md                  # Writing tone preferences
├── applications/                 # Targeted resumes (with JD)
│   └── {{company}}/
│       └── {{date-position}}/
│           ├── application.toml  # Application metadata
│           ├── jd.txt            # Job description
│           ├── resume.yaml       # Generated resume
│           └── resume.pdf        # Rendered PDF
├── resumes/                      # Generic resumes (no JD)
│   └── {{date}}-{{target}}/
│       ├── resume.yaml
│       └── resume.pdf
├── themes/                       # Custom theme definitions
│   └── example.yaml              # Example custom theme
└── templates/                    # Custom prompt overrides
```

## Tips

- **Keep your KB detailed** — include every role, project, and metric. The AI
  selects what's relevant for each job.
- **Run `mkcv validate --kb career.md`** to check your KB for missing sections.
- **Use `--interactive`** to review and stop after any pipeline stage.
- **Re-run from a stage** with `--from-stage 3` to iterate on tailoring without
  re-analyzing the JD.
- **Generic resume** — omit `--jd` to produce a general-purpose resume.
"""


def _write_if_missing(path: Path, content: str) -> None:
    """Write content to a file only if it does not already exist.

    This prevents accidental data loss when re-initializing a workspace.
    """
    if path.exists():
        logger.info("Skipped (already exists): %s", path)
        return
    path.write_text(content, encoding="utf-8")
    logger.info("Created %s", path)


_MAX_SLUG_LENGTH = 64


def _next_version(parent: Path, base_name: str) -> int:
    """Find the next version number for a directory with the given base name.

    Scans ``parent`` for directories matching ``{base_name}-v*`` and returns
    one higher than the highest existing version.  Returns 1 when no match
    is found.

    Args:
        parent: Directory to scan for existing versioned dirs.
        base_name: The prefix before ``-v{N}``.

    Returns:
        The next version number (>= 1).
    """
    if not parent.is_dir():
        return 1

    pattern = re.compile(re.escape(base_name) + r"-v(\d+)$")
    max_version = 0
    for entry in parent.iterdir():
        if entry.is_dir():
            match = pattern.match(entry.name)
            if match:
                max_version = max(max_version, int(match.group(1)))

    return max_version + 1


class WorkspaceManager:
    """Manages workspace filesystem operations.

    Handles creating workspace structures, application directories,
    and generating configuration files.
    """

    def create_workspace(self, path: Path) -> Path:
        """Create a new mkcv workspace at the given path.

        Creates (only if they don't already exist):
            - mkcv.toml (workspace config)
            - knowledge-base/ (with career.md and voice.md templates)
            - applications/ (empty)
            - templates/ (empty)
            - .gitignore
            - README.md

        Existing files are NEVER overwritten. Only missing files are
        created. This makes it safe to re-run on an existing workspace
        (e.g. after deleting mkcv.toml to reset config).

        Args:
            path: Directory to initialize.

        Returns:
            Path to the workspace root.

        Raises:
            WorkspaceExistsError: If mkcv.toml already exists.
            WorkspaceError: If existing user data would be at risk.
        """
        workspace_root = path.resolve()
        toml_path = workspace_root / "mkcv.toml"

        if toml_path.exists():
            raise WorkspaceExistsError(f"Workspace already exists: {toml_path}")

        # Safety check: detect existing workspace content even without
        # mkcv.toml. Warn but proceed — we only create missing files.
        workspace_markers = (
            "knowledge-base",
            "applications",
            "resumes",
            "templates",
            "themes",
        )
        has_existing_content = any(
            (workspace_root / marker).is_dir() for marker in workspace_markers
        )
        if has_existing_content:
            logger.warning(
                "Directory %s contains existing workspace content. "
                "Only missing files will be created; nothing will be overwritten.",
                workspace_root,
            )

        # Create root directory
        try:
            workspace_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise WorkspaceError(
                f"Cannot create workspace directory: {workspace_root}: {exc}"
            ) from exc

        # Write mkcv.toml using tomli_w
        with toml_path.open("wb") as f:
            tomli_w.dump(_MKCV_TOML_TEMPLATE, f)
        logger.info("Created %s", toml_path)

        # Create directories
        for dir_name in workspace_markers:
            dir_path = workspace_root / dir_name
            dir_path.mkdir(exist_ok=True)
            logger.debug("Ensured directory: %s", dir_path)

        # Create template files — NEVER overwrite existing files
        _write_if_missing(
            workspace_root / "knowledge-base" / "career.md",
            _CAREER_MD_TEMPLATE.format(name="Your Name"),
        )
        _write_if_missing(
            workspace_root / "knowledge-base" / "voice.md",
            _VOICE_MD_TEMPLATE,
        )
        _write_if_missing(
            workspace_root / ".gitignore",
            _GITIGNORE_TEMPLATE,
        )
        _write_if_missing(
            workspace_root / "themes" / "example.yaml",
            _EXAMPLE_THEME_TEMPLATE,
        )
        _write_if_missing(
            workspace_root / "README.md",
            _build_readme(),
        )

        return workspace_root

    def create_application(
        self,
        workspace_root: Path,
        company: str,
        position: str,
        jd_source: Path,
        *,
        preset_name: str = "standard",
        url: str | None = None,
    ) -> Path:
        """Create an application directory within the workspace.

        Creates: applications/{company_slug}/{YYYY-MM}-{position}-{preset}-v{N}/
        With: application.toml, jd.txt (copied), .mkcv/

        Version numbering increments automatically: v1, v2, v3, etc.

        Args:
            workspace_root: Workspace root path.
            company: Company name (will be slugified).
            position: Position title (will be slugified).
            jd_source: Path to the JD file (will be copied in).
            preset_name: Preset name included in directory naming.
            url: Optional job posting URL.

        Returns:
            Path to the created application directory.
        """
        app_date = date.today()
        date_str = app_date.strftime("%Y-%m")

        company_slug = self.slugify(company)
        position_slug = self.slugify(position)

        base_name = f"{date_str}-{position_slug}-{preset_name}"

        # Build full path: applications/{company_slug}/{base}-v{N}/
        apps_base = self.get_applications_dir(workspace_root)
        parent_dir = apps_base / company_slug
        version = _next_version(parent_dir, base_name)
        app_dir = parent_dir / f"{base_name}-v{version}"

        # Create directories
        app_dir.mkdir(parents=True, exist_ok=True)
        (app_dir / ".mkcv").mkdir(exist_ok=True)

        # Copy JD file
        shutil.copy2(jd_source, app_dir / "jd.txt")
        logger.info("Placed JD: %s", app_dir / "jd.txt")

        # Generate application.toml
        metadata = ApplicationMetadata(
            company=company,
            position=position,
            date=app_date,
            status="draft",
            url=url,
            created_at=datetime.now(tz=UTC),
        )
        self._write_application_toml(app_dir, metadata)

        logger.info("Created application: %s", app_dir)
        return app_dir

    def slugify(self, text: str) -> str:
        """Convert text to a filesystem-safe slug.

        Lowercase, hyphens for spaces/special chars, no consecutive hyphens.
        Unicode is NFKD-normalized and ASCII-transliterated.

        Args:
            text: Raw text to slugify.

        Returns:
            Filesystem-safe slug string.
        """
        # Normalize unicode
        text = unicodedata.normalize("NFKD", text)
        # Remove non-ASCII (accents become separate chars after NFKD)
        text = text.encode("ascii", "ignore").decode("ascii")
        # Lowercase
        text = text.lower()
        # Replace non-alphanumeric with hyphens
        text = re.sub(r"[^a-z0-9]+", "-", text)
        # Collapse consecutive hyphens
        text = re.sub(r"-{2,}", "-", text)
        # Strip leading/trailing hyphens
        text = text.strip("-")
        # Truncate
        if len(text) > _MAX_SLUG_LENGTH:
            text = text[:_MAX_SLUG_LENGTH].rstrip("-")
        return text

    def get_applications_dir(self, workspace_root: Path) -> Path:
        """Get the applications directory for a workspace.

        Args:
            workspace_root: Workspace root path.

        Returns:
            Path to the applications directory.
        """
        return workspace_root / "applications"

    def list_applications(self, workspace_root: Path) -> list[Path]:
        """List all application directories in the workspace.

        An application directory is identified by containing an
        ``application.toml`` file.

        Args:
            workspace_root: Workspace root path.

        Returns:
            Sorted list of application directory paths.
        """
        apps_dir = self.get_applications_dir(workspace_root)
        if not apps_dir.is_dir():
            return []

        return sorted(
            app_toml.parent for app_toml in apps_dir.rglob("application.toml")
        )

    # ------------------------------------------------------------------
    # Version resolution
    # ------------------------------------------------------------------

    def find_latest_application(
        self,
        workspace_root: Path,
        *,
        company: str | None = None,
    ) -> Path | None:
        """Find the most recent application directory.

        When ``company`` is provided, only that company's subdirectory
        is searched.  Otherwise, all companies are considered.

        Directories are identified by containing ``application.toml``
        and are sorted lexicographically (the ``YYYY-MM-`` prefix
        ensures chronological order).

        Args:
            workspace_root: Workspace root path.
            company: Optional company name filter (will be slugified).

        Returns:
            Path to the latest application directory, or None.
        """
        all_apps = self.list_applications(workspace_root)
        if not all_apps:
            return None

        if company is not None:
            company_slug = self.slugify(company)
            apps_dir = self.get_applications_dir(workspace_root)
            company_dir = apps_dir / company_slug
            all_apps = [app for app in all_apps if app.parent == company_dir]

        return all_apps[-1] if all_apps else None

    def resolve_resume_path(self, app_dir: Path) -> Path | None:
        """Find resume.yaml within an application directory.

        Args:
            app_dir: Path to the application directory.

        Returns:
            Path to resume.yaml if it exists, or None.
        """
        resume = app_dir / "resume.yaml"
        return resume if resume.is_file() else None

    def find_latest_resume(self, workspace_root: Path) -> Path | None:
        """Find the latest generic resume from the resumes/ directory.

        Scans ``resumes/`` for versioned directories containing
        ``resume.yaml``, sorted lexicographically, and returns
        the resume.yaml from the last (most recent) directory.

        Args:
            workspace_root: Workspace root path.

        Returns:
            Path to the latest resume.yaml, or None.
        """
        resumes_dir = workspace_root / "resumes"
        if not resumes_dir.is_dir():
            return None

        resume_dirs = sorted(
            d
            for d in resumes_dir.iterdir()
            if d.is_dir() and (d / "resume.yaml").is_file()
        )
        if not resume_dirs:
            return None

        return resume_dirs[-1] / "resume.yaml"

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _write_application_toml(
        self,
        app_dir: Path,
        metadata: ApplicationMetadata,
    ) -> None:
        """Write application.toml from metadata."""
        data: dict[str, Any] = {
            "application": {
                "company": metadata.company,
                "position": metadata.position,
                "date": metadata.date.isoformat(),
                "status": metadata.status,
                "url": metadata.url or "",
                "created_at": metadata.created_at.isoformat(),
            },
        }
        toml_path = app_dir / "application.toml"
        with toml_path.open("wb") as f:
            tomli_w.dump(data, f)
        logger.debug("Wrote %s", toml_path)
