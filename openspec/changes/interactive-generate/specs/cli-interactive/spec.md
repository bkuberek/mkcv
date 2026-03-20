# CLI Interactive Session Specification

## Purpose

Interactive resume-editing session after pipeline stages 1-3. Users review AI-generated content section-by-section via slash-command REPL, then finalize to trigger stages 4-5.

## Requirements

### Requirement: Session State Machine

The system MUST track each section's status: `pending`, `viewing`, `accepted`, `skipped`. Sections derive from `TailoredContent`: Mission, Skills, each TailoredRole, Earlier Experience (if present), Languages (if present). MUST track current section index.

#### Scenario: Initialize from TailoredContent

- GIVEN TailoredContent with mission, skills, 3 roles, earlier_experience, languages
- WHEN session initializes
- THEN 7 sections created, all `pending`, index at 0

#### Scenario: Optional fields omitted

- GIVEN TailoredContent with no earlier_experience or languages
- WHEN session initializes
- THEN only mission, skills, and role sections are created

### Requirement: Section Navigation

Sections are presented sequentially. `/goto <N>` jumps to any section. After accept/skip, auto-advance to next pending section. When all sections reviewed, transition to final review.

#### Scenario: Auto-advance after accept

- GIVEN user viewing section 1, 4 total
- WHEN `/accept` issued
- THEN section 1 = `accepted`, advances to section 2

#### Scenario: All reviewed triggers final review

- GIVEN 3 sections, none pending
- WHEN last section accepted/skipped
- THEN session transitions to final review

### Requirement: Slash Command Parser

MUST parse slash commands (case-insensitive). Unknown commands show help hint. Empty input re-displays current section.

| Command | Behavior |
|---------|----------|
| `/accept` | Accept section, auto-advance |
| `/edit` | Alias for `/regenerate` |
| `/regenerate <prompt>` | Store prompt (Phase 1 stub) |
| `/skip` | Skip section, auto-advance |
| `/cancel` | Exit without output |
| `/sections` | Show status list |
| `/display` | Re-display current section |
| `/help` | Command reference |
| `/done` | Finalize (all sections must be reviewed) |
| `/goto <N>` | Jump to section |

#### Scenario: Unknown command

- GIVEN user types `/foobar`
- WHEN parsed
- THEN error: "Unknown command. Type /help for available commands."

### Requirement: Section Display

MUST render sections via Rich. Roles show company/position/dates/bullets. Skills show grouped labels. Mission shows text.

#### Scenario: Display role

- GIVEN TailoredRole with company, position, 3 bullets
- WHEN displayed
- THEN shows company, position, date range, bullet texts

### Requirement: Skip Exclusion

Skipped sections MUST be excluded from final TailoredContent. SHOULD warn if all roles skipped.

#### Scenario: Skip a role

- GIVEN 3 roles, user skips role-2
- WHEN building final content
- THEN output has 2 roles

### Requirement: Final Review

After all sections reviewed, MUST show complete resume preview. User chooses `/done`, `/sections` (to re-edit), or `/cancel`.

#### Scenario: Done from final review

- GIVEN user in final review
- WHEN `/done` issued
- THEN session returns finalized TailoredContent

#### Scenario: Cancel from final review

- GIVEN user in final review
- WHEN `/cancel` issued
- THEN session exits, no files written

### Requirement: Regenerate Stub (Phase 1)

`/regenerate <prompt>` MUST accept input but SHALL NOT invoke LLM. MUST display stub message and re-show current section.

#### Scenario: Regenerate stub

- GIVEN user viewing mission
- WHEN `/regenerate make it technical`
- THEN message: "Regeneration available in future release"
- AND section re-displayed unchanged

### Requirement: Cancel Safety

`/cancel` MUST work from any state. `KeyboardInterrupt` treated as `/cancel`. Exit code 0.

#### Scenario: Ctrl+C handling

- GIVEN session active
- WHEN Ctrl+C pressed
- THEN clean exit with "Cancelled." message
