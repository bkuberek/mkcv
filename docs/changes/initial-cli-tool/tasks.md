# Tasks: Initial CLI Tool (v2)

**Change**: initial-cli-tool
**Date**: 2026-03-18
**Spec**: `docs/changes/initial-cli-tool/specs/spec.md` (10 requirements, 104 scenarios)
**Design**: `docs/changes/initial-cli-tool/design.md` (v2 — workspace model)
**Previous version**: v1 (19 tasks)
**This version**: v2 (22 tasks)

---

## Structural Convention

**ONE CLASS PER FILE** for all behavioral classes: exception classes, port protocols,
service classes, and adapter classes. Pydantic data models grouped by pipeline stage
are acceptable in the same file (they form inseparable data units). Packages use
`__init__.py` for re-exports.

**Design doc note**: The design uses consolidated files (`core/exceptions.py`,
`core/ports.py`, `core/services.py`) for presentation clarity. The implementation
MUST split these into per-class modules under subpackages (`core/exceptions/`,
`core/ports/`, `core/services/`) as specified in the user's approved layout.

---

## Phase 1: Project Foundation

### T-001 — pyproject.toml, .gitignore, README, and package root

**Description**: Create the project's build configuration, gitignore, a minimal
README, the `src/mkcv/__init__.py` with `__version__`, and `src/mkcv/__main__.py`.
This is the foundation that everything else depends on. After this task, `uv sync`
works and `import mkcv` succeeds. Includes `tomli-w` as a runtime dependency (new
in v2 for TOML writing).

**Dependencies**: None

**Files created**:
- `pyproject.toml` — Package metadata, dependencies (including `tomli-w>=1.0`),
  tool config (ruff, mypy, pytest) per design section B
- `.gitignore` — Python, IDE, `.mkcv/`, `.secrets.toml`, `.mypy_cache/`, `.ruff_cache/`
- `README.md` — One-paragraph project description
- `src/mkcv/__init__.py` — `__version__` via `importlib.metadata`, package docstring
- `src/mkcv/__main__.py` — Stub: `from mkcv.cli.app import main; main()`
  (will error until CLI exists, which is fine)
- `src/mkcv/py.typed` — PEP 561 marker (empty file)

**Verification**:
```bash
uv sync
uv run python -c "import mkcv; print(mkcv.__version__)"
# Should print "0.1.0"
```

**Effort**: S (5 files + 1 empty marker)

**Scenarios covered**: S-001, S-002, S-057 (partial)

---

### T-002 — Core exception hierarchy

**Description**: Create the `core/exceptions/` package with one file per exception
class. The base `MkcvError` carries `exit_code` and `message`. Each subclass sets
its own default `exit_code`. `PipelineStageError` carries `stage` and `stage_name`.
`ProviderError` and subclasses carry `provider` and `model`. New in v2:
`WorkspaceError` (exit_code=7) and subclasses `WorkspaceNotFoundError`,
`WorkspaceExistsError`, `InvalidWorkspaceError`. The `__init__.py` re-exports all
exception classes.

**Dependencies**: T-001

**Files created**:
- `src/mkcv/core/__init__.py` — Empty package marker
- `src/mkcv/core/exceptions/__init__.py` — Re-exports all exception classes
- `src/mkcv/core/exceptions/base.py` — `MkcvError(Exception)` with `exit_code: int = 1`
- `src/mkcv/core/exceptions/configuration.py` — `ConfigurationError(MkcvError)`, exit_code=3
- `src/mkcv/core/exceptions/provider.py` — `ProviderError(MkcvError)`, exit_code=4, with `provider`/`model` attrs
- `src/mkcv/core/exceptions/rate_limit.py` — `RateLimitError(ProviderError)`
- `src/mkcv/core/exceptions/authentication.py` — `AuthenticationError(ProviderError)`
- `src/mkcv/core/exceptions/context_length.py` — `ContextLengthError(ProviderError)`
- `src/mkcv/core/exceptions/provider_connection.py` — `ProviderConnectionError(ProviderError)`
- `src/mkcv/core/exceptions/pipeline.py` — `PipelineError(MkcvError)`, exit_code=5
- `src/mkcv/core/exceptions/pipeline_stage.py` — `PipelineStageError(PipelineError)` with `stage`/`stage_name`
- `src/mkcv/core/exceptions/validation.py` — `ValidationError(PipelineError)`
- `src/mkcv/core/exceptions/render.py` — `RenderError(MkcvError)`, exit_code=6
- `src/mkcv/core/exceptions/template.py` — `TemplateError(MkcvError)`, exit_code=1
- `src/mkcv/core/exceptions/workspace.py` — `WorkspaceError(MkcvError)` exit_code=7,
  `WorkspaceNotFoundError`, `WorkspaceExistsError`, `InvalidWorkspaceError` **(NEW)**

**Verification**:
```bash
uv run python -c "
from mkcv.core.exceptions import (
    MkcvError, ConfigurationError, ProviderError, RateLimitError,
    AuthenticationError, ContextLengthError, ProviderConnectionError,
    PipelineError, PipelineStageError, ValidationError, RenderError,
    TemplateError, WorkspaceError, WorkspaceNotFoundError,
    WorkspaceExistsError, InvalidWorkspaceError,
)
assert issubclass(ProviderError, MkcvError)
assert issubclass(RateLimitError, ProviderError)
assert issubclass(PipelineStageError, PipelineError)
assert issubclass(WorkspaceError, MkcvError)
assert issubclass(WorkspaceNotFoundError, WorkspaceError)
assert MkcvError('x').exit_code == 1
assert ProviderError('x').exit_code == 4
assert RenderError('x').exit_code == 6
assert WorkspaceError('x').exit_code == 7
print('All exception checks passed')
"
```

