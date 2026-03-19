# Technical Design: Theme System Overhaul

## 1. Architecture Decisions

### AD-1: YAML Post-Processing Strategy — ruamel.yaml Round-Trip

**Decision:** Use `ruamel.yaml` for YAML post-processing (Option B).

**Rationale:**
- `ruamel.yaml` 0.19.1 is already in the dependency tree (transitive via `rendercv`).
  No new dependency needed.
- Round-trip preservation of comments, key ordering, and formatting means the
  LLM-generated YAML stays human-readable and diff-friendly.
- PyYAML (also available) would work but loses comments and reorders keys.
- Regex replacement (Option C) is fragile — the `design:` section can appear in
  comments or string values. A proper parser is the right tool.

**Implementation:** A new `YamlPostProcessor` class in `core/services/` that:
1. Parses the raw YAML string with `ruamel.yaml` round-trip mode.
2. Replaces or injects the `design` top-level mapping.
3. Dumps back to a string, preserving the `cv:` section formatting.

### AD-2: Theme Resolution — Extend Existing ThemeService

**Decision:** Extend the existing `ThemeService` module (Option B) rather than
creating a new resolver service.

**Rationale:**
- `core/services/theme.py` already has `discover_themes()` and `get_theme()`.
  Adding resolution logic here keeps theme concerns cohesive.
- A separate `ThemeResolver` would be a one-function service — not worth the
  extra file and DI wiring overhead.
- Resolution logic is simple: CLI flag > config > default. This is 5 lines
  of code, not a service boundary.

**Implementation:** Add a `resolve_theme()` function to `core/services/theme.py`:
```python
def resolve_theme(
    cli_theme: str | None,
    config_theme: str,
    default: str = "sb2nov",
) -> str:
    """Resolve the effective theme from CLI flag, config, or default."""
    if cli_theme is not None:
        return cli_theme
    return config_theme or default
```

The CLI commands call this function, passing the CLI flag and `settings.rendering.theme`.

### AD-3: Custom Theme Loading — Workspace Discovery + Pydantic Validation

**Decision:** Custom themes are YAML files in `workspace/themes/` validated
against a `CustomTheme` Pydantic model. They are discovered by `ThemeService`
and merged into the theme list.

**Rationale:**
- Follows the existing workspace convention (like `templates/` for prompt overrides).
- Pydantic validation gives clear error messages for malformed theme files.
- Custom themes are NOT directly instantiated as RenderCV theme objects — instead,
  their properties are merged into the YAML `design:` section by the post-processor.
  This avoids coupling to RenderCV internals while still producing valid output.

**Implementation:** Custom theme files follow this structure:
```yaml
# themes/mytheme.yaml
name: mytheme
extends: classic        # base RenderCV theme
description: "My custom blue theme"
applies_to: all         # "all" (default), "resume", or "cover_letter"
overrides:
  font: "Charter"
  font_size: "11pt"
  page_size: "a4paper"
  primary_color: "004080"
```

### AD-4: Design Override Injection — Post-Stage-4 in Pipeline

**Decision:** Design overrides are applied as a post-processing step after
Stage 4 generates the YAML, within `PipelineService._structure_yaml()`.

**Rationale:**
- The LLM cannot be trusted to reliably emit the correct theme/design values.
- Post-processing is deterministic and testable.
- Applying overrides inside `_structure_yaml()` means the saved `resume.yaml`
  already contains the correct design section — no further transformation needed
  at render time.
- The `ResumeDesign` model carries the override values through the system.

### AD-5: Config Schema — Flat Overrides Under `[rendering]`

**Decision:** Add override fields directly under `[rendering]` in the existing
config schema, plus a new `[rendering.overrides]` sub-table for explicit
design property overrides.

**Rationale:**
- `settings.toml` already has `[default.rendering]` with `theme`, `font`,
  `font_size`, and `page_size`. These are the same fields that `ResumeDesign`
  models. We reuse them rather than duplicating.
- The `[rendering.overrides]` sub-table is for additional properties
  (e.g. `primary_color`) that go beyond the basic fields already present.
- Dynaconf handles nested TOML tables natively.

**Config schema:**
```toml
[rendering]
theme = "classic"
font = "Charter"
font_size = "11pt"
page_size = "a4paper"

[rendering.overrides]
primary_color = "004080"
# Additional RenderCV design overrides
```

### AD-6: Cover Letter Theme Compatibility — Shared Design Model

**Decision:** Design the theme system so that resumes and cover letters share the
same theme identity and design properties. The `ResumeDesign` model property names
are chosen to align with both RenderCV YAML fields AND cover letter Typst template
variables. Implementation is deferred, but interfaces must not block it.

**Rationale:**
- Cover letter support was added (March 2026) with a separate rendering pipeline:
  `CoverLetterRendererPort` → `TypstCoverLetterRenderer` using direct `typst.compile()`.
