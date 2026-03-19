# Tasks: Restructure Application Workspace

**Change:** restructure-application-workspace
**Date:** 2026-03-19
**Spec:** `docs/specs/restructure-application-workspace.md`
**Design:** `docs/changes/restructure-application-workspace/design.md`

---

## Phase 1: JD Document Model & Reader [COMPLETE]

### New Models

```
TASK-1.1: Create Compensation model [x]
Type: new
File(s): src/mkcv/core/models/compensation.py
Depends on: (none)
Effort: S
Description:
  Create a new Pydantic model `Compensation` with optional string fields:
  `base`, `equity`, `bonus`, `total`. All fields default to `None`.
  Follow one-class-per-file convention.
Acceptance:
  - File exists with class Compensation(BaseModel)
  - `uv run python -c "from mkcv.core.models.compensation import Compensation; print(Compensation())"`
    prints a model with all None fields
```

```
TASK-1.2: Create JDFrontmatter model
Type: new
File(s): src/mkcv/core/models/jd_frontmatter.py
Depends on: TASK-1.1
Effort: S
Description:
  Create `JDFrontmatter(BaseModel)` with fields: company (str|None),
  position (str|None), url (str|None), location (str|None),
  workplace (str|None with description), compensation (Compensation|None),
  posted_date (date|None), source (str|None with description),
  tags (list[str] with default_factory=list).
  Import Compensation from mkcv.core.models.compensation.
  Use `model_config = ConfigDict(extra="ignore")` to silently drop unknown keys
  (SC-1-2-6 forward compat).
Acceptance:
  - `JDFrontmatter()` creates an empty instance
  - `JDFrontmatter(company="Acme", unknown_field="x")` silently ignores unknown_field
```

```
TASK-1.3: Create JDDocument model
Type: new
File(s): src/mkcv/core/models/jd_document.py
Depends on: TASK-1.2
Effort: S
Description:
  Create `JDDocument(BaseModel)` with fields: metadata (JDFrontmatter|None = None),
  body (str), source_path (Path|None = None).
  Add a Pydantic validator on `body` that rejects empty/whitespace-only strings
  (raise ValueError "body must not be empty").
Acceptance:
  - `JDDocument(body="hello")` works
  - `JDDocument(body="")` raises ValidationError
  - `JDDocument(body="  \n  ")` raises ValidationError
  - Covers SC-1-1-1, SC-1-1-2, SC-1-1-3
```

### JD Reader Updates

```
TASK-1.4: Add parse_jd_document() to jd_reader.py
Type: modify
File(s): src/mkcv/core/services/jd_reader.py
Depends on: TASK-1.3
Effort: M
Description:
  Add imports: `re`, `yaml` (PyYAML), JDFrontmatter, JDDocument, ValidationError (pydantic).
  Add module-level constant:
    _FRONTMATTER_PATTERN = re.compile(r"\A\s*---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)
  Note: \A\s* tolerates leading whitespace (SC-1-2-7).
  
  Add function `parse_jd_document(text: str, *, source_path: Path | None = None) -> JDDocument`:
  1. Strip leading whitespace from text before matching (for SC-1-2-7).
  2. Match _FRONTMATTER_PATTERN. If no match, return JDDocument(body=text.strip(), source_path=source_path).
  3. Extract yaml_str and body_str from groups.
  4. Try yaml.safe_load(yaml_str). On YAMLError: log warning, return JDDocument(body=text.strip(), ...).
  5. If result is not dict: return JDDocument(body=text.strip(), ...).
  6. Try JDFrontmatter.model_validate(raw). On ValidationError: log warning for invalid fields
     (e.g., bad workplace literal), set metadata=None, use body_str.
  7. If body_str.strip() is empty: raise JDReadError("JD body is empty after frontmatter").
  8. Return JDDocument(metadata=metadata, body=body_str.strip(), source_path=source_path).

  Handle SC-1-2-4 (only opening ---): the regex won't match, so full text becomes body.
  Handle SC-1-2-5 (malformed YAML): caught by yaml.YAMLError.
  Handle SC-1-2-9 (invalid workplace): JDFrontmatter has extra="ignore" and workplace is str|None,
  so invalid literals are accepted as strings. Add a @field_validator on JDFrontmatter that checks
  workplace in ("remote", "hybrid", "onsite", None) and logs+sets to None if invalid.
Acceptance:
  - Covers SC-1-2-1 through SC-1-2-9
  - `uv run pytest tests/test_core/test_services/test_jd_reader.py -v` passes
```

```
TASK-1.5: Change read_jd() return type from str to JDDocument
Type: modify
File(s): src/mkcv/core/services/jd_reader.py
Depends on: TASK-1.4
Effort: S
Description:
  Update the `read_jd()` function:
  - Change return type annotation from `str` to `JDDocument`.
  - For stdin: `text = _read_stdin(); return parse_jd_document(text)`
  - For URL: `text = asyncio.run(_fetch_url(source)); return parse_jd_document(text)`
  - For file: `path = Path(source); text = _read_file(path); return parse_jd_document(text, source_path=path)`
  
  WARNING: This is a BREAKING CHANGE for all callers. Callers must be updated
  atomically (TASK-1.6 and TASK-1.7) or tests will fail.
Acceptance:
  - `read_jd(str(file))` returns a JDDocument, not a str
  - `read_jd(str(file)).body` returns the text content
  - Covers SC-1-3-1, SC-1-3-2
```

### Caller Updates (must be done atomically with TASK-1.5)

```
TASK-1.6: Update generate.py to use JDDocument
Type: modify
File(s): src/mkcv/cli/commands/generate.py
Depends on: TASK-1.5
Effort: M
Description:
  Update `_resolve_jd()` (line 389):
  - Change return type from `tuple[str, str]` to `tuple[str, str]`
    (keep returning jd_text string and display label — extract body from JDDocument).
  - `jd_doc = read_jd(source)` instead of `jd_text = read_jd(source)`
  - `jd_text = jd_doc.body`
  - Return `(jd_text, display)` as before.
  
  NOTE: In a later phase (Phase 4), this function will also return the JDDocument
  for frontmatter metadata extraction. For now, the minimal change is to call
  `.body` on the return value to maintain backward compat.
  
  No other changes to generate.py needed in this phase.
Acceptance:
  - `_resolve_jd("path/to/jd.txt")` still returns (str, str)
  - All existing tests in test_generate.py pass
  - The mocked `_resolve_jd` in tests returns (str, str), so no test changes needed
```

```
TASK-1.7: Update cover_letter.py to use JDDocument
Type: modify
File(s): src/mkcv/cli/commands/cover_letter.py
Depends on: TASK-1.5
Effort: S
Description:
  Update line 122: `jd_text = read_jd(jd)` to:
    `jd_doc = read_jd(jd)`
    `jd_text = jd_doc.body`
  No other changes needed in this phase.
Acceptance:
  - Cover letter command still works with plain text JD files
```

### Tests for Phase 1

```
TASK-1.8: Write tests for Compensation model
Type: test
File(s): tests/test_core/test_models/test_jd_models.py (NEW)
Depends on: TASK-1.1
Effort: S
Description:
  New test file. Tests:
  - test_compensation_all_none_defaults
  - test_compensation_with_all_fields
  - test_compensation_partial_fields
Acceptance:
  - `uv run pytest tests/test_core/test_models/test_jd_models.py -v` passes
```