**Effort**: M (16 files, but most are 5-15 lines each)

**Scenarios covered**: S-024, S-025, S-025b

---

### T-003 — Core Pydantic models (pipeline stages + workspace)

**Description**: Create all Pydantic v2 data models in `core/models/` organized
by pipeline stage, plus the new workspace models. Each model file contains one or
more closely-related models forming a single logical unit. New in v2:
`workspace_config.py` (WorkspaceConfig, WorkspaceNaming, WorkspacePaths,
WorkspaceDefaults) and `application_metadata.py` (ApplicationMetadata). The
`__init__.py` re-exports all public model classes.

**Dependencies**: T-001

**Files created**:
- `src/mkcv/core/models/__init__.py` — Re-exports all model classes (per design J.6)
- `src/mkcv/core/models/jd_analysis.py` — `Requirement`, `JDAnalysis`
- `src/mkcv/core/models/experience.py` — `SelectedExperience`, `ExperienceSelection`
- `src/mkcv/core/models/content.py` — `TailoredBullet`, `TailoredRole`, `MissionStatement`, `SkillGroup`, `TailoredContent`
- `src/mkcv/core/models/resume.py` — `SocialNetwork`, `ExperienceEntry`, `SkillEntry`, `ResumeCV`, `ResumeDesign`, `RenderCVResume`
- `src/mkcv/core/models/review.py` — `BulletReview`, `KeywordCoverage`, `ATSCheck`, `ReviewReport`
- `src/mkcv/core/models/pipeline.py` — `StageMetadata`, `PipelineResult`
- `src/mkcv/core/models/workspace_config.py` — `WorkspaceConfig`, `WorkspaceNaming`, `WorkspacePaths`, `WorkspaceDefaults` **(NEW)**
- `src/mkcv/core/models/application_metadata.py` — `ApplicationMetadata` with `Literal` status **(NEW)**

**Verification**:
```bash
uv run python -c "
from mkcv.core.models import (
    Requirement, JDAnalysis, SelectedExperience, ExperienceSelection,
    TailoredBullet, TailoredRole, MissionStatement, SkillGroup, TailoredContent,
    SocialNetwork, ExperienceEntry, ResumeCV, ResumeDesign, RenderCVResume,
    BulletReview, KeywordCoverage, ATSCheck, ReviewReport,
    StageMetadata, PipelineResult,
    WorkspaceConfig, WorkspaceNaming, WorkspacePaths, WorkspaceDefaults,
    ApplicationMetadata,
)
print(f'Imported all model classes successfully')
"
uv run mypy src/mkcv/core/models/
```

**Effort**: M (9 files, moderate model complexity)

**Scenarios covered**: S-026, S-027, S-028, S-029, S-029b, S-029c, S-029d, S-033

---

### T-004 — Core port protocols (one per file)

**Description**: Create the `core/ports/` package with one Protocol per file.
Each port is a `@runtime_checkable Protocol` defining the hexagonal boundary.
`RenderedOutput` is a Pydantic model co-located with `RendererPort` since it is
the port's return type. The `__init__.py` re-exports all protocols. Unchanged
from v1 — no new ports for workspace (WorkspaceManager is a direct adapter).

**Dependencies**: T-001, T-003 (ports reference model types in signatures)

**Files created**:
- `src/mkcv/core/ports/__init__.py` — Re-exports all port protocols
- `src/mkcv/core/ports/llm.py` — `LLMPort(Protocol)` with `complete()` and `complete_structured()`
- `src/mkcv/core/ports/renderer.py` — `RendererPort(Protocol)` with `render()`, plus `RenderedOutput(BaseModel)`
- `src/mkcv/core/ports/prompts.py` — `PromptLoaderPort(Protocol)` with `render_prompt()` and `list_templates()`
- `src/mkcv/core/ports/artifacts.py` — `ArtifactStorePort(Protocol)` with `create_run_dir()`, `save_artifact()`, `load_artifact()`, `save_input()`

**Verification**:
```bash
uv run python -c "
from mkcv.core.ports import LLMPort, RendererPort, PromptLoaderPort, ArtifactStorePort
from typing import runtime_checkable, Protocol
assert issubclass(LLMPort, Protocol)
assert issubclass(RendererPort, Protocol)
assert issubclass(PromptLoaderPort, Protocol)
assert issubclass(ArtifactStorePort, Protocol)
print('All ports are runtime_checkable Protocols')
"
uv run mypy src/mkcv/core/ports/
```

**Effort**: S (5 files)

**Scenarios covered**: S-020, S-021, S-022, S-023

---

### T-005 — Core service stubs (one per file, including WorkspaceService)

**Description**: Create the `core/services/` package with one service class per
file. Each service depends only on port protocols (never adapters or config).
All business methods are stubs that raise `NotImplementedError`. New in v2:
`WorkspaceService` with `build_application_path()`, `build_workspace_config()`,
`build_application_metadata()`, and `validate_workspace_structure()`.

**Dependencies**: T-002, T-003, T-004

