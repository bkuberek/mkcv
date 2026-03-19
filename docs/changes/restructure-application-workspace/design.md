# Technical Design: Restructure Application Workspace

## Overview

Restructure the application directory layout from a flat, version-in-dirname
scheme to a hierarchical structure that separates position, date, and output
type. This enables multiple output types (resumes, cover letters, interview
prep) per application, per-output versioning, richer JD metadata via YAML
frontmatter, and stable paths that don't encode volatile details like preset.

### Current Layout
```
applications/{company}/{YYYY-MM}-{position}-{preset}-v{N}/
  ├── application.toml
  ├── jd.txt
  ├── resume.yaml, resume.pdf
  ├── cover_letter.txt, cover_letter.md, cover_letter.pdf
  └── .mkcv/
```

### New Layout
```
applications/{company}/{position}/{YYYY-MM-DD}/
  ├── application.toml          # enriched metadata
  ├── jd.md                     # markdown + YAML frontmatter
  ├── resumes/v{N}/             # per-version resume output
  │   ├── resume.yaml
  │   ├── resume.pdf
  │   └── .mkcv/                # pipeline artifacts for this version
  ├── cover-letter/v{N}/        # per-version cover letter
  │   ├── cover_letter.md
  │   ├── cover_letter.pdf
  │   └── .mkcv/
  ├── interview-prep/           # future
  └── study-guides/             # future
```

---

## 1. Architecture Overview

### Layers Affected

| Layer | Impact | Files |
|-------|--------|-------|
| **Core Models** | New models (JDFrontmatter, Compensation, JDDocument, RunMetadata); modified ApplicationMetadata, WorkspaceConfig | `src/mkcv/core/models/` |
| **Core Ports** | Extended WorkspacePort protocol with new method signatures | `src/mkcv/core/ports/workspace.py` |
| **Core Services** | Modified JD reader, workspace service, pipeline (output_dir threading); new migration service | `src/mkcv/core/services/` |
| **Adapters** | Major rewrite of WorkspaceManager; minor ArtifactStore updates | `src/mkcv/adapters/filesystem/` |
| **CLI** | Updated generate, cover-letter, status commands; new migrate command | `src/mkcv/cli/commands/` |
| **Factory** | Wire MigrationService | `src/mkcv/adapters/factory.py` |

### Module Dependency Diagram

```
CLI layer
  ├── generate.py ──────────┬── create_pipeline_service()
  │                         ├── create_workspace_service()
  │                         └── jd_reader.read_jd() → JDDocument
  ├── cover_letter.py ──────┬── create_cover_letter_service()
  │                         └── create_workspace_service()
  ├── status.py ────────────── create_workspace_service()
  └── migrate.py (NEW) ────── create_migration_service()

Core Services
  ├── workspace.py ─────────── WorkspacePort (protocol)
  ├── pipeline.py ──────────── ArtifactStorePort, LLMPort, PromptLoaderPort
  ├── cover_letter.py ──────── ArtifactStorePort, LLMPort, CoverLetterRendererPort
  └── jd_reader.py ─────────── (no port; pure function returning JDDocument)

Adapters
  ├── WorkspaceManager ─────── implements WorkspacePort
  ├── FileSystemArtifactStore ── implements ArtifactStorePort
  └── MigrationService (NEW) ── uses WorkspaceManager
```

### Hexagonal Architecture Compliance

- **All new models** live in `core/models/` — no adapter imports
- **JD parsing** (frontmatter regex + yaml.safe_load) lives in `core/services/jd_reader.py` — uses only stdlib `re` and `yaml` from PyYAML (already a transitive dep via rendercv)
- **WorkspacePort** protocol is extended; concrete implementation stays in `adapters/filesystem/`
- **MigrationService** is a core service that depends on WorkspacePort, not concrete WorkspaceManager

---

## 2. New/Modified Pydantic Models

### 2a. Compensation (NEW)

**File:** `src/mkcv/core/models/compensation.py`

```python
"""Compensation information model."""

from pydantic import BaseModel


class Compensation(BaseModel):
    """Compensation details extracted from a job description.

    All fields are optional strings to handle varied formats
    (e.g., "$150k-$200k", "Competitive", "150000 USD").
    """

    base: str | None = None
    equity: str | None = None
    bonus: str | None = None
    total: str | None = None
```

### 2b. JDFrontmatter (NEW)

**File:** `src/mkcv/core/models/jd_frontmatter.py`

```python
"""JD YAML frontmatter model."""

from datetime import date

from pydantic import BaseModel, Field

from mkcv.core.models.compensation import Compensation


class JDFrontmatter(BaseModel):
    """YAML frontmatter metadata for a job description document.

    Parsed from the `---` delimited header of a jd.md file.
    All fields are optional — a JD can have partial or no frontmatter.
    """

    company: str | None = None
    position: str | None = None
    url: str | None = None
    location: str | None = None
    workplace: str | None = Field(
        default=None,
        description="remote, hybrid, onsite",
    )
    compensation: Compensation | None = None
    posted_date: date | None = None
    source: str | None = Field(
        default=None,
        description="Where the JD was found: linkedin, company-site, etc.",
    )
    tags: list[str] = Field(default_factory=list)
```

### 2c. JDDocument (NEW)

