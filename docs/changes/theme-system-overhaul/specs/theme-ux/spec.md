# Delta Spec: theme-ux

> Change: theme-system-overhaul
> Domain: User experience for theme discovery, selection, and documentation
> Status: draft
> RFC 2119 keywords: MUST, SHALL, SHOULD, MAY, MUST NOT

## Overview

Users need clear, discoverable information about available themes, how to
select them, and how to customize them. This spec covers improvements to
`mkcv themes` output, CLI help text, the distinction between themes and
templates, and `mkcv init` scaffolding.

---

## REQ-UX-1: `mkcv themes` shows configured default

The `mkcv themes` output MUST indicate which theme is the current default
(as resolved from config). This helps users understand what theme will be
used when they don't explicitly specify one.

### Scenario UX-1.1: Default theme indicated in table

```gherkin
Given settings.rendering.theme = "classic"
When the user runs `mkcv themes`
Then the theme "classic" row MUST have a visual indicator showing it is the default
And the indicator SHOULD be a text marker like "(default)" or a badge
```

### Scenario UX-1.2: sb2nov shown as default when no config

```gherkin
Given no workspace or global config overrides rendering.theme
When the user runs `mkcv themes`
Then "sb2nov" MUST be indicated as the default theme
```

### Scenario UX-1.3: Custom theme as default shown correctly

```gherkin
Given settings.rendering.theme = "mytheme"
And themes/mytheme.yaml exists in the workspace
When the user runs `mkcv themes`
Then "mytheme" MUST appear in the list with a custom theme indicator
And "mytheme" MUST also be indicated as the default
```

---

## REQ-UX-2: `mkcv themes` shows custom themes

Custom themes from the workspace `themes/` directory MUST appear in the
`mkcv themes` output, visually distinguished from built-in themes.

### Scenario UX-2.1: Custom themes listed with badge

```gherkin
Given themes/mytheme.yaml exists in the workspace
When the user runs `mkcv themes`
Then the output MUST include a row for "mytheme"
And the row MUST include a visual indicator that it is a custom theme
And the indicator SHOULD be text like "[custom]" or similar badge
```

### Scenario UX-2.2: Mix of built-in and custom themes

```gherkin
Given 5 built-in themes and 2 custom themes exist
When the user runs `mkcv themes`
Then all 7 themes MUST be listed
And built-in themes MUST NOT have the custom indicator
And custom themes MUST have the custom indicator
```

### Scenario UX-2.3: No custom themes, no custom section

```gherkin
Given no themes/ directory or empty themes/ directory
When the user runs `mkcv themes`
Then only built-in themes MUST be shown
And no "[custom]" badges MUST appear
```

---

## REQ-UX-3: `mkcv themes --preview` shows overrides

When previewing a theme with `--preview`, the output SHOULD show any active
config overrides that would modify the theme's default properties.

### Scenario UX-3.1: Preview shows active overrides

```gherkin
Given settings.rendering.overrides.font = "Charter"
And settings.rendering.overrides.page_size = "a4paper"
When the user runs `mkcv themes --preview sb2nov`
Then the preview panel MUST show the theme's base properties
And MUST indicate which properties are overridden by config
And the overridden values MUST be shown (e.g., Font: Charter [override])
```

### Scenario UX-3.2: Preview with no overrides shows defaults only

```gherkin
Given no rendering overrides are configured
When the user runs `mkcv themes --preview classic`
Then the preview panel MUST show the theme's default properties
And no override indicators MUST be shown
```

### Scenario UX-3.3: Preview of custom theme

```gherkin
Given themes/mytheme.yaml exists with custom colors and font
When the user runs `mkcv themes --preview mytheme`
Then the preview panel MUST show the custom theme's properties
And the panel MUST indicate that it is a custom theme
```

---

## REQ-UX-4: Help text for --theme flag

The `--theme` flag on `generate` and `render` commands MUST have help text
that guides users to discover available themes.

### Scenario UX-4.1: Generate --theme help text

```gherkin
Given the user runs `mkcv generate --help`
When inspecting the --theme flag description
Then the help text MUST mention that themes control visual design
And SHOULD reference `mkcv themes` for listing available themes
```

### Scenario UX-4.2: Render --theme help text

```gherkin
Given the user runs `mkcv render --help`
When inspecting the --theme flag description
Then the help text MUST mention that themes control visual design
And SHOULD reference `mkcv themes` for listing available themes
```

---

## REQ-UX-5: Theme vs template distinction

The system MUST clearly distinguish between themes (visual design: fonts,
colors, margins, page layout) and templates (AI prompt templates: `.j2` files
controlling how content is generated). This distinction MUST be surfaced in
help text to prevent user confusion.

### Scenario UX-5.1: Themes command help explains distinction

```gherkin
Given the user runs `mkcv themes --help`
When inspecting the command description
Then the help text MUST explain that themes control visual appearance
And SHOULD mention that templates (in templates/ directory) control AI behavior
And the two concepts MUST be clearly distinguished
```

### Scenario UX-5.2: Generate command help mentions both

```gherkin
Given the user runs `mkcv generate --help`
When inspecting the full help output
Then the --theme flag help MUST reference visual design
And MUST NOT conflate themes with prompt templates
```

---

## REQ-UX-6: `mkcv init` scaffolds themes/ directory

When initializing a new workspace, `mkcv init` MUST create a `themes/`
directory containing an example custom theme file that demonstrates the
format and available properties.

### Scenario UX-6.1: Init creates themes/ directory

```gherkin
Given an empty directory
When the user runs `mkcv init .`
Then the workspace MUST contain a themes/ directory
```

### Scenario UX-6.2: Init creates example theme file

```gherkin
Given an empty directory
When the user runs `mkcv init .`
Then themes/example.yaml MUST be created
And the file MUST contain a valid custom theme definition
And the file MUST contain comments explaining the format
And the file MUST contain comments listing available properties
```

### Scenario UX-6.3: Init does not overwrite existing themes/

```gherkin
Given a directory with an existing themes/ directory containing mytheme.yaml
When the user runs `mkcv init .`
Then themes/mytheme.yaml MUST NOT be modified or deleted
And themes/example.yaml SHOULD be created if it does not exist
```

### Scenario UX-6.4: Init summary shows themes/ directory

```gherkin
Given an empty directory
When the user runs `mkcv init .`
Then the printed summary MUST list the themes/ directory
And MUST list themes/example.yaml as a created file
```

---

## REQ-UX-7: Theme-related error messages are actionable

All theme-related error messages MUST be actionable — they MUST tell the
user what went wrong and how to fix it.

### Scenario UX-7.1: Unknown theme error suggests alternatives

```gherkin
Given the user runs `mkcv generate --theme clssic --jd job.txt --kb career.md`
When theme validation fails (typo: "clssic" not found)
Then the error message MUST contain the unknown name "clssic"
And SHOULD suggest similar theme names (e.g., "Did you mean: classic?")
Or MUST list all available themes
And SHOULD suggest running `mkcv themes` to see options
```

### Scenario UX-7.2: Custom theme validation error is specific

```gherkin
Given themes/broken.yaml has an invalid color value
When theme discovery encounters the error
Then the error/warning message MUST name the file "broken.yaml"
And MUST indicate the specific validation failure
And SHOULD suggest how to fix it (e.g., "color must be 6-digit hex")
```

### Scenario UX-7.3: Missing RenderCV error suggests install

```gherkin
Given RenderCV is not installed
When the user runs `mkcv themes`
Then the output MUST indicate that no themes are available
And MUST suggest installing rendercv (e.g., `uv add "rendercv[full]"`)
```
