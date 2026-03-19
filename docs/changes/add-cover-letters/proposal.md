# Proposal: Add Cover Letter Generation (v2)

## Intent

Users applying for jobs need cover letters alongside their resumes. Currently mkcv generates tailored resumes but offers no cover letter support, forcing users to write them manually or use separate tools. This breaks the workflow — a user who just generated a perfectly tailored resume should be able to produce a matching cover letter in the same tool, using the same JD analysis and career knowledge.

The cover letter feature must work flexibly: with a job-specific resume from an application directory, with a generic resume, or with just the knowledge base and job description (no resume at all). This flexibility is critical because users don't always generate a resume first.

Additionally, the workspace has no mechanism to find "the latest version" of an application or resume — a foundational gap that must be filled before cover letters can auto-resolve inputs.

## Scope

### In Scope

1. **`mkcv cover-letter` subcommand** (MVP) — standalone first-class command with multiple input modes
2. **`--cover-letter` flag on `generate`** — convenience chain that runs cover letter after resume pipeline
3. **Version resolution infrastructure** — workspace methods for finding latest application/resume versions (benefits entire project)
4. **CoverLetterService** — separate service with 2 LLM stages (generate + review)
5. **Cover letter Pydantic models** — CoverLetter, CoverLetterResult, CoverLetterReview
6. **Prompt templates** — generate_cover_letter.j2, review_cover_letter.j2
7. **Typst-based PDF rendering** — TypstCoverLetterRenderer (direct typst.compile(), NOT RenderCV)
8. **Cover letter Typst template** — bundled .typ template for professional formatting
9. **Factory wiring** — create_cover_letter_service() in factory.py
10. **Preset/provider configuration** — cover letter stages reuse existing preset infrastructure
11. **Consolidate duplicated `_next_version()` logic** — single source of truth in workspace layer

### Out of Scope