**Files created**:
- `src/mkcv/core/services/__init__.py` — Re-exports all service classes
- `src/mkcv/core/services/pipeline.py` — `PipelineService` with `run()` and `run_stage()` stubs
- `src/mkcv/core/services/render.py` — `RenderService` with `render()` stub
- `src/mkcv/core/services/validation.py` — `ValidationService` with `validate_ats()` and `check_keyword_coverage()` stubs
- `src/mkcv/core/services/workspace.py` — `WorkspaceService` with workspace business logic **(NEW)**

**Verification**:
```bash
uv run python -c "
from mkcv.core.services import PipelineService, RenderService, ValidationService
from mkcv.core.services.workspace import WorkspaceService
print('All services imported successfully')
"
uv run mypy src/mkcv/core/services/
```

**Effort**: S (5 files)

**Scenarios covered**: S-030, S-031, S-032, S-032b, S-032c

---

## Phase 2: Configuration & Infrastructure

### T-006 — Dynaconf configuration layer (including workspace config support)

**Description**: Create the `config/` package with the `Configuration(Dynaconf)`
class, bundled `settings.toml` (updated with `[workspace]` section defaults),
`.secrets.toml`, and the `settings` singleton export. New in v2: `config/workspace.py`
with `find_workspace_root()`, `load_workspace_toml()`, and
`load_workspace_into_settings()`. The Configuration class includes a `workspace_root`
property and `in_workspace` check. The `settings.toml` includes the new
`[workspace]` section with defaults for `applications_dir`, `templates_dir`,
`knowledge_base_dir`, `application_pattern`, and `company_slug`.

**Dependencies**: T-001

**Files created**:
- `src/mkcv/config/__init__.py` — Exports `settings` singleton
- `src/mkcv/config/configuration.py` — `Configuration(Dynaconf)` class with validators,
  `workspace_root` property, `in_workspace` property
- `src/mkcv/config/workspace.py` — `find_workspace_root()`, `load_workspace_toml()`,
  `load_workspace_into_settings()` **(NEW)**
- `src/mkcv/config/settings.toml` — All default settings per design D.3 (with
  `[workspace]` section)
- `src/mkcv/config/.secrets.toml` — Secret placeholders per design D.4

**Verification**:
```bash
uv run python -c "
from mkcv.config import settings
print(f'theme={settings.get(\"defaults.theme\")}')
print(f'provider={settings.get(\"pipeline.default_provider\")}')
print(f'workspace_kb_dir={settings.get(\"workspace.knowledge_base_dir\")}')
print(f'in_workspace={settings.in_workspace}')
print('Config loaded successfully')
"
uv run python -c "
from mkcv.config.workspace import find_workspace_root
from pathlib import Path
result = find_workspace_root(Path('/tmp'))
assert result is None  # No mkcv.toml in /tmp
print('Workspace discovery returns None correctly')
"
```

**Effort**: M (5 files, config + workspace discovery logic)

**Scenarios covered**: S-015, S-016, S-017, S-018, S-019, S-019b, S-019c,
S-067, S-068, S-069, S-070, S-071

---

### T-007 — Prompt templates (Jinja2 stubs)

**Description**: Create all 7 Jinja2 prompt template files in `src/mkcv/prompts/`.
Each stage template contains a placeholder comment, a minimal valid Jinja2 structure
with variable placeholders. The `_voice_anchor.j2` partial contains default voice
guidelines. Each stage template includes it via `{% include '_voice_anchor.j2' %}`.
Unchanged from v1.

**Dependencies**: T-001

**Files created**:
- `src/mkcv/prompts/_voice_anchor.j2` — Voice consistency guidelines
- `src/mkcv/prompts/analyze_jd.j2` — Stage 1 stub with `{{ jd_text }}`
- `src/mkcv/prompts/select_experience.j2` — Stage 2 stub with `{{ jd_analysis }}` and `{{ kb_text }}`
- `src/mkcv/prompts/tailor_bullets.j2` — Stage 3a stub with `{{ selected_experience }}`
- `src/mkcv/prompts/write_mission.j2` — Stage 3b stub with `{{ themes }}`
- `src/mkcv/prompts/structure_yaml.j2` — Stage 4 stub with `{{ tailored_content }}`
- `src/mkcv/prompts/review.j2` — Stage 5 stub with `{{ resume_yaml }}`

**Verification**:
```bash
uv run python -c "
from jinja2 import Environment, FileSystemLoader
import importlib.resources
path = str(importlib.resources.files('mkcv') / 'prompts')
env = Environment(loader=FileSystemLoader(path))
for t in env.loader.list_templates():
    env.parse(env.loader.get_source(env, t)[0])
    print(f'  {t} — valid Jinja2')
print('All templates are syntactically valid')
"
```

**Effort**: S (7 files, minimal content)

**Scenarios covered**: S-046, S-047, S-048

---

## Phase 3: Adapters

### T-008 — FileSystemPromptLoader adapter

**Description**: Implement `FileSystemPromptLoader` in `adapters/filesystem/prompt_loader.py`.
Uses Jinja2 `ChoiceLoader` with user-override directory (if configured) taking
priority over bundled templates loaded via `importlib.resources`. Implements
`PromptLoaderPort` protocol. Raises `TemplateError` on missing templates.
Unchanged from v1.

**Dependencies**: T-002, T-004, T-007

