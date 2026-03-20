# Design: Interactive Regeneration & Enhanced Editing

## 1. Architecture Overview

This design introduces three capabilities into the interactive resume review session: `/edit` for all section types, free-text LLM-powered regeneration, and `prompt_toolkit`-based tab completion. All new components respect the hexagonal architecture: business logic lives in `core/`, CLI concerns stay in `cli/`, and new dependencies are injected through constructor parameters or Protocol ports.

### New Component Map

```
cli/interactive/
  session.py            (MODIFIED) — section-specific editors, free-text dispatch,
                                      regeneration orchestration, pluggable prompt fn
  commands.py           (MODIFIED) — FREE_TEXT command kind for bare text
  display.py            (MODIFIED) — help text updates, re-render hint after regen
  prompt_input.py       (NEW)      — prompt_toolkit wrapper with CommandCompleter
  sections.py           (MINOR)    — no structural changes needed

core/services/
  regeneration.py       (NEW)      — RegenerationService: section-focused LLM regen

core/ports/
                        (NO NEW PORT) — RegenerationService uses existing LLMPort
                                        and PromptLoaderPort directly; a dedicated
                                        port is unnecessary since nothing else will
                                        implement this interface

prompts/
  regenerate_section.j2 (NEW)      — Jinja2 template for section regeneration

adapters/factory.py     (MODIFIED) — create_regeneration_service() factory function
cli/commands/generate.py(MODIFIED) — wire RegenerationService into interactive flow
```

### Dependency Direction

```
cli/interactive/session.py
  ├── uses RegenerationService  (core/services/)
  ├── uses prompt_input.py      (cli/interactive/ — same layer)
  └── uses commands, display, sections (cli/interactive/)

RegenerationService
  ├── depends on LLMPort         (core/ports/ — Protocol)
  └── depends on PromptLoaderPort (core/ports/ — Protocol)

prompt_input.py
  └── depends on prompt_toolkit  (third-party)
  └── depends on commands.py     (for _COMMAND_MAP keys)
```

Core never imports from CLI or adapters. The `RegenerationService` takes `LLMPort` and `PromptLoaderPort` by constructor injection, following the same pattern as `PipelineService`.

### Why No New Port

The proposal mentions a possible `RegenerationPort`. After analysis, this is unnecessary:

- `RegenerationService` is the only implementation and will remain so.
- It is already testable via mock `LLMPort` and `PromptLoaderPort` injected at construction.
- Adding a Protocol for a single concrete implementation adds indirection without value.
- If a second implementation arises later, extracting a port is trivial (one-commit refactor).

---

## 2. Component Design

### 2.1 `commands.py` — FREE_TEXT Command Kind

**Change**: Add `FREE_TEXT = auto()` to `CommandKind`. Modify `parse()` so bare text (no leading `/`) returns `FREE_TEXT` instead of `UNKNOWN`.

```python
class CommandKind(Enum):
    # ... existing members ...
    FREE_TEXT = auto()    # NEW: bare text input → regeneration instruction
    UNKNOWN = auto()      # now only for unrecognized /slash commands
```

Parser change in `parse()`:

```python
if not stripped.startswith("/"):
    return ParsedCommand(kind=CommandKind.FREE_TEXT, args=stripped)
```

`UNKNOWN` is now reserved exclusively for unrecognized `/` commands (e.g., `/foo`). This is a semantic improvement: bare text has meaning (regeneration instruction), while `/foo` is genuinely unknown.

### 2.2 `RegenerationService` — Core Service

**File**: `src/mkcv/core/services/regeneration.py`

**Responsibility**: Accept a `TailoredContent`, a section identifier, accumulated user instructions, and original pipeline context, then invoke the LLM to regenerate that specific section.

```python
class RegenerationService:
    def __init__(
        self,
        llm: LLMPort,
        prompts: PromptLoaderPort,
        model: str,
        temperature: float = 0.5,
        max_tokens: int = 4096,
    ) -> None: ...

    async def regenerate_section(
        self,
        content: TailoredContent,
        section_kind: SectionKind,
        instructions: list[str],
        context: RegenerationContext,
        *,
        role_index: int | None = None,
    ) -> TailoredContent:
        """Regenerate a single section and return updated content."""
        ...
```