**File:** `src/mkcv/core/models/jd_document.py`

```python
"""Parsed JD document with optional frontmatter."""

from pathlib import Path

from pydantic import BaseModel

from mkcv.core.models.jd_frontmatter import JDFrontmatter


class JDDocument(BaseModel):
    """A job description document with optional structured metadata.

    Represents the result of parsing a JD file that may contain
    YAML frontmatter (jd.md) or be plain text (jd.txt).
    """

    metadata: JDFrontmatter | None = None
    body: str
    source_path: Path | None = None
```

### 2d. ApplicationMetadata (MODIFIED)

**File:** `src/mkcv/core/models/application_metadata.py`

```python
"""Application metadata model (parsed from application.toml)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from mkcv.core.models.compensation import Compensation


class ApplicationMetadata(BaseModel):
    """Metadata about a job application, stored in application.toml."""

    company: str
    position: str
    date: date
    status: Literal[
        "draft", "applied", "interviewing", "offered", "rejected", "withdrawn"
    ] = "draft"
    url: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)

    # --- New fields (v2 layout) ---
    preset: str | None = None
    compensation: Compensation | None = None
    location: str | None = None
    workplace: str | None = None
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
```

All new fields default to `None`/empty, so existing `application.toml` files
parsed from the old layout remain valid without modification.

### 2e. RunMetadata (NEW)

**File:** `src/mkcv/core/models/run_metadata.py`

```python
"""Per-run metadata written alongside versioned outputs."""

from datetime import datetime

from pydantic import BaseModel, Field


class RunMetadata(BaseModel):
    """Metadata for a single generation run (resume or cover letter).

    Written to `.mkcv/run_metadata.json` inside each version directory.
    """

    preset: str
    provider: str
    model: str
    timestamp: datetime = Field(default_factory=datetime.now)
    duration_seconds: float = 0.0
    review_score: int = 0
    total_cost_usd: float = 0.0
```

### 2f. WorkspaceConfig (MODIFIED)

**File:** `src/mkcv/core/models/workspace_config.py`

```python
"""Workspace configuration model (parsed from mkcv.toml)."""

from pydantic import BaseModel, Field


class WorkspacePaths(BaseModel):
    """Path configuration within a workspace."""

    knowledge_base: str = "knowledge-base/career.md"
    applications_dir: str = "applications"
    templates_dir: str = "templates"


class WorkspaceNaming(BaseModel):
    """Naming convention configuration."""

    company_slug: bool = True
    application_pattern: str = "{company}/{position}/{date}"


class WorkspaceDefaults(BaseModel):
    """Default settings for workspace operations."""

    theme: str = "sb2nov"
    profile: str = "premium"


class WorkspaceConfig(BaseModel):
    """Workspace configuration parsed from mkcv.toml."""

    version: str = "0.1.0"
    paths: WorkspacePaths = Field(default_factory=WorkspacePaths)
    naming: WorkspaceNaming = Field(default_factory=WorkspaceNaming)
    defaults: WorkspaceDefaults = Field(default_factory=WorkspaceDefaults)
    voice_guidelines: str = ""
```

The only change is `WorkspaceNaming.application_pattern` default value
from `"{date}-{position}"` to `"{company}/{position}/{date}"`.

---

## 3. JD Reader Design

### 3.1 Frontmatter Parsing

The JD reader gains a new function `parse_jd_document()` that detects and
parses YAML frontmatter from markdown files. The existing `read_jd()` function
is updated to return `JDDocument` instead of `str`.

**Frontmatter regex:**

```python
import re
import yaml

_FRONTMATTER_PATTERN = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n(.*)",
    re.DOTALL,
)
```

This matches:
- `---` at the very start of the file (anchored with `\A`)
- YAML content between the two `---` delimiters
- Everything after the closing `---` is the body

**Parsing function:**

```python
def parse_jd_document(text: str, *, source_path: Path | None = None) -> JDDocument:
    """Parse a JD text that may contain YAML frontmatter.

    If the text starts with `---`, attempts to parse YAML frontmatter.
    On parse failure, treats the entire text as the body (no metadata).
    Plain text without frontmatter returns metadata=None.

    Args:
        text: Raw JD text content.
        source_path: Optional path to the source file.

    Returns:
        JDDocument with parsed metadata (if any) and body text.
    """
```

**Implementation approach:**

```python
def parse_jd_document(text: str, *, source_path: Path | None = None) -> JDDocument:
    match = _FRONTMATTER_PATTERN.match(text)
    if match is None:
        return JDDocument(body=text.strip(), source_path=source_path)

    yaml_str, body = match.group(1), match.group(2)
    try:
        raw = yaml.safe_load(yaml_str)
    except yaml.YAMLError:
        logger.warning(
            "Malformed YAML frontmatter in JD; treating as plain text",
            exc_info=True,
        )
        return JDDocument(body=text.strip(), source_path=source_path)

    if not isinstance(raw, dict):
        return JDDocument(body=text.strip(), source_path=source_path)

    try:
        metadata = JDFrontmatter.model_validate(raw)
    except ValidationError:
        logger.warning(
            "Invalid JD frontmatter fields; ignoring metadata",
            exc_info=True,
        )
        return JDDocument(body=body.strip(), source_path=source_path)

    return JDDocument(
        metadata=metadata,
        body=body.strip(),
        source_path=source_path,
    )
```