**Files created**:
- `src/mkcv/adapters/__init__.py` — Package marker
- `src/mkcv/adapters/filesystem/__init__.py` — Package marker
- `src/mkcv/adapters/filesystem/prompt_loader.py` — `FileSystemPromptLoader` class

**Verification**:
```bash
uv run python -c "
from mkcv.adapters.filesystem.prompt_loader import FileSystemPromptLoader
from mkcv.core.ports import PromptLoaderPort
loader = FileSystemPromptLoader()
assert isinstance(loader, PromptLoaderPort)
result = loader.render_prompt('_voice_anchor.j2', {})
assert len(result) > 0
templates = loader.list_templates()
assert '_voice_anchor.j2' in templates
print(f'PromptLoader works: {len(templates)} templates found')
"
```

**Effort**: S (3 files, 1 has real logic)

**Scenarios covered**: S-035, S-036, S-037, S-038

---

### T-009 — FileSystemArtifactStore adapter (workspace-aware)

**Description**: Implement `FileSystemArtifactStore` in `adapters/filesystem/artifact_store.py`.
Creates timestamped run directories, saves artifacts as JSON or YAML (using
`pydantic.model_dump_json()` for models), loads and deserializes back, and
saves input files to a run's `input/` subdirectory. Implements `ArtifactStorePort`.
Updated in v2: supports workspace mode where `create_run_dir()` accepts an optional
`output_dir` parameter to write intermediates inside an application dir's `.mkcv/`
subdirectory. Includes `save_final_output()` for placing resume.yaml/pdf at the
application directory root.

**Dependencies**: T-004

**Files created**:
- `src/mkcv/adapters/filesystem/artifact_store.py` — `FileSystemArtifactStore` class
  (workspace-aware per design section K)

**Verification**:
```bash
uv run python -c "
from mkcv.adapters.filesystem.artifact_store import FileSystemArtifactStore
from mkcv.core.ports import ArtifactStorePort
store = FileSystemArtifactStore()
assert isinstance(store, ArtifactStorePort)
print('ArtifactStore satisfies ArtifactStorePort')
"
```

**Effort**: S (1 file, moderate logic)

**Scenarios covered**: S-039, S-040, S-041, S-041b

---

### T-010 — LLM stub adapter and renderer stub adapter

**Description**: Create the LLM adapter package with `StubLLMAdapter` and a base
module with the provider registry. Create the renderer adapter package with a
`StubRenderer`. Both are stub implementations that raise `NotImplementedError`
(or return a fixed stub response for `StubLLMAdapter.complete()`). These exist
so the full wiring can be tested without real API keys. Unchanged from v1.

**Dependencies**: T-004

**Files created**:
- `src/mkcv/adapters/llm/__init__.py` — Package marker
- `src/mkcv/adapters/llm/base.py` — `PROVIDER_REGISTRY`, `RETRY_CONFIG`, `create_llm_adapter_for_provider()`
- `src/mkcv/adapters/llm/stub.py` — `StubLLMAdapter` class
- `src/mkcv/adapters/renderers/__init__.py` — Package marker
- `src/mkcv/adapters/renderers/stub.py` — `StubRenderer` class

**Verification**:
```bash
uv run python -c "
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.adapters.renderers.stub import StubRenderer
from mkcv.core.ports import LLMPort, RendererPort
assert isinstance(StubLLMAdapter(), LLMPort)
assert isinstance(StubRenderer(), RendererPort)
print('Stub adapters satisfy their port protocols')
"
```

**Effort**: S (5 files, mostly stubs)

**Scenarios covered**: S-042, S-043

---

### T-011 — WorkspaceManager adapter

**Description**: Implement `WorkspaceManager` in `adapters/filesystem/workspace_manager.py`.
This is the key new v2 component. It handles all workspace filesystem operations:
`create_workspace()` (creates mkcv.toml, knowledge-base/, applications/, templates/,
.gitignore), `create_application()` (creates company/date-position directory structure,
copies JD, writes application.toml), `slugify()` (Unicode-safe name sanitization),
collision resolution (`-2`, `-3` suffixes), and `list_knowledge_base_files()`.
This is NOT behind a port protocol — it's a direct adapter. Uses `tomli_w` for
TOML writing.

**Dependencies**: T-002, T-003 (uses WorkspaceError, ApplicationMetadata, WorkspaceConfig)

**Files created**:
- `src/mkcv/adapters/filesystem/workspace_manager.py` — `WorkspaceManager` class
  per design section H

**Verification**:
```bash
uv run python -c "
from mkcv.adapters.filesystem.workspace_manager import WorkspaceManager
mgr = WorkspaceManager()
assert mgr.slugify('DeepL') == 'deepl'
assert mgr.slugify('Senior Staff Engineer (API)') == 'senior-staff-engineer-api'
assert mgr.slugify('O\\'Reilly & Sons') in ('oreilly-sons', 'oreilly-and-sons')
print('WorkspaceManager imported and slugify works')
"
```

**Effort**: M (1 file, substantial logic — ~200 lines)

**Scenarios covered**: S-074, S-075, S-076, S-077, S-078, S-089, S-090

---

### T-012 — Factory functions (DI wiring, including workspace)

**Description**: Create `factories.py` with factory functions that wire
adapters to services. Reads from the `settings` singleton to configure adapters.
For this change, `create_llm_adapter()` returns `StubLLMAdapter` and
`create_render_service()` raises `NotImplementedError`. New in v2:
`create_workspace_manager()` factory. All other factories return functional
implementations.

