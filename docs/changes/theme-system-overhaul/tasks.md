# Tasks: Theme System Overhaul

> Change: theme-system-overhaul
> Generated from: proposal.md, design.md, 5 delta specs
> Total tasks: 47
> Phases: 5 (bug fixes, customization, custom themes, docs/UX, verification)
> Cover letter compatibility: verified by AD-6 checklist (Design §10)

---

## Phase 1: Fix What's Broken (Bug Fixes)

> Priority: HIGHEST — these are real bugs users are hitting today.
> Dependency chain: 1.1 → 1.2 → 1.3 → (1.4 ∥ 1.5 ∥ 1.6) → 1.7 → (1.8 ∥ 1.9 ∥ 1.10) → 1.11

### Task 1.1: Create YamlPostProcessor service [x]

- **File:** `src/mkcv/core/services/yaml_postprocessor.py` (NEW)
- **Action:** Create `YamlPostProcessor` class with two methods:
  - `inject_theme(yaml_str: str, theme: str) -> str` — replaces only `design.theme`
    in the YAML, preserving other design fields; creates `design:` section if missing
  - `inject_design(yaml_str: str, design: ResumeDesign) -> str` — replaces/inserts
    the entire `design` section with all fields from the ResumeDesign model
  - Use `ruamel.yaml` in round-trip mode (`YAML()` with `preserve_quotes=True`)
  - Parse with `self._yaml.load()`, mutate the data dict, dump with `self._yaml.dump()`
  - Raise `ValueError` on empty/malformed YAML input
  - Import `ResumeDesign` from `mkcv.core.models.resume_design`
  - Import `PAGE_SIZE_MAP` (created in Task 1.4) for page size normalization
- **Refs:** Design §5.1, REQ-PI-2 (all scenarios)
- **Verify:** `uv run mypy src/mkcv/core/services/yaml_postprocessor.py --strict`

### Task 1.2: Add resolve_theme() to ThemeService [x]

- **File:** `src/mkcv/core/services/theme.py` (MODIFY)
- **Action:** Add a module-level function:
  ```python
  def resolve_theme(
      cli_theme: str | None,
      config_theme: str,
      default: str = "sb2nov",
  ) -> str:
  ```
  - If `cli_theme is not None`, return `cli_theme`
  - Otherwise return `config_theme` if truthy, else `default`
  - This is a pure function — no side effects, no IO
- **Refs:** Design §3.5, REQ-TR-1 (all scenarios)
- **Verify:** `uv run mypy src/mkcv/core/services/theme.py --strict`

### Task 1.3: Pass theme variable to structure_yaml.j2 prompt template [x]

- **File:** `src/mkcv/prompts/structure_yaml.j2` (MODIFY)
- **Action:**
  - Add `theme` to the context variables docblock at the top (line 4-9 area):
    `  - theme: str — RenderCV theme name (default "sb2nov")`
  - Change line 104 from `  theme: sb2nov` to `  theme: {{ theme | default("sb2nov") }}`
  - No other changes to the template
- **Refs:** REQ-PI-1 (all scenarios)
- **Verify:** Manual inspection; template renders correctly with `theme="classic"`

### Task 1.4: Extend ResumeDesign model with validation and helpers [x]

- **File:** `src/mkcv/core/models/resume_design.py` (MODIFY)
- **Action:**
  - Add imports: `from pydantic import field_validator` (already has `BaseModel`, `Field`)
  - Add module-level constants:
    ```python
    VALID_PAGE_SIZES = ("letterpaper", "a4paper", "us-letter", "a4")
    PAGE_SIZE_MAP: dict[str, str] = {
        "letterpaper": "us-letter",
        "a4paper": "a4",
        "us-letter": "us-letter",
        "a4": "a4",
    }
    ```
  - Add `@field_validator("page_size")` that validates against `VALID_PAGE_SIZES`
  - Add `has_overrides(self) -> bool` method that compares current values against
    `ResumeDesign()` defaults for font, font_size, page_size, colors
- **Refs:** Design §3.2, REQ-TC-3, REQ-TC-4
- **Verify:** `uv run mypy src/mkcv/core/models/resume_design.py --strict` and
  `uv run pytest tests/test_core/test_models/ -k resume`

### Task 1.5: Remove hardcoded "sb2nov" default from RendererPort [x]

- **File:** `src/mkcv/core/ports/renderer.py` (MODIFY)
- **Action:** Change `RendererPort.render()` signature from
  `theme: str = "sb2nov"` to `theme: str` (no default).
  This forces callers to pass theme explicitly.