### 3.2 Updated read_jd Signature

```python
def read_jd(source: str) -> JDDocument:
    """Resolve a JD source string to a JDDocument.

    Synchronous entry point. For URLs, internally runs the async
    fetch via asyncio.run.

    Args:
        source: A file path, HTTP/HTTPS URL, or "-"/"" for stdin.

    Returns:
        JDDocument with optional frontmatter metadata and body text.

    Raises:
        JDReadError: If the source cannot be read or is empty.
    """
```

Internally, `_read_file()`, `_fetch_url()`, and `_read_stdin()` continue to
return `str`. The `read_jd()` function wraps their output:

```python
def read_jd(source: str) -> JDDocument:
    if source in _STDIN_SENTINELS:
        text = _read_stdin()
        return parse_jd_document(text)

    if _is_url(source):
        text = asyncio.run(_fetch_url(source))
        return parse_jd_document(text)

    path = Path(source)
    text = _read_file(path)
    return parse_jd_document(text, source_path=path)
```

### 3.3 Backward Compatibility

- Plain `.txt` files without frontmatter: `metadata=None`, `body=<full text>` -- works identically to before
- `.md` files without frontmatter: same as `.txt`
- `.md` files with frontmatter: metadata parsed, body extracted
- Malformed frontmatter: logged as warning, treated as plain text

### 3.4 Caller Updates

Every caller that currently receives `str` from `read_jd()` must be updated
to use `jd_doc.body` for the text content:

| Caller | Current | New |
|--------|---------|-----|
| `generate.py: _resolve_jd()` | `jd_text = read_jd(source)` | `jd_doc = read_jd(source); jd_text = jd_doc.body` |
| `cover_letter.py` | `jd_text = read_jd(jd)` | `jd_doc = read_jd(jd); jd_text = jd_doc.body` |
| `pipeline.py: generate()` | reads `jd_path` as raw text | unchanged — pipeline receives `jd_path`, reads file directly |

The `jd_doc.metadata` (JDFrontmatter) is used by `generate.py` to:
1. Auto-fill `--company` and `--position` from frontmatter when not provided
2. Pass enrichment data to `create_application()` (location, compensation, etc.)

**generate.py changes (workspace mode):**

```python
jd_doc = read_jd(jd)
jd_text = jd_doc.body

# Auto-fill from frontmatter if not provided via CLI
if jd_doc.metadata:
    company = company or jd_doc.metadata.company
    position = position or jd_doc.metadata.position
```

### 3.5 Error Handling

- `yaml.YAMLError` during frontmatter parse: warning logged, full text returned as body, no error raised
- `pydantic.ValidationError` on JDFrontmatter fields: warning logged, body still extracted correctly, metadata set to None
- Empty body after frontmatter extraction: raises `JDReadError` (same as current empty-file behavior)

---

## 4. Directory Management Design

### 4.1 New create_application() Implementation

The core change: directory path construction moves from
`{date}-{position}-{preset}-v{N}` to `{position}/{YYYY-MM-DD}`.

**WorkspaceManager.create_application() — new signature:**

```python
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
```

The `jd_source` parameter accepts `Path` (file to copy) or `str` (raw text
to write). The `jd_document` parameter, when provided, enables writing the JD
as markdown with frontmatter.

**Implementation approach:**

```python
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
    today = date.today()

    app_dir = self._build_application_path(
        workspace_root, company, position, today
    )

    # Create directory structure
    app_dir.mkdir(parents=True, exist_ok=True)

    # Write JD file (as markdown with frontmatter if possible)
    if jd_document is not None:
        self._write_jd_markdown(jd_document, app_dir, url=url)
    elif isinstance(jd_source, Path):
        # Legacy: copy file, converting to .md
        shutil.copy2(jd_source, app_dir / "jd.md")
    else:
        # Raw text
        (app_dir / "jd.md").write_text(jd_source, encoding="utf-8")

    # Build and write application.toml
    metadata = self._build_application_metadata(
        company=company,
        position=position,
        date=today,
        url=url,
        preset_name=preset_name,
        jd_document=jd_document,
    )
    self._write_application_toml(app_dir, metadata)

    logger.info("Created application: %s", app_dir)
    return app_dir
```

### 4.2 Path Construction

```python
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
        WorkspaceError: If the directory already exists.
    """
    apps_base = self.get_applications_dir(workspace_root)
    company_slug = self.slugify(company)
    position_slug = self.slugify(position)
    date_str = app_date.strftime("%Y-%m-%d")

    app_dir = apps_base / company_slug / position_slug / date_str

    if app_dir.exists():
        raise WorkspaceError(
            f"Application directory already exists: {app_dir}. "
            "Use the existing directory or choose a different date."
        )

    return app_dir
```

**Design rationale for no version in date dir:** The YYYY-MM-DD format
means at most one application per position per day. If a user re-applies to
the same position at the same company on the same day, they should use the
existing directory. Versioning happens at the sub-folder level (resumes/v1,
resumes/v2).

### 4.3 Sub-folder Creation and Versioning