- The cover letter port already has `theme: str = "professional"` parameter (inert).
- The single Typst template (`cover_letter.typ.j2`) hardcodes Source Sans Pro, 11pt,
  US Letter — the same properties that `ResumeDesign` models.
- Users expect `mkcv generate --theme classic --cover-letter` to produce a resume
  AND cover letter in the same visual style.

**Implications for this change:**
1. `resolve_theme()` is a pure function with no resume-specific coupling — usable
   by any command.
2. `ResumeDesign` property names (`font`, `font_size`, `page_size`, `colors`) align
   with what a parameterized Typst template would need. Consider renaming to
   `DocumentDesign` in a follow-up, but keep the property names stable now.
3. `CustomTheme` model includes `applies_to: Literal["all", "resume", "cover_letter"]`
   defaulting to `"all"`, so custom themes can optionally target a specific document type.
4. `ThemeInfo` model includes `source` field but does NOT add a `document_type` field
   yet — all built-in themes are resume-only, and custom themes use `applies_to`.
5. The `[rendering]` config section applies to all document types by default. A future
   `[cover_letter.rendering]` section could override specific properties.

**What a follow-up change needs to do (NOT this change):**
- Add `theme` kwarg to `CoverLetterService.generate()` and pass to renderer
- Parameterize `cover_letter.typ.j2` to accept font/colors/page_size from context
- Add `--theme` flag to `cover-letter` CLI command
- Wire theme through `_chain_cover_letter()` in `generate.py`
- Optionally create multiple Typst cover letter templates per theme

## 2. Data Flow

### 2.1 Theme Selection Flow

```
                    CLI --theme flag
                         |
                         v
              +-----------------------+
              | resolve_theme()       |
              | (core/services/theme) |
              +-----------+-----------+
                          |
              cli_theme ? |
                  +-------+-------+
                  | yes           | no
                  v               v
             use cli_theme   settings.rendering.theme
                                  |
                          config_theme ? 
                              +---+---+
                              | yes   | no
                              v       v
                         use config  "sb2nov"
                              |       |
                              +---+---+
                                  |
                                  v
                          effective_theme
                                  |
              +-------------------+-------------------+
              |                                       |
              v                                       v
    PipelineService.generate()              RenderService.render_resume()
    (Stage 4 prompt + post-process)         (pass to RenderCVAdapter)
              |
              v
    structure_yaml.j2
    {{ theme }} variable
              |
              v
    LLM generates YAML
              |
              v
    YamlPostProcessor.inject_design()
    (force-set design.theme)
              |
              v
    resume.yaml (on disk)
```

### 2.2 Design Override Flow

```
    settings.toml                  CLI --theme
    [rendering]                        |
    theme = "classic"                  |
    font = "Charter"                   |
    page_size = "a4paper"              |
    [rendering.overrides]              |
    primary_color = "004080"           |
         |                             |
         v                             v
    _build_resume_design()      resolve_theme()
    (factory or pipeline)              |
         |                             |
         v                             v
    ResumeDesign(                 effective_theme
      theme="classic",                 |
      font="Charter",                  |
      page_size="a4paper",             |
      colors={"primary":"004080"}      |
    )                                  |
         |                             |
         +-------------+---------------+
                        |
                        v
           PipelineService.generate()
                        |
                        v
              _structure_yaml()
                        |
                        v
              LLM generates YAML
              (with {{ theme }} hint)
                        |
                        v
              YamlPostProcessor.inject_design(
                  yaml_str, resume_design
              )
                        |
                        v
              resume.yaml with correct design:
                design:
                  theme: classic
                  font: Charter
                  page_size: a4paper
                  color: "004080"
```

### 2.3 Custom Theme Flow

```
    workspace/themes/mytheme.yaml
              |
              v
    ThemeService.discover_custom_themes(workspace_root)
              |
              v
    CustomTheme.model_validate(yaml_data)
    - Validates name, extends, overrides
    - Checks name != built-in theme name
              |
              v
    ThemeInfo(name="mytheme", source="custom", ...)
              |
              v
    discover_themes(workspace_root) merges:
      [built-in ThemeInfo...] + [custom ThemeInfo...]
              |
              +----> mkcv themes (display with [custom] badge)
              |
              +----> resolve_theme() (custom names are valid)
              |
              v
    When rendering with custom theme:
    1. Load CustomTheme from workspace/themes/{name}.yaml
    2. Build ResumeDesign from CustomTheme.overrides + base theme
    3. YamlPostProcessor injects design section
    4. RenderCV renders with the base theme + overridden properties
```

## 3. Interface Definitions

### 3.1 YamlPostProcessor (New Service)

**File:** `src/mkcv/core/services/yaml_postprocessor.py`