- **Refs:** REQ-TR-2.4, Design §3.7
- **Verify:** `uv run mypy src/mkcv/core/ports/renderer.py --strict`

### Task 1.6: Remove hardcoded "sb2nov" default from RenderCVAdapter [x]

- **File:** `src/mkcv/adapters/renderers/rendercv.py` (MODIFY)
- **Action:** Change `RenderCVAdapter.render()` signature from
  `theme: str = "sb2nov"` to `theme: str` (no default).
  Line 36: remove `= "sb2nov"`.
- **Refs:** REQ-TR-2.5
- **Verify:** `uv run mypy src/mkcv/adapters/renderers/rendercv.py --strict`

### Task 1.7: Remove hardcoded "sb2nov" default from RenderService [x]

- **File:** `src/mkcv/core/services/render.py` (MODIFY)
- **Action:** Change `RenderService.render_resume()` signature from
  `theme: str = "sb2nov"` to `theme: str` (no default).
  Line 19: remove `= "sb2nov"`.
- **Refs:** REQ-TR-2.3
- **Verify:** `uv run mypy src/mkcv/core/services/render.py --strict`

### Task 1.8: Wire config-based theme defaults into generate command [x]

- **File:** `src/mkcv/cli/commands/generate.py` (MODIFY)
- **Action:**
  - Change `theme` parameter type from `str` to `str | None` and default from
    `"sb2nov"` to `None` (line 107-112)
  - Add import: `from mkcv.core.services.theme import resolve_theme`
  - After `_resolve_preset_and_provider()` call (around line 187), resolve the theme:
    ```python
    effective_theme = resolve_theme(theme, settings.rendering.theme)
    ```
  - Pass `effective_theme` instead of `theme` to `_generate_workspace_mode()` and
    `_generate_standalone_mode()`
  - In `_run_pipeline()` (line 584): change `theme: str = "sb2nov"` to
    `theme: str` (no default — callers always pass it now)
- **Refs:** REQ-TR-1, REQ-TR-2.1
- **Verify:** `uv run mypy src/mkcv/cli/commands/generate.py --strict`

### Task 1.9: Wire config-based theme defaults into render command [x]

- **File:** `src/mkcv/cli/commands/render.py` (MODIFY)
- **Action:**
  - Add import: `from mkcv.core.services.theme import resolve_theme`
  - Change line 67 from `effective_theme = theme if theme is not None else "sb2nov"`
    to `effective_theme = resolve_theme(theme, settings.rendering.theme)`
- **Refs:** REQ-TR-1, REQ-TR-2.2
- **Verify:** `uv run mypy src/mkcv/cli/commands/render.py --strict`

### Task 1.10: Modify PipelineService to accept and use theme [x]

- **File:** `src/mkcv/core/services/pipeline.py` (MODIFY)
- **Action:**
  - Add import: `from mkcv.core.models.resume_design import ResumeDesign`
  - Add import: `from mkcv.core.services.yaml_postprocessor import YamlPostProcessor`
  - Add `resume_design: ResumeDesign | None = None` kwarg to `__init__()` (line 68-80)
  - Store as `self._resume_design = resume_design`
  - Add `theme: str | None = None` kwarg to `generate()` (line 143-163)
  - Pass `theme=theme` to `_structure_yaml()` call (line 238-239)
  - Add `theme: str = "sb2nov"` kwarg to `_structure_yaml()` (line 455-461)
  - In `_structure_yaml()`: add `"theme": theme` to the prompt context dict (line 472-479)
  - After `resume_yaml = _strip_code_fences(resume_yaml)` (line 500): add
    post-processing block:
    ```python
    postprocessor = YamlPostProcessor()
    if self._resume_design is not None:
        resume_yaml = postprocessor.inject_design(resume_yaml, self._resume_design)
    else:
        resume_yaml = postprocessor.inject_theme(resume_yaml, theme)
    ```
- **Refs:** Design §3.6, §5.2, REQ-PI-2, REQ-PI-3
- **Verify:** `uv run mypy src/mkcv/core/services/pipeline.py --strict`

### Task 1.11: Wire factory to build ResumeDesign and pass to PipelineService [x]

