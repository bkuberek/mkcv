# Batch Render Specification

## Purpose

Defines the behavior for rendering a single resume YAML across multiple themes
in one invocation, including theme argument parsing, validation, per-theme
rendering with error isolation, and output organization.

## Requirements

### Requirement: Multi-Theme Argument Parsing

The `--theme` CLI flag MUST accept a comma-separated list of theme names
(e.g. `--theme sb2nov,classic,moderncv`). Whitespace around commas MUST be
trimmed. Empty segments between commas MUST be ignored.

#### Scenario: Comma-separated theme list

- GIVEN the user invokes `mkcv render resume.yaml --theme sb2nov,classic,moderncv`
- WHEN the CLI parses the `--theme` argument
- THEN `parse_theme_argument` returns the list `["sb2nov", "classic", "moderncv"]`

#### Scenario: Whitespace around commas is trimmed

- GIVEN the user invokes `mkcv render resume.yaml --theme "sb2nov , classic"`
- WHEN the CLI parses the `--theme` argument
- THEN `parse_theme_argument` returns `["sb2nov", "classic"]`

#### Scenario: Empty segments are ignored

- GIVEN the user invokes `mkcv render resume.yaml --theme "sb2nov,,classic,"`
- WHEN the CLI parses the `--theme` argument
- THEN `parse_theme_argument` returns `["sb2nov", "classic"]`

#### Scenario: Duplicate theme names are deduplicated

- GIVEN the user invokes `mkcv render resume.yaml --theme "classic,sb2nov,classic"`
- WHEN the CLI parses the `--theme` argument
- THEN `parse_theme_argument` returns `["classic", "sb2nov"]`
- AND the order of first occurrence is preserved

### Requirement: Expand "all" Keyword

The special value `all` (case-insensitive) MUST expand to every theme returned
by `discover_themes()`. The keyword `all` MUST be reserved and SHALL NOT be
used as a custom theme name.

#### Scenario: Expand "all" to all discovered themes

- GIVEN 5 built-in themes are discovered (classic, engineeringclassic, engineeringresumes, moderncv, sb2nov)
- AND no custom themes exist
- WHEN the user invokes `mkcv render resume.yaml --theme all`
- THEN `parse_theme_argument` returns all 5 theme names

#### Scenario: "all" is case-insensitive

- GIVEN built-in themes are discoverable
- WHEN the user invokes `mkcv render resume.yaml --theme ALL`
- THEN `parse_theme_argument` expands it the same as `all`

#### Scenario: "all" includes custom themes from workspace

- GIVEN 5 built-in themes are discovered
- AND the workspace has 2 valid custom themes ("corporate", "minimal")
- WHEN the user invokes `mkcv render resume.yaml --theme all`
- THEN `parse_theme_argument` returns all 7 theme names

#### Scenario: "all" mixed with explicit names is rejected

- GIVEN the user invokes `mkcv render resume.yaml --theme "all,classic"`
- WHEN the CLI parses the `--theme` argument
- THEN the system MUST raise a validation error
- AND the error message MUST indicate that `all` cannot be combined with other theme names

### Requirement: Theme Name Validation

All theme names MUST be validated before any rendering begins. If any name
does not match a discovered theme (built-in or custom), the system MUST fail
fast with a clear error listing all unknown theme names.

#### Scenario: All names are valid

- GIVEN themes "sb2nov" and "classic" are discovered
- WHEN `parse_theme_argument("sb2nov,classic", workspace_root)` is called
- THEN it returns `["sb2nov", "classic"]` without error

#### Scenario: One name is invalid

- GIVEN "sb2nov" is a valid theme but "nonexistent" is not
- WHEN `parse_theme_argument("sb2nov,nonexistent", workspace_root)` is called
- THEN the system MUST raise an error before any rendering starts
- AND the error message MUST include the unknown theme name "nonexistent"
- AND the error message SHOULD list available themes

#### Scenario: Multiple names are invalid

- GIVEN "bad1" and "bad2" are not valid themes
- WHEN `parse_theme_argument("sb2nov,bad1,classic,bad2", workspace_root)` is called
- THEN the system MUST raise an error
- AND the error message MUST list both "bad1" and "bad2" as unknown

#### Scenario: Theme name validation is case-insensitive

- GIVEN "sb2nov" is a valid theme
- WHEN `parse_theme_argument("SB2NOV", workspace_root)` is called
- THEN it SHOULD resolve to the canonical lowercase theme name "sb2nov"

### Requirement: Per-Theme Rendering

For each validated theme, `BatchRenderService` MUST:
1. Read the source YAML file once
2. Call `YamlPostProcessor.inject_theme()` to produce a theme-specific YAML
3. Write the themed YAML to `<output_dir>/<theme>/resume.yaml`
4. Delegate to `RenderService.render_resume()` with the themed YAML and the
   theme subdirectory as output
5. Collect the `RenderedOutput` into a `ThemeRenderResult`

#### Scenario: Render two themes successfully

- GIVEN a valid resume YAML at `/tmp/resume.yaml`
- AND themes "sb2nov" and "classic" are valid
- WHEN `BatchRenderService.render_batch(yaml_path, output_dir, themes=["sb2nov", "classic"], formats=["pdf"])` is called
- THEN the service renders "sb2nov" producing `<output_dir>/sb2nov/` with a PDF
- AND the service renders "classic" producing `<output_dir>/classic/` with a PDF
- AND the returned `BatchRenderResult` contains 2 `ThemeRenderResult` entries
- AND both entries have status "success"

