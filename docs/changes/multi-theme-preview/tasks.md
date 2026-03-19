# Tasks: Multi-Theme Preview

## Phase 1: Core Models & Service (Foundation)

- [x] **1.1** Create `src/mkcv/core/models/batch_render_result.py` with `ThemeRenderResult` and `BatchRenderResult` Pydantic models.
  - `ThemeRenderResult`: fields `theme: str`, `status: Literal["success", "error"]`, `output: RenderedOutput | None = None`, `error_message: str | None = None`.
  - `BatchRenderResult`: field `results: list[ThemeRenderResult]`, properties `total`, `succeeded`, `failed` (returning `int`), and `all_succeeded` (returning `bool`).
  - Import `RenderedOutput` from `mkcv.core.ports.renderer`.
  - Follow one-class-per-file pattern; both models in same file since they're tightly coupled (matches design doc).
  - **Verify:** `uv run python -c "from mkcv.core.models.batch_render_result import BatchRenderResult, ThemeRenderResult; print('OK')"`

- [x] **1.2** Add `parse_theme_argument()` function to `src/mkcv/core/services/theme.py`.
  - Signature: `parse_theme_argument(raw: str, workspace_root: Path | None = None) -> list[str]`.
  - Handle single theme (`"classic"` -> `["classic"]`), comma-separated (`"sb2nov,classic"` -> `["sb2nov", "classic"]`), and `"all"` keyword (case-insensitive, expands via `discover_themes()`).
  - Reject `"all"` mixed with other names (e.g. `"all,classic"`) — raise `RenderError` with message that `all` cannot be combined with other theme names. (See spec `batch-render/spec.md` scenario "all mixed with explicit names is rejected".)
  - Trim whitespace around commas, ignore empty segments, deduplicate preserving first-occurrence order.
  - Validate all names against `discover_themes()` (case-insensitive); raise `RenderError` listing all unknown names + available themes if any are invalid.
  - Return canonical theme names (from `ThemeInfo.name`, not user input casing).
  - Raise `RenderError` on empty input after stripping.
  - Import `RenderError` inside the function body (lazy import, matching design doc pattern).
  - **Verify:** `uv run python -c "from mkcv.core.services.theme import parse_theme_argument; print('OK')"`

- [x] **1.3** Create `src/mkcv/core/services/batch_render.py` with `BatchRenderService` class.
  - Constructor: `__init__(self, render_service: RenderService, postprocessor: YamlPostProcessor) -> None`.
  - Method: `render_multi_theme(self, yaml_path: Path, output_dir: Path, themes: list[str], *, formats: list[str] | None = None) -> BatchRenderResult`.
  - Read source YAML once; raise `RenderError` if file not found or unreadable.
  - For each theme: create `output_dir / "renders" / theme` dir, call `postprocessor.inject_theme()`, write variant YAML to theme subdir, call `render_service.render_resume()` with variant path and theme subdir.
  - Private `_render_single_theme()` method catches `RenderError | ValueError | OSError`, returns `ThemeRenderResult` with status `"error"` on failure, `"success"` on success.
  - Use `logging.getLogger(__name__)` for `logger.info` on render start and `logger.warning` on failure.
  - **Verify:** `uv run python -c "from mkcv.core.services.batch_render import BatchRenderService; print('OK')"`

- [x] **1.4** Add `create_batch_render_service()` factory function to `src/mkcv/adapters/factory.py`.
  - Signature: `create_batch_render_service(config: Configuration) -> BatchRenderService`.
  - Lazy-import `BatchRenderService` and `YamlPostProcessor` inside the function body (matching existing factory pattern, see `create_cover_letter_service` at line 454).
  - Call existing `create_render_service(config)` for `RenderService`, instantiate `YamlPostProcessor()`, wire into `BatchRenderService`.
  - Add necessary `TYPE_CHECKING` import or direct import for `BatchRenderService` return type annotation.
  - **Verify:** `uv run python -c "from mkcv.adapters.factory import create_batch_render_service; print('OK')"`

## Phase 2: CLI Integration

- [x] **2.1** Modify `src/mkcv/cli/commands/render.py` to detect multi-theme and dispatch to `BatchRenderService`.
  - Add import: `from mkcv.core.services.theme import parse_theme_argument` (alongside existing `resolve_theme` import on line 14).
  - In `render_command()` (line 19), after computing `effective_output_dir` and `requested_formats` (lines 69-73), add a branch:
    - If `theme is not None and ("," in theme or theme.strip().lower() == "all")`: call `parse_theme_argument(theme, settings.workspace_root)` to get `themes: list[str]`, then delegate to a new `_render_multi_theme()` helper and `return`.
    - Else: existing single-theme path (lines 72-96) unchanged.
  - Access `settings.workspace_root` — check that `settings` (imported from `mkcv.config` at line 13) exposes `workspace_root`. If it's on the `Configuration` object, use the appropriate attribute.
  - **Verify:** `uv run python -c "from mkcv.cli.commands.render import render_command; print('OK')"`

