# Tasks: Interactive Regeneration & Enhanced Editing

## Overview

This document breaks the interactive-regeneration change into implementation tasks, ordered by dependency and grouped into phases. Each task is small enough for a focused implementation session.

**Phases:**
- **Phase 0**: Shared prerequisites (models, command parsing, session constructor, dependency)
- **Phase 1**: `/edit` for all section types
- **Phase 2**: Free-text regeneration (service, prompt, session integration)
- **Phase 3**: Tab completion via `prompt_toolkit`

---

## Phase 0: Shared Prerequisites

These tasks lay the groundwork used by all three features.

### Task 1: Add `FREE_TEXT` command kind and update parser

- **Files**:
  - Modify: `src/mkcv/cli/interactive/commands.py`
  - Modify: `tests/test_cli/test_interactive/test_commands.py`
- **Dependencies**: None
- **Description**:
  Add `FREE_TEXT = auto()` to `CommandKind` enum. Change `parse()` so that bare text (no leading `/`) returns `ParsedCommand(kind=CommandKind.FREE_TEXT, args=stripped)` instead of `UNKNOWN`. `UNKNOWN` is now reserved exclusively for unrecognized `/` commands (e.g., `/foo`). This is REQ-200 and REQ-201 from the specs.
- **Acceptance**:
  - `parse("some text")` returns `ParsedCommand(kind=CommandKind.FREE_TEXT, args="some text")`
  - `parse("/foo")` returns `ParsedCommand(kind=CommandKind.UNKNOWN, args="")`
  - `parse("")` still returns `CommandKind.DISPLAY`
  - `parse("/accept")` still returns `CommandKind.ACCEPT`
  - All existing command tests pass (with bare-text test updated)
- **Tests**:
  - `test_bare_text_returns_free_text`: bare text returns `FREE_TEXT` with full text in `args`
  - `test_unknown_slash_command_still_unknown`: `/foo` returns `UNKNOWN`
  - `test_free_text_preserves_multiword_text`: "make it shorter" fully captured
  - Update existing `test_bare_text_without_slash` to expect `FREE_TEXT` instead of `UNKNOWN`

### Task 2: Extend `InteractiveSession` constructor with new parameters

- **Files**:
  - Modify: `src/mkcv/cli/interactive/session.py`
- **Dependencies**: Task 1
- **Description**:
  Add new keyword-only parameters to `InteractiveSession.__init__`: `regeneration_service: RegenerationService | None = None`, `regeneration_context: RegenerationContext | None = None` (or `pipeline_context: PipelineContext | None = None` per specs), and `prompt_fn: Callable[[str], str] | None = None`. Add `_regen_instructions: dict[int, list[str]] = {}` instance variable. Add `_ask()` helper method that delegates to `self._prompt_fn` if set, otherwise `Prompt.ask`. Replace the `Prompt.ask(prompt_label)` call in `_repl()` with `self._ask(prompt_label)`. Also replace `Prompt.ask` calls in `_edit_mission` and `_handle_done` with `self._ask`. Add stub dispatch cases for `CommandKind.FREE_TEXT` (prints "regeneration not available" if no service) and update `CommandKind.REGENERATE` similarly. This covers REQ-205, REQ-304, and the constructor changes from the design.
- **Acceptance**:
  - `InteractiveSession(content, console)` still works (backward compatible)
  - `InteractiveSession(content, console, prompt_fn=mock_fn)` uses `mock_fn` for input
  - `_regen_instructions` dict is initialized empty
  - Free text input without regen service prints "not available" message
  - All existing session tests pass without modification
- **Tests**:
  - `test_constructor_backward_compatible`: old constructor signature still works
  - `test_prompt_fn_used_for_input`: mock prompt_fn is called instead of Prompt.ask
  - `test_free_text_without_regen_service_shows_message`: bare text with no service prints info message
  - `test_regenerate_stub_without_service_shows_message`: `/regenerate` with no service prints info

### Task 3: Add `prompt_toolkit>=3.0` dependency