```
TASK-1.9: Write tests for JDFrontmatter model
Type: test
File(s): tests/test_core/test_models/test_jd_models.py (append)
Depends on: TASK-1.2, TASK-1.8
Effort: S
Description:
  Add class TestJDFrontmatter:
  - test_all_defaults_are_none
  - test_with_all_fields
  - test_unknown_fields_silently_ignored (SC-1-2-6)
  - test_invalid_workplace_set_to_none (SC-1-2-9)
  - test_tags_default_to_empty_list
Acceptance:
  - All tests pass
```

```
TASK-1.10: Write tests for JDDocument model
Type: test
File(s): tests/test_core/test_models/test_jd_models.py (append)
Depends on: TASK-1.3, TASK-1.9
Effort: S
Description:
  Add class TestJDDocument:
  - test_body_only (SC-1-1-2)
  - test_body_with_metadata (SC-1-1-1)
  - test_empty_body_rejected (SC-1-1-3)
  - test_whitespace_body_rejected
  - test_source_path_optional
Acceptance:
  - All tests pass
```

```
TASK-1.11: Write tests for parse_jd_document()
Type: test
File(s): tests/test_core/test_services/test_jd_reader.py (append new class)
Depends on: TASK-1.4
Effort: M
Description:
  Add class TestParseJDDocument to existing test file:
  - test_parse_complete_frontmatter (SC-1-2-1)
  - test_parse_subset_frontmatter (SC-1-2-2)
  - test_parse_no_frontmatter_plain_text (SC-1-2-3)
  - test_parse_only_opening_delimiter (SC-1-2-4)
  - test_parse_malformed_yaml (SC-1-2-5)
  - test_parse_unknown_keys_ignored (SC-1-2-6)
  - test_parse_leading_whitespace (SC-1-2-7)
  - test_parse_empty_body_after_frontmatter (SC-1-2-8)
  - test_parse_invalid_workplace_dropped (SC-1-2-9)
Acceptance:
  - `uv run pytest tests/test_core/test_services/test_jd_reader.py::TestParseJDDocument -v` passes
```

```
TASK-1.12: Update existing read_jd tests for JDDocument return type
Type: test
File(s): tests/test_core/test_services/test_jd_reader.py (MODIFY existing)
Depends on: TASK-1.5
Effort: M
Description:
  UPDATE existing tests in TestReadJDFromFile, TestReadJDFromURL, TestReadJDFromStdin:
  - Every assertion `assert result == "some text"` must become
    `assert result.body == "some text"` (result is now JDDocument).
  - TestReadJDFromURL: mock return values are `str` from `_fetch_url`, which
    is unchanged. But `read_jd()` now wraps in parse_jd_document, so the
    tests that mock `_fetch_url` still work. The tests that mock `read_jd`
    directly need their return values changed to match JDDocument (but these
    are in test_generate.py, not here).
  - Specifically update these tests:
    - TestReadJDFromFile.test_reads_file_content: `assert result.body == ...`
    - TestReadJDFromFile.test_strips_whitespace: `assert result.body == ...`
    - TestReadJDFromURL.test_fetches_url_content: `assert result.body == ...`
    - TestReadJDFromURL.test_http_url_also_works: `assert result.body == ...`
    - TestReadJDFromStdin.test_reads_stdin_content: `assert result.body == ...`
    - TestReadJDFromStdin.test_empty_string_source_reads_stdin: `assert result.body == ...`
  - Add new tests:
    - test_read_jd_returns_jd_document_type
    - test_read_jd_file_with_frontmatter_parses_metadata (SC-1-3-2)
    
  WARNING: These test changes must be committed atomically with TASK-1.5, 1.6, 1.7
  or existing tests will break.
Acceptance:
  - `uv run pytest tests/test_core/test_services/test_jd_reader.py -v` all pass
```

```
TASK-1.13: Run full test suite to verify Phase 1
Type: test
File(s): (all)
Depends on: TASK-1.5, TASK-1.6, TASK-1.7, TASK-1.12
Effort: S
Description:
  Run `uv run pytest` to verify no regressions.
  Run `uv run ruff check src/ tests/` for lint.
  Run `uv run mypy src/` for type checking.
  Fix any issues found.
Acceptance:
  - All tests pass
  - No ruff violations
  - mypy --strict passes
```

---

## Phase 2: Enriched ApplicationMetadata

```
TASK-2.1: Add v2 fields to ApplicationMetadata
Type: modify
File(s): src/mkcv/core/models/application_metadata.py
Depends on: TASK-1.1
Effort: S
Description:
  Add new fields to ApplicationMetadata:
  - preset: str | None = None
  - compensation: Compensation | None = None
  - location: str | None = None
  - workplace: str | None = None
  - source: str | None = None
  - tags: list[str] = Field(default_factory=list)
  - notes: str = ""
  
  Import Compensation from mkcv.core.models.compensation.
  
  All fields have defaults, so existing v1 application.toml files continue
  to parse without error (backward compat).
  
  NOTE: The spec calls for schema_version field. However, the design doc
  omits it in favor of layout detection heuristic (_detect_layout).
  Follow the design: no schema_version field. Layout detection is used instead.
Acceptance:
  - `ApplicationMetadata(company="X", position="Y", date=date.today())` works
  - All new fields default to None/[]/""
  - Existing tests in test_workspace_models.py still pass
```

```
TASK-2.2: Create RunMetadata model
Type: new
File(s): src/mkcv/core/models/run_metadata.py
Depends on: (none)
Effort: S
Description:
  Create `RunMetadata(BaseModel)` with fields:
  - preset: str
  - provider: str
  - model: str
  - timestamp: datetime = Field(default_factory=datetime.now)
  - duration_seconds: float = 0.0
  - review_score: int = 0
  - total_cost_usd: float = 0.0
Acceptance:
  - `RunMetadata(preset="standard", provider="anthropic", model="claude-sonnet-4-20250514")`
    creates a valid instance
```

```
TASK-2.3: Update _write_application_toml() for v2 fields
Type: modify
File(s): src/mkcv/adapters/filesystem/workspace_manager.py
Depends on: TASK-2.1
Effort: S
Description:
  Update `_write_application_toml()` (line 882) to serialize the new fields:
  Add to the `data["application"]` dict:
  - "preset": metadata.preset or ""
  - "location": metadata.location or ""
  - "workplace": metadata.workplace or ""
  - "source": metadata.source or ""
  - "tags": metadata.tags
  - "notes": metadata.notes
  
  Add compensation sub-section:
  ```python
  if metadata.compensation is not None:
      comp = metadata.compensation.model_dump(exclude_none=True)
      if comp:
          data["application"]["compensation"] = comp
  ```
Acceptance:
  - New application.toml files contain all v2 fields
  - Existing code that reads application.toml still works (fields are additive)
```

```
TASK-2.4: Update _read_application_metadata in status.py for v2 compat
Type: modify
File(s): src/mkcv/cli/commands/status.py
Depends on: TASK-2.1
Effort: S
Description:
  The `_read_application_metadata()` function (line 135) creates ApplicationMetadata
  via `ApplicationMetadata(**app_data)`. Since all new fields have defaults,
  this already handles v1 TOML files (missing fields get defaults).
  
  No code change needed — but verify by running tests.
  
  If the `compensation` field in TOML is a dict (sub-table), Pydantic v2
  will auto-coerce it to Compensation model. Verify this works.
Acceptance:
  - `_read_application_metadata()` works for v1 TOML (no new fields)
  - `_read_application_metadata()` works for v2 TOML (all new fields)
```

### Tests for Phase 2