```python
"""YAML post-processing for design section injection."""

from mkcv.core.models.resume_design import ResumeDesign


class YamlPostProcessor:
    """Post-processes LLM-generated YAML to inject/replace the design section.

    Uses ruamel.yaml for round-trip parsing to preserve comments and
    formatting in the cv: section while replacing the design: section
    with validated values.
    """

    def inject_design(
        self,
        yaml_str: str,
        design: ResumeDesign,
    ) -> str:
        """Replace or insert the design section in resume YAML.

        Args:
            yaml_str: Raw YAML string from LLM or file.
            design: Validated design configuration to inject.

        Returns:
            Modified YAML string with the design section updated.

        Raises:
            ValueError: If yaml_str is not valid YAML.
        """
        ...

    def inject_theme(
        self,
        yaml_str: str,
        theme: str,
    ) -> str:
        """Replace only the design.theme value, preserving other design fields.

        Convenience method for Phase 1 when only theme needs to be set.

        Args:
            yaml_str: Raw YAML string.
            theme: Theme name to inject.

        Returns:
            Modified YAML string.
        """
        ...
```

### 3.2 ResumeDesign Model (Extended)

**File:** `src/mkcv/core/models/resume_design.py`

```python
"""Resume design/theme configuration model."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


VALID_PAGE_SIZES = ("letterpaper", "a4paper", "us-letter", "a4")

# Mapping from mkcv page_size names to RenderCV page_size names
PAGE_SIZE_MAP: dict[str, str] = {
    "letterpaper": "us-letter",
    "a4paper": "a4",
    "us-letter": "us-letter",
    "a4": "a4",
}


class ResumeDesign(BaseModel):
    """Design settings for resume rendering.

    Carries theme selection and visual overrides through the pipeline.
    Used by YamlPostProcessor to inject the design section into
    generated YAML.
    """

    theme: str = "sb2nov"
    font: str = "SourceSansPro"
    font_size: str = "10pt"
    page_size: str = "letterpaper"
    colors: dict[str, str] = Field(
        default_factory=lambda: {"primary": "003366"}
    )

    @field_validator("page_size")
    @classmethod
    def validate_page_size(cls, v: str) -> str:
        """Validate page_size against supported values."""
        if v not in VALID_PAGE_SIZES:
            raise ValueError(
                f"Invalid page_size '{v}'. "
                f"Supported: {', '.join(VALID_PAGE_SIZES)}"
            )
        return v

    def has_overrides(self) -> bool:
        """Check if any non-default overrides are set."""
        default = ResumeDesign()
        return (
            self.font != default.font
            or self.font_size != default.font_size
            or self.page_size != default.page_size
            or self.colors != default.colors
        )
```

### 3.3 CustomTheme Model (New)

**File:** `src/mkcv/core/models/custom_theme.py`

```python
"""Custom theme definition model."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CustomTheme(BaseModel):
    """A user-defined theme loaded from workspace themes/ directory.

    Custom themes extend a built-in RenderCV theme with property
    overrides for font, colors, page size, etc. The applies_to field
    controls which document types this theme targets (resume, cover
    letter, or both).
    """

    name: str
    extends: str = "classic"
    description: str = ""
    applies_to: Literal["all", "resume", "cover_letter"] = "all"
    overrides: dict[str, str] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure theme name is lowercase alphanumeric with hyphens."""
        import re
        if not re.match(r"^[a-z][a-z0-9-]*$", v):
            raise ValueError(
                f"Theme name '{v}' must be lowercase alphanumeric "
                "with hyphens, starting with a letter."
            )
        return v
```

### 3.4 ThemeInfo Model (Extended)

**File:** `src/mkcv/core/models/theme_info.py`

```python
"""Theme metadata model for resume themes."""

from typing import Literal

from pydantic import BaseModel


class ThemeInfo(BaseModel):
    """Metadata about an available resume theme."""

    name: str
    description: str
    font_family: str
    primary_color: str
    accent_color: str
    page_size: str
    source: Literal["built-in", "custom"] = "built-in"
```

### 3.5 Extended ThemeService

**File:** `src/mkcv/core/services/theme.py` (modifications)

```python
# New functions to add:

def resolve_theme(
    cli_theme: str | None,
    config_theme: str,
    default: str = "sb2nov",
) -> str:
    """Resolve effective theme from CLI, config, or default."""
    ...

def discover_custom_themes(workspace_root: Path) -> list[ThemeInfo]:
    """Discover custom themes from workspace themes/ directory.

    Args:
        workspace_root: Path to the workspace root.

    Returns:
        List of ThemeInfo for valid custom themes.
        Invalid theme files are logged as warnings and skipped.
    """
    ...

def load_custom_theme(theme_path: Path) -> CustomTheme:
    """Load and validate a custom theme YAML file.

    Args:
        theme_path: Path to the theme YAML file.

    Returns:
        Validated CustomTheme instance.

    Raises:
        ValidationError: If the theme YAML is invalid.
        FileNotFoundError: If the file doesn't exist.
    """
    ...

# Modified functions:

def discover_themes(
    workspace_root: Path | None = None,
) -> list[ThemeInfo]:
    """Discover all available themes (built-in + custom).

    Args:
        workspace_root: Optional workspace root for custom theme discovery.

    Returns:
        Sorted list of ThemeInfo for all available themes.
    """
    ...

def get_theme(
    name: str,
    workspace_root: Path | None = None,
) -> ThemeInfo | None:
    """Look up a theme by name (built-in or custom)."""
    ...
```