- **Files**:
  - Modify: `pyproject.toml`
- **Dependencies**: None
- **Description**:
  Add `"prompt_toolkit>=3.0"` to the `[project.dependencies]` list in `pyproject.toml`. Run `uv sync` to verify resolution. This is REQ-300.
- **Acceptance**:
  - `uv sync` succeeds
  - `python -c "import prompt_toolkit; print(prompt_toolkit.__version__)"` works
- **Tests**: None (dependency management; verified by `uv sync`)

### Task 4: Create wrapper Pydantic models for structured LLM output

- **Files**:
  - Create: `src/mkcv/core/models/skills_section.py`
  - Create: `src/mkcv/core/models/languages_section.py`
  - Create: `src/mkcv/core/models/earlier_experience_section.py`
- **Dependencies**: None
- **Description**:
  Create three small Pydantic models needed by `RegenerationService` for `complete_structured` calls. `SkillsSection` wraps `skills: list[SkillGroup]`. `LanguagesSection` wraps `languages: list[str]`. `EarlierExperienceSection` wraps `earlier_experience: str`. These are specified in REQ-225. Follow the one-class-per-file convention.
- **Acceptance**:
  - Each model can be instantiated with valid data
  - `mypy --strict` passes on all three files
- **Tests**:
  - Basic instantiation tests can be inline assertions or simple unit tests; these are trivial models

### Task 5: Update help text in `display.py`

- **Files**:
  - Modify: `src/mkcv/cli/interactive/display.py`
  - Modify: `tests/test_cli/test_interactive/test_display.py` (if help text is tested)
- **Dependencies**: None
- **Description**:
  Update `render_help()` to reflect new command behavior. Change `/edit` description from "Edit this section (mission text only in MVP)" to "Edit this section (mission, skills, bullets, etc.)". Change `/regenerate` description from "Regenerate section with a prompt (future)" to "Regenerate section with LLM: /regenerate <instructions>". Add a new row for `<text>` with description "Type instructions to regenerate the current section". This covers the display.py changes from the design section 3.3.
- **Acceptance**:
  - `render_help()` output shows updated descriptions
  - All existing display tests pass (with help text assertions updated if applicable)
- **Tests**:
  - Update any existing help text assertions

---

## Phase 1: `/edit` for All Section Types

### Task 6: Implement `_edit_skills()` method

- **Files**:
  - Modify: `src/mkcv/cli/interactive/session.py`
  - Modify: `tests/test_cli/test_interactive/test_session.py`
- **Dependencies**: Task 2
- **Description**:
  Implement `_edit_skills()` on `InteractiveSession`. Display numbered skill groups. Prompt for group number (or `add`/`remove N`/`cancel`). For a selected group: prompt for new label (empty = keep), prompt for new comma-separated skills (empty = keep), apply via `model_copy`. For `add`: prompt label and skills, append new `SkillGroup`. For `remove N`: confirm, then remove group at index N-1. Edge cases: no groups -> print message and return; invalid selection -> print error; `remove` last group is allowed (no minimum-group constraint in specs). Update `_handle_edit` match to dispatch `SectionKind.SKILLS` to `_edit_skills()`. All prompts use `self._ask()`. Covers REQ-100 through REQ-105.
- **Acceptance**:
  - `/edit` on Skills section shows numbered groups and prompts for selection
  - Selecting a group and providing new label/skills updates the content
  - `add` creates a new SkillGroup
  - `remove N` removes the group after confirmation
  - `cancel` aborts without changes
  - Empty label/skills input retains existing values
  - Content is updated via `model_copy`
- **Tests**:
  - `test_edit_skills_updates_label`: mock inputs for group selection + new label
  - `test_edit_skills_updates_skill_list`: mock inputs for group selection + new skills
  - `test_edit_skills_add_group`: mock inputs for `add` + label + skills
  - `test_edit_skills_remove_group`: mock inputs for `remove 1` + confirmation
  - `test_edit_skills_cancel`: mock input for `cancel`
  - `test_edit_skills_empty_groups`: skills section with 0 groups shows message
  - `test_edit_skills_invalid_selection`: non-numeric input shows error

