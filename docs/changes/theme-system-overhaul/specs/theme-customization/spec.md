# Delta Spec: theme-customization

> Change: theme-system-overhaul
> Domain: Config-based overrides for theme properties
> Status: draft
> RFC 2119 keywords: MUST, SHALL, SHOULD, MAY, MUST NOT

## Overview

Users need to customize visual properties of their resume (fonts, colors,
page size) without creating a full custom theme. This spec defines the
`[rendering.overrides]` config section that allows property-level overrides
applied via YAML post-processing after Stage 4. It also activates the
existing `ResumeDesign` model as the vehicle for these overrides.

---

## REQ-TC-1: Config section for rendering overrides

The system MUST support a `[rendering.overrides]` section in config (workspace
`mkcv.toml`, global config, or environment variables). The following keys
MUST be recognized:

| Key             | Type   | Description                         | Example         |
|-----------------|--------|-------------------------------------|-----------------|
| `font`          | string | Font family name                    | `"Charter"`     |
| `font_size`     | string | Font size with unit                 | `"11pt"`        |
| `page_size`     | string | Page size identifier                | `"a4paper"`     |
| `primary_color` | string | Primary color as hex (no `#`)       | `"004080"`      |

All keys are OPTIONAL. When a key is absent, the theme's default value
MUST be used (no override applied for that property).

### Scenario TC-1.1: All overrides specified

```gherkin
Given mkcv.toml contains:
  [rendering.overrides]
  font = "Charter"
  font_size = "11pt"
  page_size = "a4paper"
  primary_color = "004080"
When the configuration is loaded
Then settings.rendering.overrides.font MUST be "Charter"
And settings.rendering.overrides.font_size MUST be "11pt"
And settings.rendering.overrides.page_size MUST be "a4paper"
And settings.rendering.overrides.primary_color MUST be "004080"
```

### Scenario TC-1.2: Partial overrides specified

```gherkin
Given mkcv.toml contains:
  [rendering.overrides]
  font = "Charter"
When the configuration is loaded
Then settings.rendering.overrides.font MUST be "Charter"
And font_size, page_size, and primary_color MUST NOT be set
And the theme's defaults for those properties MUST be used
```

### Scenario TC-1.3: No overrides section

```gherkin
Given mkcv.toml has no [rendering.overrides] section
When the configuration is loaded
Then settings.rendering.overrides MUST be absent or empty
And no overrides MUST be applied to the theme
```

### Scenario TC-1.4: Overrides via environment variables

```gherkin
Given MKCV_RENDERING__OVERRIDES__FONT is set to "Georgia"
When the configuration is loaded
Then settings.rendering.overrides.font MUST be "Georgia"
```

---

## REQ-TC-2: Overrides applied via YAML post-processing

When config overrides are present, the YAML post-processor (which also
handles theme injection per REQ-PI-2) MUST merge these overrides into the
`design` section of the generated YAML. Overrides MUST be applied after
Stage 4 completes and after the theme is injected.

### Scenario TC-2.1: Font override applied to YAML

```gherkin
Given the resolved theme is "sb2nov"
And settings.rendering.overrides.font = "Charter"
When Stage 4 produces YAML and the post-processor runs
Then the output YAML design section MUST contain:
  font: Charter
And design.theme MUST still be "sb2nov"
```

### Scenario TC-2.2: Multiple overrides applied

```gherkin
Given the resolved theme is "classic"
And settings.rendering.overrides contains:
  font = "Georgia"
  font_size = "11pt"
  primary_color = "004080"
When Stage 4 produces YAML and the post-processor runs
Then the output YAML design section MUST contain:
  theme: classic
  font: Georgia
  font_size: 11pt
  primary_color: "004080"
```

### Scenario TC-2.3: Overrides do not affect non-design sections

```gherkin
Given settings.rendering.overrides.font = "Charter"
When Stage 4 produces YAML with cv.name = "John Doe" and the post-processor runs
Then cv.name MUST still be "John Doe"
And only the design section MUST be modified
```

### Scenario TC-2.4: No overrides means no design modifications beyond theme

```gherkin
Given settings.rendering.overrides is empty or absent
When Stage 4 produces YAML and the post-processor runs
Then the design section MUST contain only the theme field (from REQ-PI-2)
And no additional design properties MUST be injected
```

---

## REQ-TC-3: A4 paper size support

