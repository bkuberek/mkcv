# Tasks: Interactive Resume Generation

## Phase 1: Foundation (Types & Parsing)

- [x] 1.1 Create `src/mkcv/cli/interactive/__init__.py` exporting `InteractiveSession`
- [x] 1.2 Create `src/mkcv/cli/interactive/sections.py` with `SectionKind` enum, `SectionState` enum, `SectionInfo` dataclass, and `build_sections(content: TailoredContent) -> list[SectionInfo]` that maps mission/skills/roles/earlier_experience/languages to section list
- [x] 1.3 Create `src/mkcv/cli/interactive/commands.py` with `CommandKind` enum (ACCEPT, SKIP, EDIT, DISPLAY, SECTIONS, GOTO, DONE, CANCEL, HELP, UNKNOWN), `ParsedCommand` dataclass, and `parse(raw: str) -> ParsedCommand` function handling case-insensitive slash commands, `/goto <N>` args, empty input as DISPLAY, unknown commands as UNKNOWN

## Phase 2: Core Implementation (Session & Display)

- [x] 2.1 Create `src/mkcv/cli/interactive/display.py` with Rich rendering functions: `render_section(console, section_info, content)` for role/mission/skills display, `render_status_grid(console, sections)` for section list with status, `render_help(console)` for command reference, `render_final_review(console, content, sections)` for complete preview
- [x] 2.2 Create `src/mkcv/cli/interactive/session.py` with `InteractiveSession.__init__(content, console)` and `run() -> TailoredContent | None`. Implement REPL loop: display current section, prompt input, parse command, dispatch. Track section states (PENDING/ACCEPTED/SKIPPED), auto-advance after accept/skip, validate `/done` requires all non-pending, build final `TailoredContent` excluding skipped sections via `model_copy`
- [x] 2.3 Handle `/cancel` and `KeyboardInterrupt` in session — return `None`, print "Cancelled." message

## Phase 3: CLI Integration

- [x] 3.1 Modify `src/mkcv/cli/commands/generate.py`: in `_run_pipeline()` (or equivalent), after stage 3 completes when `interactive=True`, instantiate `InteractiveSession(content, console)`, call `run()`, exit cleanly if `None`, otherwise replace stage-3 content and continue to stages 4-5
- [x] 3.2 Remove or bypass `_InteractiveProgressCallback` stage-gate prompts when `--interactive` is set — stages 1-3 run with spinners only, no continue/stop prompt
- [x] 3.3 Add `/regenerate <prompt>` stub in `commands.py` and `session.py` — accept input, display "Regeneration available in future release", re-show section unchanged

## Phase 4: Testing

- [x] 4.1 Create `tests/test_cli/test_interactive/test_commands.py` — parametrized tests for `parse()`: all slash commands, case insensitivity, `/goto 3` arg extraction, empty input, unknown command, bare text
- [x] 4.2 Create `tests/test_cli/test_interactive/test_sections.py` — test `build_sections()` with full TailoredContent (7 sections), minimal content (no languages/earlier_experience), and empty roles
- [x] 4.3 Create `tests/test_cli/test_interactive/test_session.py` — mock `Console` and `input`; test accept-advance, skip-advance, `/done` validation (rejects with pending sections), `/cancel` returns `None`, `/goto` navigation, final content excludes skipped roles
- [x] 4.4 Create `tests/test_cli/test_interactive/test_display.py` — capture Rich output via `Console(file=StringIO)`, verify role renders company/position/bullets, status grid shows correct states, help lists all commands
- [x] 4.5 Add integration test in `tests/test_cli/test_generate.py` — mock `create_pipeline_service` and `InteractiveSession`, verify `--interactive` calls session after stage 3 and resumes stages 4-5 with modified content

## Phase 5: Cleanup

- [x] 5.1 Run `uv run mypy --strict src/mkcv/cli/interactive/` and fix any type errors
- [x] 5.2 Run `uv run ruff check src/mkcv/cli/interactive/ tests/test_cli/test_interactive/` and fix lint issues
- [x] 5.3 Remove dead `_InteractiveProgressCallback` class from `generate.py` if fully replaced