```python
def create_output_version(
    self,
    app_dir: Path,
    output_type: str,
) -> Path:
    """Create a new versioned output directory within an application.

    Args:
        app_dir: Application directory path.
        output_type: One of "resumes", "cover-letter".

    Returns:
        Path to the new version directory (e.g., app_dir/resumes/v2/).
    """
    parent = app_dir / output_type
    parent.mkdir(parents=True, exist_ok=True)

    version = self._next_version(parent)
    version_dir = parent / f"v{version}"
    version_dir.mkdir()
    (version_dir / ".mkcv").mkdir()

    return version_dir
```

```python
@staticmethod
def _next_version(parent: Path) -> int:
    """Find the next version number in a directory.

    Scans for directories matching v{N} and returns N+1.
    Returns 1 when no versions exist.

    Args:
        parent: Directory to scan (e.g., app_dir/resumes/).

    Returns:
        The next version number (>= 1).
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
```

**Note:** The existing module-level `_next_version(parent, base_name)` function
is superseded by this simpler version that only looks for `v{N}` patterns.
The old function is kept for backward compatibility in generic resume versioning
(`resumes/` directory at workspace root) until that is also migrated.

### 4.4 Writing JD as Markdown with Frontmatter

```python
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
        url: Optional URL to include in frontmatter (overrides document metadata).

    Returns:
        Path to the written jd.md file.
    """
    lines: list[str] = []

    # Build frontmatter from metadata
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
            lines.append("---")
            lines.append(yaml.dump(fm_dict, default_flow_style=False).strip())
            lines.append("---")
            lines.append("")

    lines.append(jd_document.body)
    lines.append("")  # trailing newline

    jd_path = app_dir / "jd.md"
    jd_path.write_text("\n".join(lines), encoding="utf-8")
    return jd_path
```

### 4.5 Enriched application.toml

```python
def _build_application_metadata(
    self,
    *,
    company: str,
    position: str,
    date: date,
    url: str | None,
    preset_name: str,
    jd_document: JDDocument | None,
) -> ApplicationMetadata:
    """Build ApplicationMetadata, enriching from JD frontmatter."""
    fm = jd_document.metadata if jd_document else None

    return ApplicationMetadata(
        company=company,
        position=position,
        date=date,
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
```

The `_write_application_toml()` method is updated to serialize the new fields:

```python
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
```

---

## 5. Application Discovery Design

### 5.1 Dual-Layout Detection

The system must handle both old and new layouts during the transition period.
Layout detection is based on directory structure:

```python
def _detect_layout(self, app_dir: Path) -> Literal["v1", "v2"]:
    """Detect whether an application directory uses the old or new layout.

    v1 (old): application.toml is alongside resume.yaml and jd.txt
    v2 (new): application.toml is alongside jd.md with resumes/ subfolder

    Args:
        app_dir: Directory containing application.toml.

    Returns:
        "v1" for old layout, "v2" for new layout.
    """
    if (app_dir / "resumes").is_dir() or (app_dir / "jd.md").is_file():
        return "v2"
    return "v1"
```

### 5.2 New find_latest_application() — Timestamp Sort

The old implementation sorts lexicographically, relying on `YYYY-MM-` prefix.
The new layout uses `YYYY-MM-DD` at a deeper nesting level, so lexicographic
sort of the date directory still works. However, to support both layouts and
provide stable ordering, we sort by `created_at` from `application.toml`.

```python
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
        # Match company at any depth (v1: parent, v2: grandparent+)
        all_apps = [
            app for app in all_apps
            if self._matches_company(app, apps_dir, company_slug)
        ]

    if not all_apps:
        return None

    # Sort by created_at timestamp
    return max(all_apps, key=self._app_sort_key)
```

```python
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
    toml_path = app_dir / "application.toml"
    if toml_path.is_file():
        try:
            import tomllib
            with toml_path.open("rb") as f:
                data = tomllib.load(f)
            created = data.get("application", {}).get("created_at", "")
            if created:
                return (str(created), str(app_dir))
        except Exception:
            pass
    return ("", str(app_dir))
```

### 5.3 Updated resolve_resume_path()

```python
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
```

```python
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
```

### 5.4 Updated list_applications()

```python
def list_applications(self, workspace_root: Path) -> list[Path]:
    """List all application directories in the workspace.

    An application directory is identified by containing an
    application.toml file. Works for both old and new layouts.

    Args:
        workspace_root: Workspace root path.

    Returns:
        List of application directory paths, sorted by created_at.
    """
    apps_dir = self.get_applications_dir(workspace_root)
    if not apps_dir.is_dir():
        return []

    apps = [
        app_toml.parent
        for app_toml in apps_dir.rglob("application.toml")
    ]

    return sorted(apps, key=self._app_sort_key)
```

This is functionally identical to the current implementation (using `rglob`)
but switches from lexicographic to timestamp-based sorting.

---

## 6. Output Placement Design

### 6.1 Generate Command Flow

The generate command changes how it determines `output_dir`:

**Current flow:**
1. `create_application()` returns app_dir
2. Pipeline runs with `output_dir=app_dir`
3. resume.yaml and .mkcv/ go directly into app_dir

**New flow:**
1. `create_application()` returns app_dir (the date directory)
2. `create_output_version(app_dir, "resumes")` returns version_dir
3. Pipeline runs with `output_dir=version_dir`
4. resume.yaml and .mkcv/ go into `resumes/v{N}/`

