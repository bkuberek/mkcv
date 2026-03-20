# Proposal: Interactive Regeneration & Enhanced Editing

## Intent

The interactive resume review (`--interactive`) currently supports only basic accept/skip/edit-mission operations. Users cannot edit skills, experience bullets, earlier experience, or languages. Non-command free text is rejected as "Unknown command" instead of being treated as regeneration instructions. There is no tab completion for commands. This change completes the interactive experience by enabling `/edit` for all section types, free-text LLM-powered regeneration, and `prompt_toolkit`-based tab completion.

## Scope

### In Scope

1. **`/edit` for all section types** -- Extend `_handle_edit` in `session.py` to support Skills, Experience (per-role bullets), Earlier Experience, and Languages sections with structured editing UIs appropriate to each type.
2. **Free-text regeneration** -- Non-command bare text (currently `UNKNOWN`) becomes regeneration instructions for the current section. Accumulate user instructions per-section, re-invoke the LLM (stage 3) with the original prompt plus user instructions, replace the section content, and re-display. The `/regenerate` command (currently a stub) gains the same behavior with optional inline instructions.
3. **Tab completion** -- Replace `rich.prompt.Prompt.ask` with a `prompt_toolkit`-based input that provides prefix-matching tab completion for all slash commands and section numbers for `/goto`.

### Out of Scope

- Full undo/redo history for edits
- Streaming LLM tokens during regeneration
- Interactive editing for cover letters
- Regeneration of multiple sections in a single instruction
- Cross-section regeneration constraints (e.g., "make skills consistent with experience")
- GUI/web interface

## Approach

### Feature 1: `/edit` for All Section Types

Extend the `match` block in `InteractiveSession._handle_edit()` with handlers for each `SectionKind`:

| Section | Edit UX |
|---------|---------|
| **Mission** | Already implemented: inline text or prompted input. No change. |
| **Skills** | Display numbered skill groups. User picks a group by number, then edits the comma-separated skill list or the group label. Option to add/remove entire groups. |
| **Experience** | Display numbered bullets for the selected role. User picks a bullet by number and provides replacement text. Option to add/remove bullets. Edits update the `TailoredBullet.rewritten` field (keeping `original` and marking `confidence` as `"medium"`). |
| **Earlier Experience** | Prompted free-text replacement (same pattern as mission editing). |
| **Languages** | Prompted comma-separated list replacement. |

Each editor method follows the same pattern as `_edit_mission`: prompt for input, validate non-empty, apply via `model_copy(update=...)` on the content, print confirmation.

### Feature 2: Free-Text Regeneration

**Command parsing change**: In `commands.py`, bare text (no leading `/`) currently returns `UNKNOWN`. Change this to return a new `CommandKind.FREE_TEXT` with the text as `args`. The `/regenerate` command continues to work as an explicit synonym.

**Session state**: Add a `_regen_instructions: dict[int, list[str]]` field to `InteractiveSession`, keyed by section index. Instructions accumulate within a section; navigating away (`/goto`, `/accept`, `/skip`) does NOT clear them (the user may return). Instructions reset only on successful regeneration or explicit `/accept`.

**Regeneration flow**:
1. User types free text or `/regenerate <instructions>` on the current section.
2. Session appends the instruction to `_regen_instructions[current_index]`.
3. Session calls a new `RegenerationService.regenerate_section()` method (in core), passing: the current `TailoredContent`, the section identifier (kind + index), accumulated instructions, and the original pipeline context (JD analysis, KB text, ATS keywords).
4. The service builds a focused prompt: the original stage-3 prompt context for just that section, plus a "User feedback" block containing all accumulated instructions.
5. The LLM returns a replacement section (typed as the appropriate Pydantic model).
6. Session merges the result into `_content` via `model_copy` and re-renders.

**Async integration**: The interactive REPL is synchronous. Regeneration calls `asyncio.run()` to execute the async LLM call, matching the existing pattern in `_run_interactive_pipeline` for stages 4-5.

**New port dependency**: `InteractiveSession` needs access to LLM infrastructure for regeneration. The session constructor gains an optional `regeneration_service: RegenerationService | None` parameter (None disables regeneration, preserving backward compatibility and testability). The `_run_interactive_pipeline` function in `generate.py` wires this up.

### Feature 3: Tab Completion

**New dependency**: Add `prompt_toolkit>=3.0` to `pyproject.toml` dependencies.

**New module**: `src/mkcv/cli/interactive/prompt_input.py` wrapping `prompt_toolkit.PromptSession` with:
- A `CommandCompleter` that offers prefix completion for all entries in `_COMMAND_MAP` keys.
- For `/goto`, a nested completer that suggests section numbers `1..N`.
- Styled prompt matching the existing `[N/M] SectionLabel` format.
- Graceful fallback to `rich.prompt.Prompt.ask` if `prompt_toolkit` is unavailable or stdin is not a TTY (for testing).