### 3.6 Updated PipelineService Signature

**File:** `src/mkcv/core/services/pipeline.py` (modifications)

```python
class PipelineService:
    def __init__(
        self,
        providers: dict[str, LLMPort],
        prompts: PromptLoaderPort,
        artifacts: ArtifactStorePort,
        stage_configs: dict[int, StageConfig] | None = None,
        preset: Preset | None = None,
        resume_design: ResumeDesign | None = None,  # NEW
    ) -> None:
        ...
        self._resume_design = resume_design

    async def generate(
        self,
        jd_path: Path,
        kb_path: Path,
        *,
        output_dir: Path,
        from_stage: int = 1,
        stage_callback: StageCallbackPort | None = None,
        theme: str | None = None,  # NEW — for Stage 4 prompt
    ) -> PipelineResult:
        ...
```

### 3.7 RendererPort — Remove Default

**File:** `src/mkcv/core/ports/renderer.py`

The `theme` parameter default `"sb2nov"` is removed. Callers must pass
the theme explicitly. This prevents hidden defaults from silently overriding
config.

```python
@runtime_checkable
class RendererPort(Protocol):
    def render(
        self,
        yaml_path: Path,
        output_dir: Path,
        *,
        theme: str,  # no default — callers must be explicit
        formats: list[str] | None = None,
    ) -> RenderedOutput:
        ...
```

Similarly for `RenderService.render_resume()` and `RenderCVAdapter.render()`.

## 4. Concrete File Change List

### Phase 1: Fix What's Broken

| File | Action | Changes |
|------|--------|---------|
| `src/mkcv/core/services/yaml_postprocessor.py` | **Create** | `YamlPostProcessor` class with `inject_design()` and `inject_theme()` |
| `src/mkcv/prompts/structure_yaml.j2` | **Modify** | Replace hardcoded `theme: sb2nov` with `theme: {{ theme \| default("sb2nov") }}` |
| `src/mkcv/core/services/pipeline.py` | **Modify** | Add `resume_design` to `__init__`, `theme` kwarg to `generate()`, pass `theme` to Stage 4 prompt context, call `YamlPostProcessor.inject_design()` after LLM output |
| `src/mkcv/core/services/render.py` | **Modify** | Remove `theme="sb2nov"` default from `render_resume()` — make `theme` required |
| `src/mkcv/core/services/theme.py` | **Modify** | Add `resolve_theme()` function |
| `src/mkcv/core/models/resume_design.py` | **Modify** | Add `field_validator` for `page_size`, add `has_overrides()` method, add `PAGE_SIZE_MAP` |
| `src/mkcv/core/ports/renderer.py` | **Modify** | Remove `"sb2nov"` default from `theme` parameter in `RendererPort.render()` |
| `src/mkcv/adapters/renderers/rendercv.py` | **Modify** | Remove `"sb2nov"` default from `RenderCVAdapter.render()` |
| `src/mkcv/cli/commands/generate.py` | **Modify** | Read theme default from `settings.rendering.theme` via `resolve_theme()`, pass `theme` to `pipeline.generate()` |
| `src/mkcv/cli/commands/render.py` | **Modify** | Replace `effective_theme = theme if theme is not None else "sb2nov"` with `resolve_theme(theme, settings.rendering.theme)` |
| `src/mkcv/adapters/factory.py` | **Modify** | Add `_build_resume_design()` helper, pass `resume_design` to `PipelineService` in `create_pipeline_service()` |
| `tests/test_core/test_services/test_yaml_postprocessor.py` | **Create** | Unit tests for `YamlPostProcessor` |
| `tests/test_core/test_services/test_render.py` | **Modify** | Update tests to pass explicit `theme` argument |
| `tests/test_core/test_services/test_pipeline.py` | **Modify** | Add tests for `theme` kwarg in `generate()`, verify theme passed to prompt context |

### Phase 2: Theme Customization

| File | Action | Changes |
|------|--------|---------|
| `src/mkcv/config/settings.toml` | **Modify** | Add `[default.rendering.overrides]` section with commented-out examples |
| `src/mkcv/config/configuration.py` | **Modify** | Add validators for `rendering.overrides.*` fields |
| `src/mkcv/adapters/factory.py` | **Modify** | Read `settings.rendering.*` fields to build `ResumeDesign` in `_build_resume_design()` |
| `tests/test_config/test_configuration.py` | **Modify** | Add tests for rendering.overrides validation |

### Phase 3: Custom Themes

