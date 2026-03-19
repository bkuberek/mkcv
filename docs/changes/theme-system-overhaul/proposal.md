# Proposal: Theme System Overhaul

## Intent

The theme system in mkcv is fundamentally broken: the `--theme` CLI flag is silently
ignored because the `structure_yaml.j2` prompt hardcodes `theme: sb2nov` in its
example YAML, causing every LLM to emit that theme regardless of what the user
requested. Configuration-based theme defaults (`settings.rendering.theme`) are
similarly dead code -- both `render` and `generate` commands hardcode `"sb2nov"` as
their fallback instead of reading from config. The `ResumeDesign` model exists with
font/color/size fields but is never used in the pipeline. Beyond these bugs, users
have no way to customize theme properties (fonts, colors, page size) or define custom
themes.

This change fixes the broken theme plumbing, activates the orphaned `ResumeDesign`
model, adds theme property overrides via config, supports custom user-defined themes,
and wires up A4 paper size for international users.

**Cover letter context:** mkcv now supports cover letter generation (added March 2026)
via a separate rendering pipeline (`CoverLetterRendererPort` → `TypstCoverLetterRenderer`
using direct Typst compilation, not RenderCV). The cover letter renderer already has
a `theme` parameter in its port/adapter but it is currently inert. This change designs
the theme system so that resumes and cover letters share the same theme concept — a
single `--theme` choice should apply to both document types. Cover letter theme
*implementation* is deferred to a follow-up change, but the architecture must support it.

## Scope

### In Scope

#### Phase 1: Fix What's Broken (Bug Fixes)

1. **Fix `--theme` flag being silently ignored**
   - Modify `structure_yaml.j2` to accept a `{{ theme }}` template variable instead
     of hardcoding `theme: sb2nov` in the example YAML
   - Pass `theme` through the pipeline: `generate_command` -> `_run_pipeline` ->
     `PipelineService.generate()` -> `_structure_yaml()` -> prompt context
   - Add post-processing in `_structure_yaml()` to regex-replace the `design.theme`
     value in the generated YAML, ensuring the correct theme is always used even if
     the LLM ignores the instruction

2. **Wire up config-based theme defaults**
   - `generate_command`: change default from `"sb2nov"` to read
     `settings.rendering.theme` (falling back to `"sb2nov"` only if unset)
   - `render_command`: change `effective_theme` fallback from `"sb2nov"` to read
     `settings.rendering.theme`
   - `RenderService.render_resume()`: change default from `"sb2nov"` to require
     explicit theme parameter (no implicit default)
   - `RendererPort.render()` and `RenderCVAdapter.render()`: same -- remove implicit
     `"sb2nov"` default, make callers pass it explicitly

3. **Activate or remove the orphaned `ResumeDesign` model**
   - Wire `ResumeDesign` into the pipeline as the vehicle for design overrides
   - `RenderCVResume.design` already defaults to `ResumeDesign()` -- use this model
     to carry theme + font + color + page_size through the system
   - If design overrides are specified in config, apply them via YAML post-processing

#### Phase 2: Theme Customization

4. **Theme property overrides via config**
   - Add `[rendering.overrides]` section to settings schema:
     ```toml
     [rendering]
     theme = "classic"

     [rendering.overrides]
     font = "Charter"
     font_size = "11pt"
     page_size = "a4paper"
     primary_color = "004080"
     ```
   - After Stage 4 generates the YAML, post-process to merge these overrides into
     the `design` section
   - Read overrides from `settings.rendering.overrides` in the pipeline or render
     service

5. **A4 paper size support**
   - `page_size` already exists in `ResumeDesign` and `settings.toml` -- just needs
     to be wired through to the YAML post-processor
   - Validate against RenderCV's supported values: `"letterpaper"`, `"a4paper"`

#### Phase 3: Custom Themes

6. **User-defined themes via workspace `themes/` directory**
   - Define a `CustomTheme` Pydantic model (YAML format following RenderCV's
     ClassicTheme property structure: colors, typography, margins, page settings)
   - Look for `themes/<name>.yaml` in workspace root
   - Register custom themes with `ThemeService.discover_themes()` alongside built-in
     RenderCV themes
   - Custom themes appear in `mkcv themes` output with a `[custom]` badge

7. **Custom theme validation**
   - Validate custom theme YAML against the `CustomTheme` model on load
   - Provide clear error messages for invalid theme files
   - Validate theme name doesn't conflict with built-in RenderCV themes

#### Phase 4: Documentation & UX

8. **CLI help text improvements**
   - `--theme` help: list available themes inline or reference `mkcv themes`
   - `mkcv themes` output: indicate which theme is the configured default
   - `mkcv themes --preview`: show config overrides if any are active

9. **`mkcv init` generates example custom theme**
   - Add a `themes/example.yaml` to workspace init scaffolding
   - Include comments explaining the format and available properties