**`RegenerationContext`** — A Pydantic model holding the pipeline context needed for regeneration:

```python
class RegenerationContext(BaseModel):
    """Context from the original pipeline run, needed for section regeneration."""
    jd_analysis: dict[str, object]      # JDAnalysis.model_dump()
    ats_keywords: list[str]
    kb_text: str
    selection: dict[str, object] | None = None  # ExperienceSelection.model_dump()
```

**File**: `src/mkcv/core/models/regeneration_context.py` (one class per file convention).

**Design decisions**:

1. **Returns full `TailoredContent`** rather than a partial section. The service builds the replacement section (typed as the appropriate Pydantic sub-model), then merges it into the content via `model_copy(update=...)`. This keeps the merge logic in one place and gives the caller a ready-to-use content object.

2. **Section identification** uses `SectionKind` + optional `role_index`, matching the existing `SectionInfo` pattern in `sections.py`. No new enum or identifier needed.

3. **Structured output** for type-safe sections. For `MISSION`, the LLM returns `MissionStatement`. For `SKILLS`, it returns `list[SkillGroup]`. For `EXPERIENCE` (single role), it returns `TailoredRole`. For `EARLIER_EXPERIENCE` and `LANGUAGES`, the LLM returns plain text/list that maps directly. The service uses `llm.complete_structured()` for typed sections and `llm.complete()` for text sections.

4. **Model and temperature**: Uses stage-3 configuration (the "tailor" stage), since regeneration is fundamentally a section-level re-tailoring. Passed in at construction from factory.

### 2.3 `regenerate_section.j2` — Prompt Template

**File**: `src/mkcv/prompts/regenerate_section.j2`

A single template that handles all section types via Jinja2 conditionals. This avoids template proliferation while keeping the prompt focused.

**Template structure**:

```
{% include '_voice_anchor.j2' %}

## Task
Regenerate the {{ section_type }} section of a resume.

## Target Role
Company: {{ jd_analysis.company }}
Position: {{ jd_analysis.role_title }}
...

## ATS Keywords
{{ ats_keywords | join(', ') }}

## Current Content
{{ current_section_content }}

## User Feedback (apply ALL of these instructions)
{% for instruction in instructions %}
- {{ instruction }}
{% endfor %}

## Output Instructions
{% if section_type == "mission" %}
  Return a JSON MissionStatement with `text` and `rationale`.
{% elif section_type == "skills" %}
  Return a JSON array of SkillGroup objects [{"label": ..., "skills": [...]}].
{% elif section_type == "experience" %}
  Return a JSON TailoredRole object with company, position, bullets, etc.
{% elif section_type == "earlier_experience" %}
  Return a plain text string (1-2 sentences).
{% elif section_type == "languages" %}
  Return a JSON array of language strings.
{% endif %}
```

The template receives the current section content so the LLM can see what it is modifying, plus the accumulated user instructions as a list. Including all instructions (not just the latest) gives the LLM full context of what the user wants changed.

### 2.4 `prompt_input.py` — Tab Completion

**File**: `src/mkcv/cli/interactive/prompt_input.py`

**Classes**:

```python
class CommandCompleter(Completer):
    """Prefix-matching completer for interactive slash commands."""
    def __init__(self, commands: list[str], section_count: int) -> None: ...
    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]: ...

class PromptInput:
    """prompt_toolkit-based input with tab completion."""
    def __init__(self, commands: list[str], section_count: int) -> None: ...
    def ask(self, label: str) -> str: ...
```

**Completion behavior**:

- On `/` prefix: offer all command names from `_COMMAND_MAP` keys (deduplicated).
- On `/goto ` or `/g `: offer section numbers `1` through `N`.
- On bare text: no completion (user is typing free-text instructions).

**Fallback**: If `prompt_toolkit` import fails (not installed, not a TTY, CI environment), fall back to `rich.prompt.Prompt.ask`. The `PromptInput` class handles this internally:

```python
class PromptInput:
    def __init__(self, commands: list[str], section_count: int) -> None:
        try:
            from prompt_toolkit import PromptSession
            # ... set up session with completer
            self._use_prompt_toolkit = True
        except ImportError:
            self._use_prompt_toolkit = False

    def ask(self, label: str) -> str:
        if self._use_prompt_toolkit and sys.stdin.isatty():
            return self._pt_session.prompt(f"{label} > ")
        return Prompt.ask(label)
```

**Integration with session**: `InteractiveSession.__init__` accepts an optional `prompt_fn: Callable[[str], str] | None` parameter. When provided, it replaces `Prompt.ask` calls. The production wiring in `generate.py` passes `PromptInput(...).ask`. Tests pass a mock or `None` (which falls back to the existing `Prompt.ask` behavior).

### 2.5 `session.py` — Enhanced InteractiveSession

**Modified constructor**:

```python
class InteractiveSession:
    def __init__(
        self,
        content: TailoredContent,
        console: Console,
        *,
        regeneration_service: RegenerationService | None = None,
        regeneration_context: RegenerationContext | None = None,
        prompt_fn: Callable[[str], str] | None = None,
    ) -> None:
        self._content = content
        self._console = console
        self._sections = build_sections(content)
        self._current_index = 0
        self._regen_service = regeneration_service
        self._regen_context = regeneration_context
        self._regen_instructions: dict[int, list[str]] = {}
        self._prompt_fn = prompt_fn
```

All new parameters are optional with `None` defaults, preserving full backward compatibility. Existing code that constructs `InteractiveSession(content, console)` continues to work.

**New dispatch cases**:

```python
def _dispatch(self, cmd: ParsedCommand) -> TailoredContent | None:
    match cmd.kind:
        # ... existing cases ...
        case CommandKind.FREE_TEXT:
            self._handle_free_text(cmd.args)
        case CommandKind.REGENERATE:
            self._handle_regenerate(cmd.args)
        # UNKNOWN now only for unrecognized /commands
        case CommandKind.UNKNOWN:
            self._console.print("[red]Unknown command.[/red] ...")
```

**Instruction accumulation** (`_regen_instructions: dict[int, list[str]]`):

- Keyed by section index (not `SectionKind`), because there can be multiple `EXPERIENCE` sections.
- `_handle_free_text(text)` and `_handle_regenerate(args)` both append to `_regen_instructions[self._current_index]`.
- Instructions are cleared for a section only on successful regeneration or `/accept`. They persist across `/goto` navigation.
- On `/accept`, the section's instructions are cleared (the user is satisfied).

**Regeneration handler**:

```python
def _handle_free_text(self, text: str) -> None:
    if self._regen_service is None or self._regen_context is None:
        self._console.print(
            "[dim]Regeneration is not available in this session.[/dim]"
        )
        return
    self._do_regenerate(text)

def _handle_regenerate(self, args: str) -> None:
    if self._regen_service is None or self._regen_context is None:
        self._console.print(
            "[dim]Regeneration is not available in this session.[/dim]"
        )
        return
    if args:
        self._do_regenerate(args)
    else:
        self._console.print(
            "[dim]Provide instructions: /regenerate <what to change>[/dim]"
        )

def _do_regenerate(self, instruction: str) -> None:
    section = self._sections[self._current_index]
    idx = self._current_index

    # Accumulate
    self._regen_instructions.setdefault(idx, []).append(instruction)

    self._console.print(
        f"[cyan]Regenerating {section.label}...[/cyan]"
    )

    # Call async service from sync REPL
    try:
        updated = asyncio.run(
            self._regen_service.regenerate_section(
                content=self._content,
                section_kind=section.kind,
                instructions=self._regen_instructions[idx],
                context=self._regen_context,
                role_index=section.role_index,
            )
        )
    except Exception as exc:
        self._console.print(f"[red]Regeneration failed: {exc}[/red]")
        return

    self._content = updated
    self._console.print("[green]Section regenerated.[/green]")
    # Section will be re-rendered at the top of the REPL loop
```

**Section-specific edit handlers**:

```python
def _handle_edit(self, args: str) -> None:
    section = self._sections[self._current_index]
    match section.kind:
        case SectionKind.MISSION:
            self._edit_mission(args)
        case SectionKind.SKILLS:
            self._edit_skills()
        case SectionKind.EXPERIENCE:
            assert section.role_index is not None
            self._edit_experience(section.role_index)
        case SectionKind.EARLIER_EXPERIENCE:
            self._edit_earlier_experience()
        case SectionKind.LANGUAGES:
            self._edit_languages()
```