| File | Action | Changes |
|------|--------|---------|
| `src/mkcv/core/models/custom_theme.py` | **Create** | `CustomTheme` Pydantic model |
| `src/mkcv/core/models/theme_info.py` | **Modify** | Add `source: Literal["built-in", "custom"]` field with default `"built-in"` |
| `src/mkcv/core/services/theme.py` | **Modify** | Add `discover_custom_themes()`, `load_custom_theme()`, update `discover_themes()` and `get_theme()` to accept optional `workspace_root` |
| `src/mkcv/cli/commands/themes.py` | **Modify** | Pass `workspace_root` to `discover_themes()`, show `[custom]` badge, indicate configured default |
| `src/mkcv/adapters/filesystem/workspace_manager.py` | **Modify** | Scaffold `themes/` directory and `themes/example.yaml` in `create_workspace()` |
| `tests/test_core/test_models/test_custom_theme.py` | **Create** | Unit tests for `CustomTheme` model validation |
| `tests/test_core/test_services/test_theme.py` | **Create** | Tests for `discover_custom_themes()`, `resolve_theme()`, custom theme loading |
| `tests/test_core/test_models/test_theme_info.py` | **Modify** | Add test for `source` field |

### Phase 4: Documentation & UX

| File | Action | Changes |
|------|--------|---------|
| `src/mkcv/cli/commands/generate.py` | **Modify** | Update `--theme` help text to reference `mkcv themes` |
| `src/mkcv/cli/commands/render.py` | **Modify** | Update `--theme` help text |
| `src/mkcv/cli/commands/themes.py` | **Modify** | Show configured default, show overrides in preview |

### Summary

| Action | Count |
|--------|-------|
| **Create** | 5 files (3 source + 2 test) |
| **Modify** | 17 files (13 source + 4 test) |
| **Delete** | 0 files |

## 5. Detailed Implementation Notes

### 5.1 YamlPostProcessor Implementation

```python
# src/mkcv/core/services/yaml_postprocessor.py

import logging
from io import StringIO
from typing import Any

from ruamel.yaml import YAML

from mkcv.core.models.resume_design import ResumeDesign, PAGE_SIZE_MAP

logger = logging.getLogger(__name__)


class YamlPostProcessor:
    """Post-processes resume YAML to inject the design section."""

    def __init__(self) -> None:
        self._yaml = YAML()
        self._yaml.preserve_quotes = True  # type: ignore[assignment]

    def inject_design(self, yaml_str: str, design: ResumeDesign) -> str:
        """Replace or insert the design section."""
        data = self._yaml.load(yaml_str)
        if data is None:
            raise ValueError("Empty or invalid YAML")

        # Build the design dict matching RenderCV schema
        design_dict: dict[str, Any] = {"theme": design.theme}

        if design.has_overrides():
            if design.font != "SourceSansPro":
                design_dict["font"] = design.font
            if design.font_size != "10pt":
                design_dict["font_size"] = design.font_size
            if design.page_size != "letterpaper":
                design_dict["page_size"] = PAGE_SIZE_MAP.get(
                    design.page_size, design.page_size
                )
            if design.colors.get("primary") != "003366":
                design_dict["color"] = design.colors.get(
                    "primary", "003366"
                )

        data["design"] = design_dict

        stream = StringIO()
        self._yaml.dump(data, stream)
        return stream.getvalue()

    def inject_theme(self, yaml_str: str, theme: str) -> str:
        """Replace only design.theme, preserving other design fields."""
        data = self._yaml.load(yaml_str)
        if data is None:
            raise ValueError("Empty or invalid YAML")

        if "design" not in data:
            data["design"] = {}
        data["design"]["theme"] = theme

        stream = StringIO()
        self._yaml.dump(data, stream)
        return stream.getvalue()
```

### 5.2 Pipeline Modifications

Key changes to `_structure_yaml()` in `src/mkcv/core/services/pipeline.py`:

```python
async def _structure_yaml(
    self,
    content: TailoredContent,
    kb_text: str,
    *,
    run_dir: Path,
    theme: str = "sb2nov",  # NEW
) -> tuple[str, StageMetadata]:
    """Stage 4: Structure tailored content into RenderCV YAML."""
    # ... existing code ...

    prompt = self._prompts.render(
        "structure_yaml.j2",
        {
            "tailored_content": content.model_dump(),
            "kb_text": kb_text,
            "theme": theme,  # NEW — pass to template
            **self._density_context(),
        },
    )

    # ... existing LLM call ...

    resume_yaml = _strip_code_fences(resume_yaml)

    # NEW: Post-process to ensure correct design section
    if self._resume_design is not None:
        postprocessor = YamlPostProcessor()
        resume_yaml = postprocessor.inject_design(
            resume_yaml, self._resume_design
        )
    else:
        # Phase 1: at minimum, force the correct theme
        postprocessor = YamlPostProcessor()
        resume_yaml = postprocessor.inject_theme(resume_yaml, theme)

    # ... rest of existing code ...
```