The system MUST support `"a4paper"` as a valid page_size value. The supported
page_size values MUST be at least: `"letterpaper"` and `"a4paper"`. These
MUST align with RenderCV's supported page size identifiers.

### Scenario TC-3.1: A4 paper size via config

```gherkin
Given mkcv.toml contains:
  [rendering.overrides]
  page_size = "a4paper"
When a resume is generated and rendered
Then the rendered PDF MUST use A4 paper dimensions
```

### Scenario TC-3.2: Letter paper size remains default

```gherkin
Given no page_size override is configured
When a resume is generated and rendered
Then the rendered PDF MUST use the theme's default page size
```

### Scenario TC-3.3: Invalid page size rejected

```gherkin
Given mkcv.toml contains:
  [rendering.overrides]
  page_size = "tabloid"
When the configuration is loaded or the post-processor runs
Then the system MUST raise a validation error
And the error message MUST indicate "tabloid" is not a valid page size
And the error message SHOULD list valid page sizes
```

---

## REQ-TC-4: Override value validation

The system MUST validate override values before applying them. Invalid
values MUST produce clear error messages.

### Scenario TC-4.1: Invalid color format rejected

```gherkin
Given mkcv.toml contains:
  [rendering.overrides]
  primary_color = "#004080"
When the overrides are validated
Then the system MUST reject the value (hex colors MUST NOT include '#' prefix)
And the error message MUST indicate the expected format
```

### Scenario TC-4.2: Valid color accepted

```gherkin
Given mkcv.toml contains:
  [rendering.overrides]
  primary_color = "004080"
When the overrides are validated
Then the value MUST be accepted
```

### Scenario TC-4.3: Invalid font size format rejected

```gherkin
Given mkcv.toml contains:
  [rendering.overrides]
  font_size = "11"
When the overrides are validated
Then the system MUST reject the value (font_size MUST include a unit like "pt")
Or the system MAY accept bare numbers and append "pt" automatically
```

### Scenario TC-4.4: Valid font size accepted

```gherkin
Given mkcv.toml contains:
  [rendering.overrides]
  font_size = "11pt"
When the overrides are validated
Then the value MUST be accepted
```

---

## REQ-TC-5: ResumeDesign model activated in the pipeline

The existing `ResumeDesign` Pydantic model MUST be used as the data vehicle
for carrying design configuration (theme + overrides) through the system.
It MUST NOT remain orphaned/dead code.

### Scenario TC-5.1: ResumeDesign populated from config

```gherkin
Given settings.rendering.theme = "classic"
And settings.rendering.overrides.font = "Charter"
And settings.rendering.overrides.page_size = "a4paper"
When a ResumeDesign is constructed from the configuration
Then design.theme MUST be "classic"
And design.font MUST be "Charter"
And design.page_size MUST be "a4paper"
And design.font_size MUST be the model's default (no override)
```

### Scenario TC-5.2: ResumeDesign with no overrides

```gherkin
Given settings.rendering.theme = "sb2nov"
And no overrides are configured
When a ResumeDesign is constructed from the configuration
Then design.theme MUST be "sb2nov"
And all other fields MUST use the model's defaults
```

### Scenario TC-5.3: ResumeDesign fields map to YAML design section

```gherkin
Given a ResumeDesign with theme="classic", font="Charter", page_size="a4paper"
When the YAML post-processor applies the design
Then the YAML design section MUST contain:
  theme: classic
  font: Charter
  page_size: a4paper
```

---

## REQ-TC-6: Overrides apply to both generate and render paths

Design overrides from config MUST be available in both the `generate` command
(applied during YAML post-processing) and the `render` command (applied
during rendering). The same config values MUST produce the same visual result
regardless of which command is used.

### Scenario TC-6.1: Overrides in resume.yaml persist for render

```gherkin
Given settings.rendering.overrides.font = "Charter"
When `mkcv generate --jd job.txt --kb career.md` completes
Then the saved resume.yaml MUST contain font: Charter in the design section
When `mkcv render resume.yaml` is subsequently run
Then the rendered PDF MUST use the Charter font
```

### Scenario TC-6.2: Overrides embedded in YAML are self-contained

```gherkin
Given a resume.yaml containing design.font = "Charter" and design.page_size = "a4paper"
When the resume.yaml is rendered on a machine with no overrides configured
Then the rendered PDF MUST use Charter font and A4 page size
Because the design section in the YAML is self-contained
```