**generate.py workspace mode changes:**

```python
def _generate_workspace_mode(...) -> None:
    # ... (same as before up to app_dir creation) ...

    workspace_service = create_workspace_service()
    app_dir = workspace_service.setup_application(
        workspace_root=workspace_root,
        company=company,
        position=position,
        jd_source=jd_file,
        preset_name=preset,
        url=url,
        jd_document=jd_doc,
    )

    # Create versioned output directory for resume
    version_dir = workspace_service.create_output_version(app_dir, "resumes")
    run_dir = output_dir or version_dir

    # Write JD to version dir for pipeline (pipeline reads jd_path directly)
    jd_path = _write_jd_file(jd_text, run_dir)

    _run_pipeline(
        jd=jd_path,
        kb=kb,
        output_dir=run_dir,
        # ...
    )
```

### 6.2 Cover Letter Command Flow

Similar pattern:

```python
# In cover_letter.py
version_dir = workspace_service.create_output_version(app_dir, "cover-letter")
gen_dir = output_dir or version_dir
```

### 6.3 Pipeline Output Threading

The `PipelineService.generate()` method already accepts `output_dir: Path` and
uses it correctly. The `.mkcv/` artifact subdirectory is created relative to
`output_dir`, so artifacts naturally land in `resumes/v{N}/.mkcv/`.

No changes needed to `PipelineService` or `ArtifactStorePort` internals.

### 6.4 RunMetadata Writing

After a successful pipeline run, the CLI layer writes run metadata:

```python
def _write_run_metadata(
    result: PipelineResult,
    version_dir: Path,
    *,
    preset: str,
) -> None:
    """Write run metadata to the version directory."""
    run_meta = RunMetadata(
        preset=preset,
        provider=result.stages[0].provider if result.stages else "unknown",
        model=result.stages[0].model if result.stages else "unknown",
        timestamp=result.timestamp,
        duration_seconds=result.total_duration_seconds,
        review_score=result.review_score,
        total_cost_usd=result.total_cost_usd,
    )

    meta_dir = version_dir / ".mkcv"
    meta_dir.mkdir(parents=True, exist_ok=True)
    meta_path = meta_dir / "run_metadata.json"
    meta_path.write_text(
        run_meta.model_dump_json(indent=2),
        encoding="utf-8",
    )
```

---

## 7. Status Command Design

### 7.1 Updated Table Columns

The status table gains new columns to reflect the richer metadata:

```python
def _build_application_table(app_dirs: list[Path]) -> Table:
    table = Table(
        show_header=True,
        header_style="bold",
        padding=(0, 2),
        expand=False,
    )
    table.add_column("Company", style="cyan", no_wrap=True)
    table.add_column("Position")
    table.add_column("Date")
    table.add_column("Status")
    table.add_column("Preset", style="dim")
    table.add_column("Versions", justify="center")
    table.add_column("Resume", justify="center")
    table.add_column("CL", justify="center")
    table.add_column("Layout", style="dim")
```

### 7.2 Version Summary Logic

```python
def _count_versions(app_dir: Path, output_type: str) -> int:
    """Count versioned subdirectories for an output type."""
    parent = app_dir / output_type
    if not parent.is_dir():
        return 0
    pattern = re.compile(r"^v(\d+)$")
    return sum(
        1 for entry in parent.iterdir()
        if entry.is_dir() and pattern.match(entry.name)
    )
```

### 7.3 Row Population

```python
for app_dir in app_dirs:
    metadata = _read_application_metadata(app_dir)
    layout = _detect_layout(app_dir)

    if layout == "v2":
        resume_count = _count_versions(app_dir, "resumes")
        cl_count = _count_versions(app_dir, "cover-letter")
        has_resume = resume_count > 0
        has_cl = cl_count > 0
        versions_str = f"r:{resume_count} cl:{cl_count}"
    else:
        # Old layout
        has_resume = (app_dir / "resume.yaml").is_file()
        has_cl = any(app_dir.glob("cover_letter.*"))
        versions_str = "v1 (legacy)"

    # ... populate row ...
    table.add_row(
        company, position, date_str, status,
        metadata.preset or "-",
        versions_str,
        _check_mark(has_resume),
        _check_mark(has_cl),
        layout,
    )
```

### 7.4 Old-Layout Display

Old-layout applications are clearly marked with `v1` in the Layout column
and `v1 (legacy)` in the Versions column. A hint is shown at the bottom:

```python
if any(_detect_layout(d) == "v1" for d in app_dirs):
    out.print(
        "  [dim]Tip: Run `mkcv migrate` to upgrade legacy "
        "application directories.[/dim]"
    )
```

---

## 8. Migration Design

### 8.1 MigrationService

**File:** `src/mkcv/core/services/migration.py`

```python
class MigrationService:
    """Migrates application directories from v1 to v2 layout."""

    def __init__(self, workspace: WorkspacePort) -> None:
        self._workspace = workspace
```

### 8.2 Detection of Old-Layout Directories