### 5.3 Template Modification

In `src/mkcv/prompts/structure_yaml.j2`, line 104:

```yaml
# Before:
design:
  theme: sb2nov

# After:
design:
  theme: {{ theme | default("sb2nov") }}
```

### 5.4 CLI Theme Resolution

In `src/mkcv/cli/commands/generate.py`:

```python
# Before (line 112):
theme: Annotated[str, ...] = "sb2nov",

# After:
theme: Annotated[str | None, ...] = None,
```

And in `_run_pipeline()` / the mode functions, resolve the theme:

```python
from mkcv.core.services.theme import resolve_theme

# In generate_command(), before passing to mode functions:
effective_theme = resolve_theme(theme, settings.rendering.theme)
```

In `src/mkcv/cli/commands/render.py`:

```python
# Before (line 67):
effective_theme = theme if theme is not None else "sb2nov"

# After:
from mkcv.core.services.theme import resolve_theme
effective_theme = resolve_theme(theme, settings.rendering.theme)
```

### 5.5 Factory: Building ResumeDesign from Config

In `src/mkcv/adapters/factory.py`:

```python
def _build_resume_design(config: Configuration, theme: str) -> ResumeDesign:
    """Build a ResumeDesign from configuration settings.

    Args:
        config: Application configuration.
        theme: Resolved theme name.

    Returns:
        ResumeDesign populated from config rendering settings.
    """
    font = str(getattr(config.rendering, "font", "SourceSansPro"))
    font_size = str(getattr(config.rendering, "font_size", "10pt"))
    page_size = str(getattr(config.rendering, "page_size", "letterpaper"))

    colors: dict[str, str] = {"primary": "003366"}
    try:
        overrides = getattr(config.rendering, "overrides", None)
        if overrides is not None:
            primary = getattr(overrides, "primary_color", None)
            if primary:
                colors["primary"] = str(primary)
    except AttributeError:
        pass

    return ResumeDesign(
        theme=theme,
        font=font,
        font_size=font_size,
        page_size=page_size,
        colors=colors,
    )
```

Updated `create_pipeline_service()`:

```python
def create_pipeline_service(
    config: Configuration,
    preset_name: str = "default",
    *,
    provider_override: str | None = None,
    theme: str = "sb2nov",  # NEW
) -> PipelineService:
    """Create a fully-wired PipelineService."""
    # ... existing code ...
    resume_design = _build_resume_design(config, theme)

    return PipelineService(
        providers=providers,
        prompts=prompt_loader,
        artifacts=artifact_store,
        stage_configs=stage_configs,
        preset=preset,
        resume_design=resume_design,  # NEW
    )
```

### 5.6 Custom Theme Discovery

The `discover_custom_themes()` function scans `workspace_root/themes/` for
YAML files, validates them against `CustomTheme`, and converts to `ThemeInfo`:

```python
def discover_custom_themes(workspace_root: Path) -> list[ThemeInfo]:
    """Discover custom themes from workspace themes/ directory."""
    themes_dir = workspace_root / "themes"
    if not themes_dir.is_dir():
        return []

    custom_themes: list[ThemeInfo] = []
    for yaml_file in sorted(themes_dir.glob("*.yaml")):
        try:
            custom = load_custom_theme(yaml_file)
            # Resolve base theme for defaults
            base = get_theme(custom.extends)
            custom_themes.append(
                ThemeInfo(
                    name=custom.name,
                    description=custom.description or f"Custom theme based on {custom.extends}",
                    font_family=custom.overrides.get("font", base.font_family if base else ""),
                    primary_color=custom.overrides.get("primary_color", base.primary_color if base else ""),
                    accent_color=base.accent_color if base else "",
                    page_size=custom.overrides.get("page_size", base.page_size if base else "letterpaper"),
                    source="custom",
                )
            )
        except Exception:
            logger.warning("Invalid custom theme: %s", yaml_file, exc_info=True)

    return custom_themes
```

### 5.7 Workspace Init Scaffolding

In `WorkspaceManager.create_workspace()`, add after the existing template creation:

```python
# Create themes directory and example
themes_dir = workspace_root / "themes"
themes_dir.mkdir(exist_ok=True)
_write_if_missing(
    themes_dir / "example.yaml",
    _EXAMPLE_THEME_TEMPLATE,
)
```

With the template:

```python
_EXAMPLE_THEME_TEMPLATE = """\
# Example custom theme for mkcv
# Rename this file to use it: mv example.yaml mytheme.yaml
#
# Custom themes extend a built-in RenderCV theme with property overrides.
# Available base themes: classic, engineeringclassic, engineeringresumes,
#                        moderncv, sb2nov
#
# applies_to controls which documents use this theme:
#   "all" (default) — both resumes and cover letters
#   "resume"        — resumes only
#   "cover_letter"  — cover letters only
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
```

## 6. RenderCV Integration Notes

### Page Size Mapping

