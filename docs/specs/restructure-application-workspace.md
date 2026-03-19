# Specification: Restructure Application Workspace

**Change:** restructure-application-workspace
**Version:** 1.0.0
**Date:** 2026-03-19
**Status:** Draft

---

## Overview

Restructures the application workspace directory layout from a flat,
date-preset-versioned scheme to a hierarchical, artifact-versioned scheme.
Introduces JD-as-markdown-with-frontmatter, enriched application metadata,
independent resume/cover-letter versioning, and a migration command.

### Current Layout
```
{workspace}/applications/{company_slug}/{YYYY-MM}-{position}-{preset}-v{N}/
├── application.toml
├── jd.txt
├── resume.yaml
├── resume.pdf
├── cover_letter.txt
├── cover_letter.md
├── cover_letter.pdf
└── .mkcv/
    ├── stage1_analysis.json
    ├── stage2_selection.json
    └── ...
```

### New Layout
```
{workspace}/applications/{company_slug}/{position_slug}/{YYYY-MM-DD}/
├── application.toml          # enriched metadata (schema v2)
├── jd.md                     # markdown with YAML frontmatter
├── resumes/
│   └── v{N}/
│       ├── resume.yaml
│       ├── resume.pdf
│       ├── run-metadata.toml
│       └── .mkcv/
│           ├── stage1_analysis.json
│           └── ...
├── cover-letter/
│   └── v{N}/
│       ├── cover_letter.md
│       ├── cover_letter.txt
│       ├── cover_letter.pdf
│       ├── run-metadata.toml
│       └── .mkcv/
│           ├── cover_letter_content.json
│           └── ...
├── interview-prep/           # future placeholder (not created by default)
└── study-guides/             # future placeholder (not created by default)
```

---

## Phase 1: JD Document Model & Reader

### Purpose

Replace plain-text JD ingestion with a structured JD document model that
supports YAML frontmatter for metadata while preserving the body text for
the LLM pipeline. This phase introduces no breaking changes — plain `.txt`
files continue to work.

---

### REQ-1-1: JD Document Model

The system MUST define a `JDDocument` Pydantic model representing a parsed
job description with structured metadata and body text.

**Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `body` | `str` | MUST | The full job description text (everything below the frontmatter). Sent to the LLM pipeline. |
| `company` | `str \| None` | MAY | Company name from frontmatter |
| `position` | `str \| None` | MAY | Position/role title from frontmatter |
| `url` | `str \| None` | MAY | Original job posting URL |
| `compensation` | `str \| None` | MAY | Compensation range/details |
| `location` | `str \| None` | MAY | Job location (city, state, country) |
| `workplace` | `Literal["remote", "hybrid", "onsite"] \| None` | MAY | Workplace arrangement |
| `tags` | `list[str]` | MAY | User-defined tags for categorization |
| `source` | `str \| None` | MAY | Where the JD was found (e.g., "LinkedIn", "company website") |
| `date_posted` | `date \| None` | MAY | When the job was posted |
| `date_closes` | `date \| None` | MAY | Application deadline, if known |

**Acceptance criteria:**
- All frontmatter fields except `body` are optional with `None` defaults.
- `body` MUST always be a non-empty string.
- The model MUST be located at `src/mkcv/core/models/jd_document.py`.

#### SC-1-1-1: Create JDDocument from complete frontmatter

- GIVEN a Markdown string with YAML frontmatter containing company, position, url, location, workplace, compensation, tags, source, date_posted, date_closes
- WHEN `JDDocument` is constructed with the parsed frontmatter and body
- THEN all fields are populated with the provided values
- AND `body` contains only the content below the frontmatter delimiter

#### SC-1-1-2: Create JDDocument with no frontmatter fields

- GIVEN a plain text job description with no frontmatter
- WHEN `JDDocument` is constructed with `body=<text>` and no other arguments
- THEN `body` contains the full text
- AND all optional fields are `None` (or empty list for `tags`)

#### SC-1-1-3: Empty body rejected

- GIVEN an attempt to create a `JDDocument` with `body=""`
- WHEN the model is validated
- THEN a `ValidationError` is raised

---

### REQ-1-2: JD Frontmatter Parsing

The system MUST provide a function `parse_jd_document(text: str) -> JDDocument`
that extracts YAML frontmatter from a Markdown-formatted JD string.

**Frontmatter format:**
```markdown
---
company: Acme Corp
position: Senior Software Engineer
url: https://acme.com/jobs/123
location: San Francisco, CA
workplace: hybrid
compensation: $180k-$220k
tags: [python, distributed-systems]
source: LinkedIn
date_posted: 2026-03-15
date_closes: 2026-04-15
---

# Senior Software Engineer

Acme Corp is looking for...
```

**Rules:**
- Frontmatter MUST be delimited by `---` on a line by itself at the start and end.
- Leading whitespace before the opening `---` MUST be tolerated (stripped).
- The body is everything after the closing `---` delimiter, with leading/trailing whitespace stripped.
- Unknown frontmatter keys MUST be silently ignored (forward compatibility).
- The parser MUST use `yaml.safe_load` (from PyYAML, already a transitive dependency).
- The function MUST be located in `src/mkcv/core/services/jd_reader.py` (extending the existing module).

#### SC-1-2-1: Parse complete frontmatter

