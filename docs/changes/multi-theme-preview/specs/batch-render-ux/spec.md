# Batch Render UX Specification

## Purpose

Defines the CLI display and user feedback behavior during and after multi-theme
batch rendering, including progress indication, summary tables, and error
reporting.

## Requirements

### Requirement: Progress Display During Batch Rendering

During a multi-theme batch render, the CLI MUST display progress indicating
which theme is currently being rendered and its position in the batch.

#### Scenario: Progress shown for each theme in a batch

- GIVEN themes "sb2nov", "classic", and "moderncv" are being rendered
- WHEN the batch render begins processing "classic" (2nd of 3)
- THEN the CLI displays a message like `Rendering theme 2/3: classic...`
- AND each theme's progress line appears before that theme's rendering starts

#### Scenario: Progress includes total count

- GIVEN 5 themes are being rendered
- WHEN rendering begins for each theme
- THEN the progress message MUST include the current theme number and total count
- AND the format SHOULD be `Rendering theme {n}/{total}: {theme_name}...`

#### Scenario: No progress display for single theme

- GIVEN a single theme is rendered (not a batch)
- WHEN the render completes
- THEN no batch progress messages are displayed
- AND the output matches the current single-theme behavior exactly

### Requirement: Summary Table After Batch Render

After a multi-theme batch render completes, the CLI MUST display a Rich table
summarizing results for every theme in the batch.

#### Scenario: All themes succeed — summary table

- GIVEN themes "sb2nov" and "classic" both rendered successfully
- WHEN the batch render completes
- THEN the CLI displays a Rich table with columns: Theme, Status, PDF Path
- AND the "sb2nov" row shows status "success" (or checkmark) and its PDF path
- AND the "classic" row shows status "success" (or checkmark) and its PDF path

#### Scenario: Summary table column layout

- GIVEN a batch render has completed
- WHEN the summary table is displayed
- THEN the table MUST contain at minimum these columns:
  - **Theme**: the theme name
  - **Status**: success or error indicator
  - **PDF Path**: path to the generated PDF (or empty if failed)

#### Scenario: Summary table row ordering

- GIVEN themes "moderncv", "sb2nov", "classic" were rendered in that order
- WHEN the summary table is displayed
- THEN the rows MUST appear in render order (moderncv, sb2nov, classic)

### Requirement: Error Reporting in Summary Table

When one or more themes fail during batch rendering, the summary table MUST
clearly indicate which themes failed and include the error message.

#### Scenario: Mixed success and failure in summary table

- GIVEN themes "sb2nov", "classic", and "moderncv" were rendered
- AND "classic" failed with error "Typst compilation failed: missing font"
- WHEN the summary table is displayed
- THEN the "sb2nov" row shows success status and its PDF path
- AND the "classic" row shows error status and the message "Typst compilation failed: missing font"
- AND the "moderncv" row shows success status and its PDF path

#### Scenario: Error row styling

- GIVEN a theme "classic" failed during batch rendering
- WHEN the summary table row for "classic" is displayed
- THEN the status cell MUST use red/error styling to visually distinguish it from success rows
- AND the PDF Path column for this row SHOULD display the error message or be empty

#### Scenario: All themes fail — summary table still shown

- GIVEN themes "sb2nov" and "classic" both failed
- WHEN the batch render completes
- THEN the summary table is still displayed (not suppressed)
- AND both rows show error status with their respective error messages

### Requirement: Batch Summary Statistics

After the summary table, the CLI SHOULD display a brief summary line
indicating how many themes succeeded and how many failed.

#### Scenario: Summary line with mixed results

- GIVEN 3 themes were rendered: 2 succeeded, 1 failed
- WHEN the summary table has been displayed
- THEN a summary line is printed: e.g. `Rendered 2/3 themes successfully.`

#### Scenario: Summary line when all succeed

- GIVEN 4 themes were rendered and all succeeded
- WHEN the summary table has been displayed
- THEN a summary line is printed: e.g. `Rendered 4/4 themes successfully.`

#### Scenario: Summary line when all fail

- GIVEN 2 themes were rendered and both failed
- WHEN the summary table has been displayed
- THEN a summary line is printed: e.g. `Rendered 0/2 themes successfully.`

### Requirement: Single-Theme Output Unchanged

When a single theme is rendered (no batch), the CLI MUST NOT display a
summary table or batch progress. The output MUST match the existing
single-theme render behavior exactly.

#### Scenario: Single theme — no table

- GIVEN the user invokes `mkcv render resume.yaml --theme classic`
- WHEN the render completes successfully
- THEN the output shows individual format paths (PDF, PNG, etc.) as today
- AND no summary table is displayed
- AND no batch progress messages are displayed

#### Scenario: Single theme with --open flag

- GIVEN the user invokes `mkcv render resume.yaml --theme classic --open`
- WHEN the render completes
- THEN the PDF is opened with the system viewer as today
- AND no summary table is displayed

### Requirement: Validation Error Display

When theme name validation fails (before any rendering), the CLI MUST display
a clear error message and exit without rendering.

#### Scenario: Unknown theme names displayed clearly

- GIVEN the user invokes `mkcv render resume.yaml --theme sb2nov,faketheme`
- AND "faketheme" is not a discovered theme
- WHEN theme validation runs
- THEN the CLI displays an error: `Unknown theme(s): faketheme`
- AND the error message SHOULD list available themes
- AND the process exits with a non-zero exit code
- AND no rendering is attempted

#### Scenario: "all" mixed with names — clear error

- GIVEN the user invokes `mkcv render resume.yaml --theme "all,classic"`
- WHEN theme validation runs
- THEN the CLI displays an error indicating `all` cannot be combined with other names
- AND the process exits with a non-zero exit code

### Requirement: Batch Render with --open Flag

When `--open` is used with a multi-theme batch render, the system SHOULD
open the first successfully rendered PDF, or MAY skip opening if the behavior
is ambiguous.

#### Scenario: --open with multi-theme opens first PDF

- GIVEN themes "sb2nov" and "classic" both rendered successfully
- AND `--open` flag is set
- WHEN the batch render completes
- THEN the system SHOULD open the first successfully rendered PDF
- OR the system MAY print a message indicating `--open` is not supported for batch renders

#### Scenario: --open with multi-theme where first theme fails

- GIVEN themes "sb2nov" and "classic" are rendered
- AND "sb2nov" fails but "classic" succeeds
- AND `--open` flag is set
- WHEN the batch render completes
- THEN the system SHOULD open "classic"'s PDF (first successful)
- OR the system MAY skip opening entirely