Each editor method follows the same pattern as the existing `_edit_mission`:

- **`_edit_skills()`**: Display numbered skill groups. Prompt for group number. Prompt for new comma-separated skill list or new label. Apply via `model_copy`.
- **`_edit_experience(role_index)`**: Display numbered bullets for the role. Prompt for bullet number. Prompt for replacement text. Update `TailoredBullet.rewritten` and set `confidence` to `"medium"`. Apply via `model_copy`.
- **`_edit_earlier_experience()`**: Prompt for replacement free text. Apply via `model_copy`.
- **`_edit_languages()`**: Prompt for comma-separated language list. Split, strip, filter empty. Apply via `model_copy`.

All editors use `self._prompt_fn` (or fall back to `Prompt.ask`) for input.

**Prompt function abstraction in REPL loop**:

```python
def _ask(self, label: str) -> str:
    if self._prompt_fn is not None:
        return self._prompt_fn(label)
    return Prompt.ask(label)
```

Replace all `Prompt.ask(...)` calls in the REPL with `self._ask(...)`.

---

## 3. Integration Points

### 3.1 `generate.py` — Wiring

In `_run_interactive_pipeline()`, after loading stage-3 content and before creating the `InteractiveSession`:

```python
# Build regeneration context from stage artifacts
stage1_path = artifact_dir / "stage1_analysis.json"
stage2_path = artifact_dir / "stage2_selection.json"

regen_context = None
regen_service = None

if stage1_path.is_file() and stage2_path.is_file():
    from mkcv.core.models.regeneration_context import RegenerationContext
    from mkcv.adapters.factory import create_regeneration_service

    jd_data = json.loads(stage1_path.read_text(encoding="utf-8"))
    sel_data = json.loads(stage2_path.read_text(encoding="utf-8"))
    kb_text = kb.read_text(encoding="utf-8")

    regen_context = RegenerationContext(
        jd_analysis=jd_data,
        ats_keywords=jd_data.get("ats_keywords", []),
        kb_text=kb_text,
        selection=sel_data,
    )
    regen_service = create_regeneration_service(
        settings,
        preset_name=preset_name,
        provider_override=provider_override,
    )

# Build prompt input with tab completion
from mkcv.cli.interactive.prompt_input import PromptInput
prompt_input = PromptInput(
    commands=list(_COMMAND_MAP.keys()),   # imported from commands.py
    section_count=len(build_sections(content)),
)

session = InteractiveSession(
    content,
    console,
    regeneration_service=regen_service,
    regeneration_context=regen_context,
    prompt_fn=prompt_input.ask,
)
```

### 3.2 `factory.py` — New Factory Function

```python
def create_regeneration_service(
    config: Configuration,
    preset_name: str = "default",
    *,
    provider_override: str | None = None,
) -> RegenerationService:
    """Create a RegenerationService using stage-3 (tailor) configuration."""
    from mkcv.core.services.regeneration import RegenerationService

    stage_configs = _resolve_stage_configs(config, preset_name=preset_name)
    tailor_config = stage_configs[3]  # Stage 3 = tailor

    if provider_override:
        tailor_config = StageConfig(
            provider=provider_override,
            model=tailor_config.model,
            temperature=tailor_config.temperature,
        )

    llm = _create_llm_adapter(tailor_config.provider, config)
    prompts = _create_prompt_loader(config)

    return RegenerationService(
        llm=llm,
        prompts=prompts,
        model=tailor_config.model,
        temperature=tailor_config.temperature,
    )
```

### 3.3 `display.py` — Help Text Update

Update `render_help()` to reflect new behavior:

| Command | Description |
|---------|-------------|
| `/edit` | Edit this section (mission, skills, bullets, etc.) |
| `/regenerate` | Regenerate section with LLM: `/regenerate <instructions>` |
| `<text>` | Type instructions to regenerate the current section |

### 3.4 `__init__.py` — No Change