#### Scenario: Source YAML is read once, not per-theme

- GIVEN 3 themes are requested
- WHEN `BatchRenderService.render_batch()` is called
- THEN the source YAML file MUST be read exactly once
- AND `inject_theme()` is called once per theme with the same source content

#### Scenario: Themed YAML written to subdirectory

- GIVEN theme "classic" is being rendered
- AND the output directory is `/tmp/output`
- WHEN the batch service processes theme "classic"
- THEN a themed YAML file is written to `/tmp/output/classic/resume.yaml`
- AND `RenderService.render_resume()` is called with that YAML path and `/tmp/output/classic/` as output_dir

### Requirement: Error Isolation

When one theme fails during batch rendering, the system MUST continue rendering
the remaining themes. A per-theme failure SHALL NOT abort the entire batch.

#### Scenario: One theme fails, others succeed

- GIVEN themes "sb2nov", "classic", and "moderncv" are requested
- AND "classic" raises a `RenderError` during rendering
- WHEN `BatchRenderService.render_batch()` is called
- THEN "sb2nov" renders successfully
- AND "classic" is recorded with status "error" and the error message
- AND "moderncv" renders successfully (not aborted)
- AND the `BatchRenderResult` contains 3 entries: 2 success, 1 error

#### Scenario: All themes fail

- GIVEN themes "sb2nov" and "classic" are requested
- AND both raise `RenderError` during rendering
- WHEN `BatchRenderService.render_batch()` is called
- THEN the `BatchRenderResult` contains 2 entries, both with status "error"
- AND each entry includes its respective error message
- AND the batch service does NOT raise an exception

#### Scenario: Error in inject_theme is isolated

- GIVEN themes "sb2nov" and "classic" are requested
- AND `inject_theme()` raises `ValueError` for "sb2nov"
- WHEN `BatchRenderService.render_batch()` is called
- THEN "sb2nov" is recorded with status "error"
- AND "classic" rendering proceeds normally

### Requirement: Output Organization

Multi-theme rendering MUST create one subdirectory per theme under the output
directory. The subdirectory name MUST match the theme name exactly.

#### Scenario: Output directory structure for multi-theme render

- GIVEN themes "sb2nov" and "classic" are rendered to `/tmp/output`
- WHEN both render successfully with format "pdf,png"
- THEN the directory structure is:
  ```
  /tmp/output/
  ├── sb2nov/
  │   ├── resume.yaml
  │   ├── *_CV.pdf
  │   └── *_CV_1.png
  └── classic/
      ├── resume.yaml
      ├── *_CV.pdf
      └── *_CV_1.png
  ```

#### Scenario: Output subdirectory is created if it does not exist

- GIVEN the output directory `/tmp/output` exists but `/tmp/output/classic/` does not
- WHEN theme "classic" is rendered
- THEN the service MUST create `/tmp/output/classic/` before writing files

#### Scenario: Output subdirectory already exists

- GIVEN `/tmp/output/classic/` already exists with files from a previous render
- WHEN theme "classic" is rendered again
- THEN the service MUST overwrite the themed YAML and render output
- AND existing files in the subdirectory are NOT deleted preemptively

### Requirement: Single-Theme Backward Compatibility

When a single theme name is provided (no commas, not `all`), the render
command MUST behave identically to the current implementation: same code path,
same output location, same CLI output.

#### Scenario: Single theme renders directly (no subdirectory)

- GIVEN the user invokes `mkcv render resume.yaml --theme classic`
- WHEN the CLI processes the command
- THEN the system delegates to `RenderService` directly (not `BatchRenderService`)
- AND the output is written to the output directory without a theme subdirectory
- AND the behavior is identical to the current implementation

#### Scenario: No --theme flag uses resolve_theme default

- GIVEN the user invokes `mkcv render resume.yaml` without `--theme`
- WHEN the CLI processes the command
- THEN `resolve_theme()` resolves the default theme from config or fallback
- AND the single-theme code path is used

### Requirement: BatchRenderResult Model

The system MUST provide a `BatchRenderResult` Pydantic model that aggregates
per-theme rendering results.

#### Scenario: BatchRenderResult structure

- GIVEN a batch render of 3 themes completes (2 success, 1 error)
- WHEN the `BatchRenderResult` is constructed
- THEN it contains a `results` field: `list[ThemeRenderResult]`
- AND each `ThemeRenderResult` has fields: `theme` (str), `status` (Literal["success", "error"]), `output` (RenderedOutput | None), `error_message` (str | None)
- AND successful entries have `output` populated and `error_message` as None
- AND error entries have `output` as None and `error_message` populated

#### Scenario: BatchRenderResult convenience properties

- GIVEN a `BatchRenderResult` with 3 results (2 success, 1 error)
- THEN `result.succeeded` SHOULD return the 2 successful `ThemeRenderResult` entries
- AND `result.failed` SHOULD return the 1 failed `ThemeRenderResult` entry
- AND `result.all_succeeded` SHOULD return `False`

### Requirement: Factory Wiring

A `create_batch_render_service()` factory function MUST be added to
`adapters/factory.py` that assembles `BatchRenderService` with its
dependencies (`RenderService`, `YamlPostProcessor`).

#### Scenario: Factory creates a functional BatchRenderService

- GIVEN the factory module is imported
- WHEN `create_batch_render_service(config)` is called
- THEN it returns a `BatchRenderService` instance
- AND the instance has a working `RenderService` and `YamlPostProcessor`