### Task 7: Implement `_edit_experience()` method

- **Files**:
  - Modify: `src/mkcv/cli/interactive/session.py`
  - Modify: `tests/test_cli/test_interactive/test_session.py`
- **Dependencies**: Task 2
- **Description**:
  Implement `_edit_experience(role_index: int)` on `InteractiveSession`. Display numbered bullets for the role. Prompt for bullet number (or `add`/`remove N`/`summary`/`tech`/`cancel`). For a selected bullet: prompt for new text, update `TailoredBullet.rewritten` and set `confidence` to `"medium"` (preserve `original`). For `add`: prompt for text, append new `TailoredBullet(original="[user-added]", rewritten=text, keywords_incorporated=[], confidence="medium")`. For `remove N`: reject if only 1 bullet; otherwise confirm and remove. For `summary`: prompt for new summary text (empty = keep). For `tech`: prompt for new tech_stack text (empty = keep). Apply all changes via `model_copy`. Update `_handle_edit` match to dispatch `SectionKind.EXPERIENCE`. Covers REQ-110 through REQ-115.
- **Acceptance**:
  - `/edit` on Experience shows numbered bullets
  - Selecting a bullet and providing text updates `rewritten` and sets `confidence="medium"`
  - `add` appends a new bullet
  - `remove N` removes a bullet (rejected if only 1)
  - `summary` and `tech` sub-editors work
  - Content updated via `model_copy` on role then on content.roles
- **Tests**:
  - `test_edit_experience_updates_bullet_text`: select bullet, provide new text
  - `test_edit_experience_preserves_original`: `original` field unchanged after edit
  - `test_edit_experience_sets_confidence_medium`: confidence becomes "medium"
  - `test_edit_experience_add_bullet`: add new bullet with user-added marker
  - `test_edit_experience_remove_bullet`: remove bullet with confirmation
  - `test_edit_experience_remove_last_bullet_rejected`: cannot remove if only 1
  - `test_edit_experience_summary`: edit role summary
  - `test_edit_experience_tech_stack`: edit role tech_stack
  - `test_edit_experience_cancel`: cancel aborts
  - `test_edit_experience_empty_input`: empty text shows error

### Task 8: Implement `_edit_earlier_experience()` method

- **Files**:
  - Modify: `src/mkcv/cli/interactive/session.py`
  - Modify: `tests/test_cli/test_interactive/test_session.py`
- **Dependencies**: Task 2
- **Description**:
  Implement `_edit_earlier_experience()` on `InteractiveSession`. Prompt for replacement free text. Non-empty input replaces `self._content.earlier_experience` via `model_copy`. Empty input prints warning and leaves unchanged. Update `_handle_edit` match to dispatch `SectionKind.EARLIER_EXPERIENCE`. Covers REQ-120.
- **Acceptance**:
  - `/edit` on Earlier Experience prompts for new text
  - Non-empty text replaces the content field
  - Empty text leaves unchanged with warning
- **Tests**:
  - `test_edit_earlier_experience_replaces_text`: provide new text, verify update
  - `test_edit_earlier_experience_empty_input`: empty input shows warning, no change

### Task 9: Implement `_edit_languages()` method

- **Files**:
  - Modify: `src/mkcv/cli/interactive/session.py`
  - Modify: `tests/test_cli/test_interactive/test_session.py`
- **Dependencies**: Task 2
- **Description**:
  Implement `_edit_languages()` on `InteractiveSession`. Prompt for comma-separated language list. Parse input: split by comma, strip whitespace, filter empty strings. Non-empty result replaces `self._content.languages` via `model_copy`. Empty result (or only commas/whitespace) prints warning and leaves unchanged. Update `_handle_edit` match to dispatch `SectionKind.LANGUAGES`. Covers REQ-130.