- GIVEN a Markdown string with valid YAML frontmatter containing all supported fields
- WHEN `parse_jd_document(text)` is called
- THEN a `JDDocument` is returned with all frontmatter fields populated
- AND `body` contains only the content after the closing `---`

#### SC-1-2-2: Parse frontmatter with subset of fields

- GIVEN a Markdown string with YAML frontmatter containing only `company` and `position`
- WHEN `parse_jd_document(text)` is called
- THEN `company` and `position` are populated
- AND all other optional fields are `None`
- AND `body` contains the rest of the document

#### SC-1-2-3: No frontmatter (plain text)

- GIVEN a plain text string with no `---` delimiters
- WHEN `parse_jd_document(text)` is called
- THEN a `JDDocument` is returned with `body` set to the full text
- AND all metadata fields are `None`

#### SC-1-2-4: Frontmatter with only opening delimiter

- GIVEN a string that starts with `---` but has no closing `---`
- WHEN `parse_jd_document(text)` is called
- THEN the entire text (including the `---`) is treated as body
- AND all metadata fields are `None`

#### SC-1-2-5: Malformed YAML in frontmatter

- GIVEN a Markdown string with `---` delimiters but invalid YAML between them (e.g., unbalanced brackets)
- WHEN `parse_jd_document(text)` is called
- THEN a `JDDocument` is returned with `body` set to the full original text (including the malformed frontmatter)
- AND all metadata fields are `None`
- AND a warning is logged

#### SC-1-2-6: Unknown frontmatter keys are ignored

- GIVEN frontmatter containing `company: Acme` and `foo: bar`
- WHEN `parse_jd_document(text)` is called
- THEN `company` is "Acme"
- AND `foo` is silently ignored (no error, no warning)

#### SC-1-2-7: Leading whitespace before frontmatter

- GIVEN a string with blank lines or spaces before the opening `---`
- WHEN `parse_jd_document(text)` is called
- THEN the frontmatter is still correctly parsed

#### SC-1-2-8: Empty body after frontmatter

- GIVEN a string with valid frontmatter but empty or whitespace-only content after the closing `---`
- WHEN `parse_jd_document(text)` is called
- THEN a `JDReadError` is raised with a message indicating the body is empty

#### SC-1-2-9: Workplace field validation

- GIVEN frontmatter with `workplace: "in-office"`
- WHEN `parse_jd_document(text)` is called
- THEN `workplace` is `None` (invalid literal silently dropped)
- AND a warning is logged

---

### REQ-1-3: Updated read_jd Returns JDDocument

The existing `read_jd(source: str) -> str` function MUST be updated to return
`JDDocument` instead of `str`.

**Backward compatibility:**
- All callers that previously used the return value as plain text MUST use
  `jd_doc.body` instead.
- The pipeline MUST send only `jd_doc.body` to the LLM (not the frontmatter).
- CLI commands MUST use frontmatter metadata (company, position) as defaults
  when `--company` / `--position` are not explicitly provided.

#### SC-1-3-1: read_jd with .txt file

- GIVEN a path to a plain `.txt` JD file with no frontmatter
- WHEN `read_jd(source)` is called
- THEN a `JDDocument` is returned with `body` equal to the file content
- AND all metadata fields are `None`

#### SC-1-3-2: read_jd with .md file containing frontmatter

- GIVEN a path to a `.md` JD file with YAML frontmatter
- WHEN `read_jd(source)` is called
- THEN a `JDDocument` is returned with frontmatter fields populated
- AND `body` contains only the post-frontmatter content

#### SC-1-3-3: read_jd with URL source

- GIVEN an HTTP URL that returns Markdown content with frontmatter
- WHEN `read_jd(source)` is called
- THEN the response content is parsed for frontmatter
- AND a `JDDocument` is returned

#### SC-1-3-4: Pipeline receives only body text

- GIVEN a `JDDocument` with frontmatter fields populated
- WHEN the pipeline's `generate()` method reads the JD
- THEN only `jd_doc.body` is passed to `_analyze_jd()`
- AND frontmatter metadata is NOT sent to the LLM

---

### REQ-1-4: JD File Saved as Markdown

When the workspace manager saves the JD to an application directory, it MUST
save it as `jd.md` (not `jd.txt`).

**Rules:**
- If the input JD already has frontmatter, it MUST be preserved verbatim.
- If the input JD is plain text (no frontmatter), the system SHOULD generate
  frontmatter from available metadata (company, position, url from CLI flags
  or LLM analysis) and prepend it.
- The body text MUST be preserved exactly as provided.

#### SC-1-4-1: Save JD with existing frontmatter

- GIVEN a `JDDocument` parsed from Markdown with frontmatter
- WHEN the JD is saved to the application directory
- THEN the file is named `jd.md`
- AND the original frontmatter + body are preserved verbatim

#### SC-1-4-2: Save plain-text JD with generated frontmatter

- GIVEN a plain-text JD (no frontmatter) with company="Acme" and position="SWE"
- WHEN the JD is saved to the application directory
- THEN the file is named `jd.md`
- AND YAML frontmatter is prepended with company, position, and any other known metadata
- AND the original body text follows after `---`

#### SC-1-4-3: Backward-compatible reading of jd.txt

- GIVEN an application directory containing `jd.txt` (old format) but no `jd.md`
- WHEN the system reads the JD from the application directory
- THEN `jd.txt` is read and parsed as plain text
- AND a `JDDocument` is returned with `body` set to the file content