```python
def find_legacy_applications(
    self,
    workspace_root: Path,
) -> list[Path]:
    """Find all v1-layout application directories.

    Returns:
        List of application directories using the old layout.
    """
    all_apps = self._workspace.list_applications(workspace_root)
    return [
        app for app in all_apps
        if self._is_legacy_layout(app)
    ]

@staticmethod
def _is_legacy_layout(app_dir: Path) -> bool:
    """Check if a directory uses the v1 layout.

    v1 indicators:
    - No resumes/ subdirectory
    - No jd.md file (has jd.txt instead)
    - Directory name matches YYYY-MM-{position}-{preset}-v{N} pattern
    """
    if (app_dir / "resumes").is_dir():
        return False
    if (app_dir / "jd.md").is_file():
        return False
    return True
```

### 8.3 Transformation Algorithm

For each v1 application directory at
`applications/{company}/{YYYY-MM}-{position}-{preset}-v{N}/`:

1. **Parse the old directory name** to extract date, position, preset, version
2. **Read application.toml** to get company, position, date
3. **Create new directory:** `applications/{company}/{position}/{YYYY-MM-DD}/`
4. **Move application.toml** to new location, enriching with preset
5. **Convert jd.txt to jd.md** (no frontmatter — just rename)
6. **Create resumes/v1/** and move resume.yaml, resume.pdf, .mkcv/
7. **Create cover-letter/v1/** and move cover_letter.* files
8. **Remove old directory** (if empty after moves)

```python
@dataclass
class MigrationPlan:
    """Planned migration for a single application."""

    source: Path
    target: Path
    company: str
    position: str
    date: date
    preset: str
    files_to_move: list[tuple[Path, Path]]  # (src, dst)
    warnings: list[str]


def plan_migration(
    self,
    app_dir: Path,
    workspace_root: Path,
) -> MigrationPlan:
    """Plan the migration for a single v1 application.

    Does not perform any filesystem operations.

    Args:
        app_dir: Legacy application directory.
        workspace_root: Workspace root path.

    Returns:
        MigrationPlan describing all planned operations.
    """


def execute_migration(
    self,
    plan: MigrationPlan,
) -> None:
    """Execute a planned migration.

    Creates the new directory structure and moves files.

    Args:
        plan: Migration plan from plan_migration().

    Raises:
        WorkspaceError: If the target directory already exists
            or file operations fail.
    """


def migrate_all(
    self,
    workspace_root: Path,
    *,
    dry_run: bool = False,
) -> list[MigrationPlan]:
    """Migrate all legacy applications in a workspace.

    Args:
        workspace_root: Workspace root path.
        dry_run: If True, plan but don't execute.

    Returns:
        List of migration plans (executed unless dry_run).
    """
```

### 8.4 JD txt-to-md Conversion

Simple rename — no frontmatter is added during migration since we don't
have structured metadata to populate. The file is moved as `jd.md` and
remains plain text (which is valid markdown).

```python
def _convert_jd(self, old_jd: Path, new_app_dir: Path) -> Path:
    """Convert jd.txt to jd.md by moving with rename."""
    new_path = new_app_dir / "jd.md"
    shutil.move(str(old_jd), str(new_path))
    return new_path
```

### 8.5 --dry-run Output Format

```
$ mkcv migrate --dry-run

  mkcv migrate — dry run (no changes)

  Found 3 legacy applications:

  1. acme/2025-01-senior-engineer-standard-v1/
     → acme/senior-engineer/2025-01-15/
     Files: application.toml, jd.txt→jd.md, resume.yaml, resume.pdf, .mkcv/
     Resume → resumes/v1/

  2. acme/2025-02-staff-engineer-comprehensive-v1/
     → acme/staff-engineer/2025-02-20/
     Files: application.toml, jd.txt→jd.md, resume.yaml
     Resume → resumes/v1/

  3. startup/2025-03-cto-concise-v1/
     → startup/cto/2025-03-10/
     Files: application.toml, jd.txt→jd.md, resume.yaml, resume.pdf
     Resume → resumes/v1/  Cover letter → cover-letter/v1/

  Run `mkcv migrate` to execute.
```

### 8.6 Error Recovery

- **Target exists:** Skip and warn (don't overwrite)
- **File move fails:** Log error, continue with remaining files, report at end
- **Partial migration:** The old directory is NOT removed if any files remain
- **Atomic-ish safety:** Plan all, then execute. Errors mid-execution leave
  both old and new directories — the user can manually resolve.

---

## 9. Port/Interface Changes

### 9.1 WorkspacePort Protocol Updates

**File:** `src/mkcv/core/ports/workspace.py`

```python
@runtime_checkable
class WorkspacePort(Protocol):
    """Interface for workspace and application directory management."""

    def create_workspace(self, path: Path) -> Path: ...

    def update_readme(self, workspace_root: Path) -> bool: ...

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
        ...

    def create_output_version(
        self,
        app_dir: Path,
        output_type: str,
    ) -> Path:
        """Create a new versioned output subdirectory.

        Args:
            app_dir: Application directory path.
            output_type: One of "resumes", "cover-letter".

        Returns:
            Path to the new version directory.
        """
        ...

    def list_applications(self, workspace_root: Path) -> list[Path]: ...

    def find_latest_application(
        self,
        workspace_root: Path,
        *,
        company: str | None = None,
    ) -> Path | None: ...

    def resolve_resume_path(self, app_dir: Path) -> Path | None: ...

    def resolve_cover_letter_path(self, app_dir: Path) -> Path | None:
        """Find the latest cover letter in an application directory.

        Args:
            app_dir: Path to the application directory.

        Returns:
            Path to cover_letter.md or .pdf if it exists, or None.
        """
        ...
```

### 9.2 Backward Compatibility

The `create_application()` signature is backward-compatible:
- `jd_source` continues to accept `Path` (existing behavior)
- `jd_document` is a new keyword-only optional parameter
- All new parameters have defaults

`list_applications()` and `find_latest_application()` signatures are unchanged.
The implementations handle both layouts internally.

---

## 10. Factory/DI Changes

### 10.1 Updated create_workspace_service()

No change needed — `WorkspaceService` wraps `WorkspacePort` and the new
methods are automatically delegated through the protocol.

### 10.2 WorkspaceService Additions

**File:** `src/mkcv/core/services/workspace.py`

Add delegation methods for the new port methods:

```python
def create_output_version(self, app_dir: Path, output_type: str) -> Path:
    """Create a new versioned output subdirectory."""
    return self._workspace.create_output_version(app_dir, output_type)

def resolve_cover_letter_path(self, app_dir: Path) -> Path | None:
    """Find the latest cover letter in an application directory."""
    return self._workspace.resolve_cover_letter_path(app_dir)
```

### 10.3 New create_migration_service()

**File:** `src/mkcv/adapters/factory.py`

```python
def create_migration_service() -> MigrationService:
    """Create a fully-wired MigrationService.

    Returns:
        MigrationService with WorkspaceManager adapter.
    """
    from mkcv.core.services.migration import MigrationService

    manager = WorkspaceManager()
    return MigrationService(workspace=manager)
```

---

## 11. Function Signatures

### New Public Functions

```python
# --- core/models/compensation.py ---
# (Pydantic model only, no functions)

# --- core/models/jd_frontmatter.py ---
# (Pydantic model only, no functions)

# --- core/models/jd_document.py ---
# (Pydantic model only, no functions)

# --- core/models/run_metadata.py ---
# (Pydantic model only, no functions)

# --- core/services/jd_reader.py ---
def parse_jd_document(
    text: str,
    *,
    source_path: Path | None = None,
) -> JDDocument: ...

def read_jd(source: str) -> JDDocument: ...  # return type changed

# --- core/services/migration.py ---
class MigrationService:
    def __init__(self, workspace: WorkspacePort) -> None: ...

    def find_legacy_applications(
        self,
        workspace_root: Path,
    ) -> list[Path]: ...

    def plan_migration(
        self,
        app_dir: Path,
        workspace_root: Path,
    ) -> MigrationPlan: ...

    def execute_migration(
        self,
        plan: MigrationPlan,
    ) -> None: ...

    def migrate_all(
        self,
        workspace_root: Path,
        *,
        dry_run: bool = False,
    ) -> list[MigrationPlan]: ...

# --- core/services/workspace.py ---
class WorkspaceService:
    def create_output_version(
        self,
        app_dir: Path,
        output_type: str,
    ) -> Path: ...

    def resolve_cover_letter_path(
        self,
        app_dir: Path,
    ) -> Path | None: ...

# --- adapters/filesystem/workspace_manager.py ---
class WorkspaceManager:
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
    ) -> Path: ...

    def create_output_version(
        self,
        app_dir: Path,
        output_type: str,
    ) -> Path: ...

    def resolve_cover_letter_path(
        self,
        app_dir: Path,
    ) -> Path | None: ...

    # Private helpers:
    def _build_application_path(
        self,
        workspace_root: Path,
        company: str,
        position: str,
        app_date: date,
    ) -> Path: ...

    @staticmethod
    def _next_version(parent: Path) -> int: ...

    def _write_jd_markdown(
        self,
        jd_document: JDDocument,
        app_dir: Path,
        *,
        url: str | None = None,
    ) -> Path: ...

    def _build_application_metadata(
        self,
        *,
        company: str,
        position: str,
        date: date,
        url: str | None,
        preset_name: str,
        jd_document: JDDocument | None,
    ) -> ApplicationMetadata: ...

    def _detect_layout(self, app_dir: Path) -> Literal["v1", "v2"]: ...

    def _matches_company(
        self,
        app_dir: Path,
        apps_dir: Path,
        company_slug: str,
    ) -> bool: ...

    @staticmethod
    def _app_sort_key(app_dir: Path) -> tuple[str, str]: ...

    def _find_latest_version(self, parent: Path) -> Path | None: ...

# --- adapters/factory.py ---
def create_migration_service() -> MigrationService: ...

# --- cli/commands/migrate.py (NEW) ---
def migrate_command(
    *,
    dry_run: bool = False,
) -> None: ...

# --- cli/commands/generate.py (MODIFIED) ---
def _write_run_metadata(
    result: PipelineResult,
    version_dir: Path,
    *,
    preset: str,
) -> None: ...
```

### Modified Function Signatures

```python
# --- core/services/jd_reader.py ---
# BEFORE: def read_jd(source: str) -> str
# AFTER:  def read_jd(source: str) -> JDDocument

# --- cli/commands/generate.py ---
# _resolve_jd now returns (JDDocument, str) instead of (str, str)
def _resolve_jd(source: str) -> tuple[JDDocument, str]: ...

# --- core/ports/workspace.py ---
# create_application gains jd_document parameter
# create_output_version is NEW
# resolve_cover_letter_path is NEW
```

---

## 12. Error Handling

### 12.1 New Exception Types

No new exception classes are needed. The existing hierarchy covers all cases:

| Scenario | Exception | Existing? |
|----------|-----------|-----------|
| Application dir already exists | `WorkspaceError` | Yes |
| JD file not found / empty | `JDReadError` | Yes |
| Malformed frontmatter YAML | Warning logged, graceful degradation | N/A |
| Invalid frontmatter fields | Warning logged, metadata=None | N/A |
| Migration target exists | `WorkspaceError` | Yes |
| Migration file move fails | `WorkspaceError` | Yes |
| No workspace for migrate | `WorkspaceNotFoundError` | Yes |
| Invalid output_type | `ValueError` (stdlib) | Yes |

### 12.2 Error Scenarios

**JD frontmatter parse failure:**
```python
# In parse_jd_document()
try:
    raw = yaml.safe_load(yaml_str)
except yaml.YAMLError:
    logger.warning("Malformed YAML frontmatter; treating as plain text")
    return JDDocument(body=text.strip(), source_path=source_path)
```

**Application directory collision (same position, same date):**
```python
# In _build_application_path()
if app_dir.exists():
    raise WorkspaceError(
        f"Application directory already exists: {app_dir}. "
        "Use the existing directory or choose a different date."
    )
```

**Version directory creation race (concurrent runs):**
```python
# _next_version + mkdir is not atomic, but:
# 1. CLI is single-process, so races are unlikely
# 2. mkdir() with exist_ok=False would catch a race
# 3. Sufficient for a single-user CLI tool
```

**Migration — partial failure:**
```python
# Each file move is wrapped in try/except
# Failures are collected in a warnings list
# Old dir is only removed if completely empty
# User is informed of partial migration state
```

---

## Appendix A: File Creation Summary

### New Files

| File | Type | Description |
|------|------|-------------|
| `src/mkcv/core/models/compensation.py` | Model | Compensation data |
| `src/mkcv/core/models/jd_frontmatter.py` | Model | JD YAML frontmatter |
| `src/mkcv/core/models/jd_document.py` | Model | Parsed JD document |
| `src/mkcv/core/models/run_metadata.py` | Model | Per-version run metadata |
| `src/mkcv/core/services/migration.py` | Service | v1→v2 layout migration |
| `src/mkcv/cli/commands/migrate.py` | CLI | `mkcv migrate` command |

### Modified Files

| File | Changes |
|------|---------|
| `src/mkcv/core/models/application_metadata.py` | Add preset, compensation, location, workplace, source, tags fields |
| `src/mkcv/core/models/workspace_config.py` | Update application_pattern default |
| `src/mkcv/core/ports/workspace.py` | Add create_output_version(), resolve_cover_letter_path(); update create_application() |
| `src/mkcv/core/services/jd_reader.py` | Add parse_jd_document(); change read_jd() return type to JDDocument |
| `src/mkcv/core/services/workspace.py` | Add create_output_version(), resolve_cover_letter_path() delegations |
| `src/mkcv/adapters/filesystem/workspace_manager.py` | Major rewrite: new path construction, versioned outputs, dual-layout detection |
| `src/mkcv/adapters/factory.py` | Add create_migration_service() |
| `src/mkcv/cli/commands/generate.py` | Update JD handling (JDDocument), output_dir threading, run metadata writing |
| `src/mkcv/cli/commands/cover_letter.py` | Update JD handling, output placement to cover-letter/v{N}/ |
| `src/mkcv/cli/commands/status.py` | New table columns, dual-layout display |
| `src/mkcv/cli/app.py` | Register migrate command |

### Not Modified

| File | Reason |
|------|--------|
| `src/mkcv/core/services/pipeline.py` | Already accepts output_dir; no internal changes needed |
| `src/mkcv/core/services/cover_letter.py` | Already accepts output_dir; no internal changes needed |
| `src/mkcv/adapters/filesystem/artifact_store.py` | Works with any output_dir; no changes needed |
| `src/mkcv/core/ports/artifacts.py` | Interface unchanged |
| `src/mkcv/core/ports/llm.py` | Unrelated to this change |

---

## Appendix B: YAML Dependency Note

The JD frontmatter parser uses `yaml.safe_load()` from PyYAML. PyYAML is
already a transitive dependency via `rendercv` and `dynaconf`. It is NOT
listed as a direct dependency in `pyproject.toml`. Since the proposal specifies
"no new external deps", this is acceptable — but an implementer should verify
that `import yaml` works without adding a new dependency.

If PyYAML were not available, the fallback would be a regex-only parser
that extracts key-value pairs from the frontmatter block. However, this is
unnecessary given the existing transitive dependency.

---

## Appendix C: mkcv.toml Template Update

The workspace template (`_MKCV_TOML_TEMPLATE` in `workspace_manager.py`)
should be updated to reflect the new naming pattern:

```toml
[naming]
company_slug = true
application_pattern = "{company}/{position}/{date}"
```

This only affects newly created workspaces. Existing workspaces keep their
old `mkcv.toml` and the old pattern is recognized via dual-layout detection.
