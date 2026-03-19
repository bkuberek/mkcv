# Technical Design: Multi-Theme Preview

## Overview

Extend `mkcv render` to accept comma-separated theme names (or `all`) and
render a resume YAML file across multiple themes in a single invocation. Each
theme's output is isolated in a subdirectory to avoid RenderCV's fixed-name
file collisions. Single-theme behavior is preserved unchanged.

---

## Architecture Decisions

### AD-1: BatchRenderService composes RenderService (not RendererPort directly)

**Decision:** `BatchRenderService` depends on `RenderService`, not `RendererPort`.

**Rationale:**
- `RenderService.render_resume()` is the established contract for rendering.
  Bypassing it to use `RendererPort` directly would duplicate the delegation
  logic and couple the batch service to adapter details.
- If `RenderService` gains pre/post-processing logic in the future (logging,
  metrics, caching), `BatchRenderService` inherits it automatically.
- Keeps the dependency graph shallow: CLI -> BatchRenderService -> RenderService -> RendererPort.

**Trade-off:** One extra layer of indirection. Acceptable because `RenderService`
is a thin pass-through today and the composition cost is negligible.

### AD-2: Theme argument parsing lives in `core/services/theme.py`

**Decision:** Add `parse_theme_argument()` to the existing `theme.py` module
rather than handling it in the CLI layer.

**Rationale:**
- Testable in isolation without CLI framework involvement.
- Reusable if other commands (e.g. future `mkcv compare`) need the same parsing.
- Keeps CLI layer thin — it calls `parse_theme_argument()` and branches on the
  result length.
- `theme.py` already owns `discover_themes()` and `resolve_theme()`, so theme
  name validation belongs here.

### AD-3: Output directory strategy — `renders/<theme>/` for multi, unchanged for single

**Decision:**
- **Multi-theme:** Create `<output_dir>/renders/<theme_name>/` per theme.
- **Single-theme:** Use `<output_dir>` directly (current behavior, no `renders/` prefix).

