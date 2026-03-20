# Proposal: Interactive Resume Generation

## Intent

Current `--interactive` is a basic continue/stop gate between pipeline stages. Users need a guided, section-by-section building experience with generate/custom-prompt/skip/edit/accept per section, final review, and slash-command UX inspired by Claude Code.

## Scope

### In Scope
- Interactive session manager in `src/mkcv/cli/interactive/` (session state, command parser, Rich display)
- Section-level flow: Mission, Skills, Experience (per-role), Education, Languages, Earlier Experience
- Slash commands: `/generate`, `/edit`, `/skip`, `/accept`, `/cancel`, `/sections`, `/display`, `/help`, `/done`
- Final review screen with Done/Edit/Cancel; Edit returns to section picker with status grid
- Pipeline stages 1-3 run up front; interactive session presents TailoredContent sections; `/done` triggers stages 4+5 and render
- Tests for command parser, session state, display (mocked I/O)

### Out of Scope
- Per-section LLM regeneration (phase 2)
- GUI/web interface, streaming tokens, multi-level undo, cover letter interactive mode

## Approach

All interactivity in CLI layer. Stages 1-3 run non-interactively producing `TailoredContent`. Interactive session presents each section for review/edit. On `/done`, stages 4-5 execute and PDF renders.

**New modules** in `src/mkcv/cli/interactive/`:
- `session.py` — state machine (sections, status, navigation)
- `commands.py` — slash-command parser/dispatcher
- `display.py` — Rich section renderers
- `prompt_input.py` — custom prompt input

**Integration**: `generate.py` branches into interactive flow after stage 3.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/mkcv/cli/interactive/` | New | Session manager, commands, display, input |
| `src/mkcv/cli/commands/generate.py` | Modified | Branch into interactive flow after stage 3 |
| `src/mkcv/core/ports/stage_callback.py` | Modified | Add `InteractiveCallbackPort` with section hooks |
| `tests/test_cli/test_interactive/` | New | Session, command, display tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Terminal input complexity | Med | Use `rich.prompt`; keep REPL loop synchronous |
| Async/sync event loop conflicts | Med | `asyncio.run()` per pipeline invocation; sync REPL |
| Scope creep into per-section regen | Med | Explicitly defer to phase 2 |

## Rollback Plan

Delete `src/mkcv/cli/interactive/`, revert `generate.py` integration point. No core changes to revert.

## Dependencies

- `rich` (existing) for terminal UI

## Success Criteria

- [ ] `mkcv generate --interactive` enters section-by-section flow
- [ ] All slash commands work: `/skip`, `/accept`, `/edit`, `/generate`, `/sections`, `/display`, `/done`, `/cancel`, `/help`
- [ ] `/done` triggers stages 4+5 and renders PDF; `/cancel` exits cleanly
- [ ] Tests cover command parsing, state transitions, display formatting
- [ ] `mypy --strict` and `ruff check` pass