```
TASK-2.5: Write tests for ApplicationMetadata v2 fields
Type: test
File(s): tests/test_core/test_models/test_workspace_models.py (append)
Depends on: TASK-2.1
Effort: S
Description:
  Add new tests to TestApplicationMetadata class:
  - test_v2_fields_default_to_none: preset, compensation, location, workplace, source all None
  - test_v2_tags_default_to_empty_list
  - test_v2_notes_default_to_empty_string
  - test_v2_all_fields_populated: create with all new fields, verify
  - test_v1_compat_missing_new_fields: construct from dict with only v1 fields
  - test_compensation_as_nested_model: create with Compensation(base="$150k")
Acceptance:
  - All tests pass
```

```
TASK-2.6: Write tests for RunMetadata model
Type: test
File(s): tests/test_core/test_models/test_run_metadata.py (NEW)
Depends on: TASK-2.2
Effort: S
Description:
  New test file. Tests:
  - test_creation_with_required_fields
  - test_defaults_for_optional_fields
  - test_timestamp_auto_populated
  - test_model_dump_json_serializable
Acceptance:
  - `uv run pytest tests/test_core/test_models/test_run_metadata.py -v` passes
```

```
TASK-2.7: Write test for v2 application.toml round-trip
Type: test
File(s): tests/test_adapters/test_workspace_manager.py (append)
Depends on: TASK-2.3
Effort: S
Description:
  Add test to TestCreateApplication:
  - test_application_toml_contains_v2_fields: Create application, read TOML back,
    verify preset, location, tags etc. are present.
  - test_v1_application_toml_readable_by_v2_code: manually write a v1 TOML file
    (no new fields), read it with _read_application_metadata, verify defaults applied.
Acceptance:
  - Tests pass
```

```
TASK-2.8: Update WorkspaceNaming default application_pattern
Type: modify
File(s): src/mkcv/core/models/workspace_config.py
Depends on: (none)
Effort: S
Description:
  Change `WorkspaceNaming.application_pattern` default from `"{date}-{position}"`
  to `"{company}/{position}/{date}"` (line 18).
  
  WARNING: This will break test_default_naming in test_workspace_models.py.
  Must update test atomically.
Acceptance:
  - `WorkspaceNaming().application_pattern == "{company}/{position}/{date}"`
```

```
TASK-2.9: Update test for WorkspaceNaming default
Type: test
File(s): tests/test_core/test_models/test_workspace_models.py (MODIFY)
Depends on: TASK-2.8
Effort: S
Description:
  Update test_default_naming (line 38):
  - Change assertion from `== "{date}-{position}"` to `== "{company}/{position}/{date}"`
  
  WARNING: Must be committed atomically with TASK-2.8.
Acceptance:
  - test_default_naming passes with new assertion
```

```
TASK-2.10: Update _MKCV_TOML_TEMPLATE and settings.toml
Type: modify
File(s):
  - src/mkcv/adapters/filesystem/workspace_manager.py (template on line 36)
  - src/mkcv/config/settings.toml (line 113)
Depends on: TASK-2.8
Effort: S
Description:
  In workspace_manager.py, update _MKCV_TOML_TEMPLATE line 36:
    `application_pattern = "{date}-{position}"`
    → `application_pattern = "{company}/{position}/{date}"`
  
  In settings.toml, update line 113:
    `naming_pattern = "{date}-{position}"`
    → `naming_pattern = "{company}/{position}/{date}"`
Acceptance:
  - `mkcv init /tmp/test-ws` creates mkcv.toml with new pattern
  - SC-CC-4-1: New workspace uses updated pattern
```

```
TASK-2.11: Run full test suite to verify Phase 2
Type: test
File(s): (all)
Depends on: TASK-2.9, TASK-2.10
Effort: S
Description:
  Run `uv run pytest` to verify no regressions.
  Run `uv run ruff check src/ tests/` and `uv run mypy src/`.
Acceptance:
  - All tests pass, no lint or type errors
```

---

## Phase 3: New Directory Structure

### Path Construction

```
TASK-3.1: Add _build_application_path() to WorkspaceManager
Type: modify
File(s): src/mkcv/adapters/filesystem/workspace_manager.py
Depends on: TASK-2.1
Effort: S
Description:
  Add new private method `_build_application_path(self, workspace_root, company, position, app_date) -> Path`:
  - `apps_base = self.get_applications_dir(workspace_root)`
  - `company_slug = self.slugify(company)`
  - `position_slug = self.slugify(position)`
  - `date_str = app_date.strftime("%Y-%m-%d")`
  - `app_dir = apps_base / company_slug / position_slug / date_str`
  - If `app_dir.exists()` and `(app_dir / "application.toml").is_file()`:
    raise WorkspaceError with message about existing dir (SC-3-2-1)
  - Return app_dir
  
  This uses YYYY-MM-DD format (SC-2-3-1) and company/position/date structure (SC-3-1-1).
Acceptance:
  - Returns path like `applications/acme-corp/senior-software-engineer/2026-03-19`
  - Raises WorkspaceError if dir exists with application.toml
  - Does NOT raise if dir exists without application.toml (SC-3-2-3)
```

```
TASK-3.2: Rewrite create_application() for new layout
Type: modify
File(s): src/mkcv/adapters/filesystem/workspace_manager.py
Depends on: TASK-3.1, TASK-1.3
Effort: L
Description:
  Rewrite `create_application()` (line 677). New signature:
  ```python
  def create_application(
      self,
      workspace_root: Path,
      company: str,
      position: str,
      jd_source: Path | str,
      *,
      preset_name: str = "standard",
      url: str | None = None,
      jd_document: JDDocument | None = None,
  ) -> Path:
  ```
  
  Implementation:
  1. `today = date.today()`
  2. `app_dir = self._build_application_path(workspace_root, company, position, today)`
  3. `app_dir.mkdir(parents=True, exist_ok=True)`
  4. `(app_dir / "resumes").mkdir(exist_ok=True)` — create empty resumes/ dir (SC-3-3-1)
  5. Write JD as jd.md:
     - If jd_document is not None: call `self._write_jd_markdown(jd_document, app_dir, url=url)`
     - Elif isinstance(jd_source, Path): copy to app_dir / "jd.md" (not jd.txt)
     - Else (str): write raw text to app_dir / "jd.md"
  6. Build metadata: `self._build_application_metadata(company=company, position=position, date=today, url=url, preset_name=preset_name, jd_document=jd_document)`
  7. `self._write_application_toml(app_dir, metadata)`
  8. Return app_dir
  
  Remove: creation of `.mkcv/` directory (artifacts now go in resumes/v{N}/.mkcv/)
  Remove: `shutil.copy2(jd_source, app_dir / "jd.txt")` — replaced by jd.md logic
  Remove: versioning in dirname (no more `-v{N}` suffix)
  
  WARNING: This changes the directory layout fundamentally. Many existing tests
  will break and must be updated (TASK-3.9).
Acceptance:
  - New apps created at `applications/{company_slug}/{position_slug}/{YYYY-MM-DD}/`
  - Contains: application.toml, jd.md, resumes/ (empty dir)
  - Does NOT contain: .mkcv/, jd.txt
  - Covers SC-3-1-1, SC-3-3-1
```