**Dependencies**: T-005, T-006, T-008, T-009, T-010, T-011

**Files created**:
- `src/mkcv/factories.py` — Factory functions: `create_prompt_loader()`,
  `create_artifact_store()`, `create_llm_adapter()`, `create_pipeline_service()`,
  `create_render_service()`, `create_validation_service()`,
  `create_workspace_manager()` **(NEW)**

**Verification**:
```bash
uv run python -c "
from mkcv.factories import (
    create_pipeline_service, create_validation_service,
    create_workspace_manager,
)
ps = create_pipeline_service()
vs = create_validation_service()
wm = create_workspace_manager()
print(f'PipelineService: {type(ps).__name__}')
print(f'ValidationService: {type(vs).__name__}')
print(f'WorkspaceManager: {type(wm).__name__}')
print('Factory wiring works')
"
```

**Effort**: S (1 file)

**Scenarios covered**: S-044, S-045, S-045b, S-045c

---

## Phase 4: CLI Layer

### T-013 — CLI app shell and console helpers

**Description**: Create the Cyclopts root app with the meta app pattern for global
parameters (`--verbose`, `--log-format`, `--config`, `--workspace`), the `main()`
entry point, and the Rich console helpers module. The `--workspace` global option
is new in v2 — it overrides workspace auto-discovery. The meta app launcher calls
`_setup_workspace()` which uses `find_workspace_root()` and
`load_workspace_into_settings()` from `config/workspace.py`. Also create
`cli/commands/__init__.py`.

After this task, `uv run mkcv --help` and `uv run mkcv --version` work.

**Dependencies**: T-001, T-006

**Files created**:
- `src/mkcv/cli/__init__.py` — Package marker
- `src/mkcv/cli/app.py` — Root `App`, meta app with `--workspace`, `launcher()`,
  `main()`, `_configure_logging()`, `_setup_workspace()` per design section C.1
- `src/mkcv/cli/console.py` — `console`, `error_console`, `print_error()`,
  `print_success()`, `print_warning()`
- `src/mkcv/cli/commands/__init__.py` — Package marker

**Verification**:
```bash
uv run mkcv --help
uv run mkcv --version
uv run python -m mkcv --help
```

**Effort**: S (4 files)

**Scenarios covered**: S-003, S-004, S-005, S-014, S-014b

---

### T-014 — Stub CLI subcommands (render, validate, themes)

**Description**: Create the 3 stub command modules in `cli/commands/`. Each command
follows the pattern from design section C.3: async function with `Annotated`
type-hinted parameters, docstring-driven help text, and a stub body that prints
a "not yet implemented" message via the Rich console. Register commands in `app.py`.

These are the commands with NO workspace-specific logic.

**Dependencies**: T-013

**Files created**:
- `src/mkcv/cli/commands/render.py` — `render` command with all params per R-002.3
- `src/mkcv/cli/commands/validate.py` — `validate` command with all params per R-002.4
- `src/mkcv/cli/commands/themes.py` — `themes` command with all params per R-002.6

**Files modified**:
- `src/mkcv/cli/app.py` — Register `render`, `validate`, `themes` subcommands

**Verification**:
```bash
uv run mkcv render --help
uv run mkcv validate --help
uv run mkcv themes --help
```

**Effort**: S (3 new files + 1 modified)

**Scenarios covered**: S-009, S-010, S-011, S-013

---

### T-015 — `mkcv init` command (workspace initialization)

**Description**: Implement the `init` command in `cli/commands/init_cmd.py`. This
is a fully functional command (not a stub). It accepts an optional positional `path`
argument and `--name` flag, calls `WorkspaceManager.create_workspace()`, and prints
a summary of created files. Handles idempotency: skips existing files, creates
missing directories. Handles `WorkspaceError` with proper exit codes.

**Dependencies**: T-011, T-013 (needs WorkspaceManager and CLI app)

**Files created**:
- `src/mkcv/cli/commands/init_cmd.py` — `init` command per design section F.1

**Files modified**:
- `src/mkcv/cli/app.py` — Register `init` subcommand

**Verification**:
```bash
# Create a temp workspace and verify
uv run mkcv init /tmp/mkcv-test-init
ls /tmp/mkcv-test-init/mkcv.toml
ls /tmp/mkcv-test-init/knowledge-base/career.md
ls /tmp/mkcv-test-init/applications/
uv run mkcv init --help
rm -rf /tmp/mkcv-test-init
```

**Effort**: S (1 new file + 1 modified, real logic)

**Scenarios covered**: S-012, S-062, S-063, S-064, S-065, S-066

---

### T-016 — `mkcv generate` command (workspace-aware)

**Description**: Implement the `generate` command in `cli/commands/generate.py`.
This is the most complex command. It operates in two modes:

**Workspace mode**: auto-resolves KB from `knowledge-base/`, creates application
directory via WorkspaceManager, copies JD, generates `application.toml`, configures
artifact store for workspace paths. Pipeline execution is stubbed.

**Non-workspace mode**: requires explicit `--jd` and `--kb`, outputs to `.mkcv/`
in CWD. Warns if `--company`/`--position` are used without workspace.

All filesystem operations (dir creation, JD copy, application.toml) are functional.
Only the AI pipeline call is stubbed.

**Dependencies**: T-011, T-012, T-013 (needs WorkspaceManager, factories, CLI app)

**Files created**:
- `src/mkcv/cli/commands/generate.py` — `generate` command per design section F.2

