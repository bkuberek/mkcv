# Delta Spec: custom-themes

> Change: theme-system-overhaul
> Domain: User-defined themes via workspace directory
> Status: draft
> RFC 2119 keywords: MUST, SHALL, SHOULD, MAY, MUST NOT

## Overview

Users need the ability to define custom themes beyond RenderCV's built-in set.
Custom themes are YAML files placed in a `themes/` directory within the
workspace. This spec defines the format, discovery, registration, validation,
and error handling for custom themes.

---

## REQ-CT-1: Workspace themes/ directory

The system MUST look for a `themes/` directory in the workspace root for
user-defined custom theme files. Each file matching `themes/<name>.yaml`
MUST be treated as a custom theme definition.

### Scenario CT-1.1: Custom theme discovered from workspace

```gherkin
Given a workspace with the file themes/mytheme.yaml containing valid theme YAML
When ThemeService.discover_themes() is called
Then the result MUST include a theme named "mytheme"
And the theme MUST be marked as a custom theme (not built-in)
```

### Scenario CT-1.2: Empty themes/ directory

```gherkin
Given a workspace with an empty themes/ directory
When ThemeService.discover_themes() is called
Then only built-in RenderCV themes MUST be returned
And no error MUST be raised
```

### Scenario CT-1.3: No themes/ directory

```gherkin
Given a workspace without a themes/ directory
When ThemeService.discover_themes() is called
Then only built-in RenderCV themes MUST be returned
And no error MUST be raised
```

### Scenario CT-1.4: Non-YAML files in themes/ are ignored

```gherkin
Given a workspace with themes/ containing:
  - mytheme.yaml (valid)
  - README.md
  - notes.txt
  - .DS_Store
When ThemeService.discover_themes() is called
Then only "mytheme" MUST be added as a custom theme
And non-.yaml files MUST be silently ignored
```

### Scenario CT-1.5: Standalone mode (no workspace) has no custom themes

```gherkin
Given the user is NOT in a workspace (standalone mode)
When ThemeService.discover_themes() is called
Then only built-in RenderCV themes MUST be returned
```

---

## REQ-CT-2: Custom theme YAML format

A custom theme YAML file MUST follow a structure compatible with RenderCV's
theme property model. The file MUST define visual properties such as colors,
typography, margins, and page settings. The system MUST define a `CustomTheme`
Pydantic model that validates this format.

The theme name MUST be derived from the filename (e.g., `mytheme.yaml` ->
theme name `"mytheme"`), NOT from a field inside the YAML.

### Scenario CT-2.1: Minimal valid custom theme

```gherkin
Given themes/minimal.yaml contains:
  colors:
    primary: "2E4057"
  typography:
    font_family: "Charter"
When the file is loaded and validated
Then a CustomTheme model MUST be successfully created
And the theme name MUST be "minimal"
```

### Scenario CT-2.2: Full custom theme

```gherkin
Given themes/corporate.yaml contains:
  colors:
    primary: "003366"
    section_titles: "006699"
  typography:
    font_family: "Georgia"
    font_size: "11pt"
  page:
    size: "a4paper"
    margins:
      top: "1.5cm"
      bottom: "1.5cm"
      left: "1.5cm"
      right: "1.5cm"
When the file is loaded and validated
Then a CustomTheme model MUST be successfully created
And the theme name MUST be "corporate"
```

### Scenario CT-2.3: Theme name derived from filename

```gherkin
Given themes/my-special-theme.yaml exists with valid content
When the theme is loaded
Then the theme name MUST be "my-special-theme"
```

---

## REQ-CT-3: Custom theme registration in ThemeService

Custom themes discovered from the workspace MUST be merged into the results
of `ThemeService.discover_themes()` alongside built-in RenderCV themes. The
ThemeInfo model for custom themes MUST include a `source` field distinguishing
them from built-in themes.

### Scenario CT-3.1: Custom themes appear alongside built-in themes

```gherkin
Given RenderCV has 5 built-in themes
And the workspace has 2 custom themes: mytheme.yaml, corporate.yaml
When discover_themes() is called
Then the result MUST contain 7 themes total
And themes MUST be sorted by name
```

### Scenario CT-3.2: ThemeInfo source field for custom themes

```gherkin
Given themes/mytheme.yaml exists in the workspace
When discover_themes() returns the ThemeInfo for "mytheme"
Then ThemeInfo.source MUST be "custom" (or equivalent marker)
```

### Scenario CT-3.3: ThemeInfo source field for built-in themes

```gherkin
Given the built-in theme "classic" from RenderCV
When discover_themes() returns the ThemeInfo for "classic"
Then ThemeInfo.source MUST be "built-in" (or equivalent marker)
```

### Scenario CT-3.4: get_theme() finds custom themes

```gherkin
Given themes/mytheme.yaml exists in the workspace
When get_theme("mytheme") is called
Then the result MUST NOT be None
And the returned ThemeInfo.name MUST be "mytheme"
```

---

## REQ-CT-4: Name collision prevention

Custom theme names MUST NOT conflict with built-in RenderCV theme names.
If a custom theme file has the same name as a built-in theme, the system
MUST reject it with a clear error.

### Scenario CT-4.1: Custom theme conflicts with built-in