```
TASK-3.3: Add _write_jd_markdown() helper
Type: modify
File(s): src/mkcv/adapters/filesystem/workspace_manager.py
Depends on: TASK-1.3
Effort: S
Description:
  Add private method `_write_jd_markdown(self, jd_document, app_dir, *, url=None) -> Path`:
  - Build frontmatter from jd_document.metadata (if not None)
  - Write `---\n{yaml}\n---\n\n{body}\n` to app_dir / "jd.md"
  - If metadata is None or has no populated fields, write body only (no frontmatter block)
  - Use yaml.dump() for the frontmatter dict
  - Return path to written file
  
  Follow design doc section 4.4 exactly.
Acceptance:
  - JD with frontmatter is written with `---` delimiters
  - JD without frontmatter is written as plain markdown
  - Covers SC-1-4-1, SC-1-4-2
```

```
TASK-3.4: Add _build_application_metadata() helper
Type: modify
File(s): src/mkcv/adapters/filesystem/workspace_manager.py
Depends on: TASK-2.1
Effort: S
Description:
  Add private method `_build_application_metadata(self, *, company, position, date, url, preset_name, jd_document) -> ApplicationMetadata`:
  - Extract frontmatter metadata from jd_document (if provided)
  - Build ApplicationMetadata with all v2 fields populated from frontmatter
  - Follow design doc section 4.5 exactly
Acceptance:
  - Returns ApplicationMetadata with enriched fields from JD frontmatter
  - Falls back to None for fields not in frontmatter
```

### Sub-folder Versioning

```
TASK-3.5: Add create_output_version() to WorkspaceManager
Type: modify
File(s): src/mkcv/adapters/filesystem/workspace_manager.py
Depends on: (none)
Effort: S
Description:
  Add public method `create_output_version(self, app_dir, output_type) -> Path`:
  - `parent = app_dir / output_type`
  - `parent.mkdir(parents=True, exist_ok=True)`
  - `version = self._next_version_subfolder(parent)` (new static method)
  - `version_dir = parent / f"v{version}"`
  - `version_dir.mkdir()`
  - `(version_dir / ".mkcv").mkdir()`
  - Return version_dir
  
  Add static method `_next_version_subfolder(parent: Path) -> int`:
  - Scan for directories matching `v{N}` pattern (re.compile(r"^v(\d+)$"))
  - Return max(N) + 1, or 1 if none exist
  
  NOTE: This is distinct from the existing module-level `_next_version()` which
  uses a `{base_name}-v{N}` pattern. Keep the old one for backward compat
  (used by _default_output_dir in generate.py for generic resumes).
Acceptance:
  - First call returns app_dir/resumes/v1/ with .mkcv/ inside
  - Second call returns app_dir/resumes/v2/
  - Works for "resumes" and "cover-letter" output types
```

### Application Discovery Updates

```
TASK-3.6: Add _detect_layout() to WorkspaceManager
Type: modify
File(s): src/mkcv/adapters/filesystem/workspace_manager.py
Depends on: (none)
Effort: S
Description:
  Add method `_detect_layout(self, app_dir: Path) -> Literal["v1", "v2"]`:
  - If `(app_dir / "resumes").is_dir()` or `(app_dir / "jd.md").is_file()`: return "v2"
  - Return "v1"
  
  Follow design doc section 5.1.
Acceptance:
  - Correctly identifies v1 and v2 layouts (SC-3-5-1, SC-3-5-2, SC-3-5-3)
```

```
TASK-3.7: Update list_applications() for timestamp sort
Type: modify
File(s): src/mkcv/adapters/filesystem/workspace_manager.py
Depends on: TASK-3.6
Effort: M
Description:
  Update `list_applications()` (line 781):
  - Keep using `apps_dir.rglob("application.toml")` for discovery
  - Change sort from `sorted(...)` (lexicographic) to `sorted(..., key=self._app_sort_key)`
  
  Add static method `_app_sort_key(app_dir: Path) -> tuple[str, str]`:
  - Read created_at from application.toml
  - Return (created_at_str, str(app_dir)) for stable sort
  - On any error, return ("", str(app_dir)) — lexicographic fallback
  
  Update `find_latest_application()` (line 805):
  - Instead of filtering by `app.parent == company_dir`, use `_matches_company()`
  - Instead of `all_apps[-1]`, use `max(all_apps, key=self._app_sort_key)` or
    just use `all_apps[-1]` since list_applications already sorts by timestamp.
  
  Add method `_matches_company(self, app_dir, apps_dir, company_slug) -> bool`:
  - `relative = app_dir.relative_to(apps_dir)`
  - `return relative.parts[0] == company_slug`
  - This works for both v1 (company is first dir) and v2 (company is first dir too)
  
  WARNING: Existing tests use `app.parent == company_dir` to verify filtering.
  The new `_matches_company()` approach works for both layouts.
  Test test_find_latest_application_with_company_filter (line 74 in resolution tests)
  asserts `result.parent.name == "alpha-inc"` — this still holds for v1 layout.
Acceptance:
  - list_applications returns apps sorted by created_at timestamp
  - find_latest_application filters by company correctly for both layouts
  - Covers SC-3-4-1, SC-3-4-2
```

```
TASK-3.8: Update resolve_resume_path() for new layout
Type: modify
File(s): src/mkcv/adapters/filesystem/workspace_manager.py
Depends on: TASK-3.5
Effort: S
Description:
  Update `resolve_resume_path()` (line 839):
  - First, check new layout: `resumes_dir = app_dir / "resumes"`
    - If resumes_dir.is_dir(), find latest v{N} dir, check for resume.yaml
  - Fall back to old layout: `app_dir / "resume.yaml"`
  
  Add helper `_find_latest_version(self, parent: Path) -> Path | None`:
  - Scan for v{N} directories, return the one with highest N, or None
  
  Add `resolve_cover_letter_path(self, app_dir: Path) -> Path | None`:
  - Same pattern: check `cover-letter/v{latest}/cover_letter.md` then
    `cover-letter/v{latest}/cover_letter.pdf`
  - Fall back to `app_dir / "cover_letter.md"` or `app_dir / "cover_letter.pdf"`
  
  Follow design doc section 5.3.
Acceptance:
  - Finds resume in resumes/v2/ when v1/ and v2/ exist (SC-3-4-3)
  - Falls back to app_dir/resume.yaml for old layout (SC-3-4-4)
```

### Port & Service Updates

```
TASK-3.9: Update WorkspacePort protocol
Type: modify
File(s): src/mkcv/core/ports/workspace.py
Depends on: TASK-1.3
Effort: S
Description:
  Update create_application() signature:
  - Change `jd_source: Path` to `jd_source: Path | str`
  - Add keyword-only param: `jd_document: JDDocument | None = None`
  - Add import for JDDocument
  
  Add new protocol methods:
  - `create_output_version(self, app_dir: Path, output_type: str) -> Path: ...`
  - `resolve_cover_letter_path(self, app_dir: Path) -> Path | None: ...`
Acceptance:
  - Protocol defines all new method signatures
  - mypy validates WorkspaceManager against the protocol
```

```
TASK-3.10: Update WorkspaceService to delegate new methods
Type: modify
File(s): src/mkcv/core/services/workspace.py
Depends on: TASK-3.9
Effort: S
Description:
  Update `setup_application()` (line 48):
  - Change `jd_source: Path` to `jd_source: Path | str`
  - Add keyword-only param: `jd_document: JDDocument | None = None`
  - Pass `jd_document=jd_document` to self._workspace.create_application()
  
  Add new delegation methods:
  - `create_output_version(self, app_dir, output_type) -> Path`
  - `resolve_cover_letter_path(self, app_dir) -> Path | None`
Acceptance:
  - WorkspaceService correctly delegates all new methods to the port
```

### Test Updates for Phase 3