**Files modified**:
- `src/mkcv/cli/app.py` — Register `generate` subcommand

**Verification**:
```bash
# Non-workspace mode (should run stub successfully)
touch /tmp/test_jd.txt /tmp/test_kb.md
uv run mkcv generate --jd /tmp/test_jd.txt --kb /tmp/test_kb.md
# Should print stub message and exit 0

# Workspace mode
uv run mkcv init /tmp/mkcv-gen-test
echo "Test JD" > /tmp/mkcv-gen-test/jd.txt
uv run mkcv --workspace /tmp/mkcv-gen-test generate --jd /tmp/mkcv-gen-test/jd.txt --company TestCo --position "Engineer"
ls /tmp/mkcv-gen-test/applications/testco/
rm -rf /tmp/mkcv-gen-test

uv run mkcv generate --help
```

**Effort**: M (1 new file + 1 modified, complex branching logic)

**Scenarios covered**: S-006, S-007, S-008, S-008b, S-080, S-081, S-082, S-083,
S-084, S-085, S-086, S-087

---

## Phase 5: Testing

### T-017 — Test infrastructure and conftest

**Description**: Create the test directory structure with all `__init__.py` markers
and the root `conftest.py` with shared fixtures. Fixtures include all v1 fixtures
plus new workspace fixtures: `workspace_manager`, `workspace_root` (creates a
temporary workspace), `workspace_with_kb` (workspace with populated career.md),
and `sample_application_metadata`.

**Dependencies**: T-001 through T-012 (needs all source code to create fixtures)

**Files created**:
- `tests/__init__.py`
- `tests/conftest.py` — All shared fixtures per design section P.2
- `tests/test_cli/__init__.py`
- `tests/test_cli/test_commands/__init__.py`
- `tests/test_config/__init__.py`
- `tests/test_core/__init__.py`
- `tests/test_core/test_models/__init__.py`
- `tests/test_core/test_ports/__init__.py`
- `tests/test_core/test_services/__init__.py`
- `tests/test_adapters/__init__.py`
- `tests/test_prompts/__init__.py`

**Verification**:
```bash
uv run pytest --collect-only tests/conftest.py
# Should show fixture definitions without errors
```

**Effort**: S (11 files, mostly empty markers + 1 conftest)

**Scenarios covered**: R-007.1, R-007.2, R-007.3

---

### T-018 — Core tests (exceptions, models, ports, services + workspace)

**Description**: Write unit tests for the core domain layer. This includes:
- **Exception tests** (`test_exceptions.py`): hierarchy, exit codes, message/attr
  carrying, WorkspaceError exit_code=7, WorkspaceNotFoundError
- **Model tests** (8 files): valid construction, invalid rejection (seniority levels,
  confidence values, score ranges, highlight min/max), JSON roundtrip. New:
  `test_workspace_config.py` (WorkspaceConfig defaults, WorkspaceNaming, WorkspacePaths),
  `test_application_metadata.py` (ApplicationMetadata status enum validation, serialization)
- **Port tests** (`test_protocols.py`): verify all protocols are runtime_checkable,
  verify stub adapters satisfy protocols via `isinstance`
- **Service tests** (4 files): constructor injection, stub methods raise NotImplementedError.
  New: `test_workspace_service.py` (build_application_path, slugification)

Also verify the hexagonal boundary: core imports nothing from adapters/cli/config.

**Dependencies**: T-017

**Files created**:
- `tests/test_core/test_exceptions.py`
- `tests/test_core/test_models/test_jd_analysis.py`
- `tests/test_core/test_models/test_experience.py`
- `tests/test_core/test_models/test_content.py`
- `tests/test_core/test_models/test_resume.py`
- `tests/test_core/test_models/test_review.py`
- `tests/test_core/test_models/test_pipeline.py`
- `tests/test_core/test_models/test_workspace_config.py` **(NEW)**
- `tests/test_core/test_models/test_application_metadata.py` **(NEW)**
- `tests/test_core/test_ports/test_protocols.py`
- `tests/test_core/test_services/test_pipeline_service.py`
- `tests/test_core/test_services/test_render_service.py`
- `tests/test_core/test_services/test_validation_service.py`
- `tests/test_core/test_services/test_workspace_service.py` **(NEW)**

**Verification**:
```bash
uv run pytest tests/test_core/ -v
```

**Effort**: L (14 files with substantive test logic)

**Scenarios covered**: S-024, S-025, S-025b, S-026, S-027, S-028, S-029,
S-029b, S-029c, S-029d, S-030, S-031, S-032, S-032b, S-032c, S-033, S-034, S-060

---

### T-019 — Config, adapter, prompt, and workspace manager tests

**Description**: Write tests for the configuration layer, adapter implementations,
factory functions, prompt infrastructure, and the new WorkspaceManager.
- **Config tests**: default loading, env var override, validator rejection, `validate_all()`.
  New: `test_workspace_discovery.py` — `find_workspace_root()` walks up correctly,
  `load_workspace_into_settings()` merges into Dynaconf, 5-layer resolution order
- **Prompt loader tests**: bundled template loading, rendering with context,
  user-override directory, missing template raises `TemplateError`
- **Artifact store tests**: `create_run_dir` structure, save/load JSON roundtrip,
  save/load YAML, `save_input`, missing artifact raises. New: workspace mode paths