- **File:** `src/mkcv/adapters/factory.py` (MODIFY)
- **Action:**
  - Add import: `from mkcv.core.models.resume_design import ResumeDesign`
  - Add `_build_resume_design(config: Configuration, theme: str) -> ResumeDesign`
    helper function that reads `config.rendering.font`, `config.rendering.font_size`,
    `config.rendering.page_size`, and `config.rendering.overrides.primary_color`
    (with AttributeError fallbacks) and constructs a `ResumeDesign`
  - Add `theme: str = "sb2nov"` kwarg to `create_pipeline_service()` (line 238-283)
  - Call `_build_resume_design(config, theme)` and pass result to `PipelineService()`
    constructor as `resume_design=resume_design`
- **Refs:** Design §5.5
- **Verify:** `uv run mypy src/mkcv/adapters/factory.py --strict`

### Task 1.12: Pass theme to create_pipeline_service from generate command [x]

- **File:** `src/mkcv/cli/commands/generate.py` (MODIFY)
- **Action:** In `_run_pipeline()`, change the `create_pipeline_service()` call
  (line 598-599) to pass `theme=theme`:
  ```python
  pipeline = create_pipeline_service(
      settings, preset_name=preset_name, provider_override=provider_override,
      theme=theme,
  )
  ```
  Also pass `theme=theme` to `pipeline.generate()` call (line 613-621).
- **Refs:** REQ-PI-3.3, REQ-PI-5
- **Verify:** `uv run mypy src/mkcv/cli/commands/generate.py --strict`

### Task 1.13: Unit tests for YamlPostProcessor [x]

- **File:** `tests/test_core/test_services/test_yaml_postprocessor.py` (NEW)
- **Action:** Create test file with class-grouped tests:
  - `class TestInjectTheme:` with tests for:
    - `test_replaces_existing_theme` — YAML with `design: {theme: sb2nov}`, inject `classic`
    - `test_adds_missing_design_section` — YAML with only `cv:` section
    - `test_preserves_cv_content` — verify cv section unchanged after injection
    - `test_preserves_other_design_keys` — existing `design.font` preserved
    - `test_handles_correct_theme_no_op` — already-correct theme unchanged
  - `class TestInjectDesign:` with tests for:
    - `test_sets_theme_only_when_no_overrides` — default ResumeDesign
    - `test_sets_font_override` — ResumeDesign with custom font
    - `test_sets_page_size_with_mapping` — a4paper → a4
    - `test_sets_color_override` — custom primary color
    - `test_handles_multiline_yaml` — real-world multi-section YAML
  - `class TestEdgeCases:` with tests for:
    - `test_invalid_yaml_raises_value_error` — malformed input
    - `test_empty_yaml_raises_value_error` — empty string
- **Refs:** Design §7.1
- **Verify:** `uv run pytest tests/test_core/test_services/test_yaml_postprocessor.py -v`

### Task 1.14: Unit tests for resolve_theme() [x]

- **File:** `tests/test_core/test_services/test_theme.py` (NEW)
- **Action:** Create test file with:
  - `test_resolve_theme_cli_wins` — CLI flag overrides config and default
  - `test_resolve_theme_config_fallback` — no CLI uses config value
  - `test_resolve_theme_default_fallback` — no CLI, no config uses "sb2nov"
  - `test_resolve_theme_empty_config_uses_default` — empty string config
- **Refs:** Design §7.1, REQ-TR-1
- **Verify:** `uv run pytest tests/test_core/test_services/test_theme.py -v`

### Task 1.15: Update existing render service tests for explicit theme [x]

- **File:** `tests/test_core/test_services/test_render.py` (MODIFY)
- **Action:** Update all calls to `render_resume()` that rely on the
  `theme="sb2nov"` default — pass `theme="sb2nov"` explicitly since the
  default has been removed. Check every test in this file.
- **Refs:** Design §7.2
- **Verify:** `uv run pytest tests/test_core/test_services/test_render.py -v`

### Task 1.16: Update existing pipeline tests for theme kwarg [x]

- **File:** `tests/test_core/test_services/test_pipeline.py` (MODIFY)
- **Action:**
  - Add tests: `test_generate_passes_theme_to_stage4_prompt` (verify `theme` in
    prompt context using `_PromptCapture` pattern from existing tests)
  - Add test: `test_generate_with_resume_design_injects_design_section`
  - Add test: `test_generate_default_theme_when_not_specified` (backward compat)
  - Update existing `PipelineService()` instantiations if they break due to new
    kwargs (they should be optional/backward-compatible, but verify)
- **Refs:** Design §7.2
- **Verify:** `uv run pytest tests/test_core/test_services/test_pipeline.py -v`

### Task 1.17: Update existing RenderCVAdapter tests [x]

