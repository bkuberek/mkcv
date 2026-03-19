# Delta Spec: theme-pipeline-integration

> Change: theme-system-overhaul
> Domain: How the selected theme flows through the AI pipeline and into rendered output
> Status: draft
> RFC 2119 keywords: MUST, SHALL, SHOULD, MAY, MUST NOT

## Overview

The AI pipeline's Stage 4 (structure_yaml) currently hardcodes `theme: sb2nov`
in its prompt template example YAML. Because LLMs tend to copy example values,
the `--theme` flag is silently ignored. This spec defines how the resolved theme
flows into the prompt, how post-processing enforces correctness, and how the
pipeline signature changes to accept a theme parameter.

---

## REQ-PI-1: Theme passed to Stage 4 prompt template

The `structure_yaml.j2` prompt template MUST accept a `theme` template variable.
The template MUST NOT contain any hardcoded theme name in its example YAML.
The `{{ theme }}` variable MUST be used wherever the example YAML shows the
design.theme value.

### Scenario PI-1.1: Template uses theme variable

```gherkin
Given the structure_yaml.j2 prompt template
When the template is rendered with theme = "classic"
Then the rendered prompt MUST contain "theme: classic" in the example YAML
And MUST NOT contain "theme: sb2nov" unless "sb2nov" was the passed value
```

### Scenario PI-1.2: Template with default theme

```gherkin
Given the structure_yaml.j2 prompt template
When the template is rendered with theme = "sb2nov"
Then the rendered prompt MUST contain "theme: sb2nov" in the example YAML
```

### Scenario PI-1.3: Template comment documents the variable

```gherkin
Given the structure_yaml.j2 prompt template header comment
When the context variables are listed
Then "theme" MUST be listed as a context variable with a description
```

---

## REQ-PI-2: YAML post-processing enforces theme in design section

After Stage 4 generates the YAML, the system MUST post-process the YAML to
ensure the `design.theme` field contains the correct (resolved) theme name.
This MUST be done deterministically, regardless of what the LLM emitted.

The post-processor MUST:
- Parse the YAML safely (no arbitrary code execution)
- Set `design.theme` to the resolved theme name
- Preserve all other YAML content (keys, values, ordering, structure)
- Handle the case where no `design` section exists (create it)
- Handle the case where `design.theme` already has the correct value (no-op)

### Scenario PI-2.1: Post-processor corrects wrong theme

```gherkin
Given Stage 4 produced YAML containing:
  design:
    theme: sb2nov
And the resolved theme is "classic"
When the YAML post-processor runs
Then the output YAML MUST contain:
  design:
    theme: classic
And all other YAML content MUST be preserved
```

### Scenario PI-2.2: Post-processor adds missing design section

```gherkin
Given Stage 4 produced YAML containing only a cv: section (no design:)
And the resolved theme is "moderncv"
When the YAML post-processor runs
Then the output YAML MUST contain:
  design:
    theme: moderncv
And the cv: section MUST be preserved
```

### Scenario PI-2.3: Post-processor preserves correct theme

```gherkin
Given Stage 4 produced YAML containing:
  design:
    theme: classic
And the resolved theme is "classic"
When the YAML post-processor runs
Then the output YAML MUST be functionally identical to the input
```

### Scenario PI-2.4: Post-processor preserves other design fields

```gherkin
Given Stage 4 produced YAML containing:
  design:
    theme: sb2nov
    font: Charter
    page_size: letterpaper
And the resolved theme is "classic"
When the YAML post-processor runs
Then the output YAML MUST contain:
  design:
    theme: classic
    font: Charter
    page_size: letterpaper
```

### Scenario PI-2.5: Post-processor handles malformed YAML gracefully

```gherkin
Given Stage 4 produced output that is not valid YAML
When the YAML post-processor runs
Then the system MUST raise a PipelineStageError
And the error message MUST indicate YAML parsing failure
```

---

## REQ-PI-3: Pipeline.generate() accepts theme parameter

The `PipelineService.generate()` method MUST accept a `theme` keyword argument.
This parameter MUST be passed through to the Stage 4 prompt context and to
the YAML post-processor.

### Scenario PI-3.1: Theme passed to generate()

```gherkin
Given a PipelineService instance
When generate() is called with theme="classic"
Then Stage 4 MUST receive "classic" in its prompt context
And the YAML post-processor MUST enforce theme="classic"
```

### Scenario PI-3.2: Theme defaults to None or config

```gherkin
Given a PipelineService instance
When generate() is called without the theme argument
Then the system SHOULD use the configuration default (settings.rendering.theme)
Or the caller MUST be required to provide the theme explicitly
```

### Scenario PI-3.3: CLI passes theme through pipeline invocation

```gherkin
Given the user runs `mkcv generate --theme engineeringresumes --jd job.txt --kb career.md`
When the generate command invokes the pipeline
Then pipeline.generate() MUST receive theme="engineeringresumes"
```

---

## REQ-PI-4: Rendered output uses the resolved theme

The final rendered PDF MUST reflect the resolved theme. The theme embedded
in the `resume.yaml` output (after post-processing) MUST match the resolved
theme. When the YAML is subsequently rendered (either auto-render or explicit
`mkcv render`), the output MUST use that theme.

### Scenario PI-4.1: Auto-render uses pipeline theme

```gherkin
Given the user runs `mkcv generate --theme classic --jd job.txt --kb career.md`
And auto-render is enabled (default)
When the pipeline completes and auto-render executes
Then the PDF MUST be rendered using theme "classic"
```

### Scenario PI-4.2: resume.yaml contains correct theme

```gherkin
Given the user runs `mkcv generate --theme moderncv --jd job.txt --kb career.md`
When the pipeline completes
Then the saved resume.yaml file MUST contain:
  design:
    theme: moderncv
```

### Scenario PI-4.3: Re-render uses YAML-embedded theme by default

```gherkin
Given a resume.yaml file containing design.theme = "moderncv"
When the user runs `mkcv render resume.yaml` (no --theme flag)
Then the render command SHOULD use "moderncv" from the YAML
Or fall back to config default (as defined in REQ-TR-1)
```

---

## REQ-PI-5: _run_pipeline passes theme to pipeline and auto-render

The internal `_run_pipeline()` function in the generate command MUST pass the
resolved theme both to `pipeline.generate()` (for Stage 4) and to the
auto-render step. The theme MUST be the same value for both.

### Scenario PI-5.1: Theme flows end-to-end

```gherkin
Given the user runs `mkcv generate --theme classic --jd job.txt --kb career.md`
When _run_pipeline is invoked with theme="classic"
Then pipeline.generate() MUST receive theme="classic"
And _auto_render() MUST receive theme="classic"
And both MUST use the same theme value
```

### Scenario PI-5.2: No theme leakage between runs

```gherkin
Given a first generate run with --theme classic
And a second generate run with --theme moderncv
When both runs complete
Then the first resume.yaml MUST contain theme: classic
And the second resume.yaml MUST contain theme: moderncv
And neither run MUST affect the other
```