---

## Phase 2: Enriched ApplicationMetadata

### Purpose

Extend the `ApplicationMetadata` model and `application.toml` schema with
richer fields to support the new layout, dual-layout detection, and
migration.

---

### REQ-2-1: ApplicationMetadata v2 Model

The `ApplicationMetadata` model MUST be extended with the following new fields:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `company` | `str` | MUST | — | Company name (existing) |
| `position` | `str` | MUST | — | Position title (existing) |
| `date` | `date` | MUST | — | Application date (existing, now YYYY-MM-DD) |
| `status` | `Literal[...]` | MUST | `"draft"` | Application status (existing) |
| `url` | `str \| None` | MAY | `None` | Job posting URL (existing) |
| `created_at` | `datetime` | MUST | `now()` | Creation timestamp (existing) |
| `schema_version` | `int` | MUST | `2` | Metadata schema version for migration/compat |
| `location` | `str \| None` | MAY | `None` | Job location |
| `workplace` | `Literal["remote","hybrid","onsite"] \| None` | MAY | `None` | Workplace arrangement |
| `compensation` | `str \| None` | MAY | `None` | Compensation range |
| `source` | `str \| None` | MAY | `None` | Where the JD was found |
| `tags` | `list[str]` | MAY | `[]` | User-defined tags |
| `preset` | `str` | SHOULD | `"standard"` | Preset used for generation |
| `notes` | `str` | MAY | `""` | Free-form user notes |

**Acceptance criteria:**
- `schema_version` MUST default to `2` for newly created metadata.
- The model MUST accept old-format data (missing `schema_version`) and treat it as version 1.
- New fields with defaults MUST NOT break parsing of existing `application.toml` files.

#### SC-2-1-1: Create v2 metadata

- GIVEN all fields including new v2 fields
- WHEN `ApplicationMetadata` is constructed
- THEN `schema_version` is `2`
- AND all new fields are populated

#### SC-2-1-2: Parse v1 application.toml (backward compat)

- GIVEN an `application.toml` with only v1 fields (company, position, date, status, url, created_at)
- WHEN `ApplicationMetadata` is parsed from the TOML data
- THEN `schema_version` defaults to `1`
- AND all new fields use their defaults (`None`, `[]`, `""`, `"standard"`)

#### SC-2-1-3: Parse v2 application.toml

- GIVEN an `application.toml` with `schema_version = 2` and all new fields
- WHEN `ApplicationMetadata` is parsed
- THEN all fields are correctly populated

#### SC-2-1-4: Enriched metadata from JD frontmatter

- GIVEN a JD with frontmatter containing location, workplace, compensation
- WHEN an application is created via `setup_application()`
- THEN the `ApplicationMetadata` SHOULD be enriched with the JD frontmatter values

---

### REQ-2-2: application.toml v2 Schema

The `application.toml` file MUST be written in the following format:

```toml
[application]
schema_version = 2
company = "Acme Corp"
position = "Senior Software Engineer"
date = "2026-03-19"
status = "draft"
url = "https://acme.com/jobs/123"
created_at = "2026-03-19T10:30:00+00:00"
location = "San Francisco, CA"
workplace = "hybrid"
compensation = "$180k-$220k"
source = "LinkedIn"
preset = "standard"
tags = ["python", "backend"]
notes = ""
```

#### SC-2-2-1: Write v2 application.toml

- GIVEN a `ApplicationMetadata` with `schema_version = 2`
- WHEN `_write_application_toml()` is called
- THEN the file contains all v2 fields under `[application]`
- AND `date` is in `YYYY-MM-DD` format (not `YYYY-MM`)

#### SC-2-2-2: Read v1 application.toml in v2 code