- **Acceptance**:
  - `/edit` on Languages prompts for comma-separated list
  - "English, Spanish, French" updates languages to `["English", "Spanish", "French"]`
  - Empty input or ",,," leaves unchanged with warning
- **Tests**:
  - `test_edit_languages_replaces_list`: provide comma-separated input, verify update
  - `test_edit_languages_strips_whitespace`: " English , Spanish " -> ["English", "Spanish"]
  - `test_edit_languages_empty_input`: empty input shows warning, no change
  - `test_edit_languages_only_commas`: ",, ," treated as empty, shows warning

---

## Phase 2: Free-Text Regeneration

### Task 10: Create `RegenerationService` core service

- **Files**:
  - Create: `src/mkcv/core/services/regeneration.py`
  - Create: `tests/test_core/test_regeneration_service.py`
- **Dependencies**: Task 4
- **Description**:
  Create `RegenerationService` class in core layer. Constructor takes `llm: LLMPort`, `prompts: PromptLoaderPort`, `model: str`, `temperature: float = 0.5`. Implement `async regenerate_section()` method per REQ-220 through REQ-226. The method: (1) extracts the current section content from `TailoredContent` based on `section_kind` and optional `role_index`, (2) builds the prompt via `prompts.render("regenerate_section.j2", {...})` with section content, instructions, and pipeline context, (3) calls `llm.complete_structured()` with the appropriate response model per section kind (`MissionStatement` for MISSION, `SkillsSection` for SKILLS, `TailoredRole` for EXPERIENCE, `EarlierExperienceSection` for EARLIER_EXPERIENCE, `LanguagesSection` for LANGUAGES), (4) merges the result into the content via `model_copy(update=...)`, (5) returns the updated `TailoredContent`. Import `SectionKind` from `mkcv.cli.interactive.sections` -- note: this creates a core->cli dependency. To avoid this, accept `section_kind` as a string and map internally, OR move `SectionKind` to a shared location. The cleanest approach per the hexagonal architecture: accept a string `section_type: str` parameter (one of "mission", "skills", "experience", "earlier_experience", "languages") to keep core clean.
- **Acceptance**:
  - Service can regenerate each of the 5 section types
  - Returns a new `TailoredContent` with only the targeted section replaced
  - Other sections remain unchanged
  - Prompt includes all accumulated instructions and current section content
  - LLM errors propagate as `PipelineStageError`
  - `mypy --strict` passes
- **Tests**:
  - `test_regenerate_mission_returns_updated_content`: mock LLM returns MissionStatement
  - `test_regenerate_skills_returns_updated_content`: mock LLM returns SkillsSection
  - `test_regenerate_experience_returns_updated_content`: mock LLM returns TailoredRole
  - `test_regenerate_earlier_experience_returns_updated_content`: mock LLM returns EarlierExperienceSection
  - `test_regenerate_languages_returns_updated_content`: mock LLM returns LanguagesSection
  - `test_prompt_includes_all_instructions`: verify `prompts.render` receives all instructions
  - `test_prompt_includes_current_section_content`: verify current content is in the prompt context
  - `test_other_sections_unchanged`: regenerating mission does not affect skills/roles
  - `test_llm_error_propagates`: LLM exception propagates to caller
  - `test_experience_uses_role_index`: correct role is replaced when `role_index` is specified

### Task 11: Create `regenerate_section.j2` prompt template

- **Files**:
  - Create: `src/mkcv/prompts/regenerate_section.j2`
- **Dependencies**: None
- **Description**:
  Create the Jinja2 template for section regeneration per REQ-224 and design section 2.3. The template receives: `section_type` (string), `current_content` (dict/string of the current section), `instructions` (list of strings), `jd_analysis` (dict or None), `ats_keywords` (list or None), `kb_text` (string or None). Use Jinja2 conditionals for section-type-specific output instructions. Include a "User Feedback" block listing all accumulated instructions. Include current section content so the LLM can see what it is modifying. Include ATS keywords and JD context when available.