- **Factory tests**: factory functions return correct types, including
  `create_workspace_manager()`
- **Template tests**: all templates exist, all are valid Jinja2, voice anchor includable
- **WorkspaceManager tests** (NEW): `create_workspace()` creates full structure,
  idempotency, `create_application()` creates company/date-position dir, `slugify()`
  edge cases (Unicode, special chars, length), collision resolution (`-2` suffix),
  `list_knowledge_base_files()`, `.gitignore` content

**Dependencies**: T-017

**Files created**:
- `tests/test_config/test_configuration.py`
- `tests/test_config/test_workspace_discovery.py` **(NEW)**
- `tests/test_adapters/test_prompt_loader.py`
- `tests/test_adapters/test_artifact_store.py`
- `tests/test_adapters/test_factory.py`
- `tests/test_adapters/test_workspace_manager.py` **(NEW)**
- `tests/test_prompts/test_templates.py`

**Verification**:
```bash
uv run pytest tests/test_config/ tests/test_adapters/ tests/test_prompts/ -v
```

**Effort**: L (7 files, substantial test logic especially workspace manager)

**Scenarios covered**: S-015, S-016, S-017, S-019b, S-019c, S-035, S-036,
S-037, S-038, S-039, S-040, S-041, S-041b, S-044, S-045, S-045b, S-045c,
S-046, S-047, S-048, S-067, S-068, S-069, S-070, S-071, S-072, S-073,
S-074, S-075, S-076, S-077, S-089, S-090, S-091

---

### T-020 — CLI tests (app + all commands, workspace + non-workspace)

**Description**: Write tests for the CLI layer. Test `--help` and
`--version` on the root app, and `--help` plus basic invocation for each of
the 5 subcommands. Updated in v2: two-mode testing for `generate` (workspace
vs non-workspace), full integration tests for `init` (creates workspace structure,
idempotent re-run), and `--workspace` global option. Uses Cyclopts' test pattern
(calling `app()` with token lists).

**Dependencies**: T-017, T-013 through T-016

**Files created**:
- `tests/test_cli/test_app.py` — Root app: `--help`, `--version`, `--workspace` accepted
- `tests/test_cli/test_commands/test_generate.py` — `TestGenerateWorkspaceMode` and
  `TestGenerateNonWorkspaceMode` per design P.4 **(UPDATED)**
- `tests/test_cli/test_commands/test_render.py` — Render command smoke tests
- `tests/test_cli/test_commands/test_validate.py` — Validate command smoke tests
- `tests/test_cli/test_commands/test_init_cmd.py` — Init command: workspace creation,
  idempotency, `--name` populates KB **(UPDATED)**
- `tests/test_cli/test_commands/test_themes.py` — Themes command smoke tests

**Verification**:
```bash
uv run pytest tests/test_cli/ -v
```

**Effort**: L (6 files, generate and init tests are substantial)

**Scenarios covered**: S-004, S-005, S-006, S-007, S-008, S-008b, S-009,
S-010, S-011, S-012, S-013, S-014, S-014b, S-062, S-063, S-064, S-065,
S-078, S-079, S-080, S-081, S-082, S-083, S-084, S-085, S-086, S-087, S-088

---

## Phase 6: Quality & Documentation

### T-021 — Code quality: ruff, mypy, full test suite pass

**Description**: Run all quality checks and fix any issues. This is not a "write
new code" task — it's a quality gate that ensures everything passes together.
Fix any ruff violations, mypy strict errors, and failing tests. Format all code
with `ruff format`. This task may require minor adjustments to type annotations,
imports, or test assertions across any previously-created file.

**Dependencies**: T-001 through T-020

**Files modified**: Any files that fail quality checks (fixes only, no new features)

**Verification**:
```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run pytest -v
uv run pytest --cov=mkcv  # Verify >=80% coverage
```

**Effort**: M (cross-cutting fixes)

**Scenarios covered**: S-049, S-050, S-051, S-052, S-053, S-058, S-059

---

### T-022 — Documentation updates (AGENTS.md, architecture, ADR)

**Description**: Update `AGENTS.md` to reflect the new tech stack (Cyclopts,
Dynaconf, hexagonal architecture, workspace model). Update `docs/specs/architecture.md`
to describe hexagonal ports/adapters and workspace components. Update
`docs/specs/cli-interface.md` to reference Cyclopts, `--workspace` global option,
and exit code 7. Create `docs/decisions/001-architecture-and-cli.md` as an ADR
documenting the 7 key decisions (Cyclopts, Dynaconf, hexagonal, manual DI,
prompt templates, test directory, workspace model).

**Dependencies**: T-021 (docs should reflect the final, quality-verified code)

**Files modified**:
- `AGENTS.md` — Rewrite tech stack section (add Cyclopts, Dynaconf, workspace)
- `docs/specs/architecture.md` — Rewrite to hexagonal architecture + workspace
- `docs/specs/cli-interface.md` — Update to Cyclopts, `--workspace`, exit code 7

**Files created**:
- `docs/decisions/001-architecture-and-cli.md` — ADR with 7 decisions

**Verification**:
```bash
grep -q "cyclopts" AGENTS.md && echo "AGENTS.md mentions cyclopts"
grep -q "dynaconf" AGENTS.md && echo "AGENTS.md mentions dynaconf"
grep -q "workspace" AGENTS.md && echo "AGENTS.md mentions workspace"
grep -q "hexagonal" docs/specs/architecture.md && echo "Architecture spec describes hexagonal"
grep -q "workspace" docs/specs/cli-interface.md && echo "CLI spec mentions workspace"
test -f docs/decisions/001-architecture-and-cli.md && echo "ADR exists"
```