RenderCV uses `"us-letter"` and `"a4"` as page size values (see
`ClassicTheme.Page.size`). The mkcv config uses `"letterpaper"` and
`"a4paper"` (LaTeX conventions). `ResumeDesign` accepts both forms;
`PAGE_SIZE_MAP` normalizes to RenderCV values in the post-processor.

### Theme Name in Generated YAML

RenderCV's `build_rendercv_dictionary_and_model()` reads the `design.theme`
field from the YAML to determine which theme class to instantiate. The
post-processor ensures this field matches the user's selection, overriding
whatever the LLM emitted.

### Custom Theme Rendering

Custom themes don't create new RenderCV theme classes. Instead:
1. The `design.theme` is set to the `extends` base theme.
2. Additional properties (font, colors, page_size) are set as sibling keys
   in the `design:` section.
3. RenderCV applies these overrides to the base theme at parse time.

This approach avoids coupling to RenderCV's internal theme class hierarchy
and uses only its documented YAML schema.

## 7. Testing Strategy

### 7.1 Unit Tests

**`tests/test_core/test_services/test_yaml_postprocessor.py`** (New):

| Test | Description |
|------|-------------|
| `test_inject_theme_replaces_existing_theme` | Given YAML with `design: {theme: sb2nov}`, inject `classic` |
| `test_inject_theme_adds_missing_design_section` | Given YAML with only `cv:`, adds `design: {theme: ...}` |
| `test_inject_theme_preserves_cv_content` | Verify `cv:` section is unchanged after injection |
| `test_inject_design_sets_font` | Verify font override appears in output |
| `test_inject_design_sets_page_size` | Verify page_size override with mapping |
| `test_inject_design_sets_color` | Verify primary_color override |
| `test_inject_design_no_overrides_only_theme` | Default ResumeDesign only sets theme |
| `test_inject_design_handles_multiline_yaml` | Real-world multi-section YAML |
| `test_inject_design_invalid_yaml_raises` | Empty/malformed input raises ValueError |
| `test_inject_theme_preserves_other_design_keys` | Existing `design.font` preserved by `inject_theme()` |

**`tests/test_core/test_models/test_custom_theme.py`** (New):

| Test | Description |
|------|-------------|
| `test_valid_custom_theme` | Valid YAML parses correctly |
| `test_name_validation_rejects_uppercase` | Name must be lowercase |
| `test_name_validation_rejects_special_chars` | Name must be alphanumeric with hyphens |
| `test_extends_defaults_to_classic` | Missing `extends` defaults to `"classic"` |
| `test_overrides_is_optional` | Empty overrides dict is valid |

**`tests/test_core/test_services/test_theme.py`** (New):

| Test | Description |
|------|-------------|
| `test_resolve_theme_cli_wins` | CLI flag overrides config and default |
| `test_resolve_theme_config_fallback` | No CLI flag uses config value |
| `test_resolve_theme_default_fallback` | No CLI and no config uses "sb2nov" |
| `test_discover_custom_themes_empty_dir` | No themes/ dir returns empty list |
| `test_discover_custom_themes_valid_file` | Valid YAML file returns ThemeInfo |
| `test_discover_custom_themes_invalid_file_skipped` | Malformed YAML is skipped with warning |
| `test_discover_custom_themes_name_conflict_with_builtin` | Custom theme with built-in name is rejected |

### 7.2 Modified Tests

**`tests/test_core/test_services/test_render.py`**:
- Update `test_render_resume_delegates_to_renderer` — expect explicit theme, no default
- Update all calls to `render_resume()` to pass `theme` explicitly

**`tests/test_core/test_services/test_pipeline.py`**:
- Add `test_generate_passes_theme_to_stage4_prompt` — verify `theme` in prompt context
- Add `test_generate_with_resume_design_injects_design_section` — verify YAML post-processing
- Add `test_generate_default_theme_when_not_specified` — backward compatibility

**`tests/test_core/test_models/test_theme_info.py`**:
- Add `test_source_defaults_to_builtin` — verify default value
- Add `test_source_can_be_custom` — verify custom source value

**`tests/test_config/test_configuration.py`**:
- Add `test_rendering_overrides_loaded` — verify overrides section parsed
- Add `test_rendering_theme_validator` — verify theme validation

### 7.3 Integration Tests (in existing test files)

- `tests/test_cli/test_generate.py`: Test `--theme classic` flag propagation
- `tests/test_cli/test_render.py`: Test theme resolution from config
- `tests/test_cli/test_themes.py`: Test custom theme display

### 7.4 Test Patterns to Follow

Based on existing tests in the codebase:
- Use `pytest.fixture` for shared test data (`conftest.py` or local).
- Use `MagicMock` for port interfaces (see `test_render.py`).
- Use `StubLLMAdapter` with canned responses for pipeline tests.
- Use `tmp_path` fixture for filesystem operations.
- One assertion per test where practical.
- Descriptive test names: `test_{what}_{condition}_{expected}`.
- Group related tests in classes: `class TestYamlPostProcessorInjectTheme:`.
- Use `_PromptCapture` pattern (from `test_pipeline.py`) to verify prompt context.