- **Acceptance**:
  - Template renders without errors for all 5 section types
  - Template includes user instructions, current content, and context
  - Template produces section-type-specific output instructions
- **Tests**:
  - Template rendering is tested indirectly through `RegenerationService` tests (Task 10)
  - Optionally: direct template render tests using the prompt loader

### Task 12: Add `create_regeneration_service()` factory function

- **Files**:
  - Modify: `src/mkcv/adapters/factory.py`
- **Dependencies**: Task 10
- **Description**:
  Add `create_regeneration_service()` to `factory.py` following the same pattern as `create_pipeline_service()`. The function creates a `RegenerationService` using stage-3 (tailor) configuration: reads stage configs, extracts the stage-3 config for provider/model/temperature, creates the LLM adapter and prompt loader, constructs `RegenerationService`. Accepts `config`, `preset_name`, and optional `provider_override`. This follows the design section 3.2.
- **Acceptance**:
  - `create_regeneration_service(settings, preset_name="standard")` returns a working service
  - Uses stage-3 provider/model/temperature
  - `provider_override` correctly overrides the provider
  - `mypy --strict` passes
- **Tests**:
  - Factory tests are typically integration-level; ensure the function signature and return type are correct. A basic test that it constructs without error (with mocked config) is sufficient.

### Task 13: Implement regeneration dispatch in `InteractiveSession`

- **Files**:
  - Modify: `src/mkcv/cli/interactive/session.py`
  - Modify: `tests/test_cli/test_interactive/test_session.py`
- **Dependencies**: Task 2, Task 10
- **Description**:
  Implement the full regeneration flow in `InteractiveSession`. Add `_handle_free_text(text)` and `_handle_regenerate(args)` methods. Both delegate to `_do_regenerate(instruction)` which: (1) appends instruction to `_regen_instructions[current_index]`, (2) shows a Rich status spinner "Regenerating...", (3) calls `asyncio.run(self._regen_service.regenerate_section(...))` with appropriate parameters, (4) on success updates `self._content` and rebuilds sections if needed, (5) on error prints message and returns. Handle edge cases: `/regenerate` with no args and no history -> print hint (REQ-210); `/regenerate` with no args but existing history -> retry with existing instructions (REQ-211). Clear instructions on `/accept` (REQ-204). Update `_dispatch` to route `FREE_TEXT` to `_handle_free_text` and `REGENERATE` to `_handle_regenerate` (replacing the stub). Map `SectionKind` to section_type string for the service call.
- **Acceptance**:
  - Free text triggers regeneration when service is configured
  - `/regenerate <instructions>` triggers regeneration
  - `/regenerate` with no args and no history prints hint
  - `/regenerate` with no args and existing history retries
  - Instructions accumulate across multiple free-text inputs on same section
  - Instructions persist across `/goto` navigation
  - Instructions clear on `/accept`
  - LLM errors are caught and displayed; REPL continues
  - Spinner shown during LLM call
  - Content is updated on success
- **Tests**:
  - `test_free_text_triggers_regeneration`: mock service, verify called with correct args
  - `test_regenerate_command_with_args`: `/regenerate make it shorter` triggers service
  - `test_regenerate_no_args_no_history_shows_hint`: prints usage hint
  - `test_regenerate_no_args_with_history_retries`: re-runs with existing instructions
  - `test_instructions_accumulate_across_turns`: two inputs -> list of 2
  - `test_instructions_persist_across_goto`: goto + goto back, instructions still there
  - `test_instructions_cleared_on_accept`: accept clears instructions for that section
  - `test_regeneration_error_shows_message`: exception caught, error printed, REPL continues
  - `test_regeneration_updates_content`: content is replaced on success

### Task 14: Wire regeneration service into `_run_interactive_pipeline`

- **Files**:
  - Modify: `src/mkcv/cli/commands/generate.py`