The `InteractiveSession` constructor signature changes are backward-compatible (all new params have defaults). No import changes needed.

---

## 4. Data Flow

### 4.1 Free-Text Regeneration Sequence

```
User                    Session                 RegenerationService         LLM
  |                       |                            |                     |
  |-- "make it shorter" ->|                            |                     |
  |                       |-- parse() -> FREE_TEXT     |                     |
  |                       |-- append to _regen_instructions[idx]             |
  |                       |                            |                     |
  |                       |-- asyncio.run(             |                     |
  |                       |     regen_service          |                     |
  |                       |       .regenerate_section( |                     |
  |                       |         content,           |                     |
  |                       |         MISSION,           |                     |
  |                       |         ["make it shorter"],                     |
  |                       |         context))          |                     |
  |                       |                            |                     |
  |                       |                            |-- prompts.render(   |
  |                       |                            |   "regenerate_      |
  |                       |                            |    section.j2",     |
  |                       |                            |    {...})           |
  |                       |                            |                     |
  |                       |                            |-- llm.complete_     |
  |                       |                            |   structured(...)-->|
  |                       |                            |                     |
  |                       |                            |<-- MissionStatement |
  |                       |                            |                     |
  |                       |                            |-- content.model_copy|
  |                       |                            |   (update={...})    |
  |                       |                            |                     |
  |                       |<-- updated TailoredContent |                     |
  |                       |                            |                     |
  |                       |-- self._content = updated  |                     |
  |                       |-- re-render section        |                     |
  |<-- display updated----|                            |                     |
```

### 4.2 Accumulated Instructions (Multi-Turn)

```
Turn 1: User types "make it shorter"
  _regen_instructions[0] = ["make it shorter"]
  LLM receives: instructions = ["make it shorter"]
  → Regenerated mission displayed

Turn 2: User types "emphasize distributed systems"
  _regen_instructions[0] = ["make it shorter", "emphasize distributed systems"]
  LLM receives: instructions = ["make it shorter", "emphasize distributed systems"]
  → Regenerated mission displayed (incorporating BOTH instructions)

Turn 3: User types "/accept"
  _regen_instructions[0] is cleared
  Section marked ACCEPTED, advance to next
```

### 4.3 `/edit` Flow (Skills Example)

```
User                    Session
  |                       |
  |-- "/edit" ----------->|
  |                       |-- match SectionKind.SKILLS
  |                       |-- _edit_skills()
  |                       |   |
  |<-- "Skill groups:     |   |
  |     1. Languages:     |   |
  |        Python, Go"    |   |
  |     "Pick group #:"   |   |
  |                       |   |
  |-- "1" --------------->|   |
  |                       |   |
  |<-- "Edit skills       |   |
  |     (comma-separated):|   |
  |     [Python, Go]"     |   |
  |                       |   |
  |-- "Python, Go, Rust"->|   |
  |                       |   |-- model_copy(update skills[0].skills)
  |<-- "Skills updated."  |   |
  |                       |
  |-- (section re-renders)|
```

---

## 5. Dependency Changes

### 5.1 `prompt_toolkit`

**Add to `pyproject.toml`**:

```toml
dependencies = [
    # ... existing ...
    "prompt_toolkit>=3.0",
]
```

**Rationale**: `prompt_toolkit` is a well-maintained, pure-Python package (~1MB). It is the standard library for building interactive CLI prompts in Python and is already a transitive dependency of IPython and many CLI tools. Version 3.0+ is stable and widely adopted.

**Compatibility with `rich`**: Both libraries write to stdout. The design handles this by:
1. Using `prompt_toolkit` only for the input prompt line.
2. Using `rich` for all output rendering (panels, tables, etc.).
3. The two never write simultaneously -- `prompt_toolkit` reads input, then `rich` renders output.

### 5.2 No Other New Dependencies

`RegenerationService` uses existing `LLMPort`, `PromptLoaderPort`, and Pydantic models. No new third-party packages beyond `prompt_toolkit`.

---

## 6. Testing Strategy

### 6.1 `test_commands.py` — Parser Changes