**Rationale:**
- Backward compatible: existing single-theme scripts and workflows see no change.
- The `renders/` prefix groups multi-theme output cleanly and signals it is
  batch-generated (vs. a user's single-render).
- Each theme subdirectory gets its own copy of the YAML variant + all output
  formats, preventing RenderCV's `{Name}_CV.pdf` collisions.

### AD-4: Theme-specific YAML files — write to subdirectory and keep

**Decision:** Write the theme-injected YAML variant to each theme's subdirectory
(`renders/<theme>/resume.yaml`) before rendering. Do **not** clean up afterward.

**Rationale:**
- RenderCV's `build_rendercv_dictionary_and_model()` takes `input_file_path`
  and uses its parent as a reference directory. Writing the variant to the
  theme subdirectory keeps paths consistent.
- Keeping the YAML is useful for debugging (inspect what was rendered),
  re-rendering a single theme manually, and costs negligible disk space.

### AD-5: Per-theme error isolation — catch, record, continue

**Decision:** Catch `RenderError` per theme, record the failure in
`ThemeRenderResult`, and continue rendering remaining themes.

**Rationale:**
- One broken theme (e.g. a custom theme with an invalid Typst template) should
  not block the user from seeing all other themes.
- The summary table clearly shows which themes failed and why.
- Fail-fast validation of theme *names* still happens upfront in
  `parse_theme_argument()` — only *rendering* failures are isolated.

### AD-6: Validate all theme names upfront before rendering any

**Decision:** `parse_theme_argument()` validates every theme name against
`discover_themes()` and raises `RenderError` listing all unknown names
before any rendering begins.

**Rationale:**
- A typo like `--theme sb2nov,clasic` should fail immediately, not after
  successfully rendering sb2nov.
- Upfront validation gives clear, actionable error messages.
- Rendering is the expensive operation; validation is cheap.

---

## Data Flow

### Multi-Theme Render Flow

```
CLI render_command()
│
├─ parse_theme_argument("sb2nov,classic", workspace_root)
│   ├─ Split on ","  →  ["sb2nov", "classic"]
│   ├─ discover_themes(workspace_root)  →  [ThemeInfo, ...]
│   ├─ Validate each name exists
│   └─ Return ["sb2nov", "classic"]
│
├─ len(themes) > 1  →  multi-theme path
│
├─ create_batch_render_service(settings)
│   ├─ RenderCVAdapter()
│   ├─ RenderService(renderer)
│   ├─ YamlPostProcessor()
│   └─ BatchRenderService(render_service, postprocessor)
│
└─ batch_service.render_multi_theme(yaml_path, output_dir, themes, formats)
    │
    ├─ Read source YAML once  →  yaml_str
    │
    ├─ For each theme in ["sb2nov", "classic"]:
    │   ├─ theme_dir = output_dir / "renders" / theme
    │   ├─ theme_dir.mkdir(parents=True, exist_ok=True)
    │   ├─ postprocessor.inject_theme(yaml_str, theme)  →  themed_yaml
    │   ├─ Write themed_yaml  →  theme_dir / yaml_path.name
    │   ├─ render_service.render_resume(themed_yaml_path, theme_dir, theme, formats)
    │   │   └─  →  RenderedOutput
    │   └─ Collect ThemeRenderResult(theme, "success", output)
    │       (or on RenderError: ThemeRenderResult(theme, "error", None, msg))
    │
    └─ Return BatchRenderResult(results=[...])

CLI: Print Rich summary table from BatchRenderResult
```

### Single-Theme Flow (Unchanged)

```
CLI render_command()
│
├─ parse_theme_argument("classic", workspace_root)
│   └─ Return ["classic"]
│
├─ len(themes) == 1  →  single-theme path (existing code)
│
├─ resolve_theme("classic", config_theme)
├─ create_render_service(settings)
└─ service.render_resume(yaml_path, output_dir, theme, formats)
    └─ Print individual file paths (existing output)
```

---

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/mkcv/core/models/batch_render_result.py` | **New** | `ThemeRenderResult` and `BatchRenderResult` Pydantic models |
| `src/mkcv/core/services/batch_render.py` | **New** | `BatchRenderService` orchestrating multi-theme rendering |
| `src/mkcv/core/services/theme.py` | **Modified** | Add `parse_theme_argument()` function |
| `src/mkcv/cli/commands/render.py` | **Modified** | Parse comma-separated themes; branch to batch path |
| `src/mkcv/adapters/factory.py` | **Modified** | Add `create_batch_render_service()` factory function |
| `tests/test_core/test_services/test_batch_render.py` | **New** | Unit tests for `BatchRenderService` |
| `tests/test_core/test_services/test_theme.py` | **Modified** | Tests for `parse_theme_argument()` |
| `tests/test_cli/test_render.py` | **Modified** | CLI integration tests for multi-theme flag (if exists) |

**Totals:** 3 new files, 4–5 modified files.

---

## Interface Definitions

### ThemeRenderResult Model

```python
# src/mkcv/core/models/batch_render_result.py
"""Batch render result models for multi-theme rendering."""

from typing import Literal

from pydantic import BaseModel

from mkcv.core.ports.renderer import RenderedOutput


class ThemeRenderResult(BaseModel):
    """Result of rendering a single theme."""

    theme: str
    status: Literal["success", "error"]
    output: RenderedOutput | None = None
    error_message: str | None = None


class BatchRenderResult(BaseModel):
    """Aggregate result of rendering multiple themes."""

    results: list[ThemeRenderResult]

    @property
    def total(self) -> int:
        """Total number of themes attempted."""
        return len(self.results)

    @property
    def succeeded(self) -> int:
        """Number of themes rendered successfully."""
        return sum(1 for r in self.results if r.status == "success")

    @property
    def failed(self) -> int:
        """Number of themes that failed to render."""
        return sum(1 for r in self.results if r.status == "error")

    @property
    def all_succeeded(self) -> bool:
        """Whether every theme rendered successfully."""
        return self.failed == 0
```

### BatchRenderService

```python
# src/mkcv/core/services/batch_render.py
"""Batch rendering service for multi-theme resume rendering."""

import logging
from pathlib import Path

from mkcv.core.exceptions.render import RenderError
from mkcv.core.models.batch_render_result import (
    BatchRenderResult,
    ThemeRenderResult,
)
from mkcv.core.services.render import RenderService
from mkcv.core.services.yaml_postprocessor import YamlPostProcessor

logger = logging.getLogger(__name__)


class BatchRenderService:
    """Renders a resume across multiple themes.

    Composes RenderService and YamlPostProcessor to iterate over
    a list of themes, injecting each theme into the YAML and
    rendering to an isolated subdirectory.
    """

    def __init__(
        self,
        render_service: RenderService,
        postprocessor: YamlPostProcessor,
    ) -> None:
        self._render_service = render_service
        self._postprocessor = postprocessor

    def render_multi_theme(
        self,
        yaml_path: Path,
        output_dir: Path,
        themes: list[str],
        *,
        formats: list[str] | None = None,
    ) -> BatchRenderResult:
        """Render a resume YAML across multiple themes.

        Each theme's output is placed in output_dir/renders/<theme>/.
        The source YAML is read once and a theme-injected variant is
        written to each subdirectory before rendering.

        Per-theme rendering errors are caught and recorded; remaining
        themes continue rendering.

        Args:
            yaml_path: Path to the source RenderCV YAML file.
            output_dir: Base output directory.
            themes: List of validated theme names.
            formats: Output formats (e.g. ["pdf", "png"]).

        Returns:
            BatchRenderResult with per-theme outcomes.

        Raises:
            RenderError: If the source YAML file cannot be read.
        """
        resolved_yaml = yaml_path.resolve()
        if not resolved_yaml.is_file():
            raise RenderError(f"YAML file not found: {resolved_yaml}")

        try:
            yaml_str = resolved_yaml.read_text(encoding="utf-8")
        except OSError as exc:
            raise RenderError(
                f"Failed to read YAML file: {resolved_yaml}"
            ) from exc

        results: list[ThemeRenderResult] = []

        for theme in themes:
            result = self._render_single_theme(
                yaml_str=yaml_str,
                source_filename=resolved_yaml.name,
                output_dir=output_dir,
                theme=theme,
                formats=formats,
            )
            results.append(result)

        return BatchRenderResult(results=results)

    def _render_single_theme(
        self,
        *,
        yaml_str: str,
        source_filename: str,
        output_dir: Path,
        theme: str,
        formats: list[str] | None,
    ) -> ThemeRenderResult:
        """Render a single theme, catching errors.

        Args:
            yaml_str: Source YAML content.
            source_filename: Original YAML filename (for the variant).
            output_dir: Base output directory.
            theme: Theme name to inject.
            formats: Output formats.

        Returns:
            ThemeRenderResult with success or error status.
        """
        theme_dir = output_dir / "renders" / theme
        try:
            theme_dir.mkdir(parents=True, exist_ok=True)

            # Inject theme into YAML
            themed_yaml = self._postprocessor.inject_theme(yaml_str, theme)

            # Write variant to theme subdirectory
            variant_path = theme_dir / source_filename
            variant_path.write_text(themed_yaml, encoding="utf-8")

            # Render
            logger.info("Rendering theme '%s' to %s", theme, theme_dir)
            output = self._render_service.render_resume(
                variant_path,
                theme_dir,
                theme=theme,
                formats=formats,
            )

            return ThemeRenderResult(
                theme=theme,
                status="success",
                output=output,
            )

        except (RenderError, ValueError, OSError) as exc:
            logger.warning(
                "Failed to render theme '%s': %s", theme, exc, exc_info=True
            )
            return ThemeRenderResult(
                theme=theme,
                status="error",
                error_message=str(exc),
            )
```

### parse_theme_argument (addition to theme.py)

```python
# Addition to src/mkcv/core/services/theme.py

def parse_theme_argument(
    raw: str,
    workspace_root: Path | None = None,
) -> list[str]:
    """Parse a CLI --theme value into a validated list of theme names.

    Handles:
    - Single theme name: "classic" -> ["classic"]
    - Comma-separated: "sb2nov,classic" -> ["sb2nov", "classic"]
    - The keyword "all": expands to every discovered theme name.

    All theme names are validated against discovered themes.

    Args:
        raw: Raw --theme argument string.
        workspace_root: Optional workspace root for custom theme discovery.

    Returns:
        List of validated theme name strings.

    Raises:
        RenderError: If any theme name is not recognized.
    """
    from mkcv.core.exceptions.render import RenderError

    stripped = raw.strip().lower()

    available = discover_themes(workspace_root)
    available_names = {t.name.lower(): t.name for t in available}

    if stripped == "all":
        return [t.name for t in available]

    raw_names = [name.strip() for name in raw.split(",") if name.strip()]
    if not raw_names:
        raise RenderError("No theme names provided in --theme argument.")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_names: list[str] = []
    for name in raw_names:
        lower = name.lower()
        if lower not in seen:
            seen.add(lower)
            unique_names.append(name)

    # Validate all names exist
    unknown = [
        name for name in unique_names if name.lower() not in available_names
    ]
    if unknown:
        available_list = ", ".join(sorted(available_names.values()))
        raise RenderError(
            f"Unknown theme(s): {', '.join(unknown)}. "
            f"Available: {available_list}"
        )

    # Return canonical names (from ThemeInfo, not user input casing)
    return [available_names[name.lower()] for name in unique_names]
```

### Factory Function (addition to factory.py)

```python
# Addition to src/mkcv/adapters/factory.py

def create_batch_render_service(
    config: Configuration,
) -> BatchRenderService:
    """Create a fully-wired BatchRenderService.

    Args:
        config: Application configuration.

    Returns:
        BatchRenderService with RenderService and YamlPostProcessor.
    """
    from mkcv.core.services.batch_render import BatchRenderService
    from mkcv.core.services.yaml_postprocessor import YamlPostProcessor

    render_service = create_render_service(config)
    postprocessor = YamlPostProcessor()
    return BatchRenderService(
        render_service=render_service,
        postprocessor=postprocessor,
    )
```

### CLI Modifications (render.py)

```python
# Modified render_command in src/mkcv/cli/commands/render.py
# Key changes shown as diff-style pseudocode:

from mkcv.core.services.theme import parse_theme_argument, resolve_theme

def render_command(
    yaml_file: ...,
    *,
    output_dir: ... = None,
    theme: str | None = None,      # unchanged signature
    format: str = "pdf,png",
    open: bool = False,
) -> None:
    resolved_yaml = yaml_file.resolve()
    # ... existing validation ...

    effective_output_dir = (
        output_dir if output_dir is not None else resolved_yaml.parent
    )
    requested_formats = [f.strip() for f in format.split(",") if f.strip()]

    # NEW: Parse theme argument for multi-theme support
    if theme is not None and ("," in theme or theme.strip().lower() == "all"):
        # Multi-theme path
        themes = parse_theme_argument(theme, settings.workspace_root)
        _render_multi_theme(
            resolved_yaml, effective_output_dir, themes, requested_formats, open
        )
    else:
        # Single-theme path (existing behavior, unchanged)
        effective_theme = resolve_theme(theme, settings.rendering.theme)
        service = create_render_service(settings)
        result = service.render_resume(
            resolved_yaml, effective_output_dir,
            theme=effective_theme, formats=requested_formats,
        )
        # ... existing output printing ...


def _render_multi_theme(
    yaml_path: Path,
    output_dir: Path,
    themes: list[str],
    formats: list[str],
    open_pdf: bool,
) -> None:
    """Render across multiple themes and print summary table."""
    from rich.table import Table

    from mkcv.adapters.factory import create_batch_render_service

    service = create_batch_render_service(settings)
    batch_result = service.render_multi_theme(
        yaml_path, output_dir, themes, formats=formats,
    )

    # Print Rich summary table
    table = Table(title="Multi-Theme Render Results")
    table.add_column("Theme", style="cyan")
    table.add_column("Status")
    table.add_column("PDF Path")

    for r in batch_result.results:
        if r.status == "success" and r.output and r.output.pdf_path:
            table.add_row(
                r.theme,
                "[green]OK[/green]",
                str(r.output.pdf_path),
            )
        else:
            table.add_row(
                r.theme,
                "[red]FAIL[/red]",
                r.error_message or "Unknown error",
            )

    console.print()
    console.print(table)
    console.print(
        f"\n  [bold]{batch_result.succeeded}/{batch_result.total}[/bold] "
        f"themes rendered successfully."
    )

    if batch_result.failed > 0:
        console.print(
            f"  [yellow]{batch_result.failed} theme(s) failed.[/yellow]"
        )
        console.print()
        sys.exit(6)

    console.print()

    # Open first successful PDF if --open was requested
    if open_pdf:
        first_success = next(
            (r for r in batch_result.results
             if r.status == "success" and r.output and r.output.pdf_path.exists()),
            None,
        )
        if first_success and first_success.output:
            _open_file(first_success.output.pdf_path)
```

---

## Output Directory Layout

### Multi-Theme: `mkcv render resume.yaml --theme sb2nov,classic,moderncv`

```
applications/company/2026-01-swe/
├── resume.yaml                          # Original (untouched)
└── renders/
    ├── sb2nov/
    │   ├── resume.yaml                  # Theme-injected variant
    │   ├── John_Doe_CV.pdf
    │   └── John_Doe_CV_1.png
    ├── classic/
    │   ├── resume.yaml
    │   ├── John_Doe_CV.pdf
    │   └── John_Doe_CV_1.png
    └── moderncv/
        ├── resume.yaml
        ├── John_Doe_CV.pdf
        └── John_Doe_CV_1.png
```

### Single-Theme: `mkcv render resume.yaml --theme classic` (unchanged)

```
applications/company/2026-01-swe/
├── resume.yaml                          # Original
├── John_Doe_CV.pdf                      # Directly in output dir
└── John_Doe_CV_1.png
```

---

## Testing Strategy

### Unit Tests: `tests/test_core/test_services/test_batch_render.py`

| Test | Description |
|------|-------------|
| `test_render_multi_theme_two_themes_success` | Both themes render; result has 2 successes, 0 failures |
| `test_render_multi_theme_one_failure_continues` | First theme fails, second succeeds; result has 1 success, 1 failure |
| `test_render_multi_theme_all_fail` | Both themes fail; result has 0 successes |
| `test_render_multi_theme_creates_subdirectories` | Verifies `renders/<theme>/` dirs exist |
| `test_render_multi_theme_writes_themed_yaml` | Variant YAML written to each theme dir |
| `test_render_multi_theme_injects_theme_correctly` | `inject_theme()` called with correct theme name |
| `test_render_multi_theme_source_yaml_not_found` | Raises `RenderError` immediately (no partial results) |
| `test_render_multi_theme_passes_formats` | Formats forwarded to RenderService |

**Mock strategy:** Mock `RenderService.render_resume()` (return `RenderedOutput` or
raise `RenderError`). Use a real `YamlPostProcessor` (no external deps, fast).
Use `tmp_path` for output directory.

### Unit Tests: `tests/test_core/test_services/test_theme.py` (additions)

| Test | Description |
|------|-------------|
| `test_parse_theme_argument_single_theme` | `"classic"` -> `["classic"]` |
| `test_parse_theme_argument_multiple_themes` | `"sb2nov,classic"` -> `["sb2nov", "classic"]` |
| `test_parse_theme_argument_all_keyword` | `"all"` -> all discovered theme names |
| `test_parse_theme_argument_whitespace_handling` | `" sb2nov , classic "` -> `["sb2nov", "classic"]` |
| `test_parse_theme_argument_case_insensitive` | `"Classic"` -> `["classic"]` (canonical name) |
| `test_parse_theme_argument_deduplication` | `"sb2nov,sb2nov"` -> `["sb2nov"]` |
| `test_parse_theme_argument_unknown_theme_raises` | `"notreal"` -> `RenderError` with available list |
| `test_parse_theme_argument_partial_unknown_raises` | `"sb2nov,notreal"` -> `RenderError` |
| `test_parse_theme_argument_empty_raises` | `""` -> `RenderError` |

**Mock strategy:** Mock `discover_themes()` to return a fixed list of `ThemeInfo`
objects, avoiding dependency on RenderCV being installed.

### Model Tests: `tests/test_core/test_models/test_batch_render_result.py`

| Test | Description |
|------|-------------|
| `test_batch_render_result_counts` | Verify `total`, `succeeded`, `failed` properties |
| `test_batch_render_result_all_succeeded` | `all_succeeded` is True when no failures |
| `test_batch_render_result_not_all_succeeded` | `all_succeeded` is False with any failure |
| `test_theme_render_result_success` | Success result has output, no error_message |
| `test_theme_render_result_error` | Error result has error_message, no output |

---

## Backward Compatibility

| Aspect | Impact |
|--------|--------|
| `--theme classic` (single theme) | **No change.** Exact same code path, same output location. |
| `--theme` not provided | **No change.** Falls through to `resolve_theme()` as before. |
| `RenderService` API | **No change.** No modifications to existing method signatures. |
| `RendererPort` interface | **No change.** No modifications to the port. |
| `YamlPostProcessor` | **No change.** `inject_theme()` used as-is. |
| Factory functions | **Additive only.** New `create_batch_render_service()` added; existing functions untouched. |
| Output directories | Multi-theme creates new `renders/` subtree. Single-theme output location unchanged. |
| Exit codes | Multi-theme with failures exits with code 6 (`RenderError`). Matches existing convention. |

---

## Open Questions

1. **Should `--theme all` require workspace context?** Currently `discover_themes()`
   works without a workspace (returns only built-in themes). This is fine — if
   the user is outside a workspace, `all` just means all 5 built-in themes. No
   action needed unless we want to warn when outside a workspace.

2. **Should `parse_theme_argument()` be called even for single themes?** The
   current design only routes through `parse_theme_argument()` when commas or
   `all` are detected. An alternative is to always use it (giving free validation
   of single theme names against discovered themes). **Recommendation:** Keep the
   current approach — single-theme validation is deferred to RenderCV, which
   gives specific error messages. Adding upfront validation for single themes
   could be a follow-up.

3. **Rich table formatting for `--open`:** When `--open` is used with multi-theme,
   the design opens only the first successful PDF. Should it open all? Or prompt?
   **Recommendation:** Open only the first — opening 5 PDFs at once is not useful.
   Document this behavior.