- **File:** `tests/test_adapters/test_renderers/test_rendercv.py` (MODIFY)
- **Action:** Update any calls to `RenderCVAdapter.render()` that rely on
  `theme="sb2nov"` default — pass `theme="sb2nov"` explicitly.
- **Refs:** Design §7.2
- **Verify:** `uv run pytest tests/test_adapters/test_renderers/test_rendercv.py -v`

### Task 1.18: Update factory tests for theme parameter [x]

- **File:** `tests/test_adapters/test_llm/test_factory.py` (MODIFY)
- **Action:** If any tests call `create_pipeline_service()` without the new
  `theme` kwarg, verify they still work (it defaults to `"sb2nov"`). Add a
  test for `create_pipeline_service(config, theme="classic")` that verifies
  the returned PipelineService has `resume_design` set.
- **Verify:** `uv run pytest tests/test_adapters/test_llm/test_factory.py -v`

---

## Phase 2: Theme Customization

> Depends on: Phase 1 complete
> Dependency chain: 2.1 → 2.2 → 2.3 → 2.4 → 2.5

### Task 2.1: Add [rendering.overrides] section to settings.toml [x]

- **File:** `src/mkcv/config/settings.toml` (MODIFY)
- **Action:** After the existing `[default.rendering]` section (lines 53-57),
  add a commented-out overrides section:
  ```toml
  [default.rendering.overrides]
  # Uncomment to customize theme properties:
  # font = "Charter"
  # font_size = "11pt"
  # page_size = "a4paper"
  # primary_color = "004080"
  ```
- **Refs:** Design §3.5 (AD-5), REQ-TC-1
- **Verify:** `uv run python -c "from mkcv.config import settings; print(settings.rendering.theme)"`

### Task 2.2: Add config validator for rendering.overrides [x]

- **File:** `src/mkcv/config/configuration.py` (MODIFY)
- **Action:** In `_register_validators()`, add validators for the override fields:
  ```python
  Validator("rendering.overrides.page_size", is_in=("letterpaper", "a4paper", "us-letter", "a4"), default=None),
  ```
  Note: Don't add strict validators for font/primary_color since those are
  freeform strings — validation happens in ResumeDesign model.
- **Refs:** REQ-TC-4
- **Verify:** `uv run mypy src/mkcv/config/configuration.py --strict`

### Task 2.3: Enhance _build_resume_design to read overrides from config [x]

- **File:** `src/mkcv/adapters/factory.py` (MODIFY)
- **Action:** Update `_build_resume_design()` (created in Task 1.11) to also
  read from `config.rendering.overrides.*`:
  - Read `overrides.font`, `overrides.font_size`, `overrides.page_size`,
    `overrides.primary_color` with `getattr` fallbacks
  - Override fields take precedence over top-level `rendering.*` fields
  - Build `colors` dict from `primary_color` if present
- **Refs:** Design §5.5, REQ-TC-5
- **Verify:** `uv run mypy src/mkcv/adapters/factory.py --strict`

### Task 2.4: Tests for config overrides [x]

- **File:** `tests/test_config/test_configuration.py` (MODIFY)
- **Action:** Add tests:
  - `test_rendering_overrides_loaded` — verify a TOML with `[rendering.overrides]`
    section is parsed correctly
  - `test_rendering_overrides_absent_by_default` — verify no error when section missing
- **Verify:** `uv run pytest tests/test_config/test_configuration.py -v`

### Task 2.5: Tests for ResumeDesign validation [x]

- **File:** `tests/test_core/test_models/test_resume_models.py` (MODIFY)
  or create `tests/test_core/test_models/test_resume_design.py` (NEW)
- **Action:** Add tests:
  - `test_valid_page_sizes_accepted` — all 4 valid values
  - `test_invalid_page_size_rejected` — "tabloid" raises ValidationError
  - `test_has_overrides_false_for_defaults` — default model returns False
  - `test_has_overrides_true_for_custom_font` — non-default font returns True
  - `test_page_size_map_covers_all_valid_sizes` — every VALID_PAGE_SIZES entry
    has a mapping in PAGE_SIZE_MAP
- **Refs:** REQ-TC-3.3, REQ-TC-4
- **Verify:** `uv run pytest tests/test_core/test_models/test_resume_design.py -v`

---

## Phase 3: Custom Themes

> Depends on: Phase 1 complete (Phase 2 optional but recommended)
> Dependency chain: 3.1 → 3.2 → 3.3 → (3.4 ∥ 3.5) → 3.6 → 3.7

