"""Filesystem adapter for workspace and application directory management."""

import logging
import re
import shutil
import unicodedata
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import tomli_w
from ruamel.yaml import YAML

from mkcv.core.exceptions.workspace import WorkspaceError, WorkspaceExistsError
from mkcv.core.models.application_metadata import ApplicationMetadata
from mkcv.core.models.jd_document import JDDocument

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Template constants
# ---------------------------------------------------------------------------

_MKCV_TOML_TEMPLATE = """\
# mkcv workspace configuration
# Docs: https://github.com/bkuberek/mkcv

[workspace]
version = "0.1.0"

[paths]
knowledge_base_dir = "knowledge-base"
applications_dir = "applications"
templates_dir = "templates"

[naming]
company_slug = true
application_pattern = "{company}/{position}/{date}"

[defaults]
theme = "sb2nov"
profile = "premium"

# ── Rendering ───────────────────────────────────────────────────────
# Theme controls the visual design of your resume. Run `mkcv themes`
# to see all available themes and `mkcv themes --preview <name>` to
# preview one.
#
# [rendering]
# theme = "sb2nov"           # classic, engineeringresumes, moderncv, ...
# font = "SourceSansPro"     # any system font
# font_size = "10pt"
# page_size = "letterpaper"  # letterpaper or a4paper
#
# [rendering.overrides]
# primary_color = "003366"   # hex color without #

# ── Pipeline ────────────────────────────────────────────────────────
# Override AI providers per-stage. Most users don't need this — the
# defaults use Anthropic Claude. Uncomment to customise.
#
# [pipeline.stages.analyze]
# provider = "openrouter"
# model = "anthropic/claude-sonnet-4"
# temperature = 0.2
"""

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
> Regenerate this file: `mkcv init --update-readme`

This is an mkcv workspace for generating ATS-compliant resumes and cover
letters tailored to specific job applications.

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

### Generate with a cover letter

```bash
mkcv generate --jd job.txt --company Acme --position "SWE" --cover-letter
```

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

## Themes

Themes control the **visual design** of your resume — fonts, colours, margins,
and page layout. They do NOT affect AI content generation.

### Built-in themes

mkcv includes 5 themes from RenderCV:

| Theme | Description |
|-------|-------------|
| `sb2nov` | Clean single-column (default) |
| `classic` | Traditional academic style |
| `moderncv` | Two-column European style |
| `engineeringresumes` | Dense, optimised for ATS parsing |
| `engineeringclassic` | Engineering with classic typography |

Run `mkcv themes` to see all themes or `mkcv themes --preview <name>` for
a detailed preview with colours and fonts.

### Choosing a theme

```bash
# Set the default in mkcv.toml
# [defaults]
# theme = "classic"

# Or pass it per-command
mkcv generate --jd job.txt --theme classic
mkcv render resume.yaml --theme moderncv
```

### Compare themes side-by-side

Render the same resume across multiple themes in one command:

```bash
mkcv render resume.yaml --theme sb2nov,classic,moderncv
mkcv render resume.yaml --theme all        # every available theme
```

Each theme's output goes to `renders/<theme>/` so nothing is overwritten.

### Custom themes

Create your own themes in the `themes/` directory. See
`themes/example.yaml` for the format:

```yaml
name: mytheme
extends: classic
description: "My custom blue theme"
applies_to: all          # all | resume | cover_letter
overrides:
  font: "Charter"
  font_size: "11pt"
  page_size: "a4paper"   # a4paper or letterpaper
  primary_color: "004080"
```

Then use it like any built-in theme:

```bash
mkcv generate --jd job.txt --theme mytheme
```

Custom themes appear in `mkcv themes` with a `[custom]` badge.

## Templates

Templates are **prompt instructions** (Jinja2 `.j2` files) that control how the
AI generates resume content at each pipeline stage. They are separate from themes.

| Concept    | What it controls       | Where it lives   |
|------------|------------------------|-------------------|
| **Theme**  | Visual design (PDF)    | `themes/`         |
| **Template** | AI content generation | `templates/`      |

Most users never need to touch templates. If you want to customize AI behavior
(e.g. change the tone, add instructions for a specific industry), copy a
built-in template to `templates/` and edit it. mkcv will use your version
instead of the built-in one.