- **Dependencies**: Task 12, Task 13
- **Description**:
  Update `_run_interactive_pipeline()` to construct `RegenerationService` and pipeline context, then pass them to `InteractiveSession`. After loading stage-3 content: (1) load stage-1 analysis from `stage1_analysis.json`, (2) read KB text, (3) call `create_regeneration_service()`, (4) build a context dict or dataclass with `jd_analysis`, `ats_keywords`, and `kb_text`, (5) pass `regeneration_service` and context to `InteractiveSession`. If stage-1 artifact is missing, skip regeneration service (graceful degradation). This follows the design section 3.1.
- **Acceptance**:
  - Interactive pipeline creates `RegenerationService` and passes it to session
  - Regeneration works end-to-end in the interactive flow
  - If stage-1 artifact missing, session works without regeneration (graceful)
  - All existing generate tests pass
- **Tests**:
  - Integration test or manual verification: start interactive pipeline, type free text, see regeneration attempt
  - Unit test: mock factory, verify `InteractiveSession` is constructed with regen service

---

## Phase 3: Tab Completion

### Task 15: Create `prompt_input.py` module with `CommandCompleter`

- **Files**:
  - Create: `src/mkcv/cli/interactive/prompt_input.py`
  - Create: `tests/test_cli/test_interactive/test_prompt_input.py`
- **Dependencies**: Task 3
- **Description**:
  Create the `prompt_input.py` module per REQ-301 through REQ-306 and design section 2.4. Implement `CommandCompleter` extending `prompt_toolkit.completion.Completer` with `get_completions()` that: (1) on `/` prefix -> offers all command names from `_COMMAND_MAP` keys (deduplicated by alias), (2) on `/goto ` or `/g ` -> offers section numbers 1..N with labels, (3) on bare text -> no completions. Implement `create_prompt_fn(sections: list[SectionInfo]) -> Callable[[str], str] | None` factory that: (1) tries to import `prompt_toolkit`, (2) checks `sys.stdin.isatty()`, (3) if both succeed, creates `PromptSession` with `CommandCompleter` and returns a wrapper function, (4) otherwise returns `None`. Handle `EOFError` from prompt_toolkit as cancel (EC-306).
- **Acceptance**:
  - `/ac` + Tab completes to `/accept`
  - `/` + Tab shows all commands
  - `/goto ` + Tab shows section numbers with labels
  - Bare text has no completions
  - Returns `None` when `prompt_toolkit` is unavailable
  - Returns `None` when stdin is not a TTY
  - `mypy --strict` passes
- **Tests**:
  - `test_command_completer_matches_prefix`: `/a` yields `/accept`
  - `test_command_completer_returns_all_on_slash`: `/` yields all commands
  - `test_goto_completer_suggests_numbers`: `/goto ` yields 1..N with labels
  - `test_no_completion_for_bare_text`: "make it" yields no completions
  - `test_create_prompt_fn_returns_none_without_prompt_toolkit`: mock import failure
  - `test_create_prompt_fn_returns_none_when_not_tty`: mock `isatty()` -> False
  - `test_create_prompt_fn_returns_callable_when_available`: returns a callable
  - `test_eof_treated_as_cancel`: EOFError from prompt raises appropriate exception

### Task 16: Wire tab completion into `_run_interactive_pipeline`

- **Files**:
  - Modify: `src/mkcv/cli/commands/generate.py`
- **Dependencies**: Task 14, Task 15
- **Description**:
  Update `_run_interactive_pipeline()` to create the prompt function via `create_prompt_fn(sections)` and pass it to `InteractiveSession` via `prompt_fn`. Import `create_prompt_fn` from `prompt_input` and `build_sections` from `sections`. Build sections from the loaded content, create the prompt function, and pass it. If `create_prompt_fn` returns `None`, session falls back to `Prompt.ask` (already handled by `_ask()` method from Task 2). This covers REQ-308.
- **Acceptance**:
  - Tab completion works in the interactive session when running in a terminal
  - Falls back silently in non-TTY environments (e.g., piped input, tests)
  - All existing tests pass
- **Tests**:
  - Manual verification: run `mkcv generate --interactive` in terminal, confirm Tab works
  - Unit test: verify `prompt_fn` is passed to session constructor