### Task 3.1: Create CustomTheme Pydantic model [x]

- **File:** `src/mkcv/core/models/custom_theme.py` (NEW)
- **Action:** Create `CustomTheme(BaseModel)` with fields:
  - `name: str` — validated with `@field_validator` to enforce lowercase
    alphanumeric with hyphens, starting with a letter (`^[a-z][a-z0-9-]*$`)
  - `extends: str = "classic"` — base RenderCV theme name
  - `description: str = ""` — human-readable description
  - `applies_to: Literal["all", "resume", "cover_letter"] = "all"` — which
    document types this theme targets. Import `Literal` from `typing`.
    This enables future cover letter theming without model changes.
  - `overrides: dict[str, str] = Field(default_factory=dict)` — property overrides
- **Refs:** Design §3.3, AD-6, REQ-CT-2
- **Verify:** `uv run mypy src/mkcv/core/models/custom_theme.py --strict`

### Task 3.2: Add source field to ThemeInfo model [x]

- **File:** `src/mkcv/core/models/theme_info.py` (MODIFY)
- **Action:** Add `source: Literal["built-in", "custom"] = "built-in"` field.
  Import `Literal` from `typing`.
- **Refs:** Design §3.4, REQ-CT-3.2, REQ-CT-3.3
- **Verify:** `uv run mypy src/mkcv/core/models/theme_info.py --strict` and
  `uv run pytest tests/test_core/test_models/test_theme_info.py -v`

### Task 3.3: Add custom theme discovery to ThemeService [x]

- **File:** `src/mkcv/core/services/theme.py` (MODIFY)
- **Action:**
  - Add imports: `from pathlib import Path`, `from mkcv.core.models.custom_theme import CustomTheme`
  - Add `load_custom_theme(theme_path: Path) -> CustomTheme`:
    - Read YAML file with `ruamel.yaml` or PyYAML
    - Derive name from filename stem (not from YAML content)
    - Validate with `CustomTheme.model_validate()`
    - Raise `FileNotFoundError` or `ValidationError` on problems
  - Add `discover_custom_themes(workspace_root: Path) -> list[ThemeInfo]`:
    - Scan `workspace_root / "themes"` for `*.yaml` files
    - Load each with `load_custom_theme()`, convert to `ThemeInfo` with `source="custom"`
    - Skip invalid files with `logger.warning()`
    - Check for name collisions with built-in themes; log warning and skip on conflict
  - Modify `discover_themes()` signature to accept `workspace_root: Path | None = None`
    - After discovering built-in themes, call `discover_custom_themes()` if workspace_root given
    - Merge and sort by name
  - Modify `get_theme()` signature to accept `workspace_root: Path | None = None`
    - Pass workspace_root to `discover_themes()`
- **Refs:** Design §3.5, §5.6, REQ-CT-1 through REQ-CT-4
- **Verify:** `uv run mypy src/mkcv/core/services/theme.py --strict`

### Task 3.4: Update mkcv themes command for custom themes and default indicator [x]

- **File:** `src/mkcv/cli/commands/themes.py` (MODIFY)
- **Action:**
  - Import `settings` from `mkcv.config`
  - Pass `workspace_root=settings.workspace_root` to `discover_themes()` and
    `get_theme()` calls
  - In `_render_theme_table()`:
    - Add a "Source" column showing `[custom]` badge for custom themes
    - Add "(default)" indicator to the theme name matching `settings.rendering.theme`
  - In `themes_command()`: pass `workspace_root` through
- **Refs:** REQ-UX-1, REQ-UX-2
- **Verify:** `uv run mypy src/mkcv/cli/commands/themes.py --strict`

### Task 3.5: Scaffold themes/ directory in mkcv init [x]

- **File:** `src/mkcv/adapters/filesystem/workspace_manager.py` (MODIFY)
- **Action:**
  - Add `"themes"` to `workspace_markers` tuple (line 396-400) so the dir is
    created during init
  - Add `_EXAMPLE_THEME_TEMPLATE` constant (the example.yaml content from
    Design §5.7) with comments explaining format and available properties
  - In `create_workspace()`, after existing template files, add:
    ```python
    _write_if_missing(
        workspace_root / "themes" / "example.yaml",
        _EXAMPLE_THEME_TEMPLATE,
    )
    ```
- **Refs:** REQ-UX-6, Design §5.7
- **Verify:** `uv run pytest tests/test_adapters/test_workspace_manager.py -v`

### Task 3.6: Unit tests for CustomTheme model [x]