```
TASK-3.11: Update TestCreateApplication tests for new layout
Type: test
File(s): tests/test_adapters/test_workspace_manager.py (MODIFY)
Depends on: TASK-3.2
Effort: L
Description:
  The following tests must be REWRITTEN because directory layout changed:
  
  1. test_creates_application_directory (line 73): Verify app_dir is under
     `applications/{company_slug}/{position_slug}/{date}/`
  
  2. test_copies_jd_file (line 91): Change to check `jd.md` exists (not `jd.txt`)
     Rename to `test_writes_jd_markdown`
  
  3. test_jd_file_content_matches_source (line 98): Check jd.md content
     Contains the body text (may have frontmatter prepended)
  
  4. test_creates_mkcv_subdir (line 110): REMOVE — .mkcv no longer created at app level
     Replace with: `test_creates_resumes_subdir`: verify `resumes/` exists
  
  5. test_application_dir_uses_company_slug (line 119): Still valid, adjust path check
  
  6. test_handles_name_collisions_with_versioning (line 128): REWRITE —
     Same company/position/date now raises WorkspaceError (SC-3-2-1).
     New test: `test_same_date_raises_workspace_error`
     New test: `test_different_date_creates_separate_dir` (SC-3-2-2)
  
  7. test_preset_name_in_directory_name (line 143): REMOVE — preset no longer in dirname
     Replace with: `test_preset_stored_in_application_toml`
  
  8. test_different_presets_get_separate_versioning (line 156): REMOVE — no longer relevant
  
  9. test_version_increments_correctly (line 177): REMOVE — no more dirname versioning
  
  Add NEW tests:
  - test_new_layout_path_structure: verify company/position/date structure
  - test_partial_directory_reused (SC-3-2-3)
  - test_jd_document_enriches_metadata (SC-2-1-4)
Acceptance:
  - All rewritten/new tests pass
  - No references to old `-v{N}` dirname pattern in Phase 3 tests
```

```
TASK-3.12: Write tests for create_output_version()
Type: test
File(s): tests/test_adapters/test_workspace_manager.py (append)
Depends on: TASK-3.5
Effort: S
Description:
  Add class TestCreateOutputVersion:
  - test_first_version_creates_v1: returns app_dir/resumes/v1/
  - test_second_version_creates_v2: v1 exists, returns v2
  - test_creates_mkcv_inside_version: .mkcv/ dir created inside version
  - test_cover_letter_versioning_independent: resumes at v3, cover-letter creates v1
  - test_creates_parent_directory_if_missing: cover-letter/ doesn't exist yet
Acceptance:
  - All tests pass
```

```
TASK-3.13: Write tests for dual-layout detection and discovery
Type: test
File(s): tests/test_adapters/test_workspace_manager_resolution.py (MODIFY + append)
Depends on: TASK-3.6, TASK-3.7, TASK-3.8
Effort: M
Description:
  Add class TestDetectLayout:
  - test_v2_layout_with_resumes_dir (SC-3-5-1)
  - test_v2_layout_with_jd_md (SC-3-5-1)
  - test_v1_layout_no_resumes_no_jd_md (SC-3-5-2)
  - test_ambiguous_treated_as_v1 (SC-3-5-3)
  
  Add class TestResolveResumePathV2:
  - test_resolve_from_versioned_resumes (SC-3-4-3)
  - test_resolve_latest_version: v1/ and v2/ exist, returns v2/resume.yaml
  - test_fallback_to_root_resume (SC-3-4-4)
  - test_no_resume_returns_none
  
  Add to TestFindLatestApplication:
  - test_mixed_layout_sorted_by_timestamp (SC-3-4-1)
  - test_company_filter_works_for_v2_layout
  
  Update existing tests:
  - test_find_latest_application_with_company_filter: The assertion
    `result.parent.name == "alpha-inc"` may need adjustment for v2 layout
    where parent chain is company/position/date. For v1 dirs the assertion
    is still valid. Keep as-is (test uses v1 dir names).
Acceptance:
  - All resolution tests pass for both old and new layouts
```

```
TASK-3.14: Update WorkspaceService tests
Type: test
File(s): tests/test_core/test_services/test_workspace_service.py (MODIFY)
Depends on: TASK-3.10
Effort: S
Description:
  Update test_setup_application_creates_dir (line 33):
  - Change assertion `(app_dir / "jd.txt").is_file()` to `(app_dir / "jd.md").is_file()`
  - Verify `(app_dir / "resumes").is_dir()`
  
  Add new tests:
  - test_create_output_version_delegates: verify delegation to port
  - test_resolve_cover_letter_path_delegates
Acceptance:
  - All workspace service tests pass
```

```
TASK-3.15: Run full test suite to verify Phase 3
Type: test
File(s): (all)
Depends on: TASK-3.14
Effort: S
Description:
  Run `uv run pytest` — fix any remaining failures.
  Run `uv run ruff check src/ tests/` and `uv run mypy src/`.
Acceptance:
  - All tests pass, no lint or type errors
```

---

## Phase 4: Pipeline & Cover Letter Output Placement

```
TASK-4.1: Update generate.py for versioned output in workspace mode
Type: modify
File(s): src/mkcv/cli/commands/generate.py
Depends on: TASK-3.5, TASK-3.10
Effort: M
Description:
  Update `_resolve_jd()` to return JDDocument alongside the display text:
  - Change to `def _resolve_jd(source: str) -> tuple[str, str, JDDocument | None]:`
  - OR keep current signature and store jd_doc as a side effect (less clean).
  - PREFERRED: Change to return `tuple[str, str]` but also have generate_command
    call `read_jd()` directly to get JDDocument for metadata.
  
  Actually, simplest approach: In `generate_command()`, after `_resolve_jd()` returns,
  if we need frontmatter metadata, re-parse the jd_text through `parse_jd_document()`.
  This avoids changing `_resolve_jd` signature.
  
  Update `_generate_workspace_mode()`:
  - After `setup_application()` returns app_dir:
    ```python
    version_dir = workspace_service.create_output_version(app_dir, "resumes")
    run_dir = output_dir or version_dir
    ```
  - Pass `jd_document=jd_doc` to `setup_application()` (need JDDocument from read_jd).
  - Write JD to run_dir for pipeline: `jd_path = _write_jd_file(jd_text, run_dir)`
  
  Auto-fill company/position from frontmatter when not provided via CLI:
  ```python
  jd_doc = read_jd(jd) if jd is not None else None
  if jd_doc and jd_doc.metadata:
      company = company or jd_doc.metadata.company
      position = position or jd_doc.metadata.position
  jd_text = jd_doc.body if jd_doc else _build_generic_jd(target)
  ```
  
  WARNING: The `_resolve_jd` mock in test_generate.py returns `(str, str)`. 
  Since we're changing generate_command to call read_jd() directly before _resolve_jd,
  we need to update the mocking approach.
  
  ALTERNATIVE simpler approach: Keep `_resolve_jd()` unchanged for now. Inside
  `_generate_workspace_mode()`, parse frontmatter from jd_text using parse_jd_document():
  ```python
  jd_doc = parse_jd_document(jd_text)
  ```
  This avoids changing any function signatures or test mocks. The frontmatter
  parsing is idempotent (parsing already-extracted body is a no-op).
Acceptance:
  - In workspace mode, pipeline outputs go to resumes/v{N}/ not app_dir root
  - resume.yaml at resumes/v1/resume.yaml
  - .mkcv/ at resumes/v1/.mkcv/
  - Standalone mode unchanged (SC-CC-2-1)
  - Covers SC-4-1-1, SC-4-1-2, SC-4-4-1, SC-4-4-2
```