- **Draft/published workflow** — a future lifecycle (draft → published → active) is planned but explicitly deferred. For now, latest version = active version.
- **Cover letter templates/themes** — single professional template for MVP; theme selection deferred
- **Cover letter validation** — `mkcv validate` integration for cover letters deferred
- **Interactive mode** — no stage-by-stage pause for cover letter pipeline (2 stages don't warrant it)
- **Cover letter editing/regeneration from stage** — no `--from-stage` for cover letters

## Approach

### Architecture: Separate Service, Shared Infrastructure

The cover letter feature follows the same hexagonal architecture as the resume pipeline but lives in a **separate CoverLetterService** — not additional stages bolted onto PipelineService. This keeps the resume pipeline's 5-stage contract intact and allows cover letters to work independently.

```
CLI Layer                    Core Layer                     Adapter Layer
─────────────────────────────────────────────────────────────────────────
cover_letter.py ──────────→ CoverLetterService ──────────→ LLMPort (reused)
  (new command)                (new service)                PromptLoaderPort (reused)
                                                            ArtifactStorePort (reused)
generate.py ──────────────→ PipelineService (existing)     CoverLetterRendererPort (new)
  (--cover-letter flag)        then chains to ↑               → TypstCoverLetterRenderer
```

### Input Resolution Strategy

The `mkcv cover-letter` command supports four input modes, resolved in this priority:

| Mode | Flags | Resume Source | JD Source |
|------|-------|---------------|-----------|
| **Explicit app** | `--jd X --app path/` | resume.yaml from app dir | provided JD |
| **Company resolve** | `--jd X --company deepl` | auto-find latest app for company | provided JD |
| **KB only** | `--jd X --kb career.md` | none (KB + JD only) | provided JD |
| **Auto-resolve** | `--jd X` (in workspace) | latest resume from any source | provided JD |

Resolution order for auto-resolve mode:
1. If `--app` given → use that application directory's resume.yaml
2. If `--company` given → find latest application for that company → use its resume.yaml
3. If `--resume` given → use that specific resume.yaml file
4. If none of the above → find latest resume in `resumes/` directory
5. If no resume found anywhere → proceed with KB + JD only (no resume context)

The `--jd` flag is always required (cover letters are always targeted).

### Version Resolution Infrastructure (New)

This is foundational infrastructure that benefits the entire project:

```python
# In workspace_manager.py — new public methods

def find_latest_application(
    self,
    workspace_root: Path,
    company: str,
    position: str | None = None,
    preset: str | None = None,
) -> Path | None:
    """Find the highest-versioned application dir for a company.

    Scans applications/{company_slug}/ for versioned dirs,
    parses -v{N} suffix, returns the directory with highest N.
    Optionally filters by position slug and/or preset name.
    """

def find_latest_resume(
    self,
    workspace_root: Path,
) -> Path | None:
    """Find the highest-versioned resume in resumes/ directory.

    Scans resumes/ for versioned dirs, returns path to resume.yaml
    in the directory with the highest version number.
    """

def resolve_resume_path(
    self,
    app_dir: Path,
) -> Path | None:
    """Find resume.yaml within an application directory.

    Checks for resume.yaml at the top level of app_dir.
    Returns None if not found.
    """

def find_next_version(
    self,
    parent: Path,
    base_name: str,
) -> int:
    """Consolidated version numbering — single source of truth.

    Replaces the duplicated _next_version() in workspace_manager.py
    and _find_next_version() in generate.py.
    """
```

The duplicated `_next_version()` (workspace_manager.py:327) and `_find_next_version()` (generate.py:301) will be consolidated into `WorkspaceManager.find_next_version()` as a public method, exposed through WorkspacePort. The generate.py function becomes a thin wrapper that delegates to the workspace service.

### Cover Letter Pipeline (2 Stages)

**Stage 1: Generate** — LLM produces a structured cover letter from:
- Job description (always required)
- Knowledge base / career history
- Resume content (when available — provides tailoring context)
- Existing stage1_analysis.json (when available in app dir — avoids re-analyzing JD)
- Voice guidelines (when available in workspace)

**Stage 2: Review** — LLM reviews the generated cover letter for:
- Tone and professionalism
- Alignment with JD requirements
- Specific, non-generic content
- Appropriate length (3-4 paragraphs)
- Grammar and clarity

The review stage may produce a revised version if quality issues are found.

### Rendering

Cover letters use **direct Typst compilation** (not RenderCV, which is resume-specific). A new `CoverLetterRendererPort` protocol and `TypstCoverLetterRenderer` adapter handle this:

- Bundled Typst template: `src/mkcv/templates/cover_letter.typ`
- Template receives: name, date, company, position, body paragraphs, contact info
- Output: `cover_letter.pdf` in the output directory
- Uses `typst.compile()` Python API (same dependency already used by RenderCV)

### Output Location

- **Standalone**: same directory as resume, or `--output-dir`
- **Workspace (with app)**: inside the application directory alongside resume
- **Workspace (auto-resolve)**: inside the resolved application directory
- **KB-only mode**: `output/` or `--output-dir` (no application context)

Output files:
```
{output_dir}/
├── cover_letter.yaml    # Structured cover letter data
├── cover_letter.typ     # Generated Typst source
├── cover_letter.pdf     # Rendered PDF
└── .mkcv/
    └── cover_letter_review.json  # Review stage output
```

### Configuration

Cover letter LLM stages reuse the existing preset infrastructure. New config keys:

```toml
[cover_letter]
# LLM settings for cover letter generation (defaults to pipeline.stages.tailor settings)
provider = "anthropic"
model = "claude-sonnet-4-20250514"
temperature = 0.6

[cover_letter.review]
# LLM settings for cover letter review (defaults to pipeline.stages.review settings)
provider = "anthropic"
model = "claude-sonnet-4-20250514"
temperature = 0.3
```

When not configured, cover letter stages fall back to the resume pipeline's tailor (stage 3) and review (stage 5) settings respectively. This is a sensible default — the tailor stage's creative temperature suits cover letter writing, and the review stage's analytical temperature suits quality checking.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/mkcv/cli/commands/cover_letter.py` | **New** | `mkcv cover-letter` subcommand with input mode resolution |
| `src/mkcv/cli/commands/generate.py` | Modified | Add `--cover-letter` flag, chain to CoverLetterService after pipeline |
| `src/mkcv/cli/app.py` | Modified | Register `cover-letter` command |
| `src/mkcv/core/services/cover_letter.py` | **New** | CoverLetterService with 2-stage LLM pipeline |
| `src/mkcv/core/models/cover_letter.py` | **New** | CoverLetter model (structured content) |
| `src/mkcv/core/models/cover_letter_result.py` | **New** | CoverLetterResult model (service output) |
| `src/mkcv/core/models/cover_letter_review.py` | **New** | CoverLetterReview model (review stage output) |
| `src/mkcv/core/ports/cover_letter_renderer.py` | **New** | CoverLetterRendererPort protocol |
| `src/mkcv/core/ports/workspace.py` | Modified | Add version resolution methods to WorkspacePort protocol |
| `src/mkcv/core/services/workspace.py` | Modified | Delegate new version resolution methods |
| `src/mkcv/adapters/filesystem/workspace_manager.py` | Modified | Implement find_latest_application(), find_latest_resume(), resolve_resume_path(), consolidate find_next_version() |
| `src/mkcv/adapters/renderers/typst_cover_letter.py` | **New** | TypstCoverLetterRenderer adapter |
| `src/mkcv/templates/cover_letter.typ` | **New** | Bundled Typst template for cover letter PDF |
| `src/mkcv/prompts/generate_cover_letter.j2` | **New** | Prompt template for cover letter generation |
| `src/mkcv/prompts/review_cover_letter.j2` | **New** | Prompt template for cover letter review |
| `src/mkcv/adapters/factory.py` | Modified | Add create_cover_letter_service() factory function |
| `src/mkcv/config/settings.toml` | Modified | Add cover_letter defaults |
| `tests/test_cli/test_cover_letter.py` | **New** | CLI command tests |
| `tests/test_core/test_services/test_cover_letter.py` | **New** | Service unit tests |
| `tests/test_core/test_models/test_cover_letter.py` | **New** | Model tests |
| `tests/test_adapters/test_filesystem/test_workspace_manager_versioning.py` | **New** | Version resolution tests |
| `tests/test_adapters/test_renderers/test_typst_cover_letter.py` | **New** | Renderer tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Typst template quality — cover letters need precise formatting (margins, spacing, professional look) | Medium | Start with a minimal, well-tested template. Iterate on design separately from logic. |
| LLM output quality — cover letters are more subjective than resume structuring | Medium | Review stage catches tone/content issues. Prompt engineering with examples. Voice guidelines provide user control. |
| Version resolution edge cases — empty dirs, non-standard naming, mixed presets | Medium | Thorough test coverage for edge cases. Graceful fallback (None) rather than errors. |
| `_next_version()` consolidation — changing a working function that both generate and workspace use | Low | Consolidate into WorkspaceManager with identical logic. generate.py delegates. Existing tests validate behavior doesn't change. |
| typst Python package compatibility — direct typst.compile() vs RenderCV's usage | Low | typst is already a transitive dependency via RenderCV. Test direct compilation independently. |

## Rollback Plan

1. **Feature flag removal**: The `cover-letter` command and `--cover-letter` flag are additive. Remove the command registration from `app.py` line 41 and the flag from `generate.py` to fully disable.
2. **Version resolution methods**: New workspace methods are additive — existing callers don't use them. Revert the WorkspacePort additions and WorkspaceManager implementations.
3. **`_next_version()` consolidation**: If the consolidation causes issues, revert to the duplicated private functions. The public method can coexist with the private ones during transition.
4. **No schema migrations**: All new models are standalone. No existing data formats change.
5. **No config breaking changes**: New `[cover_letter]` config section is additive; existing `[pipeline]` section is untouched.

## Dependencies

- **typst** Python package — already a transitive dependency via rendercv. Direct usage for cover letter rendering.
- No new external dependencies required.

## Success Criteria

- [ ] `mkcv cover-letter --jd job.txt --app applications/company/2026-03-position-v1/` generates a cover letter PDF using the app's resume
- [ ] `mkcv cover-letter --jd job.txt --company deepl` auto-resolves the latest application and generates a cover letter
- [ ] `mkcv cover-letter --jd job.txt --kb career.md` generates a cover letter without any resume (KB + JD only)
- [ ] `mkcv cover-letter --jd job.txt` in a workspace auto-finds the latest resume and generates a cover letter
- [ ] `mkcv generate --jd job.txt --company X --position Y --cover-letter` produces both resume and cover letter
- [ ] `find_latest_application()` correctly resolves highest -v{N} directory for a company
- [ ] `find_latest_resume()` correctly resolves highest -v{N} directory in resumes/
- [ ] Duplicated `_next_version()` logic is consolidated into a single `find_next_version()` method
- [ ] Cover letter PDF renders with professional formatting via Typst template
- [ ] Review stage produces a quality score and optional revision
- [ ] Existing stage1_analysis.json is loaded (not re-generated) when available in the app directory
- [ ] Voice guidelines (voice.md) are included in cover letter prompt when available
- [ ] All new code has test coverage; `uv run pytest` passes; `uv run mypy src/` passes
- [ ] No changes to existing resume pipeline behavior (backward compatible)

## Design Notes for Future Work

**Draft/Published Workflow (deferred)**: A future change will add lifecycle states to applications and resumes. The envisioned flow: `draft` → `published` (user marks as final) → latest published = active. This will affect version resolution — `find_latest_application()` will need to respect status filters. The current implementation should use simple "highest version number = latest" logic, which will be extended (not replaced) when the lifecycle feature lands. The `ApplicationMetadata.status` field already exists with the right enum values; the resolution functions just don't filter by it yet.

**Cover Letter Templates/Themes (deferred)**: The MVP ships with one professional Typst template. Future work could add multiple templates (formal, casual, startup-friendly) and integrate with the existing `mkcv themes` command.