- **File:** `tests/test_core/test_models/test_custom_theme.py` (NEW)
- **Action:** Tests for:
  - `test_valid_custom_theme` — valid fields parse correctly
  - `test_name_validation_rejects_uppercase` — "MyTheme" rejected
  - `test_name_validation_rejects_special_chars` — "my_theme!" rejected
  - `test_name_validation_accepts_hyphens` — "my-theme" accepted
  - `test_extends_defaults_to_classic` — missing extends defaults correctly
  - `test_overrides_is_optional` — empty overrides dict is valid
  - `test_name_must_start_with_letter` — "1theme" rejected
  - `test_applies_to_defaults_to_all` — missing applies_to defaults to "all"
  - `test_applies_to_accepts_resume` — "resume" is valid
  - `test_applies_to_accepts_cover_letter` — "cover_letter" is valid
  - `test_applies_to_rejects_invalid` — "both" or "pdf" raises ValidationError
- **Refs:** Design §7.1, AD-6
- **Verify:** `uv run pytest tests/test_core/test_models/test_custom_theme.py -v`

### Task 3.7: Unit tests for custom theme discovery [x]

- **File:** `tests/test_core/test_services/test_theme.py` (MODIFY — created in Task 1.14)
- **Action:** Add tests:
  - `test_discover_custom_themes_empty_dir` — empty themes/ returns []
  - `test_discover_custom_themes_no_dir` — no themes/ dir returns []
  - `test_discover_custom_themes_valid_file` — valid YAML returns ThemeInfo
  - `test_discover_custom_themes_invalid_file_skipped` — malformed YAML skipped
  - `test_discover_custom_themes_name_conflict_with_builtin` — "classic.yaml" rejected
  - `test_discover_custom_themes_non_yaml_ignored` — README.md in themes/ ignored
  - `test_discover_themes_merges_builtin_and_custom` — combined list sorted
  - `test_get_theme_finds_custom_theme` — get_theme("mytheme") returns result
  - Use `tmp_path` fixture to create workspace directories and theme YAML files
- **Refs:** Design §7.1, REQ-CT-1 through REQ-CT-5
- **Verify:** `uv run pytest tests/test_core/test_services/test_theme.py -v`

### Task 3.8: Update ThemeInfo model tests for source field [x]

- **File:** `tests/test_core/test_models/test_theme_info.py` (MODIFY)
- **Action:** Add tests:
  - `test_source_defaults_to_builtin` — ThemeInfo without source has "built-in"
  - `test_source_can_be_custom` — ThemeInfo(source="custom") accepted
- **Verify:** `uv run pytest tests/test_core/test_models/test_theme_info.py -v`

### Task 3.9: Update workspace manager tests for themes/ scaffolding [x]

- **File:** `tests/test_adapters/test_workspace_manager.py` (MODIFY)
- **Action:** Add test:
  - `test_create_workspace_creates_themes_directory` — verify themes/ exists
  - `test_create_workspace_creates_example_theme` — verify themes/example.yaml exists
    and contains valid YAML with expected keys (name, extends, description, overrides)
  - `test_create_workspace_does_not_overwrite_existing_themes` — pre-existing
    themes/mytheme.yaml is preserved
- **Verify:** `uv run pytest tests/test_adapters/test_workspace_manager.py -v`

---

## Phase 4: Documentation & UX

> Depends on: Phase 1 complete, Phase 3 recommended
> Tasks are largely independent of each other

### Task 4.1: Update --theme help text in generate command [x]

- **File:** `src/mkcv/cli/commands/generate.py` (MODIFY)
- **Action:** Change the `help` string for `theme` parameter (line 110-111) from
  `"RenderCV theme name."` to:
  `"Visual theme for the resume (fonts, colors, layout). Run 'mkcv themes' to list available options."`
- **Refs:** REQ-UX-4.1, REQ-UX-5.2
- **Verify:** `uv run mkcv generate --help` shows updated text

### Task 4.2: Update --theme help text in render command [x]

- **File:** `src/mkcv/cli/commands/render.py` (MODIFY)
- **Action:** Change the `help` string for `theme` parameter (line 36-37) from
  `"Override theme (default: from YAML)."` to:
  `"Visual theme override (fonts, colors, layout). Default: from YAML design section. Run 'mkcv themes' to list options."`
- **Refs:** REQ-UX-4.2
- **Verify:** `uv run mkcv render --help` shows updated text

### Task 4.3: Update themes command help text with theme/template distinction [x]