```gherkin
Given themes/classic.yaml exists in the workspace
And "classic" is a built-in RenderCV theme
When ThemeService.discover_themes() is called
Then the system MUST raise an error or emit a warning
And the error message MUST indicate that "classic" conflicts with a built-in theme
And the built-in theme MUST NOT be overridden
```

### Scenario CT-4.2: Custom theme with unique name accepted

```gherkin
Given themes/mycompany.yaml exists in the workspace
And "mycompany" is NOT a built-in theme name
When ThemeService.discover_themes() is called
Then "mycompany" MUST be registered as a custom theme without error
```

### Scenario CT-4.3: Duplicate custom theme filenames

```gherkin
Given themes/ contains only uniquely named .yaml files
Then name collisions among custom themes cannot occur
Because file names in a directory are unique by definition
```

---

## REQ-CT-5: Validation and error handling for custom themes

The system MUST validate each custom theme YAML file against the
`CustomTheme` Pydantic model on load. Invalid themes MUST produce clear,
actionable error messages.

### Scenario CT-5.1: Invalid YAML syntax

```gherkin
Given themes/broken.yaml contains:
  colors:
    primary: [unclosed bracket
When the theme file is loaded
Then the system MUST raise a validation error
And the error message MUST mention "broken.yaml"
And the error message MUST indicate a YAML syntax problem
```

### Scenario CT-5.2: Missing required fields

```gherkin
Given themes/incomplete.yaml contains:
  (empty file or missing required sections)
When the theme file is loaded and validated
Then the system MUST raise a validation error
And the error message MUST mention "incomplete.yaml"
And the error message SHOULD indicate which fields are missing
```

### Scenario CT-5.3: Invalid field values

```gherkin
Given themes/badcolor.yaml contains:
  colors:
    primary: "not-a-color"
When the theme file is loaded and validated
Then the system MUST raise a validation error
And the error message MUST mention "badcolor.yaml"
And the error message SHOULD indicate what's wrong with the color value
```

### Scenario CT-5.4: Valid custom theme loads without error

```gherkin
Given themes/goodtheme.yaml contains valid theme configuration
When the theme file is loaded and validated
Then no error MUST be raised
And a CustomTheme model instance MUST be returned
```

### Scenario CT-5.5: One invalid theme does not block others

```gherkin
Given themes/ contains:
  - valid-theme.yaml (valid)
  - broken-theme.yaml (invalid YAML)
When ThemeService.discover_themes() is called
Then "valid-theme" MUST be included in results
And the system SHOULD log a warning about "broken-theme.yaml"
And the system MUST NOT crash or return an empty list
```

---

## REQ-CT-6: Custom themes usable in generate and render commands

Custom themes MUST be usable wherever built-in themes are accepted. A user
MUST be able to pass `--theme mytheme` to `generate` or `render` commands
and have the custom theme applied.

### Scenario CT-6.1: Generate with custom theme

```gherkin
Given themes/mytheme.yaml exists with valid configuration
When the user runs `mkcv generate --theme mytheme --jd job.txt --kb career.md`
Then the pipeline MUST proceed without error
And the resume.yaml MUST contain design.theme = "mytheme"
And the rendered PDF MUST use the custom theme's properties
```

### Scenario CT-6.2: Render with custom theme

```gherkin
Given themes/mytheme.yaml exists with valid configuration
And resume.yaml contains design.theme = "mytheme"
When the user runs `mkcv render resume.yaml`
Then the render MUST use the custom theme for PDF generation
```

### Scenario CT-6.3: Custom theme as config default

```gherkin
Given themes/mytheme.yaml exists with valid configuration
And mkcv.toml contains rendering.theme = "mytheme"
When the user runs `mkcv generate --jd job.txt --company C --position P`
Then the effective theme MUST be "mytheme"
And the custom theme MUST be used for pipeline and rendering
```

### Scenario CT-6.4: Custom theme not found after YAML generated

```gherkin
Given a resume.yaml was generated with design.theme = "mytheme"
And themes/mytheme.yaml has been deleted from the workspace
When the user runs `mkcv render resume.yaml`
Then the system MUST raise a clear error indicating "mytheme" is not found
And SHOULD suggest checking the themes/ directory
```

---

## REQ-CT-7: Document type targeting (applies_to)

Custom themes MAY include an `applies_to` field to specify which document types
the theme targets. Valid values are `"all"` (default), `"resume"`, or
`"cover_letter"`. This field is informational for this change and will be
enforced when cover letter theming is implemented.

### Scenario CT-7.1: Default applies_to is "all"

```gherkin
Given themes/mytheme.yaml contains:
  name: mytheme
  extends: classic
  overrides:
    font: "Charter"
And no applies_to field is specified
When the theme is loaded
Then applies_to MUST default to "all"
```

### Scenario CT-7.2: Explicit applies_to values accepted

```gherkin
Given themes/resume-only.yaml contains:
  name: resume-only
  extends: classic
  applies_to: resume
When the theme is loaded
Then applies_to MUST be "resume"
```

### Scenario CT-7.3: Invalid applies_to value rejected

```gherkin
Given themes/bad.yaml contains:
  name: bad
  applies_to: "pdf"
When the theme is loaded
Then validation MUST raise an error
And the error SHOULD indicate valid values: "all", "resume", "cover_letter"
```