**Effort**: M (3 files modified + 1 created, prose-heavy)

**Scenarios covered**: S-054, S-055, S-056

---

## Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| Phase 1: Foundation | T-001 to T-005 (5 tasks) | pyproject.toml, exceptions (+workspace), models (+workspace), ports, services (+WorkspaceService) |
| Phase 2: Config & Infra | T-006 to T-007 (2 tasks) | Dynaconf config (+workspace discovery), Jinja2 templates |
| Phase 3: Adapters | T-008 to T-012 (5 tasks) | Prompt loader, artifact store (workspace-aware), stubs, **WorkspaceManager**, factory |
| Phase 4: CLI | T-013 to T-016 (4 tasks) | Cyclopts app (+--workspace), stub commands, **init**, **generate** (workspace-aware) |
| Phase 5: Testing | T-017 to T-020 (4 tasks) | conftest, core tests (+workspace), adapter tests (+workspace), CLI tests (+workspace) |
| Phase 6: Quality & Docs | T-021 to T-022 (2 tasks) | Ruff/mypy/pytest pass, doc updates |
| **Total** | **22 tasks** | |

### Changes from v1 (19 tasks)

| Task | Change | Reason |
|------|--------|--------|
| T-002 | Updated | Added WorkspaceError, WorkspaceNotFoundError, WorkspaceExistsError, InvalidWorkspaceError |
| T-003 | Updated | Added workspace_config.py and application_metadata.py |
| T-005 | Updated | Added WorkspaceService |
| T-006 | Updated | Added config/workspace.py (find_workspace_root, load_workspace_into_settings), [workspace] section in settings.toml |
| T-009 | Updated | ArtifactStore now workspace-aware (dual-mode paths) |
| T-011 | **NEW** | WorkspaceManager adapter (create_workspace, create_application, slugify, collision handling) |
| T-012 | Updated | Added create_workspace_manager() factory |
| T-013 | Updated | Added --workspace global option, _setup_workspace() |
| T-014 | Split | Stub commands separated from workspace-aware commands |
| T-015 | **NEW** | Dedicated task for mkcv init (fully functional, not stub) |
| T-016 | **NEW** | Dedicated task for workspace-aware generate (complex dual-mode logic) |
| T-018 | Updated | Added workspace model tests, workspace service tests |
| T-019 | Updated | Added workspace discovery tests, workspace manager tests |
| T-020 | Updated | Added two-mode generate tests, init integration tests |
| T-022 | Updated | Docs now cover workspace model decision |

### Implementation Order

Tasks MUST be implemented in numerical order. Within a phase, tasks with no
inter-dependencies (e.g., T-002 and T-003) MAY be implemented in parallel.

**Critical path**: T-001 → T-002/T-003/T-004 (parallel) → T-005 → T-006/T-007
(parallel) → T-008/T-009/T-010 (parallel) → T-011 → T-012 → T-013 → T-014/T-015
(parallel) → T-016 → T-017 → T-018/T-019/T-020 (parallel) → T-021 → T-022

### File Count

- **New files**: ~85 (source + tests + config + templates + docs)
- **Modified files**: 4 (AGENTS.md, architecture.md, cli-interface.md, app.py)

### Scenario Coverage Matrix

| Scenario Range | Task(s) |
|----------------|---------|
| S-001 to S-003 | T-001, T-013 |
| S-004 to S-014b | T-013, T-014, T-015, T-016, T-020 |
| S-015 to S-019c | T-006, T-019 |
| S-020 to S-034 | T-003, T-004, T-005, T-018 |
| S-035 to S-045c | T-008, T-009, T-010, T-011, T-012, T-019 |
| S-046 to S-048 | T-007, T-019 |
| S-049 to S-053 | T-021 |
| S-054 to S-057 | T-001, T-022 |
| S-058 to S-061 | T-021, T-018 |
| S-062 to S-091 | T-011, T-015, T-016, T-019, T-020 |

### Risks

1. **Cyclopts meta app pattern** may require experimentation — the `--workspace`
   global option and `_setup_workspace()` integration is new. Mitigation: fall back
   to eager imports and explicit workspace passing if needed.
2. **Dynaconf singleton at import time** could cause issues with test isolation,
   especially when testing workspace config merging. Mitigation: use `monkeypatch`
   or Dynaconf's test mode (`TESTING=true`) in tests. May need `settings.clean()`
   between tests.
3. **mypy strict + Dynaconf** — Dynaconf doesn't ship type stubs; `ignore_missing_imports`
   override is already in the design. Additional `# type: ignore` annotations may
   be needed for Dynaconf attribute access patterns.
4. **WorkspaceManager filesystem operations** in tests — all workspace tests use
   `tmp_path` so they're isolated, but parallel test execution could theoretically
   cause issues if tests share `os.chdir()` state. Mitigation: never use `chdir()`
   in tests; always pass explicit paths.
5. **`tomli_w` TOML output format** may differ from the hand-written templates in
   the design doc. Mitigation: use template strings for `mkcv.toml` (human-readable
   comments) and `tomli_w` only for `application.toml` (machine-generated).

### Next Step

Ready for implementation (`sdd-apply`). Start with T-001.
