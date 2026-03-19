# Delta Spec: theme-resolution

> Change: theme-system-overhaul
> Domain: Theme selection and resolution across CLI flags, config, and defaults
> Status: draft
> RFC 2119 keywords: MUST, SHALL, SHOULD, MAY, MUST NOT

## Overview

The theme resolution system determines which RenderCV theme is used when
generating or rendering a resume. Currently, hardcoded `"sb2nov"` defaults in
multiple locations bypass config-based theme settings and render the `--theme`
CLI flag ineffective. This spec defines the correct resolution chain and
validation behavior.

---

## REQ-TR-1: Theme resolution chain

The system MUST resolve the effective theme using the following priority
(highest to lowest):

1. CLI `--theme` flag (explicit user intent)
2. `settings.rendering.theme` (workspace or global config)
3. Built-in default: `"sb2nov"` (defined only in `config/settings.toml`)

When a higher-priority source provides a value, lower-priority sources
MUST NOT override it.

### Scenario TR-1.1: CLI flag overrides config

```gherkin
Given a workspace with mkcv.toml containing rendering.theme = "classic"
When the user runs `mkcv generate --theme moderncv --jd job.txt --company C --position P`
Then the effective theme MUST be "moderncv"
And the pipeline and renderer MUST use "moderncv"
```

### Scenario TR-1.2: Config overrides built-in default

```gherkin
Given a workspace with mkcv.toml containing rendering.theme = "engineeringresumes"
And the user does NOT pass --theme on the command line
When the user runs `mkcv generate --jd job.txt --company C --position P`
Then the effective theme MUST be "engineeringresumes"
```

### Scenario TR-1.3: Built-in default when no config or CLI flag

```gherkin
Given no workspace config (standalone mode or config has no rendering.theme)
And the user does NOT pass --theme on the command line
When the user runs `mkcv generate --jd job.txt --kb career.md`
Then the effective theme MUST be "sb2nov"
```

### Scenario TR-1.4: Environment variable overrides config

```gherkin
Given a workspace with mkcv.toml containing rendering.theme = "classic"
And the environment variable MKCV_RENDERING__THEME is set to "moderncv"
When the user runs `mkcv generate --jd job.txt --company C --position P`
Then the effective theme MUST be "moderncv"
```

---

## REQ-TR-2: No hardcoded theme defaults outside settings.toml

The string `"sb2nov"` MUST NOT appear as a default value in any Python source
file except `config/settings.toml` (the built-in defaults file). All CLI
commands, services, ports, and adapters MUST read the default theme from the
configuration system rather than embedding it as a literal string.

### Scenario TR-2.1: generate command reads default from config

```gherkin
Given the generate_command function signature
When inspecting the default value for the --theme parameter
Then the default MUST be sourced from settings.rendering.theme
And MUST NOT be the hardcoded string "sb2nov"
```

### Scenario TR-2.2: render command reads default from config

```gherkin
Given the render_command function
When --theme is not passed by the user
Then the effective_theme fallback MUST read from settings.rendering.theme
And MUST NOT be the hardcoded string "sb2nov"
```

### Scenario TR-2.3: RenderService has no implicit default

```gherkin
Given the RenderService.render_resume() method signature
When the theme parameter is examined
Then it MUST NOT have a hardcoded default of "sb2nov"
And callers MUST pass the theme explicitly
```

### Scenario TR-2.4: RendererPort has no implicit default

```gherkin
Given the RendererPort.render() protocol method signature
When the theme parameter is examined
Then it MUST NOT have a hardcoded default of "sb2nov"
```

### Scenario TR-2.5: RenderCVAdapter has no implicit default

```gherkin
Given the RenderCVAdapter.render() method signature
When the theme parameter is examined
Then it MUST NOT have a hardcoded default of "sb2nov"
```

---

## REQ-TR-3: Theme validation at resolution time

The system MUST validate the resolved theme name before passing it to the
pipeline or renderer. If the theme name does not match any known built-in
or custom theme, the system MUST report a clear error and exit with a
non-zero exit code.

### Scenario TR-3.1: Unknown theme name rejected

```gherkin
Given no custom themes are defined
When the user runs `mkcv generate --theme nonexistent --jd job.txt --kb career.md`
Then the system MUST print an error message containing the word "nonexistent"
And the error message SHOULD list available theme names
And the exit code MUST be non-zero
```

### Scenario TR-3.2: Known built-in theme accepted

```gherkin
Given RenderCV is installed with themes: classic, engineeringresumes, moderncv, sb2nov, engineeringclassic
When the user runs `mkcv generate --theme classic --jd job.txt --kb career.md`
Then the system MUST accept "classic" without error
And proceed with the pipeline using theme "classic"
```

### Scenario TR-3.3: Theme validation is case-insensitive

```gherkin
Given the built-in theme "classic" exists
When the user runs `mkcv generate --theme Classic --jd job.txt --kb career.md`
Then the system MUST accept the theme
And resolve it to "classic" (lowercase)
```

### Scenario TR-3.4: Unknown theme in render command

```gherkin
Given no custom themes are defined
When the user runs `mkcv render resume.yaml --theme nonexistent`
Then the system MUST print an error message containing "nonexistent"
And the exit code MUST be non-zero
```

---

## REQ-TR-4: Theme resolution applies to both generate and render commands

Both the `generate` and `render` commands MUST use the same theme resolution
chain (REQ-TR-1). The resolved theme MUST be consistent across both commands
when given identical inputs.

### Scenario TR-4.1: Generate and render use same resolution

```gherkin
Given a workspace with mkcv.toml containing rendering.theme = "classic"
When the user runs `mkcv generate --jd job.txt --company C --position P` (no --theme)
Then the generate command uses theme "classic"
When the user runs `mkcv render resume.yaml` (no --theme)
Then the render command uses theme "classic"
```

### Scenario TR-4.2: Render command --theme overrides YAML embedded theme

```gherkin
Given a resume.yaml file containing design.theme = "sb2nov"
When the user runs `mkcv render resume.yaml --theme classic`
Then the rendered output MUST use theme "classic"
And the YAML's embedded theme MUST NOT take precedence over the CLI flag
```

---

## REQ-TR-5: Config key for default theme

The configuration key `rendering.theme` MUST be the single source of truth
for the default theme name. It MUST be settable at all five configuration
layers (built-in defaults, global config, workspace config, environment
variable, CLI flag).

### Scenario TR-5.1: Workspace config sets default theme

```gherkin
Given a workspace with mkcv.toml:
  [rendering]
  theme = "moderncv"
When settings.rendering.theme is accessed
Then the value MUST be "moderncv"
```

### Scenario TR-5.2: Global config sets default theme

```gherkin
Given ~/.config/mkcv/settings.toml contains:
  [default.rendering]
  theme = "classic"
And no workspace config is loaded
When settings.rendering.theme is accessed
Then the value MUST be "classic"
```

### Scenario TR-5.3: Built-in default remains sb2nov

```gherkin
Given no global config, no workspace config, and no environment variable
When settings.rendering.theme is accessed
Then the value MUST be "sb2nov"
```