**Integration**: `InteractiveSession.__init__` accepts an optional `prompt_fn` callable. Production code passes the `prompt_toolkit` wrapper; tests pass a mock. The REPL loop calls `self._prompt_fn(label)` instead of `Prompt.ask(label)`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/mkcv/cli/interactive/session.py` | Modified | Add edit handlers for all sections, free-text dispatch, regen instruction accumulation, optional regeneration service, pluggable prompt function |
| `src/mkcv/cli/interactive/commands.py` | Modified | Add `FREE_TEXT` command kind; bare text maps to `FREE_TEXT` instead of `UNKNOWN` |
| `src/mkcv/cli/interactive/display.py` | Modified | Add re-render after regeneration, update help table descriptions |
| `src/mkcv/cli/interactive/prompt_input.py` | New | `prompt_toolkit` wrapper with `CommandCompleter` |
| `src/mkcv/cli/interactive/sections.py` | Minor | May add helper for section-specific edit metadata |
| `src/mkcv/core/services/regeneration.py` | New | `RegenerationService` with `regenerate_section()` method |
| `src/mkcv/core/ports/regeneration.py` | New | `RegenerationPort` protocol (if needed for testability) |
| `src/mkcv/prompts/regenerate_section.j2` | New | Jinja2 template for section-specific regeneration prompt |
| `src/mkcv/cli/commands/generate.py` | Modified | Wire `RegenerationService` into `InteractiveSession` in `_run_interactive_pipeline` |
| `pyproject.toml` | Modified | Add `prompt_toolkit>=3.0` dependency |
| `tests/test_cli/test_interactive/test_session.py` | Modified | Add tests for new edit handlers, free-text regeneration, instruction accumulation |
| `tests/test_cli/test_interactive/test_commands.py` | Modified | Update tests for `FREE_TEXT` command kind, bare text behavior change |
| `tests/test_cli/test_interactive/test_prompt_input.py` | New | Tests for completer logic |
| `tests/test_core/test_regeneration_service.py` | New | Tests for `RegenerationService` with mock LLM |

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM regeneration quality varies | High | Med | Show the regenerated content immediately; user can re-instruct or `/edit` manually. Accumulate instructions so the LLM gets cumulative context. |
| `asyncio.run()` conflicts with existing event loop | Med | High | The interactive REPL is already synchronous and calls `asyncio.run()` for stages 4-5. Use the same pattern. If an event loop is already running (unlikely), fall back to `loop.run_until_complete()`. |
| `prompt_toolkit` conflicts with `rich` console output | Med | Med | `prompt_toolkit` and `rich` both write to stdout. Use `prompt_toolkit`'s `output` parameter to ensure clean handoff. Test on macOS and Linux terminals. Provide fallback to `rich.prompt` if detection fails. |
| Breaking change to bare-text behavior | Low | Low | Currently bare text is "Unknown command" (useless). Changing to `FREE_TEXT` is strictly more useful. Add a hint message: "Treating as regeneration instructions for [section]..." so the user knows what happened. |
| Regeneration cost (extra LLM calls) | Med | Low | Each regeneration is a single focused call (one section, not full pipeline). Display token cost after each regen. The user explicitly chose to regenerate. |
| `prompt_toolkit` dependency size | Low | Low | `prompt_toolkit` is a well-maintained, pure-Python package (~1MB). Already a transitive dependency of many CLI tools. |
| Edit complexity for Experience bullets | Med | Med | Keep the edit UX simple: numbered bullet selection, one at a time. Do not try to build a full TUI editor. |

## Effort Estimate

**Size: L (Large)**

- Feature 1 (`/edit` all sections): **S** -- Mechanical extension of the existing mission-edit pattern to four more section types.
- Feature 2 (free-text regeneration): **L** -- New service, new prompt template, async integration, instruction accumulation, section-specific prompt building, content merging.
- Feature 3 (tab completion): **M** -- New dependency, completer implementation, prompt function abstraction, fallback logic.
- Testing: **M** -- Significant test surface across commands, session, regeneration service, and prompt input.
- Integration: **S** -- Wiring in `generate.py` follows established patterns.

**Total: L** -- The regeneration service is the core complexity; the other features are straightforward extensions of existing patterns.

## Rollback Plan

- Delete `src/mkcv/core/services/regeneration.py`, `src/mkcv/cli/interactive/prompt_input.py`, `src/mkcv/prompts/regenerate_section.j2`
- Revert changes to `session.py`, `commands.py`, `display.py`, `generate.py`
- Remove `prompt_toolkit` from `pyproject.toml`
- No core model changes to revert; all edits operate through existing `model_copy` patterns

## Dependencies

- `rich` (existing) -- terminal UI
- `prompt_toolkit>=3.0` (new) -- tab completion and input handling
- LLM provider infrastructure (existing) -- for regeneration calls

## Success Criteria

- [ ] `/edit` works for Mission, Skills, Experience, Earlier Experience, and Languages sections
- [ ] Bare text input triggers section regeneration via LLM with user instructions
- [ ] `/regenerate [instructions]` triggers the same regeneration flow
- [ ] Regeneration instructions accumulate per-section across multiple attempts
- [ ] Tab completion suggests all slash commands and `/goto` section numbers
- [ ] Fallback to `rich.prompt` works when `prompt_toolkit` is unavailable or stdin is not a TTY
- [ ] All existing interactive tests continue to pass
- [ ] New tests cover: edit handlers for each section type, free-text command parsing, regeneration service with mock LLM, completer logic
- [ ] `mypy --strict` and `ruff check` pass
- [ ] `uv run pytest` passes with no regressions