- GIVEN an `application.toml` written by the old code (no `schema_version`, date as `YYYY-MM`)
- WHEN the system reads and parses it
- THEN parsing succeeds
- AND `schema_version` defaults to `1`
- AND `date` is parsed correctly (Python's `date.fromisoformat` accepts both `YYYY-MM-DD` and `YYYY-MM` with a day-of-month of `01`)

---

### REQ-2-3: Date Format Change

Application dates MUST use `YYYY-MM-DD` format (ISO 8601 full date) instead
of the current `YYYY-MM`.

- Directory names MUST use `YYYY-MM-DD`.
- `application.toml` MUST store `date` as `YYYY-MM-DD`.
- The date SHOULD be `date.today()` at the time of application creation.

#### SC-2-3-1: New application uses full date

- GIVEN today is 2026-03-19
- WHEN a new application is created
- THEN the directory name includes `2026-03-19`
- AND `application.toml` contains `date = "2026-03-19"`

---

## Phase 3: New Directory Structure

### Purpose

Rewrite the directory path construction, versioning, and resolution logic
in `WorkspaceManager` to use the new hierarchical layout.

---

### REQ-3-1: Application Directory Path Construction

Application directories MUST follow the pattern:
```
{workspace}/applications/{company_slug}/{position_slug}/{YYYY-MM-DD}/
```

**Slugification rules** (existing `slugify()` behavior, unchanged):
- Unicode NFKD normalization, then ASCII-only transliteration.
- Lowercase.
- Non-alphanumeric characters replaced with hyphens.
- Consecutive hyphens collapsed.
- Leading/trailing hyphens stripped.
- Maximum 64 characters, truncated at the last clean boundary.

**Path construction rules:**
- `company_slug` = `slugify(company)`
- `position_slug` = `slugify(position)`
- Date = `date.today().strftime("%Y-%m-%d")`
- Preset is NOT part of the path (stored in `application.toml` and `run-metadata.toml`).
- Version number is NOT in the application directory path (versioning is per-artifact inside the application).

#### SC-3-1-1: Standard path construction

- GIVEN company="Acme Corp", position="Senior Software Engineer", date=2026-03-19
- WHEN the application directory is created
- THEN the path is `applications/acme-corp/senior-software-engineer/2026-03-19/`

#### SC-3-1-2: Company with special characters

- GIVEN company="François & Associés", position="Développeur"
- WHEN the application directory is created
- THEN company_slug = `francois-associes`
- AND position_slug = `developpeur`

#### SC-3-1-3: Long position name truncation

- GIVEN position="Principal Staff Senior Distinguished Software Engineer and Technical Fellow Lead"
- WHEN slugified
- THEN the slug is truncated to 64 characters at the last clean word boundary

---

### REQ-3-2: Date Collision Handling

When an application directory already exists for the same company, position,
and date, the system MUST handle the collision.

**Rules:**
- If `applications/{company}/{position}/{YYYY-MM-DD}/` already exists AND contains an `application.toml`:
  - The system MUST raise a `WorkspaceError` explaining that an application for this company/position/date already exists.
  - The error message SHOULD suggest using the existing directory or choosing a different date.
- If the directory exists but does NOT contain `application.toml` (e.g., partially created):
  - The system MAY reuse the directory, creating only missing files.

#### SC-3-2-1: Collision with existing application

- GIVEN an existing application at `applications/acme-corp/swe/2026-03-19/` with `application.toml`
- WHEN `create_application()` is called with the same company, position, and date
- THEN a `WorkspaceError` is raised
- AND the error message mentions the existing directory

#### SC-3-2-2: Same company/position, different date

- GIVEN an existing application at `applications/acme-corp/swe/2026-03-18/`
- WHEN `create_application()` is called with company="Acme Corp", position="SWE", date=2026-03-19
- THEN the new directory `applications/acme-corp/swe/2026-03-19/` is created successfully

#### SC-3-2-3: Partial directory exists (no application.toml)

- GIVEN a directory `applications/acme-corp/swe/2026-03-19/` exists but contains no `application.toml`
- WHEN `create_application()` is called
- THEN the directory is reused
- AND `application.toml`, `jd.md`, and `resumes/` are created

---

### REQ-3-3: Application Directory Contents (Created on Setup)

When `create_application()` is called, the following MUST be created:

| Path | Created | Description |
|------|---------|-------------|
| `application.toml` | Always | v2 metadata |
| `jd.md` | Always | JD file (Markdown with frontmatter) |
| `resumes/` | Always | Empty directory for resume versions |
| `cover-letter/` | NOT created | Created on first cover letter generation |
| `interview-prep/` | NOT created | Future placeholder |
| `study-guides/` | NOT created | Future placeholder |

#### SC-3-3-1: New application directory contents

- GIVEN valid company, position, and JD source
- WHEN `create_application()` is called
- THEN `application.toml` exists with v2 schema
- AND `jd.md` exists with the JD content
- AND `resumes/` directory exists (empty)
- AND `cover-letter/` does NOT exist yet
- AND `interview-prep/` does NOT exist
- AND `study-guides/` does NOT exist

---

### REQ-3-4: WorkspacePort Interface Update

The `WorkspacePort` protocol MUST be updated to reflect the new directory
structure. Method signatures that change:

**`create_application()`:**
- MUST remove the `preset_name` parameter from the directory path construction.
- MUST accept a `jd_document: JDDocument | None` parameter for enriching metadata from frontmatter.
- MUST return the application directory path.

**`list_applications()`:**
- MUST detect both old-layout and new-layout application directories.
- Old layout: any directory containing `application.toml` directly under `{company_slug}/`.
- New layout: any directory containing `application.toml` under `{company_slug}/{position_slug}/{date}/`.

**`find_latest_application()`:**
- MUST use `created_at` from `application.toml` for sorting (not lexicographic directory names) to handle dual-layout correctly.
- MUST fall back to lexicographic sorting when `created_at` is missing or unparseable.

**`resolve_resume_path()`:**
- MUST check `resumes/v{N}/resume.yaml` in the new layout (highest version first).
- MUST fall back to `resume.yaml` in the application root (old layout).

#### SC-3-4-1: list_applications with mixed layouts

- GIVEN a workspace with:
  - Old-layout: `applications/acme-corp/2025-06-swe-standard-v1/application.toml`
  - New-layout: `applications/acme-corp/swe/2026-03-19/application.toml`
- WHEN `list_applications()` is called
- THEN both directories are returned
- AND they are sorted by `created_at` timestamp

#### SC-3-4-2: find_latest_application uses created_at

- GIVEN two applications:
  - `applications/acme-corp/swe/2026-03-18/` with `created_at = 2026-03-18T14:00:00`
  - `applications/acme-corp/swe/2026-03-19/` with `created_at = 2026-03-19T09:00:00`
- WHEN `find_latest_application(company="Acme Corp")` is called
- THEN the `2026-03-19` application is returned

#### SC-3-4-3: resolve_resume_path in new layout

- GIVEN an application dir with `resumes/v1/resume.yaml` and `resumes/v2/resume.yaml`
- WHEN `resolve_resume_path(app_dir)` is called
- THEN the path to `resumes/v2/resume.yaml` is returned (latest version)

#### SC-3-4-4: resolve_resume_path falls back to old layout

- GIVEN an old-layout application dir with `resume.yaml` in the root
- WHEN `resolve_resume_path(app_dir)` is called
- THEN the path to `resume.yaml` in the root is returned

---

### REQ-3-5: Dual-Layout Detection

The system MUST support reading from both old and new layout directories
simultaneously during the migration period.

**Detection heuristic:**
- **New layout**: `application.toml` exists AND parent directory name matches `YYYY-MM-DD` format AND grandparent is a position slug.
- **Old layout**: `application.toml` exists AND parent directory name matches `YYYY-MM-{slug}-v{N}` format.
- **Unknown**: `application.toml` exists but directory name matches neither pattern — treated as old layout.

#### SC-3-5-1: Detect new layout directory

- GIVEN `applications/acme-corp/swe/2026-03-19/application.toml`
- WHEN layout detection runs
- THEN the directory is identified as "new layout"

#### SC-3-5-2: Detect old layout directory

- GIVEN `applications/acme-corp/2025-06-swe-standard-v1/application.toml`
- WHEN layout detection runs
- THEN the directory is identified as "old layout"

#### SC-3-5-3: Ambiguous directory treated as old layout

- GIVEN `applications/acme-corp/some-unknown-dir/application.toml`
- WHEN layout detection runs
- THEN the directory is treated as "old layout" (safe default)

---

## Phase 4: Pipeline & Cover Letter Output Placement

### Purpose

Modify the pipeline and cover letter services to write outputs into the
versioned sub-folders within an application directory.

---

### REQ-4-1: Resume Version Directory

When the pipeline generates a resume in workspace mode, outputs MUST be
placed in `resumes/v{N}/` within the application directory.

**Version resolution:**
- Scan `resumes/` for existing `v{N}` directories.
- The next version is `max(existing versions) + 1`, or `1` if none exist.

**Files placed in `resumes/v{N}/`:**
| File | Description |
|------|-------------|
| `resume.yaml` | Generated resume YAML |
| `resume.pdf` | Rendered PDF (if `--render`) |
| `resume.png` | Rendered PNG (if applicable) |
| `run-metadata.toml` | Run metadata (see REQ-4-3) |
| `.mkcv/` | Pipeline stage artifacts (JSON) |

#### SC-4-1-1: First resume generation

- GIVEN a new application directory with empty `resumes/`
- WHEN the pipeline generates a resume
- THEN outputs are placed in `resumes/v1/`
- AND `resumes/v1/.mkcv/` contains stage artifacts

#### SC-4-1-2: Second resume generation (re-run)

- GIVEN an application with `resumes/v1/` already existing
- WHEN the pipeline generates another resume
- THEN outputs are placed in `resumes/v2/`
- AND `resumes/v1/` is untouched

#### SC-4-1-3: Resume with --from-stage resume

- GIVEN an application with `resumes/v1/` containing pipeline artifacts
- WHEN the pipeline is run with `--from-stage 3`
- THEN a new version `resumes/v2/` is created
- AND stage 1-2 artifacts are copied from `resumes/v1/.mkcv/` to `resumes/v2/.mkcv/`
- AND stages 3-5 run fresh and write to `resumes/v2/.mkcv/`

---

### REQ-4-2: Cover Letter Version Directory

When the cover letter service generates output in workspace mode, outputs
MUST be placed in `cover-letter/v{N}/` within the application directory.

**Version resolution:** Same rules as resume versions (independent numbering).

**Files placed in `cover-letter/v{N}/`:**
| File | Description |
|------|-------------|
| `cover_letter.md` | Markdown cover letter |
| `cover_letter.txt` | Plain text cover letter |
| `cover_letter.pdf` | Rendered PDF (if `--render`) |
| `run-metadata.toml` | Run metadata |
| `.mkcv/` | Cover letter stage artifacts |

**Directory creation:**
- The `cover-letter/` directory MUST be created on first cover letter generation (not during `setup_application()`).

#### SC-4-2-1: First cover letter generation

- GIVEN a new application with no `cover-letter/` directory
- WHEN cover letter generation runs
- THEN `cover-letter/v1/` is created
- AND all cover letter outputs are placed inside it
- AND `cover-letter/v1/.mkcv/` contains stage artifacts

#### SC-4-2-2: Independent versioning from resume

- GIVEN an application with `resumes/v3/` and `cover-letter/v1/`
- WHEN a new cover letter is generated
- THEN it goes to `cover-letter/v2/` (independent of resume versioning)

---

### REQ-4-3: Run Metadata

Each version directory (`resumes/v{N}/`, `cover-letter/v{N}/`) MUST contain
a `run-metadata.toml` file capturing generation parameters.

**Schema:**
```toml
[run]
run_id = "abc123def456"
timestamp = "2026-03-19T10:30:00+00:00"
preset = "standard"
theme = "sb2nov"
provider = "anthropic"
model = "claude-sonnet-4-20250514"
from_stage = 1
duration_seconds = 45.2
total_cost_usd = 0.0342
review_score = 85

[run.stage_models]
1 = "claude-sonnet-4-20250514"
2 = "claude-sonnet-4-20250514"
3 = "claude-sonnet-4-20250514"
4 = "gpt-4o"
5 = "claude-sonnet-4-20250514"
```

#### SC-4-3-1: Run metadata written after pipeline

- GIVEN a completed pipeline run
- WHEN the output is written to `resumes/v1/`
- THEN `resumes/v1/run-metadata.toml` exists
- AND contains the run_id, timestamp, preset, theme, and per-stage model info

#### SC-4-3-2: Run metadata for cover letter

- GIVEN a completed cover letter run
- WHEN the output is written to `cover-letter/v1/`
- THEN `cover-letter/v1/run-metadata.toml` exists
- AND contains run_id, timestamp, and stage info for the 2-stage CL pipeline

---

### REQ-4-4: Output Directory Threading

The pipeline and cover letter services MUST accept and propagate the
versioned output directory correctly.

**Changes to `PipelineService.generate()`:**
- The `output_dir` parameter MUST point to the version directory (e.g., `resumes/v1/`), NOT the application root.
- `resume.yaml` is saved to `output_dir/resume.yaml`.
- `.mkcv/` artifacts are saved to `output_dir/.mkcv/`.

**Changes to `CoverLetterService.generate()`:**
- The `output_dir` parameter MUST point to the version directory (e.g., `cover-letter/v1/`).
- Cover letter files are saved to `output_dir/`.

**Changes to CLI (`generate_command`, `cover_letter_command`):**
- In workspace mode, the CLI MUST compute the version directory before calling the service.
- The CLI is responsible for version resolution (scanning `resumes/` or `cover-letter/`).

#### SC-4-4-1: Pipeline output in versioned directory

- GIVEN workspace mode with app_dir = `applications/acme-corp/swe/2026-03-19/`
- WHEN the pipeline runs for the first time
- THEN the CLI creates `resumes/v1/`
- AND passes `output_dir = app_dir / "resumes" / "v1"` to the pipeline
- AND `resume.yaml` appears at `resumes/v1/resume.yaml`
- AND stage artifacts appear at `resumes/v1/.mkcv/`

#### SC-4-4-2: Standalone mode unchanged

- GIVEN standalone mode (no workspace)
- WHEN the pipeline runs with `output_dir = ./output/my-resume/`
- THEN behavior is unchanged — `resume.yaml` and `.mkcv/` go directly in `output_dir`
- AND no versioned sub-directories are created

#### SC-4-4-3: Cover letter chaining places output correctly

- GIVEN workspace mode with `--cover-letter` flag
- WHEN the pipeline completes and chains cover letter generation
- THEN resume output is in `resumes/v{N}/`
- AND cover letter output is in `cover-letter/v{M}/`
- AND `v{N}` and `v{M}` are determined independently

---

## Phase 5: Status Command & UX

### Purpose

Update the `mkcv status` command to display the new directory structure,
version counts, and handle mixed old/new layouts gracefully.

---

### REQ-5-1: Updated Application Table

The status command's application listing table MUST show the following columns:

| Column | Description |
|--------|-------------|
| Company | Company name from `application.toml` |
| Position | Position title |
| Date | Application date (YYYY-MM-DD) |
| Status | Application status |
| Resumes | Count of resume versions (e.g., "3 versions") or checkmark for old layout |
| Cover Letters | Count of cover letter versions or checkmark |
| Layout | `v2` for new layout, `v1` for old layout |

#### SC-5-1-1: New-layout application in table

- GIVEN an application with `resumes/v1/`, `resumes/v2/`, `cover-letter/v1/`
- WHEN `mkcv status` is run
- THEN the table row shows "2 versions" under Resumes, "1 version" under Cover Letters, and "v2" under Layout

#### SC-5-1-2: Old-layout application in table

- GIVEN an old-layout application with `resume.yaml` and `cover_letter.pdf` in the root
- WHEN `mkcv status` is run
- THEN the table row shows a checkmark under Resumes (not a version count), a checkmark under Cover Letters, and "v1" under Layout

#### SC-5-1-3: Application with no resume yet

- GIVEN a new application with no resume versions
- WHEN `mkcv status` is run
- THEN the table shows "0" or a cross mark under Resumes

---

### REQ-5-2: Version Summary in Detail View

When showing the most recent application, the status command SHOULD display
the latest version details for each artifact type.

#### SC-5-2-1: Latest version detail

- GIVEN the most recent application has `resumes/v3/` as the latest
- WHEN `mkcv status` is run
- THEN the "Most recent" line shows the application name
- AND SHOULD show "Latest resume: v3, Latest cover letter: v2" (or similar)

---

### REQ-5-3: Workspace Overview Counts

The workspace overview section MUST accurately count applications across
both layout versions.

#### SC-5-3-1: Mixed layout counts

- GIVEN 3 old-layout applications and 2 new-layout applications
- WHEN `mkcv status` is run
- THEN "Applications: 5" is displayed

---

## Phase 6: Migration Command

### Purpose

Provide an `mkcv migrate` command that converts old-layout application
directories to the new layout.

---

### REQ-6-1: Migrate Command

The system MUST provide a new CLI command `mkcv migrate` that transforms
old-layout application directories to the new layout.

**Flags:**
| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--dry-run` | `bool` | `False` | Show what would be done without making changes |
| `--company` | `str \| None` | `None` | Migrate only this company's applications |
| `--delete-old` | `bool` | `False` | Remove old directories after successful migration |

#### SC-6-1-1: Basic migration

- GIVEN an old-layout application at `applications/acme-corp/2025-06-swe-standard-v1/`
- WHEN `mkcv migrate` is run
- THEN a new directory is created at `applications/acme-corp/swe/2025-06-01/`
- AND `application.toml` is updated to v2 schema
- AND `jd.txt` is converted to `jd.md`
- AND `resume.yaml`, `resume.pdf`, `.mkcv/` are moved to `resumes/v1/`
- AND cover letter files are moved to `cover-letter/v1/`
- AND a success message is printed

#### SC-6-1-2: Dry-run mode

- GIVEN old-layout applications exist
- WHEN `mkcv migrate --dry-run` is run
- THEN the output lists each migration action that would be taken
- AND no files or directories are created, moved, or deleted

#### SC-6-1-3: --delete-old flag

- GIVEN a successful migration from old to new layout
- WHEN `--delete-old` is specified
- THEN the old directory is removed after successful migration
- AND a confirmation message is printed for each deletion

#### SC-6-1-4: --delete-old without confirmation is destructive

- GIVEN `--delete-old` is specified without `--dry-run`
- WHEN `mkcv migrate --delete-old` is run
- THEN the CLI SHOULD prompt for confirmation before deleting old directories
- AND the user can type "y" to confirm or "n" to skip deletions

---

### REQ-6-2: Migration Transformation Rules

**Directory name parsing (old → new):**
- Old pattern: `{YYYY-MM}-{position_slug}-{preset}-v{N}`
- Extract: `date` = `{YYYY-MM}-01`, `position_slug` = middle segments, `preset` = second-to-last segment, `version` = `{N}`
- New path: `{company_slug}/{position_slug}/{YYYY-MM-01}/`

**File transformations:**
| Old Location | New Location | Transformation |
|-------------|-------------|----------------|
| `application.toml` | `application.toml` | Add `schema_version = 2`, date → YYYY-MM-DD, add `preset` field |
| `jd.txt` | `jd.md` | Wrap with frontmatter from `application.toml` metadata |
| `resume.yaml` | `resumes/v1/resume.yaml` | Move (no content change) |
| `resume.pdf` | `resumes/v1/resume.pdf` | Move |
| `*.png` (resume renders) | `resumes/v1/*.png` | Move |
| `.mkcv/` (pipeline artifacts) | `resumes/v1/.mkcv/` | Move entire directory |
| `cover_letter.txt` | `cover-letter/v1/cover_letter.txt` | Move |
| `cover_letter.md` | `cover-letter/v1/cover_letter.md` | Move |
| `cover_letter.pdf` | `cover-letter/v1/cover_letter.pdf` | Move |
| `cover_letter.typ` | `cover-letter/v1/cover_letter.typ` | Move |

**Multiple versions in old layout:**
- If multiple old directories exist for the same company/position (e.g., `2025-06-swe-standard-v1`, `2025-06-swe-standard-v2`):
  - Each is migrated to the SAME application directory `swe/2025-06-01/`.
  - v1 → `resumes/v1/`, v2 → `resumes/v2/`.

#### SC-6-2-1: Parse old directory name

- GIVEN old directory name `2025-06-senior-backend-engineer-standard-v2`
- WHEN the name is parsed
- THEN `date` = `2025-06-01`
- AND `position_slug` = `senior-backend-engineer`
- AND `preset` = `standard`
- AND `version` = `2`

#### SC-6-2-2: Multiple old versions merge into one new application

- GIVEN old directories:
  - `applications/acme-corp/2025-06-swe-premium-v1/`
  - `applications/acme-corp/2025-06-swe-premium-v2/`
- WHEN `mkcv migrate` is run
- THEN a single directory `applications/acme-corp/swe/2025-06-01/` is created
- AND v1 artifacts go to `resumes/v1/`, v2 artifacts to `resumes/v2/`
- AND `application.toml` uses metadata from v1 (the original)

#### SC-6-2-3: JD conversion to markdown

- GIVEN an old application with `jd.txt` containing plain text
- WHEN migration runs
- THEN `jd.md` is created with YAML frontmatter (company, position, url from application.toml)
- AND the original JD text is the body below `---`

#### SC-6-2-4: Application with no resume (draft only)

- GIVEN an old application with `application.toml` and `jd.txt` but no `resume.yaml`
- WHEN migration runs
- THEN the new directory is created with `application.toml` and `jd.md`
- AND `resumes/` is created but empty
- AND no `cover-letter/` directory is created

---

### REQ-6-3: Migration Error Handling

**Rules:**
- If the target new-layout directory already exists with an `application.toml`, the migration for that application MUST be skipped with a warning.
- If a file move fails (permissions, disk space), the migration MUST stop for that application, report the error, and continue with other applications.
- Partial migrations MUST NOT corrupt the old directory — if migration fails midway, the old directory MUST remain intact.
- The migration MUST NOT delete old directories unless `--delete-old` is explicitly specified.

#### SC-6-3-1: Target directory already exists

- GIVEN an old-layout application that should migrate to `swe/2025-06-01/`
- AND `swe/2025-06-01/application.toml` already exists (previously migrated or created fresh)
- WHEN `mkcv migrate` is run
- THEN that application is skipped
- AND a warning is printed: "Skipping: target already exists: swe/2025-06-01/"

#### SC-6-3-2: Permission error during migration

- GIVEN the target directory is not writable
- WHEN file move is attempted
- THEN the migration for that application fails with a clear error message
- AND the old directory is left intact
- AND migration continues for other applications

#### SC-6-3-3: Partial migration rollback

- GIVEN migration starts (creates new directory, moves some files)
- AND a subsequent file move fails
- THEN already-moved files remain in the new directory (no rollback to old)
- AND the error is reported with instructions to manually complete the migration
- AND the old directory is NOT deleted (regardless of `--delete-old`)

#### SC-6-3-4: No old-layout applications found

- GIVEN all applications already use the new layout
- WHEN `mkcv migrate` is run
- THEN the output says "No old-layout applications found. Nothing to migrate."

#### SC-6-3-5: Company filter

- GIVEN old-layout applications for "acme-corp" and "big-tech"
- WHEN `mkcv migrate --company "Acme Corp"` is run
- THEN only "acme-corp" applications are migrated
- AND "big-tech" applications are untouched

---

### REQ-6-4: Migration Summary Output

After migration completes, the command MUST print a summary:

```
Migration complete:
  Migrated: 5 applications
  Skipped:  1 (already exists)
  Failed:   0

  Old directories: retained (use --delete-old to remove)
```

#### SC-6-4-1: Summary with mixed results

- GIVEN 3 old-layout apps: 2 migrate successfully, 1 target already exists
- WHEN `mkcv migrate` completes
- THEN the summary shows "Migrated: 2, Skipped: 1, Failed: 0"

---

## Cross-Cutting Concerns

### REQ-CC-1: No New External Dependencies

This change MUST NOT introduce any new external dependencies. PyYAML
(`pyyaml`) is already available as a transitive dependency and MUST be used
for YAML frontmatter parsing.

#### SC-CC-1-1: Dependency verification

- GIVEN the project's `pyproject.toml`
- WHEN dependencies are checked after implementation
- THEN no new entries appear in `[project.dependencies]`

---

### REQ-CC-2: Backward-Compatible API Surfaces

All changes to service and port interfaces MUST maintain backward
compatibility for standalone (non-workspace) mode.

- `PipelineService.generate()` MUST continue to accept a flat `output_dir`
  and place outputs directly inside it when not in workspace mode.
- `CoverLetterService.generate()` MUST behave identically in standalone mode.
- The `generate_command` and `cover_letter_command` MUST work identically
  outside a workspace.

#### SC-CC-2-1: Standalone mode unaffected

- GIVEN no workspace (running from a random directory)
- WHEN `mkcv generate --jd job.txt --kb career.md` is run
- THEN behavior is identical to the pre-change version
- AND no version sub-directories are created

---

### REQ-CC-3: Exception Hierarchy

New errors introduced by this change MUST follow the existing exception
hierarchy:

- `MigrationError(WorkspaceError)` — exit code 7 — for migration failures.
- File: `src/mkcv/core/exceptions/migration.py`

#### SC-CC-3-1: MigrationError inherits WorkspaceError

- GIVEN a `MigrationError` is raised
- THEN `isinstance(err, WorkspaceError)` is `True`
- AND `err.exit_code` is `7`

---

### REQ-CC-4: WorkspaceNaming Config Update

The `WorkspaceNaming` model's `application_pattern` field MUST be updated
from `"{date}-{position}"` to `"{position}/{date}"` in the default config.

The `mkcv.toml` template and `settings.toml` MUST reflect this change.

#### SC-CC-4-1: New workspace uses updated pattern

- GIVEN a freshly created workspace via `mkcv init`
- WHEN `mkcv.toml` is read
- THEN `application_pattern` is `"{position}/{date}"`

---

## Summary

| Phase | Requirements | Scenarios | Domain |
|-------|-------------|-----------|--------|
| 1 — JD Document Model & Reader | 4 | 17 | core/models, core/services |
| 2 — Enriched ApplicationMetadata | 3 | 7 | core/models, adapters/filesystem |
| 3 — New Directory Structure | 5 | 13 | core/ports, adapters/filesystem |
| 4 — Pipeline & Cover Letter Output | 4 | 9 | core/services, cli/commands |
| 5 — Status Command & UX | 3 | 5 | cli/commands |
| 6 — Migration Command | 4 | 10 | cli/commands, adapters/filesystem |
| CC — Cross-Cutting | 4 | 4 | all |
| **Total** | **27** | **65** | |

### Coverage Assessment
- **Happy paths:** Covered for all 6 phases
- **Edge cases:** Covered (collisions, partial dirs, mixed layouts, malformed frontmatter, empty bodies, long names, unknown keys, multiple old versions merging)
- **Error states:** Covered (permission errors, partial migration, missing files, invalid YAML, target exists)
- **Backward compatibility:** Covered (v1 TOML parsing, plain .txt JD, old-layout detection, standalone mode, dual-layout listing)

### Implementation Dependency Order
```
Phase 1 (JD Model) ──→ Phase 2 (Metadata) ──→ Phase 3 (Dir Structure) ──→ Phase 4 (Output) ──→ Phase 5 (Status)
                                                                                                       │
                                                                                              Phase 6 (Migration)
```

Phase 6 (Migration) depends on Phases 1-3 being complete but can be developed in parallel with Phases 4-5.