To see which templates are available, check the
[built-in prompts](https://github.com/bkuberek/mkcv/tree/main/src/mkcv/prompts).

## Configuration

All configuration lives in `mkcv.toml`. Settings are optional — sensible
defaults are built in. The file is pre-populated with the most common options;
uncomment what you need.

### Rendering (fonts, colours, page size)

```toml
[rendering]
theme = "classic"
font = "Charter"
font_size = "11pt"
page_size = "a4paper"          # a4paper or letterpaper

[rendering.overrides]
primary_color = "004080"       # hex colour without #
```

These apply to all resumes by default. You can override per-command with
`--theme`.

### Pipeline (AI provider per stage)

```toml
[pipeline.stages.analyze]
provider = "anthropic"
model = "claude-sonnet-4-20250514"
temperature = 0.2

[pipeline.stages.review]
provider = "openrouter"
model = "anthropic/claude-sonnet-4"
```

### Cover letter

```toml
[cover_letter]
auto_render = true

[cover_letter.stages.generate]
provider = "anthropic"
model = "claude-sonnet-4-20250514"
temperature = 0.6
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
│       └── {{position}}/
│           └── {{YYYY-MM-DD}}/
│               ├── application.toml  # Application metadata
│               ├── jd.md             # Job description (with YAML frontmatter)
│               ├── resumes/          # Versioned resume outputs
│               │   ├── v1/
│               │   │   ├── resume.yaml
│               │   │   ├── resume.pdf
│               │   │   └── .mkcv/    # Pipeline artifacts
│               │   └── v2/           # Re-run creates a new version
│               │       └── ...
│               └── cover-letter/     # Versioned cover letter outputs
│                   └── v1/
│                       ├── cover_letter.md
│                       ├── cover_letter.pdf
│                       └── .mkcv/
├── resumes/                      # Generic resumes (no JD)
│   └── {{date}}-{{target}}/
│       ├── resume.yaml
│       └── resume.pdf
├── themes/                       # Custom theme definitions
│   └── example.yaml              # Starter — rename and edit
├── templates/                    # Custom prompt overrides
└── README.md                     # This file
```

## Tips

- **Keep your KB detailed** — include every role, project, and metric. The AI
  selects what's relevant for each job.
- **Run `mkcv validate --kb career.md`** to check your KB for missing sections.
- **Use `--interactive`** to review and stop after any pipeline stage.
- **Re-run from a stage** with `--from-stage 3` to iterate on tailoring without
  re-analyzing the JD.
- **Generic resume** — omit `--jd` to produce a general-purpose resume.
- **Compare themes** — `mkcv render resume.yaml --theme all` renders every theme.
- **Update this README** — `mkcv init --update-readme` regenerates it with the
  latest mkcv version and commands.
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

        # Write mkcv.toml with commented configuration guidance
        toml_path.write_text(_MKCV_TOML_TEMPLATE, encoding="utf-8")
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

    def update_readme(self, workspace_root: Path) -> bool:
        """Regenerate the workspace README.md with the latest mkcv content.

        Args:
            workspace_root: Path to the workspace root.

        Returns:
            True if the README was updated, False if it was already current.
        """
        readme_path = workspace_root.resolve() / "README.md"
        new_content = _build_readme()

        if (
            readme_path.is_file()
            and readme_path.read_text(encoding="utf-8") == new_content
        ):
            return False

        readme_path.write_text(new_content, encoding="utf-8")
        logger.info("Updated %s", readme_path)
        return True

    def create_application(
        self,
        workspace_root: Path,
        company: str,
        position: str,
        jd_source: Path | str,
        *,
        preset_name: str = "standard",
        url: str | None = None,
        jd_document: JDDocument | None = None,
    ) -> Path:
        """Create an application directory within the workspace.

        Creates: applications/{company_slug}/{position_slug}/{YYYY-MM-DD}/
        With: application.toml, jd.md, resumes/

        Args:
            workspace_root: Workspace root path.
            company: Company name (will be slugified).
            position: Position title (will be slugified).
            jd_source: Path to JD file (copied in) or raw text.
            preset_name: Preset name stored in metadata.
            url: Optional job posting URL.
            jd_document: Optional parsed JD for frontmatter writing.

        Returns:
            Path to the created application directory.
        """
        today = date.today()
        app_dir = self._build_application_path(workspace_root, company, position, today)

        # Create directory structure
        app_dir.mkdir(parents=True, exist_ok=True)
        (app_dir / "resumes").mkdir(exist_ok=True)

        # Write JD file (as markdown with frontmatter if possible)
        if jd_document is not None:
            self._write_jd_markdown(jd_document, app_dir, url=url)
        elif isinstance(jd_source, Path):
            shutil.copy2(jd_source, app_dir / "jd.md")
        else:
            (app_dir / "jd.md").write_text(jd_source, encoding="utf-8")

        # Build and write application.toml
        metadata = self._build_application_metadata(
            company=company,
            position=position,
            app_date=today,
            url=url,
            preset_name=preset_name,
            jd_document=jd_document,
        )
        self._write_application_toml(app_dir, metadata)

        logger.info("Created application: %s", app_dir)
        return app_dir

    def _build_application_path(
        self,
        workspace_root: Path,
        company: str,
        position: str,
        app_date: date,
    ) -> Path:
        """Build the application directory path.

        Layout: applications/{company_slug}/{position_slug}/{YYYY-MM-DD}/

        Args:
            workspace_root: Workspace root path.
            company: Company name (will be slugified).
            position: Position title (will be slugified).
            app_date: Application date.

        Returns:
            Path to the application directory.

        Raises:
            WorkspaceError: If the directory already exists with an application.toml.
        """
        apps_base = self.get_applications_dir(workspace_root)
        company_slug = self.slugify(company)
        position_slug = self.slugify(position)
        date_str = app_date.strftime("%Y-%m-%d")

        app_dir = apps_base / company_slug / position_slug / date_str

        if app_dir.exists() and (app_dir / "application.toml").is_file():
            raise WorkspaceError(
                f"Application directory already exists: {app_dir}. "
                "Use the existing directory or choose a different date."
            )

        return app_dir

    def _build_application_metadata(
        self,
        *,
        company: str,
        position: str,
        app_date: date,
        url: str | None,
        preset_name: str,
        jd_document: JDDocument | None,
    ) -> ApplicationMetadata:
        """Build ApplicationMetadata, enriching from JD frontmatter."""
        fm = jd_document.metadata if jd_document else None

        return ApplicationMetadata(
            company=company,
            position=position,
            date=app_date,
            status="draft",
            url=url or (fm.url if fm else None),
            created_at=datetime.now(tz=UTC),
            preset=preset_name,
            compensation=fm.compensation if fm else None,
            location=fm.location if fm else None,
            workplace=fm.workplace if fm else None,
            source=fm.source if fm else None,
            tags=fm.tags if fm else [],
        )

    def _write_jd_markdown(
        self,
        jd_document: JDDocument,
        app_dir: Path,
        *,
        url: str | None = None,
    ) -> Path:
        """Write a JD document as markdown with YAML frontmatter.

        Args:
            jd_document: Parsed JD document.
            app_dir: Application directory to write into.
            url: Optional URL to include in frontmatter.

        Returns:
            Path to the written jd.md file.
        """
        lines: list[str] = []

        metadata = jd_document.metadata
        if metadata is not None:
            fm_dict: dict[str, object] = {}
            if metadata.company:
                fm_dict["company"] = metadata.company
            if metadata.position:
                fm_dict["position"] = metadata.position
            if url or metadata.url:
                fm_dict["url"] = url or metadata.url
            if metadata.location:
                fm_dict["location"] = metadata.location
            if metadata.workplace:
                fm_dict["workplace"] = metadata.workplace
            if metadata.compensation:
                comp = metadata.compensation.model_dump(exclude_none=True)
                if comp:
                    fm_dict["compensation"] = comp
            if metadata.posted_date:
                fm_dict["posted_date"] = metadata.posted_date.isoformat()
            if metadata.source:
                fm_dict["source"] = metadata.source
            if metadata.tags:
                fm_dict["tags"] = metadata.tags

            if fm_dict:
                from io import StringIO

                yaml_engine = YAML()
                yaml_engine.default_flow_style = False
                stream = StringIO()
                yaml_engine.dump(fm_dict, stream)
                yaml_str = stream.getvalue().strip()

                lines.append("---")
                lines.append(yaml_str)
                lines.append("---")
                lines.append("")

        lines.append(jd_document.body)
        lines.append("")  # trailing newline

        jd_path = app_dir / "jd.md"
        jd_path.write_text("\n".join(lines), encoding="utf-8")
        return jd_path

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
        ``application.toml`` file. Results sorted by created_at timestamp.

        Args:
            workspace_root: Workspace root path.

        Returns:
            Sorted list of application directory paths.
        """
        apps_dir = self.get_applications_dir(workspace_root)
        if not apps_dir.is_dir():
            return []

        apps = [app_toml.parent for app_toml in apps_dir.rglob("application.toml")]

        return sorted(apps, key=self._app_sort_key)

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

        Sorts by created_at timestamp from application.toml, falling back
        to lexicographic order for entries without timestamps.

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
            all_apps = [
                app
                for app in all_apps
                if self._matches_company(app, apps_dir, company_slug)
            ]

        if not all_apps:
            return None

        return max(all_apps, key=self._app_sort_key)

    def resolve_resume_path(self, app_dir: Path) -> Path | None:
        """Find the latest resume.yaml within an application directory.

        Checks new layout (resumes/v{latest}/resume.yaml) first,
        then falls back to old layout (app_dir/resume.yaml).

        Args:
            app_dir: Path to the application directory.

        Returns:
            Path to resume.yaml if it exists, or None.
        """
        # New layout: find latest version in resumes/
        resumes_dir = app_dir / "resumes"
        if resumes_dir.is_dir():
            latest = self._find_latest_version(resumes_dir)
            if latest is not None:
                resume = latest / "resume.yaml"
                if resume.is_file():
                    return resume

        # Old layout fallback
        resume = app_dir / "resume.yaml"
        return resume if resume.is_file() else None

    def resolve_cover_letter_path(self, app_dir: Path) -> Path | None:
        """Find the latest cover letter in an application directory.

        Checks new layout (cover-letter/v{latest}/) first,
        then falls back to old layout (app_dir/cover_letter.*).

        Args:
            app_dir: Path to the application directory.

        Returns:
            Path to cover_letter.md or .pdf if it exists, or None.
        """
        # New layout
        cl_dir = app_dir / "cover-letter"
        if cl_dir.is_dir():
            latest = self._find_latest_version(cl_dir)
            if latest is not None:
                for name in ("cover_letter.md", "cover_letter.pdf"):
                    path = latest / name
                    if path.is_file():
                        return path

        # Old layout fallback
        for name in ("cover_letter.md", "cover_letter.pdf"):
            path = app_dir / name
            if path.is_file():
                return path

        return None

    def create_output_version(
        self,
        app_dir: Path,
        output_type: str,
    ) -> Path:
        """Create a new versioned output directory within an application.

        Args:
            app_dir: Application directory path.
            output_type: One of ``"resumes"``, ``"cover-letter"``.

        Returns:
            Path to the new version directory (e.g., app_dir/resumes/v2/).
        """
        parent = app_dir / output_type
        parent.mkdir(parents=True, exist_ok=True)

        version = self._next_version_subfolder(parent)
        version_dir = parent / f"v{version}"
        version_dir.mkdir()
        (version_dir / ".mkcv").mkdir()

        return version_dir

    def _detect_layout(self, app_dir: Path) -> str:
        """Detect whether an application uses the old or new layout.

        Args:
            app_dir: Directory containing application.toml.

        Returns:
            ``"v1"`` for old layout, ``"v2"`` for new layout.
        """
        if (app_dir / "resumes").is_dir() or (app_dir / "jd.md").is_file():
            return "v2"
        return "v1"

    def _matches_company(
        self,
        app_dir: Path,
        apps_dir: Path,
        company_slug: str,
    ) -> bool:
        """Check if an application belongs to a company.

        Works for both v1 (company is direct parent) and v2
        (company is the first segment after applications/).
        """
        try:
            relative = app_dir.relative_to(apps_dir)
            return relative.parts[0] == company_slug
        except (ValueError, IndexError):
            return False

    @staticmethod
    def _app_sort_key(app_dir: Path) -> tuple[str, str]:
        """Build a sort key for application directories.

        Tries to read created_at from application.toml.
        Falls back to directory name for lexicographic sort.
        """
        import tomllib

        toml_path = app_dir / "application.toml"
        if toml_path.is_file():
            try:
                with toml_path.open("rb") as f:
                    data = tomllib.load(f)
                created = data.get("application", {}).get("created_at", "")
                if created:
                    return (str(created), str(app_dir))
            except Exception:
                pass
        return ("", str(app_dir))

    @staticmethod
    def _next_version_subfolder(parent: Path) -> int:
        """Find the next version number in a directory.

        Scans for directories matching v{N} and returns N+1.
        Returns 1 when no versions exist.
        """
        if not parent.is_dir():
            return 1

        pattern = re.compile(r"^v(\d+)$")
        max_version = 0
        for entry in parent.iterdir():
            if entry.is_dir():
                match = pattern.match(entry.name)
                if match:
                    max_version = max(max_version, int(match.group(1)))

        return max_version + 1

    def _find_latest_version(self, parent: Path) -> Path | None:
        """Find the highest-numbered v{N} directory.

        Args:
            parent: Directory containing v{N} subdirectories.

        Returns:
            Path to the latest version directory, or None.
        """
        pattern = re.compile(r"^v(\d+)$")
        versions: list[tuple[int, Path]] = []
        for entry in parent.iterdir():
            if entry.is_dir():
                match = pattern.match(entry.name)
                if match:
                    versions.append((int(match.group(1)), entry))

        if not versions:
            return None

        versions.sort(key=lambda x: x[0])
        return versions[-1][1]

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
                "preset": metadata.preset or "",
                "location": metadata.location or "",
                "workplace": metadata.workplace or "",
                "source": metadata.source or "",
                "tags": metadata.tags,
                "notes": metadata.notes,
            },
        }

        # Add compensation sub-table if present
        if metadata.compensation is not None:
            comp = metadata.compensation.model_dump(exclude_none=True)
            if comp:
                data["application"]["compensation"] = comp

        toml_path = app_dir / "application.toml"
        with toml_path.open("wb") as f:
            tomli_w.dump(data, f)
        logger.debug("Wrote %s", toml_path)