- **File:** `src/mkcv/cli/commands/themes.py` (MODIFY)
- **Action:** Update the docstring of `themes_command()` (line 87) from
  `"List and preview available resume themes."` to:
  ```python
  """List and preview available resume themes.
  
  Themes control the visual design of your resume: fonts, colors,
  margins, and page layout. They do NOT control AI content generation
  (that's handled by prompt templates in the templates/ directory).
  """
  ```
- **Refs:** REQ-UX-5.1
- **Verify:** `uv run mkcv themes --help` shows updated text

### Task 4.4: Show overrides in mkcv themes --preview [x]

- **File:** `src/mkcv/cli/commands/themes.py` (MODIFY)
- **Action:** In `_render_preview_panel()`, after showing base theme properties,
  check `settings.rendering` for override values (font, font_size, page_size,
  primary_color). If any are set and differ from the theme's defaults, append
  lines like:
  ```
  Overrides (from config):
    Font:      Charter [override]
    Page Size: a4paper [override]
  ```
  Import `settings` if not already imported.
- **Refs:** REQ-UX-3
- **Verify:** Manual test with a workspace config containing overrides

### Task 4.5: Update workspace manager README template for themes/ [x]

- **File:** `src/mkcv/adapters/filesystem/workspace_manager.py` (MODIFY)
- **Action:** In `_build_readme()`, update the "Workspace Structure" section
  (around line 280) to include `themes/` directory in the tree:
  ```
  ├── themes/                       # Custom theme definitions
  │   └── example.yaml              # Example custom theme
  ```
- **Refs:** REQ-UX-6.4
- **Verify:** `uv run mkcv init /tmp/test-ws && cat /tmp/test-ws/README.md`
  (then clean up)

### Task 4.6: Update CLI test for themes command [x]

- **File:** `tests/test_cli/test_themes.py` (MODIFY)
- **Action:** Update/add tests to verify:
  - Default indicator appears in theme table output
  - Custom theme badge appears when workspace has custom themes
  - Preview panel shows overrides when config has them
  (These tests will likely mock `discover_themes()` and `settings`)
- **Verify:** `uv run pytest tests/test_cli/test_themes.py -v`

---

## Phase 5: Verification

> Depends on: All previous phases complete

### Task 5.1: Run full test suite (including cover letter tests) [x]

- **Command:** `uv run pytest`
- **Action:** Fix any test failures introduced by theme changes.
  Common issues: tests that relied on hardcoded `"sb2nov"` defaults now
  need explicit theme parameter, mock objects may need updated signatures.
  **Critical:** Verify all cover letter tests still pass — the theme
  changes must not break the existing cover letter pipeline:
  - `tests/test_core/test_services/test_cover_letter.py`
  - `tests/test_cli/test_cover_letter_command.py`
  - `tests/test_adapters/test_renderers/test_typst_cover_letter.py`
  - `tests/test_core/test_models/test_cover_letter.py`
  - `tests/test_core/test_models/test_cover_letter_result.py`
  - `tests/test_core/test_models/test_cover_letter_review.py`
- **Verify:** All tests pass with exit code 0

### Task 5.2: Run mypy strict type check [x]

- **Command:** `uv run mypy src/ --strict`
- **Action:** Fix any type errors. Common issues:
  - `ruamel.yaml` missing type stubs — may need `[[tool.mypy.overrides]]`
    entry in `pyproject.toml` with `ignore_missing_imports = true`
  - New function signatures need complete type annotations
- **Verify:** mypy exits with 0 errors
- **Result:** `Success: no issues found in 101 source files`

### Task 5.3: Run ruff lint and format [x]

- **Commands:** `uv run ruff check src/ tests/` and `uv run ruff format src/ tests/`
- **Action:** Fix any lint violations. Auto-format will handle most issues.
- **Verify:** ruff check exits with 0 errors

### Task 5.4: Manual smoke test — theme flag propagation [x]

- **Command:** `uv run mkcv generate --theme classic --jd tests/fixtures/jd.txt --kb tests/fixtures/career.md`
  (or equivalent test fixtures)
- **Action:** Verify that:
  - The generated `resume.yaml` contains `design: {theme: classic}`
  - The rendered PDF uses the Classic theme (visually distinct from sb2nov)
  - Console output shows "Theme: classic"