- **`test_bare_text_returns_free_text`**: `parse("some text")` returns `FREE_TEXT` with `args="some text"`.
- **`test_unknown_slash_command_still_unknown`**: `parse("/foo")` returns `UNKNOWN`.
- **`test_free_text_preserves_original_text`**: Multi-word text is fully captured in `args`.
- **Update existing test**: `test_bare_text_without_slash` changes expected kind from `UNKNOWN` to `FREE_TEXT`.

### 6.2 `test_session.py` — Edit Handlers

For each section type, test:

- **`test_edit_skills_updates_skill_list`**: Mock `Prompt.ask` to return group number then new skills. Verify `content.skills[0].skills` is updated.
- **`test_edit_experience_updates_bullet`**: Mock to return bullet number then new text. Verify `content.roles[idx].bullets[n].rewritten` is updated and `confidence` is `"medium"`.
- **`test_edit_earlier_experience_replaces_text`**: Mock to return new text. Verify `content.earlier_experience` is updated.
- **`test_edit_languages_replaces_list`**: Mock to return comma-separated list. Verify `content.languages` is updated.
- **`test_edit_empty_input_shows_error`**: Empty input does not crash, shows error message.

### 6.3 `test_session.py` — Regeneration

- **`test_free_text_triggers_regeneration`**: Create session with mock `RegenerationService`. Type free text. Verify `regenerate_section` was called with correct arguments.
- **`test_free_text_without_regen_service_shows_message`**: Create session without regen service. Type free text. No crash; message shown.
- **`test_regenerate_command_triggers_regeneration`**: `/regenerate make it shorter` invokes the service.
- **`test_regenerate_without_args_shows_hint`**: `/regenerate` alone shows usage hint.
- **`test_instructions_accumulate_across_turns`**: Two free-text inputs on the same section result in a list of two instructions passed to the service.
- **`test_instructions_cleared_on_accept`**: After accumulating instructions, `/accept` clears them for that section.
- **`test_regeneration_error_shows_message_continues_repl`**: If `regenerate_section` raises, error is shown and REPL continues.

**Mock pattern**: Create a mock `RegenerationService` that returns a modified `TailoredContent`. The mock `LLMPort` is not needed at the session level -- it is tested at the service level.

### 6.4 `test_regeneration_service.py` — Core Service

- **`test_regenerate_mission_returns_updated_content`**: Mock `LLMPort.complete_structured` to return a `MissionStatement`. Verify the returned content has the new mission and other sections unchanged.
- **`test_regenerate_skills_returns_updated_content`**: Mock to return `list[SkillGroup]`.
- **`test_regenerate_experience_returns_updated_content`**: Mock to return `TailoredRole`.
- **`test_regenerate_earlier_experience_returns_updated_content`**: Mock `LLMPort.complete` to return a string.
- **`test_regenerate_languages_returns_updated_content`**: Mock to return a JSON list.
- **`test_prompt_includes_all_instructions`**: Verify that `prompts.render` receives all accumulated instructions.
- **`test_prompt_includes_current_section_content`**: Verify the prompt template receives the current section's content.
- **`test_llm_error_propagates`**: `PipelineStageError` from LLM propagates to caller.

### 6.5 `test_prompt_input.py` — Tab Completion

- **`test_command_completer_matches_prefix`**: Input `/a` yields `/accept`.
- **`test_command_completer_returns_all_on_slash`**: Input `/` yields all commands.
- **`test_goto_completer_suggests_numbers`**: Input `/goto ` yields `1`, `2`, ..., `N`.
- **`test_no_completion_for_bare_text`**: Input `make it` yields no completions.
- **`test_fallback_when_prompt_toolkit_unavailable`**: Patch `import` to fail; verify `PromptInput.ask` falls back to `Prompt.ask`.

### 6.6 Test Data Fixtures

Existing test fixtures in `test_session.py` (`_make_content`, `_make_role`, `_make_bullet`, `_make_mission`) are sufficient. Add:

- `_make_regen_context()`: Returns a `RegenerationContext` with minimal valid data.
- `_make_regen_service()`: Returns a `RegenerationService` with mock LLM and mock prompts.

---

## 7. Migration / Compatibility

### 7.1 No Breaking Changes

All changes are backward-compatible:

| Change | Compatibility |
|--------|---------------|
| `InteractiveSession` constructor | New params are keyword-only with `None` defaults |
| `CommandKind.FREE_TEXT` | New enum member; `UNKNOWN` still exists for unrecognized `/` commands |
| Bare text behavior | Was `UNKNOWN` (useless "Unknown command" message) → `FREE_TEXT` (useful regeneration). Strictly more useful. |
| `prompt_toolkit` dependency | New optional-feeling dependency (fallback exists), but added as required to avoid conditional logic in imports |

### 7.2 Existing Test Impact

One existing test needs updating:

- `test_bare_text_is_treated_as_unknown` in `test_session.py` currently expects bare text to show "Unknown command." This test will be renamed to `test_bare_text_triggers_regeneration` (or `test_bare_text_without_regen_shows_message` if no regen service is present).
- `test_bare_text_without_slash` in `test_commands.py` currently asserts `UNKNOWN` — update to assert `FREE_TEXT`.

### 7.3 Async Considerations

The interactive REPL is synchronous. Regeneration calls `asyncio.run()` to execute the async LLM call. This matches the established pattern in `_run_interactive_pipeline` where `asyncio.run()` is used for pipeline stages.

**Potential issue**: If an event loop is already running (e.g., Jupyter notebook), `asyncio.run()` will raise `RuntimeError`. This is the same limitation as the existing interactive pipeline. Mitigation: catch `RuntimeError` and attempt `loop.run_until_complete()` as a fallback, or document that the interactive mode requires a standard terminal.

### 7.4 Configuration

No new configuration keys. Regeneration uses the existing stage-3 (tailor) provider/model/temperature settings. This is correct because regeneration is fundamentally the same operation as stage 3, just scoped to one section.

---

## 8. File Inventory

### New Files

| File | Layer | Description |
|------|-------|-------------|
| `src/mkcv/core/services/regeneration.py` | Core | `RegenerationService` class |
| `src/mkcv/core/models/regeneration_context.py` | Core | `RegenerationContext` Pydantic model |
| `src/mkcv/cli/interactive/prompt_input.py` | CLI | `PromptInput`, `CommandCompleter` |
| `src/mkcv/prompts/regenerate_section.j2` | Prompts | Jinja2 template for regeneration |
| `tests/test_core/test_regeneration_service.py` | Tests | Service unit tests |
| `tests/test_cli/test_interactive/test_prompt_input.py` | Tests | Completer and fallback tests |

### Modified Files

| File | Changes |
|------|---------|
| `src/mkcv/cli/interactive/commands.py` | Add `FREE_TEXT` to `CommandKind`; update `parse()` |
| `src/mkcv/cli/interactive/session.py` | New constructor params, edit handlers for all sections, regeneration dispatch, `_ask()` abstraction |
| `src/mkcv/cli/interactive/display.py` | Update help text descriptions |
| `src/mkcv/cli/interactive/__init__.py` | No change (backward-compatible constructor) |
| `src/mkcv/cli/commands/generate.py` | Wire `RegenerationService`, `RegenerationContext`, `PromptInput` into interactive session |
| `src/mkcv/adapters/factory.py` | Add `create_regeneration_service()` |
| `pyproject.toml` | Add `prompt_toolkit>=3.0` to dependencies |
| `tests/test_cli/test_interactive/test_session.py` | New tests for edit handlers, regeneration, update bare-text test |
| `tests/test_cli/test_interactive/test_commands.py` | Update bare-text test to expect `FREE_TEXT` |

---

## 9. Open Questions / Decisions Deferred to Implementation

1. **Token cost display after regeneration**: The proposal mentions displaying token cost. This requires plumbing `llm.get_last_usage()` through the service return. Deferred to implementation -- can be added by returning a `RegenerationResult` dataclass with both `content` and `usage` fields if desired.

2. **Instruction accumulation on `/accept`**: The design clears instructions on `/accept`. An alternative is to keep them in case the user navigates back with `/goto`. Clearing is simpler and matches user expectation that "accept" means "I'm done with this section."

3. **Max instructions limit**: No hard limit on accumulated instructions. If a user types 20 instructions, all 20 go to the LLM. Context length errors would propagate naturally. Could add a soft limit (e.g., 10) with a warning in a future iteration.