10. **Theme vs template documentation**
    - Add clear help text distinguishing theme (visual design: fonts, colors, margins)
      from template (prompt instructions: `.j2` files controlling AI behavior)
    - Surface this in `mkcv themes --help` and `mkcv generate --help`

### Out of Scope

- **Cover letter theme rendering** — wiring theme properties into the Typst cover
  letter template, adding `--theme` to the `cover-letter` CLI command, and creating
  multiple cover letter Typst templates. Deferred to a follow-up change, but the
  architecture designed here MUST support it without breaking changes.
- Community theme marketplace or registry
- Visual theme builder/editor GUI
- Template system overhaul (prompt templates are a separate concern)
- Theme hot-reloading or live preview during generation
- Migration tooling for existing resumes to new themes
- Non-RenderCV rendering backends

## Approach

### Architecture

The fix follows the existing hexagonal architecture. All changes flow through the
established port/adapter pattern:

```
CLI (commands/) -> Core (services/) -> Ports (protocols) -> Adapters (renderers/)
```

**Theme resolution chain** (new):
```
CLI --theme flag
  -> falls back to settings.rendering.theme
    -> falls back to "sb2nov"
```

**Design override chain** (new):
```
settings.rendering.overrides (TOML)
  -> ResumeDesign model (Pydantic validation)
    -> YAML post-processor (injects into generated resume.yaml)
```

**Custom theme discovery** (new):
```
workspace/themes/*.yaml
  -> CustomTheme model (Pydantic validation)
    -> merged into ThemeService.discover_themes() results
```

### Key Technical Decisions

1. **YAML post-processing over prompt engineering**: The LLM cannot be trusted to
   reliably emit the correct theme name. Post-process the generated YAML to inject/
   replace the `design:` section. This is deterministic and reliable.

2. **ResumeDesign as the override vehicle**: The model already exists with the right
   fields. Activate it rather than inventing a new abstraction.

3. **Workspace `themes/` directory**: Follows the existing workspace convention
   (like `templates/` for prompt overrides). Custom themes are YAML files named
   by the theme they extend/define.

4. **Phased delivery**: Phase 1 fixes real bugs users are hitting today. Each
   subsequent phase is independently valuable and can be shipped separately.

5. **Cover letter compatibility by design**: The `ResumeDesign` model and theme
   resolution chain are designed as document-type-agnostic. `resolve_theme()` works
   for any command. `ResumeDesign` properties (font, colors, page_size) map naturally
   to the cover letter Typst template variables. The `CustomTheme` model includes an
   `applies_to` field (defaulting to `"all"`) so custom themes can target resumes,
   cover letters, or both. A future change only needs to: (a) wire `theme` through
   `CoverLetterService.generate()`, (b) parameterize `cover_letter.typ.j2` to read
   font/color/page_size from context, and (c) add `--theme` to the `cover-letter` CLI.

### Implementation Sequence

