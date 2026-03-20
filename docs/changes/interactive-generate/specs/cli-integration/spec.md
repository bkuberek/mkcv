# CLI Integration Specification

## Purpose

Defines how `generate` command integrates with the interactive session: branching after stages 1-3, resuming stages 4-5 after user finalizes.

## MODIFIED Requirements

### Requirement: Interactive Mode Behavior

(Previously: `--interactive` paused after every stage with continue/stop prompt.)

When `--interactive` is passed, stages 1-3 MUST run non-interactively with spinners. After stage 3, CLI MUST launch interactive session with `TailoredContent`. No "Continue?" prompts during stages 1-3.

#### Scenario: Interactive flag triggers section flow

- GIVEN `mkcv generate --jd jd.txt --kb kb.md --interactive`
- WHEN stages 1-3 complete
- THEN interactive session starts with stage 3 TailoredContent
- AND stages 4-5 do NOT run yet

#### Scenario: Non-interactive unchanged

- GIVEN `mkcv generate` without `--interactive`
- WHEN pipeline executes
- THEN all 5 stages run sequentially (existing behavior)

### Requirement: Resume Pipeline After Session

When session ends via `/done`, CLI MUST build modified `TailoredContent` (skipped sections removed), run stages 4-5, render PDF, display report.

#### Scenario: Done triggers stages 4-5

- GIVEN session ends with 2 accepted roles, 1 skipped
- WHEN `/done` from final review
- THEN new TailoredContent built with 2 roles
- AND stages 4-5 run with spinners
- AND PDF rendered and report displayed

#### Scenario: Cancel produces no output

- GIVEN session active
- WHEN `/cancel` issued
- THEN pipeline exits cleanly, no files written

## ADDED Requirements

### Requirement: Module Organization

Interactive code MUST reside in `src/mkcv/cli/interactive/`:

| Module | Responsibility |
|--------|---------------|
| `session.py` | State machine, section tracking |
| `commands.py` | Slash-command parser/dispatcher |
| `display.py` | Rich section renderers |
| `prompt_input.py` | User input collection |

MUST import only `mkcv.core.models`. SHALL NOT import `mkcv.core.services`, `mkcv.core.ports`, or `mkcv.adapters`.

#### Scenario: Architecture boundary

- GIVEN interactive module imports
- WHEN inspected
- THEN only `mkcv.core.models` referenced from core layer

### Requirement: Type Safety

All interactive code MUST pass `mypy --strict`. State, commands, sections typed with Pydantic models or dataclasses.

#### Scenario: Strict type checking

- GIVEN interactive module code
- WHEN `mypy --strict` run
- THEN zero errors

## REMOVED Requirements

### Requirement: Stage-Level Continue/Stop Prompt

(Reason: Replaced by section-level interactive flow. The per-stage continue/stop dialog provided by `_InteractiveProgressCallback` is removed in favor of the new section-by-section review session.)