## 8. Migration & Backward Compatibility

### Breaking Changes (Controlled)

1. **`RendererPort.render()` signature**: Removing the `theme="sb2nov"` default
   is a breaking change for any code calling `render()` without `theme=`.
   Mitigation: Only internal callers exist (`RenderService` and CLI commands).
   All are updated in the same PR.

2. **`RenderService.render_resume()` signature**: Same as above. All callers
   in `generate.py` and `render.py` already pass `theme` explicitly.

### Non-Breaking Changes

1. **`PipelineService.__init__`**: `resume_design` is added as optional kwarg
   with `None` default. Existing callers unaffected.

2. **`PipelineService.generate()`**: `theme` is added as optional kwarg with
   `None` default. Existing callers unaffected.

3. **`ThemeInfo.source`**: Added with default `"built-in"`. Existing model
   instantiations and tests continue to work.

4. **Config**: `[rendering.overrides]` is a new section. Dynaconf ignores
   unknown sections, so existing configs work unchanged.

5. **CLI `--theme` default**: Changes from hardcoded `"sb2nov"` to
   `settings.rendering.theme` which defaults to `"sb2nov"` in `settings.toml`.
   Users who never changed config see identical behavior.

## 9. Open Questions

1. **ruamel.yaml type stubs**: `ruamel.yaml` has incomplete type stubs. We may
   need a `[[tool.mypy.overrides]]` entry for `ruamel.yaml` with
   `ignore_missing_imports = true`. Need to verify if the existing `ruamel-yaml`
   0.19.1 package includes stubs or if `types-ruamel-yaml` is needed.

2. **RenderCV design field names**: RenderCV's YAML schema uses `font`,
   `font_size`, `page_size`, `color` at the top level of `design:` alongside
   `theme`. Need to verify the exact field names RenderCV accepts in the
   `design:` section (vs. nested under `typography:`, `page:`, `colors:`).
   The post-processor may need to use the nested structure:
   ```yaml
   design:
     theme: classic
     page:
       size: a4
     typography:
       font_family: Charter
       font_size: 11pt
     colors:
       name: "#004080"
   ```
   This needs empirical validation against RenderCV's schema parser.

3. **Custom theme name conflicts**: Should we allow a custom theme to shadow
   a built-in theme name (e.g., a custom `classic.yaml` that overrides the
   built-in Classic theme)? The proposal says no, but there's a case for
   allowing it as an "override" mechanism. Current design: reject conflicts.

4. **Thread safety of ruamel.yaml YAML instance**: The `YAML()` instance in
   `YamlPostProcessor` should be created per-call or confirmed thread-safe.
   Since the pipeline is async (single-threaded event loop), this is likely
   fine, but worth noting for future parallelization.

5. **Config precedence for font/page_size**: The existing `settings.toml`
   already has `font`, `font_size`, and `page_size` directly under
   `[rendering]`. These overlap with what would go in `[rendering.overrides]`.
   Current design: use the existing top-level fields for these common
   properties and reserve `[rendering.overrides]` for less common ones
   (colors, margins). This avoids config migration.

6. **ResumeDesign naming**: The model is called `ResumeDesign` but will serve
   both resumes and cover letters. Should it be renamed to `DocumentDesign`
   now, or deferred? Current decision: keep `ResumeDesign` for this change
   (avoid churn), rename in the follow-up cover letter theming change.

7. **Cover letter Typst template parameterization**: The `cover_letter.typ.j2`
   template hardcodes `#set text(font: "Source Sans Pro", size: 11pt)` and
   `#set page(paper: "us-letter")`. When cover letter theming is implemented,
   these must become template variables. The property names in `ResumeDesign`
   (`font`, `font_size`, `page_size`) are chosen to align with these Typst
   `#set` directives for a smooth transition.

## 10. Cover Letter Compatibility Checklist

This section documents the design constraints that ensure a future cover letter
theming change can be implemented without breaking changes to this system.

- [ ] `resolve_theme()` has no resume-specific imports or logic
- [ ] `ResumeDesign` property names (`font`, `font_size`, `page_size`, `colors`)
      align with what a parameterized `cover_letter.typ.j2` would need
- [ ] `CustomTheme.applies_to` field exists with default `"all"`
- [ ] `ThemeInfo.source` works for both built-in resume themes and future CL themes
- [ ] `[rendering]` config section is not coupled to resume-only concepts
- [ ] `_build_resume_design()` factory helper can be reused by
      `create_cover_letter_service()` in the future
- [ ] Cover letter tests (`tests/test_core/test_services/test_cover_letter.py`,
      `tests/test_cli/test_cover_letter_command.py`, etc.) continue to pass
      after all phases