```
TASK-4.2: Add _write_run_metadata() to generate.py
Type: modify
File(s): src/mkcv/cli/commands/generate.py
Depends on: TASK-2.2, TASK-4.1
Effort: S
Description:
  Add function `_write_run_metadata(result: PipelineResult, version_dir: Path, *, preset: str) -> None`:
  - Create RunMetadata from PipelineResult fields
  - Write to `version_dir / "run-metadata.toml"` using tomli_w
  - OR write to `version_dir / ".mkcv" / "run_metadata.json"` using model_dump_json
  
  Follow design doc section 6.4 — the design uses `.mkcv/run_metadata.json`.
  
  Call after successful pipeline run in workspace mode:
  ```python
  if use_workspace_mode and version_dir:
      _write_run_metadata(result, version_dir, preset=preset)
  ```
  
  In standalone mode, do NOT write run metadata (no version_dir).
Acceptance:
  - After pipeline run in workspace mode, run metadata JSON exists
  - Contains preset, provider, model, timestamp, duration, score
  - Covers SC-4-3-1
```

```
TASK-4.3: Update cover_letter.py for versioned output
Type: modify
File(s): src/mkcv/cli/commands/cover_letter.py
Depends on: TASK-3.5, TASK-3.10
Effort: M
Description:
  When output goes to a workspace application directory, create a versioned
  sub-folder:
  
  In the section where `resolved_output` is determined from an app_dir:
  - After resolving app_dir, call `workspace_service.create_output_version(app_dir, "cover-letter")`
  - Use the version_dir as the output directory
  
  This affects:
  - `_resolve_from_app_dir()`: resolved_output should point to cover-letter/v{N}/ not app_dir
  - `_resolve_from_company()`: same
  - `_place_in_application_dir()`: after creating app dir, create cover-letter/v1/ for output
  
  Key changes:
  1. When app_dir is known: `version_dir = workspace_service.create_output_version(app_dir, "cover-letter")`
  2. Pass version_dir as gen_dir (not app_dir)
  3. Write run metadata after CL generation
  
  NOTE: The cover-letter/ directory is created on first cover letter generation,
  NOT during setup_application (SC-3-3-1).
  
  In standalone mode (no workspace): behavior unchanged.
Acceptance:
  - Cover letter output in cover-letter/v1/ not app_dir root
  - Second generation goes to cover-letter/v2/
  - cover-letter/ directory created on demand, not by create_application
  - Covers SC-4-2-1, SC-4-2-2, SC-4-4-3
```

```
TASK-4.4: Update _chain_cover_letter in generate.py
Type: modify
File(s): src/mkcv/cli/commands/generate.py
Depends on: TASK-4.3
Effort: S
Description:
  Update `_chain_cover_letter()` (line 788):
  - When in workspace mode, compute cover-letter version dir independently:
    `cl_version_dir = workspace_service.create_output_version(app_dir, "cover-letter")`
  - Pass cl_version_dir as output_dir to cl_service.generate()
  
  Current code passes `output_dir` which is the resume version dir. Change to
  pass the CL version dir.
  
  NOTE: Need to thread app_dir through to this function. Add `app_dir: Path | None = None`
  parameter to `_chain_cover_letter()` and `_run_pipeline()`.
Acceptance:
  - Resume in resumes/v1/, cover letter in cover-letter/v1/ (independent versioning)
  - Covers SC-4-4-3
```

### Tests for Phase 4

```
TASK-4.5: Update test_generate.py for versioned workspace output
Type: test
File(s): tests/test_cli/test_generate.py (MODIFY)
Depends on: TASK-4.1
Effort: M
Description:
  Update TestGenerateWorkspaceMode:
  - test_workspace_mode_calls_workspace_service: The mock workspace_service now
    needs create_output_version to be called. Add assertion:
    `mock_ws_service.create_output_version.assert_called_once_with(app_dir, "resumes")`
  - The output_dir passed to pipeline should be the version_dir, not app_dir.
  
  Add new tests:
  - test_workspace_mode_output_in_versioned_dir: verify pipeline.generate called
    with output_dir = version_dir (resumes/v1/)
  - test_standalone_mode_no_version_dir: verify no create_output_version called
  - test_run_metadata_written_in_workspace_mode
Acceptance:
  - All generate tests pass
```

```
TASK-4.6: Write tests for run metadata writing
Type: test
File(s): tests/test_cli/test_generate.py (append) OR tests/test_cli/test_run_metadata.py (NEW)
Depends on: TASK-4.2
Effort: S
Description:
  Test _write_run_metadata function:
  - test_writes_run_metadata_json: verify file created
  - test_run_metadata_contains_expected_fields
  - test_run_metadata_not_written_standalone_mode
Acceptance:
  - Tests pass
```

```
TASK-4.7: Run full test suite to verify Phase 4
Type: test
File(s): (all)
Depends on: TASK-4.6
Effort: S
Description:
  Run `uv run pytest`, `uv run ruff check src/ tests/`, `uv run mypy src/`.
Acceptance:
  - All tests pass, no lint or type errors
```

---

## Phase 5: Status Command & UX

```
TASK-5.1: Update status table for new columns and dual layout
Type: modify
File(s): src/mkcv/cli/commands/status.py
Depends on: TASK-3.6
Effort: M
Description:
  Update `_build_application_table()` (line 92):
  
  Add columns: "Preset", "Versions", "Resume", "CL", "Layout"
  Remove columns: "Resume YAML" (replaced by "Resume"), "PDF" (replaced by "CL")
  
  New column layout (9 columns total):
  - Company, Position, Date, Status, Preset, Versions, Resume, CL, Layout
  
  For each app_dir:
  1. Read metadata (existing)
  2. Detect layout: `layout = _detect_layout(app_dir)` (import from workspace_manager or inline)
  3. If v2:
     - Count resume versions: len of v{N} dirs in resumes/
     - Count CL versions: len of v{N} dirs in cover-letter/
     - versions_str = f"r:{resume_count} cl:{cl_count}"
     - has_resume = resume_count > 0
     - has_cl = cl_count > 0
  4. If v1:
     - has_resume = (app_dir / "resume.yaml").is_file()
     - has_cl = any(app_dir.glob("cover_letter.*"))
     - versions_str = "v1 (legacy)"
  5. Display check marks and layout column
  
  Add helper `_count_versions(app_dir: Path, output_type: str) -> int`:
  - Count v{N} subdirectories
  
  Add helper `_detect_layout(app_dir: Path) -> str`:
  - Inline version of WorkspaceManager._detect_layout (to avoid coupling CLI to adapter)
  - OR import from a shared utility. For simplicity, inline it.
  
  Add migration hint at bottom:
  ```python
  if any(_detect_layout(d) == "v1" for d in app_dirs):
      out.print("  [dim]Tip: Run `mkcv migrate` to upgrade legacy application directories.[/dim]")
  ```
Acceptance:
  - v2 apps show version counts
  - v1 apps show checkmarks and "v1 (legacy)"
  - Layout column shows "v1" or "v2"
  - Covers SC-5-1-1, SC-5-1-2, SC-5-1-3
```

```
TASK-5.2: Update status overview for mixed layout counts
Type: modify
File(s): src/mkcv/cli/commands/status.py
Depends on: TASK-5.1
Effort: S
Description:
  The `_print_workspace_overview()` function already counts all applications
  via `service.list_applications()` which now uses rglob. No change needed
  for the count itself — it already finds both layouts (SC-5-3-1).
  
  Optionally add a line showing how many v1 vs v2 apps:
  ```python
  v1_count = sum(1 for d in applications if _detect_layout(d) == "v1")
  v2_count = len(applications) - v1_count
  if v1_count > 0:
      out.print(f"  Layout:         {v2_count} v2, {v1_count} v1 (legacy)")
  ```
Acceptance:
  - Mixed layout counts displayed correctly
```