- [x] **2.2** Add `_render_multi_theme()` helper function to `src/mkcv/cli/commands/render.py`.
  - Signature: `_render_multi_theme(yaml_path: Path, output_dir: Path, themes: list[str], formats: list[str], open_pdf: bool) -> None`.
  - Lazy-import `create_batch_render_service` from `mkcv.adapters.factory` and `Table` from `rich.table`.
  - Create service via `create_batch_render_service(settings)`, call `service.render_multi_theme(yaml_path, output_dir, themes, formats=formats)`.
  - Print progress line before each theme render: `Rendering theme {n}/{total}: {theme_name}...` per batch-render-ux spec. This requires either: (a) adding a callback/progress hook to `BatchRenderService`, or (b) printing progress in the CLI by iterating themes and calling per-theme directly. **Preferred approach (b):** add progress printing in `_render_multi_theme` by calling `batch_service.render_multi_theme()` which handles iteration internally — then print progress via the `BatchRenderResult` after. Alternatively, print progress line before delegating to the batch service by iterating in the CLI. **Decision:** Keep `BatchRenderService` clean; print `Rendering theme {n}/{total}: {theme}...` in `_render_multi_theme` by calling `service.render_multi_theme()` once (progress will be logged, not printed). For actual per-theme CLI progress, add a `console.print` per theme by exposing a per-theme method or accepting a callback. **Simplest:** just print progress lines in `_render_multi_theme` before the batch call indicating total count, and let the summary table serve as the detailed feedback.
  - Build and print Rich `Table` with columns: "Theme" (cyan), "Status", "PDF Path".
    - Success rows: theme name, `[green]OK[/green]`, PDF path string.
    - Error rows: theme name, `[red]FAIL[/red]`, error message.
  - Print summary line: `{succeeded}/{total} themes rendered successfully.`
  - If `batch_result.failed > 0`: print warning line and `sys.exit(6)`.
  - **Verify:** `uv run python -c "from mkcv.cli.commands.render import _render_multi_theme; print('OK')"`

- [x] **2.3** Handle `--open` flag for multi-theme in `_render_multi_theme()`.
  - If `open_pdf` is `True`: find first `ThemeRenderResult` with `status == "success"` and `output.pdf_path.exists()`, call existing `_open_file()` with that path.
  - If no successful result exists, skip opening silently.
  - **Verify:** Manual code review — this is part of task 2.2 implementation but listed separately for traceability to the spec requirement "Batch Render with --open Flag".

## Phase 3: Tests

- [x] **3.1** Create `tests/test_core/test_models/test_batch_render_result.py` with unit tests for the model.
  - Test class `TestThemeRenderResult`:
    - `test_success_result_has_output_no_error`: Create with `status="success"`, `output=RenderedOutput(...)`, verify `error_message is None`.
    - `test_error_result_has_message_no_output`: Create with `status="error"`, `error_message="fail"`, verify `output is None`.
  - Test class `TestBatchRenderResult`:
    - `test_total_counts_all_results`: 3 results -> `total == 3`.
    - `test_succeeded_counts_success_only`: 2 success + 1 error -> `succeeded == 2`.
    - `test_failed_counts_errors_only`: 2 success + 1 error -> `failed == 1`.
    - `test_all_succeeded_true_when_no_failures`: 2 success -> `all_succeeded is True`.
    - `test_all_succeeded_false_with_any_failure`: 1 success + 1 error -> `all_succeeded is False`.
  - Use `tmp_path` for creating `RenderedOutput` with real temp file paths (matching pattern from `tests/test_cli/test_render.py` fixture).
  - **Verify:** `uv run pytest tests/test_core/test_models/test_batch_render_result.py -v`