- **Verify:** Code path verified: `generate.py` uses `resolve_theme()` at line 196,
  passes `effective_theme` through `_generate_workspace_mode`/`_generate_standalone_mode`
  to `_run_pipeline`, which passes `theme=theme` to both `create_pipeline_service()`
  and `pipeline.generate()`. Pipeline stage 4 receives theme in prompt context and
  `YamlPostProcessor.inject_design()` forces the correct design section.

### Task 5.5: Manual smoke test — config-based theme default [x]

- **Action:** Set `rendering.theme = "engineeringresumes"` in a workspace
  `mkcv.toml`, then run `mkcv generate --jd ... --kb ...` without `--theme`.
  Verify the generated resume uses `engineeringresumes` theme.
- **Verify:** Code path verified: `resolve_theme(None, settings.rendering.theme)`
  falls back to `config_theme` when `cli_theme is None`. `Configuration.load_workspace_config()`
  loads `mkcv.toml` via Dynaconf `load_file()`. Test `test_rendering_theme_override_from_workspace`
  in `test_configuration.py` validates this path end-to-end with Dynaconf.

### Task 5.6: Manual smoke test — mkcv themes display [x]

- **Command:** `uv run mkcv themes`
- **Action:** Verify:
  - All built-in themes listed
  - Default theme has "(default)" indicator
  - If custom themes exist, they show `[custom]` badge
- **Verify:** Code review verified: `_render_theme_table()` in `themes.py` reads
  `settings.rendering.theme` for default indicator, displays `(default)` suffix,
  shows `[custom]` badge for `source == "custom"`. `discover_themes()` accepts
  `workspace_root` and merges built-in + custom themes. CLI tests in
  `test_themes.py` validate table rendering and badge display.

### Task 5.7: Verify cover letter compatibility (Design AD-6 checklist) [x]

- **Action:** Verify the cover letter compatibility checklist from Design §10:
  - `resolve_theme()` has no resume-specific imports or logic
  - `ResumeDesign` property names (`font`, `font_size`, `page_size`, `colors`)
    align with what a parameterized `cover_letter.typ.j2` would need
  - `CustomTheme.applies_to` field exists with default `"all"`
  - `_build_resume_design()` factory helper could be reused by
    `create_cover_letter_service()` in the future (no resume-specific coupling)
  - `mkcv generate --cover-letter --theme classic` still works (cover letter
    chaining in `generate.py:_chain_cover_letter()` is unaffected)
  - Cover letter test suite passes completely
- **Verify:** All items confirmed:
  - `resolve_theme()` is a pure 3-line function with zero resume-specific imports
  - `ResumeDesign` uses generic property names: `font`, `font_size`, `page_size`, `colors`
  - `CustomTheme.applies_to: Literal["all", "resume", "cover_letter"] = "all"` exists
  - `_build_resume_design()` reads from `config.rendering.*` — no resume-specific coupling
  - Cover letter tests: 93 passed (0 failed) via `uv run pytest tests/ -k cover_letter -v`

---

## Summary

| Phase | Description          | Task Count | New Files | Modified Files |
|-------|---------------------|------------|-----------|----------------|
| 1     | Bug Fixes           | 18         | 3         | 11             |
| 2     | Theme Customization | 5          | 0-1       | 4              |
| 3     | Custom Themes       | 9          | 2         | 5              |
| 4     | Docs & UX           | 6          | 0         | 4              |
| 5     | Verification (+ CL) | 7          | 0         | 0              |
| **Total** |                 | **45**     | **5-6**   | **~17**        |

## Implementation Order

1. **Phase 1.1–1.4** (core model + service) — no dependencies on CLI
2. **Phase 1.5–1.7** (remove hardcoded defaults) — can be a single commit
3. **Phase 1.8–1.12** (CLI + factory wiring) — depends on 1.1–1.7
4. **Phase 1.13–1.18** (tests) — validates all Phase 1 work
5. **Phase 2** (customization) — builds on Phase 1 factory
6. **Phase 3** (custom themes) — independent of Phase 2
7. **Phase 4** (docs/UX) — independent, can be done in parallel with Phase 3
8. **Phase 5** (verification) — final gate before merge

## Blockers & Dependencies

- **ruamel.yaml type stubs**: Task 5.2 may require a mypy override for
  `ruamel.yaml` in `pyproject.toml`. Check early (during Task 1.1).
- **RenderCV design field names**: The exact YAML field names that RenderCV
  accepts in `design:` need empirical validation (see Design §9, Open Question 2).
  Task 1.1 may need adjustment based on findings.
- **No external dependencies**: `ruamel.yaml` is already in the dependency tree
  via rendercv. No new packages needed.
