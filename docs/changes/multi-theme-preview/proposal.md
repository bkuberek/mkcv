# Proposal: Multi-Theme Preview

## Intent

Users want to visually compare how their resume looks across different themes
before committing to one. Today `mkcv render` only renders a single theme per
invocation, and RenderCV's fixed output naming (`{Name}_CV.pdf`) means
sequential single-theme renders to the same directory silently overwrite each
other. This change lets users render one resume across multiple (or all) themes
in a single command, with each theme's output isolated in its own subdirectory.

## Scope

### In Scope

- Extend the existing `--theme` CLI flag to accept comma-separated theme names
  (e.g. `--theme sb2nov,classic,moderncv`)
- Support the special value `all` to render every discovered theme
  (`--theme all`)
- Create theme-specific subdirectories under the output dir
  (`renders/<theme>/`) to prevent filename collisions
- New `BatchRenderService` in `core/services/` that orchestrates multi-theme
  rendering using existing `RenderService` and `YamlPostProcessor.inject_theme()`
- New `BatchRenderResult` model to aggregate per-theme results
- Factory function `create_batch_render_service()` in `adapters/factory.py`
- Rich summary table printed after batch render showing theme, status, and
  output paths

### Out of Scope

- Cover letter multi-theme rendering (uses a separate Typst renderer, not
  RenderCV themes)
- Parallel/concurrent rendering (sequential is correct and simple; can be
  added later if ~15 sec for 5 themes becomes a bottleneck)
- Side-by-side visual comparison UI (future enhancement)
- New CLI subcommand (`mkcv compare`) -- this extends the existing `render`
  command instead

## Approach

1. **CLI layer** (`cli/commands/render.py`): Parse `--theme` value for commas
   and the keyword `all`. When a single theme is given, behavior is unchanged.
   When multiple themes are detected, delegate to `BatchRenderService` instead
   of `RenderService`.

2. **Theme resolution** (`core/services/theme.py`): Add a
   `parse_theme_argument(raw: str, workspace_root: Path | None) -> list[str]`
   helper that returns a list of theme names -- splitting on commas, expanding
   `all` via `discover_themes()`, and validating each name exists.

3. **Batch service** (`core/services/batch_render.py` -- new file): Iterates
   over the theme list. For each theme:
   - Read the source YAML once
   - Call `YamlPostProcessor.inject_theme()` to produce a theme-specific YAML
     variant
   - Write the variant to `<output_dir>/<theme>/resume.yaml`
   - Delegate to `RenderService.render_resume()` with that variant and
     subdirectory as output
   - Collect `RenderedOutput` per theme into `BatchRenderResult`

4. **Model** (`core/models/batch_render_result.py` -- new file): Pydantic
   model holding `list[ThemeRenderResult]` where each entry has the theme name,
   status (success/error), `RenderedOutput | None`, and optional error message.

5. **Factory** (`adapters/factory.py`): Add `create_batch_render_service()`
   that wires `RenderService`, `YamlPostProcessor`, and the theme resolution
   function.

6. **Output**: After rendering, print a Rich table summarizing each theme's
   status and PDF path. Single-theme rendering output remains unchanged.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/mkcv/cli/commands/render.py` | Modified | Parse comma-separated themes; branch to batch service for multi-theme |
| `src/mkcv/core/services/theme.py` | Modified | Add `parse_theme_argument()` helper |
| `src/mkcv/core/services/batch_render.py` | New | `BatchRenderService` orchestrating multi-theme rendering |
| `src/mkcv/core/models/batch_render_result.py` | New | `BatchRenderResult` and `ThemeRenderResult` models |
| `src/mkcv/adapters/factory.py` | Modified | Add `create_batch_render_service()` factory function |
| `tests/test_core/test_batch_render.py` | New | Unit tests for `BatchRenderService` |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Invalid theme name in comma list causes confusing partial failure | Medium | Validate all theme names upfront in `parse_theme_argument()` before rendering any; fail fast with clear error listing unknown themes |
| Disk space from rendering all themes (~5 PDFs + PNGs) | Low | Each PDF is ~100KB; negligible. Document that `--theme all` creates one subdirectory per theme |
| RenderCV error on one theme aborts entire batch | Medium | Catch per-theme errors, record in `ThemeRenderResult`, continue with remaining themes, report failures in summary table |
| Ambiguity: user has a custom theme literally named "all" | Low | Reserve `all` as keyword; document it; reject custom themes named "all" during validation |

## Rollback Plan

All changes are additive. The single-theme code path is untouched when
`--theme` contains no commas and is not `all`. To rollback:

1. Revert the 3 modified files to their prior state (the single-theme path
   is preserved)
2. Delete the 3 new files (`batch_render.py`, `batch_render_result.py`,
   `test_batch_render.py`)

No data migration, no config schema changes, no database changes.

## Dependencies

- **theme-system-overhaul** (completed): `YamlPostProcessor.inject_theme()`,
  `discover_themes()`, `resolve_theme()` -- all already landed
- **RenderCV**: No changes required; we call `RenderService.render_resume()`
  with different output dirs
- **Rich**: Already a dependency; used for the summary table

## Success Criteria

- [ ] `mkcv render resume.yaml --theme sb2nov,classic` produces two subdirs
      with correct PDFs
- [ ] `mkcv render resume.yaml --theme all` renders every discovered theme
- [ ] `mkcv render resume.yaml --theme classic` (single theme) behavior is
      unchanged
- [ ] Invalid theme names produce a clear error before any rendering starts
- [ ] One theme failing mid-batch does not prevent other themes from rendering
- [ ] Rich summary table displays theme name, status, and PDF path for each
- [ ] All new code has unit tests with mocked renderer
- [ ] `mypy --strict` and `ruff check` pass