### Tests for Phase 5

```
TASK-5.3: Update test_status.py for new table columns
Type: test
File(s): tests/test_cli/test_status.py (MODIFY)
Depends on: TASK-5.1
Effort: M
Description:
  Update TestBuildApplicationTable:
  - test_table_has_six_columns → test_table_has_nine_columns (or however many)
  
  Update test helpers:
  - _make_application: add optional `layout="v1"|"v2"` parameter
    - v2: create resumes/ dir, use company/position/date path
    - v1: keep current flat path
  
  Add new tests:
  - test_v2_app_shows_version_count: create app with resumes/v1/ and resumes/v2/,
    verify "r:2" appears in output
  - test_v1_app_shows_legacy_label: create v1 app, verify "v1 (legacy)" in output
  - test_mixed_layout_shows_both: one v1 and one v2 app
  - test_migrate_hint_shown_for_v1: verify "mkcv migrate" tip appears
  - test_no_migrate_hint_for_all_v2: verify tip does NOT appear
Acceptance:
  - All status tests pass
```

```
TASK-5.4: Run full test suite to verify Phase 5
Type: test
File(s): (all)
Depends on: TASK-5.3
Effort: S
Description:
  Run `uv run pytest`, `uv run ruff check src/ tests/`, `uv run mypy src/`.
Acceptance:
  - All tests pass
```

---

## Phase 6: Migration Command

### Migration Service

```
TASK-6.1: Create MigrationService
Type: new
File(s): src/mkcv/core/services/migration.py
Depends on: TASK-3.2
Effort: L
Description:
  Create MigrationService class with:
  
  ```python
  class MigrationService:
      def __init__(self, workspace: WorkspacePort) -> None:
          self._workspace = workspace
  ```
  
  Add dataclass `MigrationPlan`:
  - source: Path (old app dir)
  - target: Path (new app dir)
  - company: str
  - position: str
  - date: date
  - preset: str
  - version: int
  - files_to_move: list[tuple[Path, Path]] (src, dst)
  - warnings: list[str]
  - skipped: bool = False
  - skip_reason: str = ""
  
  Methods:
  
  1. `_is_legacy_layout(app_dir: Path) -> bool`:
     - No resumes/ dir AND no jd.md file → legacy
  
  2. `find_legacy_applications(workspace_root: Path) -> list[Path]`:
     - Use self._workspace.list_applications()
     - Filter by _is_legacy_layout()
  
  3. `_parse_old_dirname(dirname: str) -> tuple[str, str, str, int] | None`:
     - Parse `{YYYY-MM}-{position_slug}-{preset}-v{N}` pattern
     - Return (date_str, position_slug, preset, version) or None
     - Use regex: r"^(\d{4}-\d{2})-(.+)-([a-z]+)-v(\d+)$"
     - The tricky part: position_slug can contain hyphens. The preset is
       always the segment before -v{N}. So parse from the end:
       match r"^(\d{4}-\d{2})-(.+?)-([a-z]+)-v(\d+)$" — greedy on position.
       Actually: preset is a known set (standard, comprehensive, concise, premium, budget).
       Better approach: split from right on `-v{N}`, then split remaining on last `-{preset}`.
  
  4. `plan_migration(app_dir: Path, workspace_root: Path) -> MigrationPlan`:
     - Read application.toml for company, position, date
     - Parse old dirname to extract preset and version
     - Compute target path: company_slug/position_slug/YYYY-MM-DD/
     - If date is YYYY-MM only: append "-01"
     - Check if target already exists: mark as skipped
     - Build file move list:
       - application.toml → target/application.toml
       - jd.txt → target/jd.md (rename only)
       - resume.yaml → target/resumes/v{N}/resume.yaml
       - resume.pdf → target/resumes/v{N}/resume.pdf
       - *.png → target/resumes/v{N}/
       - .mkcv/ → target/resumes/v{N}/.mkcv/
       - cover_letter.* → target/cover-letter/v{N}/
  
  5. `execute_migration(plan: MigrationPlan) -> None`:
     - Create target directory structure
     - Move/copy files per plan
     - Update application.toml with v2 fields (preset, date format)
     - Errors are collected in plan.warnings, not raised
  
  6. `migrate_all(workspace_root, *, dry_run=False, company=None) -> list[MigrationPlan]`:
     - Find legacy apps (optionally filtered by company)
     - Group by company/position/date to merge multiple versions (SC-6-2-2)
     - Plan each migration
     - If not dry_run: execute each
     - Return all plans
Acceptance:
  - Can plan a migration without touching filesystem
  - Can execute a migration that creates new layout
  - Handles multiple old versions merging into one new dir (SC-6-2-2)
  - Handles JD txt→md conversion (SC-6-2-3)
  - Handles draft-only apps with no resume (SC-6-2-4)
```

### CLI Command

```
TASK-6.2: Create migrate CLI command
Type: new
File(s): src/mkcv/cli/commands/migrate.py
Depends on: TASK-6.1
Effort: M
Description:
  Create new CLI command file with:
  
  ```python
  def migrate_command(
      *,
      dry_run: bool = False,
      company: str | None = None,
      delete_old: bool = False,
  ) -> None:
  ```
  
  Implementation:
  1. Find workspace root (error if not in workspace)
  2. Create MigrationService via factory
  3. Find legacy applications (filtered by company if provided)
  4. If none found: print "No old-layout applications found. Nothing to migrate." (SC-6-3-4)
  5. Plan all migrations
  6. If dry_run: print plan summary, exit (SC-6-1-2)
  7. Execute each migration
  8. If delete_old: prompt for confirmation, then remove old dirs (SC-6-1-3, SC-6-1-4)
  9. Print summary (SC-6-4-1): migrated/skipped/failed counts
  
  Use rich for output formatting. Follow --dry-run format from design doc 8.5.
Acceptance:
  - `mkcv migrate --dry-run` shows planned actions
  - `mkcv migrate` executes migrations
  - `mkcv migrate --company "Acme"` filters by company (SC-6-3-5)
  - Summary printed after completion
```

```
TASK-6.3: Register migrate command in app.py
Type: modify
File(s): src/mkcv/cli/app.py
Depends on: TASK-6.2
Effort: S
Description:
  Add line after the cover-letter registration (line 42):
  ```python
  app.command("mkcv.cli.commands.migrate:migrate_command", name="migrate")
  ```
Acceptance:
  - `mkcv migrate --help` shows the command help
  - `mkcv --help` lists migrate in commands
```

```
TASK-6.4: Add create_migration_service() to factory
Type: modify
File(s): src/mkcv/adapters/factory.py
Depends on: TASK-6.1
Effort: S
Description:
  Add factory function:
  ```python
  def create_migration_service() -> MigrationService:
      from mkcv.core.services.migration import MigrationService
      manager = WorkspaceManager()
      return MigrationService(workspace=manager)
  ```
Acceptance:
  - `create_migration_service()` returns a valid MigrationService instance
```

### Tests for Phase 6