---

## Phase 4: Final Integration & Polish

### Task 17: Update existing test for bare-text behavior change

- **Files**:
  - Modify: `tests/test_cli/test_interactive/test_session.py`
- **Dependencies**: Task 13
- **Description**:
  Update the existing `test_bare_text_is_treated_as_unknown` test (or similar) that asserts bare text shows "Unknown command." This behavior has changed: bare text now triggers `FREE_TEXT` (regeneration or "not available" message). Rename the test and update assertions. Also update any test that asserts the `/regenerate` stub message ("will be available in a future release"), since that is now replaced with actual functionality.
- **Acceptance**:
  - No tests assert old bare-text or regenerate-stub behavior
  - All tests pass
- **Tests**:
  - This task IS a test update

### Task 18: End-to-end integration verification

- **Files**:
  - Potentially modify: `tests/test_cli/test_interactive/test_session.py`
- **Dependencies**: All previous tasks
- **Description**:
  Run the full test suite (`uv run pytest`), `mypy --strict` (`uv run mypy src/`), and `ruff check` (`uv run ruff check src/ tests/`). Fix any type errors, lint issues, or test failures. Verify end-to-end flow manually if possible: run `mkcv generate --interactive` with a real JD and KB, exercise `/edit` on each section type, type free text to trigger regeneration, test tab completion, confirm `/accept` and `/done` work. This is the final integration check.
- **Acceptance**:
  - `uv run pytest` passes with no failures
  - `uv run mypy src/` passes with no errors
  - `uv run ruff check src/ tests/` passes
  - All three features work in an interactive terminal session
- **Tests**:
  - Full suite run: `uv run pytest --cov=mkcv`

---

## Task Dependency Graph

```
Task 1  (FREE_TEXT command) ──────────────────┐
Task 2  (session constructor) ────────────────┤
Task 3  (prompt_toolkit dep) ─────────┐       │
Task 4  (wrapper models) ─────┐       │       │
Task 5  (help text) ──────────┤       │       │
                               │       │       │
Task 6  (edit skills)    ◄─── Task 2   │       │
Task 7  (edit experience) ◄── Task 2   │       │
Task 8  (edit earlier exp) ◄─ Task 2   │       │
Task 9  (edit languages) ◄── Task 2    │       │
                               │       │       │
Task 10 (regen service) ◄──── Task 4   │       │
Task 11 (regen template)      │        │       │
Task 12 (regen factory) ◄──── Task 10  │       │
Task 13 (regen dispatch) ◄─── Task 2 + Task 10 │
Task 14 (wire regen) ◄─────── Task 12 + Task 13│
                                       │       │
Task 15 (prompt_input) ◄───── Task 3   │       │
Task 16 (wire completion) ◄── Task 14 + Task 15│
                                               │
Task 17 (update tests) ◄───── Task 13          │
Task 18 (integration) ◄────── ALL
```

## Parallelism Opportunities

The following tasks can be worked on in parallel:

- **Batch 1** (no deps): Tasks 1, 3, 4, 5, 11
- **Batch 2** (after Task 2): Tasks 6, 7, 8, 9 (all independent of each other)
- **Batch 3** (after Task 4): Task 10 (can start as soon as wrapper models exist)
- **Batch 4** (after Task 3): Task 15 (can start as soon as dependency is added)
- **Batch 5** (after their deps): Tasks 12, 13, 14, 16, 17 (sequential chain)
- **Final**: Task 18 (after all others)

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| Phase 0 | 1-5 | Command parsing, session constructor, dependency, models, help text |
| Phase 1 | 6-9 | `/edit` for skills, experience, earlier experience, languages |
| Phase 2 | 10-14 | Regeneration service, template, factory, session dispatch, wiring |
| Phase 3 | 15-16 | Tab completion module, wiring |
| Phase 4 | 17-18 | Test updates, full integration verification |

**Total: 18 tasks** across 5 phases.