```
Phase 1 (Bug fixes):
  1a. Add theme param to pipeline + prompt template
  1b. Add YAML post-processor for design.theme injection
  1c. Wire config defaults into CLI commands
  1d. Activate ResumeDesign model in the pipeline

Phase 2 (Customization):
  2a. Add [rendering.overrides] config schema
  2b. Extend YAML post-processor for design overrides
  2c. Validate page_size values

Phase 3 (Custom themes):
  3a. Define CustomTheme model + YAML format
  3b. Add workspace theme discovery to ThemeService
  3c. Register custom themes in discover_themes()
  3d. Update mkcv themes display

Phase 4 (Docs & UX):
  4a. CLI help text updates
  4b. mkcv init scaffolding
  4c. Theme/template distinction in help
```

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/mkcv/prompts/structure_yaml.j2` | Modified | Accept `{{ theme }}` variable instead of hardcoded `sb2nov` |
| `src/mkcv/core/services/pipeline.py` | Modified | Pass theme to Stage 4 context; add YAML post-processor |
| `src/mkcv/core/services/render.py` | Modified | Remove hardcoded `"sb2nov"` default; require explicit theme |
| `src/mkcv/core/services/theme.py` | Modified | Merge custom workspace themes into discovery results |
| `src/mkcv/core/models/resume_design.py` | Modified | Add validation, extend with override fields |
| `src/mkcv/core/models/theme_info.py` | Modified | Add `source` field (built-in vs custom) |
| `src/mkcv/core/ports/renderer.py` | Modified | Remove `"sb2nov"` default from `theme` parameter |
| `src/mkcv/cli/commands/generate.py` | Modified | Read theme default from config; pass theme through pipeline |
| `src/mkcv/cli/commands/render.py` | Modified | Read theme default from config instead of hardcoded fallback |
| `src/mkcv/cli/commands/themes.py` | Modified | Show custom themes, indicate default, show overrides |
| `src/mkcv/config/settings.toml` | Modified | Already has `[rendering]` section -- will add `[rendering.overrides]` |
| `src/mkcv/config/configuration.py` | Modified | Add validator for `rendering.overrides` |
| `src/mkcv/adapters/renderers/rendercv.py` | Modified | Remove hardcoded `"sb2nov"` default |
| `src/mkcv/adapters/factory.py` | Modified | Pass config to render service for theme resolution |
| `src/mkcv/adapters/filesystem/workspace_manager.py` | Modified | Scaffold `themes/` dir + example on `mkcv init` |
| `src/mkcv/core/models/custom_theme.py` | New | Pydantic model for custom theme YAML files |
| `src/mkcv/core/services/yaml_postprocessor.py` | New | Deterministic YAML post-processing for design injection |
| `tests/test_core/test_yaml_postprocessor.py` | New | Tests for YAML post-processing |
| `tests/test_core/test_theme_custom.py` | New | Tests for custom theme discovery + validation |
| `tests/test_cli/test_generate_theme.py` | New | Integration tests for theme flag propagation |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| YAML post-processing corrupts valid resume YAML | Medium | Use a proper YAML parser (ruamel.yaml or PyYAML) for post-processing, not regex. Round-trip preservation of comments/ordering. Extensive test coverage with real pipeline output samples. |
| RenderCV theme API changes between versions | Low | Pin RenderCV version. Theme discovery already handles missing themes gracefully. Custom themes validated against our own model, not RenderCV internals. |
| Custom theme YAML format diverges from RenderCV expectations | Medium | Validate custom themes by attempting to instantiate a RenderCV theme model. Fail fast with clear error messages at load time, not render time. |
| Breaking change to `--theme` default behavior | Low | Default remains `"sb2nov"` -- just read from config instead of hardcoding. Users who never changed config see identical behavior. |
| Pipeline `generate()` signature change breaks callers | Low | Add `theme` as keyword-only arg with default. Existing callers unaffected. Phase 1 is backward-compatible. |
| `ResumeDesign` model activation causes unexpected YAML output | Medium | Phase 1 only injects `theme` field. Design overrides (font/color) are Phase 2 and behind explicit config. No change unless user opts in. |

## Rollback Plan

**Phase 1** (bug fixes): Revert the 3-4 commits. The hardcoded `"sb2nov"` behavior
is restored. No data migration needed -- generated YAML files are self-contained.

**Phase 2** (customization): Remove `[rendering.overrides]` config section. The
YAML post-processor falls back to theme-only injection (Phase 1 behavior). Existing
config files with overrides are ignored (Dynaconf is lenient).

**Phase 3** (custom themes): Remove custom theme discovery. `themes/` directories
in workspaces become inert. `mkcv themes` shows only built-in themes. No data loss.

**Phase 4** (docs/UX): Revert help text changes. Remove example theme from init
scaffolding.

Each phase is independently revertible. No database migrations or state changes.

## Dependencies

- **RenderCV >= 2.x**: Required for theme discovery API (`discover_other_themes()`,
  `ClassicTheme` class). Already a dependency.
- **PyYAML or ruamel.yaml**: For safe YAML post-processing. PyYAML is already
  available via RenderCV's dependency tree. Prefer `ruamel.yaml` for round-trip
  preservation if already in the dep tree; otherwise use PyYAML.
- No new external dependencies required for Phase 1 or 2.

## Success Criteria

- [ ] `mkcv generate --theme classic` produces a resume rendered with the Classic theme (not sb2nov)
- [ ] `mkcv render resume.yaml --theme moderncv` renders with ModernCV theme
- [ ] Setting `theme = "engineeringresumes"` in `mkcv.toml` changes the default for all commands
- [ ] `settings.rendering.theme` is the single source of truth for default theme
- [ ] No hardcoded `"sb2nov"` strings remain outside of `settings.toml` defaults
- [ ] `ResumeDesign` model is used in the pipeline (not orphaned dead code)
- [ ] Config overrides for font/colors/page_size are applied to rendered output
- [ ] `mkcv generate` with `page_size = "a4paper"` in config produces A4 output
- [ ] Custom theme in `workspace/themes/mytheme.yaml` appears in `mkcv themes`
- [ ] `mkcv generate --theme mytheme` uses the custom theme for rendering
- [ ] Custom theme with invalid YAML produces a clear validation error
- [ ] All existing tests pass (no regressions) — including cover letter tests
- [ ] `mypy --strict` passes on all new and modified files
- [ ] `ruff check` passes on all new and modified files
- [ ] `resolve_theme()` is usable by both resume and cover letter commands (no resume-specific coupling)
- [ ] `ResumeDesign` property names align with cover letter Typst template variable names (font, page_size, colors)
- [ ] `CustomTheme` model supports `applies_to` field for future document-type targeting