```
TASK-6.5: Write tests for MigrationService
Type: test
File(s): tests/test_core/test_services/test_migration.py (NEW)
Depends on: TASK-6.1
Effort: L
Description:
  Comprehensive test suite:
  
  class TestFindLegacyApplications:
  - test_finds_v1_layout_apps
  - test_skips_v2_layout_apps
  - test_no_legacy_apps_returns_empty
  
  class TestParseOldDirname:
  - test_parse_standard_dirname (SC-6-2-1)
  - test_parse_dirname_with_multi_word_position
  - test_parse_dirname_with_unknown_preset
  - test_unparseable_dirname_returns_none
  
  class TestPlanMigration:
  - test_plan_basic_migration (SC-6-1-1)
  - test_plan_with_resume_and_cover_letter
  - test_plan_target_already_exists_skipped (SC-6-3-1)
  - test_plan_draft_only_no_resume (SC-6-2-4)
  - test_plan_preserves_old_date_as_yyyy_mm_01
  
  class TestExecuteMigration:
  - test_execute_creates_new_structure
  - test_execute_moves_resume_to_versioned_dir (SC-6-1-1)
  - test_execute_converts_jd_txt_to_md (SC-6-2-3)
  - test_execute_updates_application_toml_to_v2
  - test_execute_moves_cover_letter_files
  - test_execute_moves_mkcv_artifacts
  
  class TestMigrateAll:
  - test_dry_run_no_filesystem_changes (SC-6-1-2)
  - test_multiple_versions_merge (SC-6-2-2)
  - test_company_filter (SC-6-3-5)
  - test_summary_counts (SC-6-4-1)
Acceptance:
  - All migration tests pass
  - Tests use tmp_path filesystem, no real workspace needed
```

```
TASK-6.6: Write tests for migrate CLI command
Type: test
File(s): tests/test_cli/test_migrate.py (NEW)
Depends on: TASK-6.2
Effort: M
Description:
  class TestMigrateCommand:
  - test_no_workspace_shows_error: mock find_workspace_root → None
  - test_no_legacy_apps_shows_nothing_to_migrate (SC-6-3-4)
  - test_dry_run_shows_plan (SC-6-1-2)
  - test_migrate_executes_successfully (SC-6-1-1)
  - test_company_filter_passed_to_service (SC-6-3-5)
  - test_summary_printed (SC-6-4-1)
Acceptance:
  - All CLI tests pass
```

```
TASK-6.7: Run full test suite to verify Phase 6
Type: test
File(s): (all)
Depends on: TASK-6.6
Effort: S
Description:
  Run `uv run pytest`, `uv run ruff check src/ tests/`, `uv run mypy src/`.
Acceptance:
  - All tests pass, no lint or type errors
```

---

## Cross-Cutting Tasks

```
TASK-CC.1: Update workspace README template for new layout
Type: modify
File(s): src/mkcv/adapters/filesystem/workspace_manager.py
Depends on: TASK-3.2
Effort: S
Description:
  Update _build_readme() function's workspace structure section (around line 473):
  Change the directory tree from:
  ```
  └── {company}/
      └── {date-position}/
          ├── jd.txt
          ├── resume.yaml
          └── .mkcv/
  ```
  To:
  ```
  └── {company}/
      └── {position}/
          └── {date}/
              ├── application.toml
              ├── jd.md
              ├── resumes/v{N}/
              │   ├── resume.yaml
              │   ├── resume.pdf
              │   └── .mkcv/
              └── cover-letter/v{N}/
  ```
  
  Also update the usage examples that reference `{date-position}` to
  reflect the new `{company}/{position}/{date}` structure.
Acceptance:
  - Newly created workspace README shows new layout
  - `uv run pytest tests/test_core/test_services/test_workspace_service.py::TestWorkspaceReadme -v` passes
```

```
TASK-CC.2: Verify no new dependencies added
Type: test
File(s): pyproject.toml
Depends on: (all implementation tasks)
Effort: S
Description:
  Verify that `[project.dependencies]` in pyproject.toml has no new entries.
  `yaml` module is available via PyYAML transitive dep — verify with:
  `uv run python -c "import yaml; print(yaml.__version__)"`
  
  Covers SC-CC-1-1.
Acceptance:
  - No new deps in pyproject.toml
  - `import yaml` works without error
```

```
TASK-CC.3: Verify backward compatibility in standalone mode
Type: test
File(s): (existing test files)
Depends on: TASK-4.7
Effort: S
Description:
  Run the standalone mode tests to verify no regressions:
  - `uv run pytest tests/test_cli/test_generate.py::TestGenerateStandaloneMode -v`
  - Verify no version sub-directories created in standalone mode
  - Verify `_default_output_dir()` still works for generic resumes
  
  Covers SC-CC-2-1.
Acceptance:
  - All standalone tests pass unchanged (or with minimal mock updates)
```

```
TASK-CC.4: Final comprehensive test run
Type: test
File(s): (all)
Depends on: ALL tasks
Effort: M
Description:
  Run the complete validation suite:
  1. `uv run pytest --cov=mkcv` — all tests pass with good coverage
  2. `uv run ruff check src/ tests/` — no violations
  3. `uv run ruff format --check src/ tests/` — properly formatted
  4. `uv run mypy src/` — strict type checking passes
  5. Manual smoke test: `uv run mkcv --help` — migrate command listed
  
  Fix any remaining issues.
Acceptance:
  - 100% test pass rate
  - No lint/format/type violations
  - CLI help shows all commands including migrate
```

---

## Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| Phase 1: JD Document Model & Reader | 13 | New models, frontmatter parsing, read_jd return type change |
| Phase 2: Enriched ApplicationMetadata | 11 | v2 fields, RunMetadata, config defaults |
| Phase 3: New Directory Structure | 15 | Path construction, versioning, dual-layout, discovery |
| Phase 4: Pipeline & Cover Letter Output | 7 | Versioned output placement, run metadata |
| Phase 5: Status Command & UX | 4 | New columns, dual-layout display |
| Phase 6: Migration Command | 7 | MigrationService, CLI command, factory |
| Cross-Cutting | 4 | README template, deps check, compat, final validation |
| **Total** | **61** | |

## Implementation Order

1. **Phase 1** first — JDDocument model is a dependency for all later phases.
   TASK-1.5, 1.6, 1.7, 1.12 must be committed atomically (breaking return type change).

2. **Phase 2** next — ApplicationMetadata v2 fields needed by Phase 3's
   `_build_application_metadata()`. TASK-2.8 and 2.9 must be atomic.

3. **Phase 3** is the largest phase — complete rewrite of directory management.
   TASK-3.2 and 3.11 must be atomic (new layout + test updates).

4. **Phase 4** depends on Phase 3's `create_output_version()`.

5. **Phases 5 and 6** can be developed in parallel after Phase 3.

6. **Cross-cutting** tasks run throughout and at the end.

## Risk Areas

- **TASK-1.5 (read_jd return type change)**: Breaking change to all callers.
  Must be committed atomically with TASK-1.6, 1.7, and 1.12.

- **TASK-3.2 (create_application rewrite)**: Major change with 9 existing tests
  that need updating (TASK-3.11). Must be done atomically.

- **TASK-3.7 (list_applications sort change)**: Could affect status command and
  any code relying on lexicographic sort order.

- **TASK-6.1 (_parse_old_dirname)**: Parsing position slugs with hyphens from
  the old format `{date}-{position}-{preset}-v{N}` is ambiguous when position
  contains hyphens. Needs careful regex or known-preset-list approach.

- **Test mocks in test_generate.py**: Many tests mock `_resolve_jd` returning
  `(str, str)`. Changes to generate.py's JD handling must keep these mocks valid
  or update them carefully.