- [x] **3.2** Add `TestParseThemeArgument` class to `tests/test_core/test_services/test_theme.py` with tests for `parse_theme_argument()`.
  - All tests mock `discover_themes()` via `@patch("mkcv.core.services.theme.discover_themes")` to return a fixed list of `ThemeInfo` objects (e.g. classic, sb2nov, moderncv, engineeringclassic, engineeringresumes).
  - Tests (matching spec scenarios):
    - `test_single_theme`: `"classic"` -> `["classic"]`
    - `test_multiple_themes`: `"sb2nov,classic"` -> `["sb2nov", "classic"]`
    - `test_all_keyword_expands`: `"all"` -> all 5 names
    - `test_all_case_insensitive`: `"ALL"` -> same as `"all"`
    - `test_whitespace_trimmed`: `" sb2nov , classic "` -> `["sb2nov", "classic"]`
    - `test_empty_segments_ignored`: `"sb2nov,,classic,"` -> `["sb2nov", "classic"]`
    - `test_deduplication_preserves_order`: `"classic,sb2nov,classic"` -> `["classic", "sb2nov"]`
    - `test_case_insensitive_resolution`: `"SB2NOV"` -> `["sb2nov"]` (canonical name)
    - `test_unknown_theme_raises_render_error`: `"nonexistent"` -> raises `RenderError` mentioning "nonexistent" and listing available themes
    - `test_partial_unknown_raises_with_all_bad_names`: `"sb2nov,bad1,classic,bad2"` -> raises `RenderError` mentioning both "bad1" and "bad2"
    - `test_empty_string_raises`: `""` -> raises `RenderError`
    - `test_all_mixed_with_names_raises`: `"all,classic"` -> raises `RenderError` indicating `all` cannot be combined
  - **Verify:** `uv run pytest tests/test_core/test_services/test_theme.py::TestParseThemeArgument -v`

- [x] **3.3** Create `tests/test_core/test_services/test_batch_render.py` with unit tests for `BatchRenderService`.
  - Use `tmp_path` for output directory and source YAML file.
  - Mock `RenderService.render_resume()` (return `RenderedOutput` or raise `RenderError`).
  - Use a real `YamlPostProcessor` (no external deps, fast) — create minimal YAML: `"cv:\n  name: Test\ndesign:\n  theme: sb2nov\n"`.
  - Test class `TestBatchRenderService`:
    - `test_render_two_themes_success`: Both succeed; result has `total==2`, `succeeded==2`, `failed==0`.
    - `test_one_failure_continues_to_next`: First theme raises `RenderError`; second succeeds; result has 1 success, 1 failure.
    - `test_all_themes_fail`: Both raise `RenderError`; result has 0 successes, no exception raised.
    - `test_creates_theme_subdirectories`: Verify `output_dir / "renders" / theme` dirs exist after render.
    - `test_writes_themed_yaml_variant`: Verify variant YAML file exists at `theme_dir / source_filename` and contains injected theme name.
    - `test_injects_theme_correctly`: Verify `inject_theme` produces YAML with correct `design.theme` value per theme.
    - `test_source_yaml_not_found_raises`: Pass nonexistent path; raises `RenderError` immediately (no partial results).
    - `test_formats_passed_to_render_service`: Verify `formats` kwarg forwarded to `render_service.render_resume()`.
  - **Verify:** `uv run pytest tests/test_core/test_services/test_batch_render.py -v`

- [x] **3.4** Add multi-theme render tests to `tests/test_cli/test_render.py`.
  - Test class `TestRenderMultiTheme`:
    - `test_comma_separated_theme_dispatches_to_batch_service`: Pass `theme="sb2nov,classic"`, mock `parse_theme_argument` and `create_batch_render_service`, verify batch service called instead of single-theme `create_render_service`.
    - `test_all_keyword_dispatches_to_batch_service`: Pass `theme="all"`, verify dispatch to batch path.
    - `test_single_theme_unchanged`: Pass `theme="classic"` (no comma, not "all"), verify existing single-theme path still used (`create_render_service` called, not batch).
    - `test_no_theme_flag_unchanged`: Pass no `theme`, verify single-theme path with `resolve_theme`.
  - Mock `parse_theme_argument`, `create_batch_render_service`, the batch service's `render_multi_theme` return value, and `settings.workspace_root`.
  - Use `@patch` on `mkcv.cli.commands.render.parse_theme_argument` and `mkcv.cli.commands.render.create_batch_render_service` (or their import paths in the render module).
  - **Verify:** `uv run pytest tests/test_cli/test_render.py::TestRenderMultiTheme -v`

## Phase 4: Verification

- [x] **4.1** Run full test suite: `uv run pytest --tb=short`.
  - All existing tests must still pass (backward compatibility).
  - All new tests from Phase 3 must pass.

- [x] **4.2** Run type checker: `uv run mypy src/`.
  - Must pass with `--strict` (project default).
  - Pay attention to `BatchRenderService` constructor types, `RenderedOutput | None` optionals, and `Literal["success", "error"]` usage.

- [x] **4.3** Run linter and formatter: `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`.
  - Fix any lint or format violations.

- [x] **4.4** Verify single-theme backward compatibility manually.
  - Confirm `render_command(yaml_file, theme="classic")` still takes the existing code path (no `BatchRenderService` involved).
  - Confirm `render_command(yaml_file)` (no `--theme`) still works via `resolve_theme()`.
  - This can be verified by reviewing that existing `TestRenderThemeAndOutputDir` tests still pass unmodified.
