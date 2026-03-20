# Specs: Interactive Regeneration & Enhanced Editing

## Overview

This specification covers three features for the interactive resume review session:

1. **Feature 1**: `/edit` command extended to all section types (Skills, Experience, Earlier Experience, Languages)
2. **Feature 2**: Free-text regeneration (bare text and `/regenerate` trigger LLM-powered section re-generation)
3. **Feature 3**: Tab completion via `prompt_toolkit`

Each feature is specified with numbered requirements, acceptance criteria in Given/When/Then format, edge cases, API contracts, and data model changes.

---

## Feature 1: `/edit` for All Section Types

### Background

Currently, `InteractiveSession._handle_edit()` in `session.py` only supports `SectionKind.MISSION`. All other section kinds display a "not supported" message. The `_edit_mission()` method follows a pattern of: prompt for input, validate non-empty, apply via `model_copy(update=...)`, print confirmation. This pattern will be extended to the remaining four section types.

### Requirements

#### REQ-100: Edit Skills -- Group Selection

The `/edit` command on a Skills section MUST display all skill groups as a numbered list and prompt the user to select a group by number. The user may also type `add` to add a new group or `remove N` to remove group N.

#### REQ-101: Edit Skills -- Label Editing

When editing a selected skill group, the system MUST prompt the user for a new label. Pressing Enter with empty input MUST retain the existing label.

#### REQ-102: Edit Skills -- Skills List Editing

When editing a selected skill group, the system MUST prompt the user for a new comma-separated list of skills. Pressing Enter with empty input MUST retain the existing skills list.

#### REQ-103: Edit Skills -- Add Group

When the user types `add` in the group selection prompt, the system MUST prompt for a label and a comma-separated skills list, then append a new `SkillGroup` to the content's `skills` list.

#### REQ-104: Edit Skills -- Remove Group

When the user types `remove N` in the group selection prompt, the system MUST remove the skill group at 1-based index N from the content's `skills` list, after confirming the action.

#### REQ-105: Edit Skills -- Content Update

After any skill edit, the system MUST update `self._content` via `model_copy(update={"skills": ...})` with the modified skills list and print a confirmation message.

#### REQ-110: Edit Experience -- Bullet Selection

The `/edit` command on an Experience section MUST display the role's bullets as a numbered list and prompt the user to select a bullet by number. The user may also type `add` to add a new bullet or `remove N` to remove bullet N.

#### REQ-111: Edit Experience -- Bullet Text Replacement

When editing a selected bullet, the system MUST prompt for new bullet text. The edit MUST update the `TailoredBullet.rewritten` field with the new text, preserve the `original` field unchanged, and set `confidence` to `"medium"`.

#### REQ-112: Edit Experience -- Add Bullet

When the user types `add` in the bullet selection prompt, the system MUST prompt for bullet text and append a new `TailoredBullet` with `original` set to `"[user-added]"`, `rewritten` set to the provided text, `keywords_incorporated` set to `[]`, and `confidence` set to `"medium"`.

#### REQ-113: Edit Experience -- Remove Bullet

When the user types `remove N` in the bullet selection prompt, the system MUST remove the bullet at 1-based index N from the role's bullets list, after confirming the action. The system MUST reject removal if only one bullet remains.

#### REQ-114: Edit Experience -- Content Update

After any experience bullet edit, the system MUST update `self._content` via `model_copy` on the role and then on the content's `roles` list, and print a confirmation message.

#### REQ-115: Edit Experience -- Summary and Tech Stack

The `/edit` command on an Experience section MUST also offer the option to edit the role `summary` and `tech_stack` fields. The user types `summary` or `tech` at the edit prompt to enter those sub-editors. Each prompts for new text; empty input retains the existing value.

#### REQ-120: Edit Earlier Experience

The `/edit` command on an Earlier Experience section MUST prompt for replacement text (free-form string). Non-empty input replaces `self._content.earlier_experience`. Empty input leaves it unchanged and prints a warning.

#### REQ-130: Edit Languages

The `/edit` command on a Languages section MUST prompt for a comma-separated list of languages. Non-empty input replaces `self._content.languages` with the parsed list (stripped, non-empty items). Empty input leaves the languages unchanged and prints a warning.

#### REQ-140: Edit Command Preserves Section State

The `/edit` command MUST NOT change the section's `SectionState`. The section remains `PENDING` (or whatever state it was in) after editing. The user must explicitly `/accept` or `/skip`.

#### REQ-141: Edit Command Does Not Advance

After a successful or failed `/edit`, the REPL MUST remain on the current section (no auto-advance). The section is re-rendered at the top of the next loop iteration.

### Acceptance Criteria

#### AC-100: Edit Skills Group Label

```
Given the current section is Skills with groups [("Languages", ["Python", "Go"]), ("Cloud", ["AWS"])]
When the user types "/edit"
Then the system displays:
  1. Languages: Python, Go
  2. Cloud: AWS
  [add | remove N | cancel]
When the user types "1"
Then the system prompts "Label [Languages]:"
When the user types "Programming Languages"
Then the system prompts "Skills (comma-separated) [Python, Go]:"
When the user types ""
Then the skills content is updated with label "Programming Languages" and skills ["Python", "Go"]
And the system prints "Skills updated."
```

#### AC-101: Edit Skills Add Group

```
Given the current section is Skills
When the user types "/edit"
And the user types "add"
Then the system prompts "New group label:"
When the user types "Databases"
Then the system prompts "Skills (comma-separated):"
When the user types "PostgreSQL, Redis, MongoDB"
Then a new SkillGroup("Databases", ["PostgreSQL", "Redis", "MongoDB"]) is appended
And the system prints "Skills updated."
```

#### AC-102: Edit Skills Remove Group

```
Given the current section is Skills with 2 groups
When the user types "/edit"
And the user types "remove 1"
Then the system prompts "Remove group 'Languages'? [y/n]:"
When the user types "y"
Then group 1 is removed from the skills list
And the system prints "Skills updated."
```

#### AC-110: Edit Experience Bullet

```
Given the current section is Experience for "Acme Corp, Senior Engineer"
And the role has bullets:
  1. Led migration of monolith to microservices [high]
  2. Reduced deploy time by 40% [high]
When the user types "/edit"
Then the system displays numbered bullets
When the user types "2"
Then the system prompts "New bullet text:"
When the user types "Cut deployment time by 40% through CI/CD pipeline optimization"
Then bullet 2's rewritten field is updated, confidence is set to "medium"
And the system prints "Bullet updated."
```

#### AC-111: Edit Experience Add Bullet

```
Given the current section is Experience with 2 bullets
When the user types "/edit"
And the user types "add"
Then the system prompts "New bullet text:"
When the user types "Mentored 3 junior engineers on distributed systems design"
Then a new TailoredBullet is appended with original="[user-added]", confidence="medium"
And the system prints "Bullet added."
```

#### AC-112: Edit Experience Remove Last Bullet Rejected

```
Given the current section is Experience with 1 bullet
When the user types "/edit"
And the user types "remove 1"
Then the system prints "Cannot remove the only bullet." and stays in the edit prompt
```

#### AC-120: Edit Earlier Experience

```
Given the current section is Earlier Experience with text "Previously held roles at..."
When the user types "/edit"
Then the system prompts "New earlier experience text:"
When the user types "Senior Developer at StartupX (2015-2018), Junior Developer at BigCo (2012-2015)"
Then earlier_experience is updated to the new text
And the system prints "Earlier experience updated."
```

#### AC-130: Edit Languages

```
Given the current section is Languages with ["English", "Spanish"]
When the user types "/edit"
Then the system prompts "Languages (comma-separated):"
When the user types "English, Spanish, French"
Then languages is updated to ["English", "Spanish", "French"]
And the system prints "Languages updated."
```

#### AC-131: Edit Languages Empty Input

```
Given the current section is Languages
When the user types "/edit"
Then the system prompts "Languages (comma-separated):"
When the user types ""
Then languages remain unchanged
And the system prints "Empty input; languages unchanged."
```

### Edge Cases

| ID | Scenario | Expected Behavior |
|----|----------|-------------------|
| EC-100 | `/edit` on Skills section with 0 groups | Print "No skill groups to edit. Use /regenerate to generate skills." and return |
| EC-101 | User types a non-numeric, non-keyword value at group selection | Print "Invalid selection." and re-prompt or return to REPL |
| EC-102 | User types `remove N` where N is out of range | Print "Group number must be between 1 and {total}." |
| EC-103 | User types `cancel` at any edit sub-prompt | Abort the edit, print "Edit cancelled.", return to REPL |
| EC-110 | `/edit` on Experience section with 0 bullets | Print "No bullets to edit." and return |
| EC-111 | User enters empty text for a new bullet | Print "Empty text; bullet unchanged." and return to edit prompt |
| EC-112 | User types out-of-range bullet number | Print "Bullet number must be between 1 and {total}." |
| EC-120 | `/edit` on Earlier Experience when `earlier_experience` is None | Should not occur (section is only built if `earlier_experience` is not None) |
| EC-130 | `/edit` on Languages; user enters only commas/whitespace | Treat as empty input; print warning, leave unchanged |

### API Contracts

#### New Methods on `InteractiveSession`

```python
def _edit_skills(self) -> None:
    """Interactive editor for the Skills section.

    Displays numbered skill groups, prompts for group selection,
    then allows editing the label and skills list, or adding/removing groups.
    """

def _edit_experience(self, role_index: int) -> None:
    """Interactive editor for an Experience section.

    Args:
        role_index: Index into self._content.roles for the role to edit.

    Displays numbered bullets, prompts for bullet selection,
    then allows editing the rewritten text, or adding/removing bullets.
    Also supports editing summary and tech_stack.
    """

def _edit_earlier_experience(self) -> None:
    """Interactive editor for the Earlier Experience section.

    Prompts for free-text replacement of self._content.earlier_experience.
    """

def _edit_languages(self) -> None:
    """Interactive editor for the Languages section.

    Prompts for a comma-separated list replacement of self._content.languages.
    """
```

#### Modified Method: `_handle_edit`

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

### Data Models

No new data models. All edits operate through existing `model_copy(update=...)` patterns on:
- `TailoredContent` (top-level)
- `SkillGroup` (for skills)
- `TailoredRole` (for experience)
- `TailoredBullet` (for individual bullets)
- `MissionStatement` (already implemented)

---

## Feature 2: Free-Text Regeneration

### Background

Currently, bare text input (no leading `/`) returns `CommandKind.UNKNOWN` and displays "Unknown command." The `/regenerate` command is a stub that prints "will be available in a future release." This feature transforms bare text into regeneration instructions and implements the regeneration flow end-to-end.

### Requirements

#### REQ-200: FREE_TEXT Command Kind

The command parser MUST add a new `CommandKind.FREE_TEXT` enum variant. Bare text input (no leading `/`) MUST return `ParsedCommand(kind=CommandKind.FREE_TEXT, args=<the text>)` instead of `CommandKind.UNKNOWN`.

#### REQ-201: Unknown Slash Commands Remain UNKNOWN

Input starting with `/` that does not match any entry in `_COMMAND_MAP` MUST still return `CommandKind.UNKNOWN`. Only non-slash bare text changes behavior.

#### REQ-202: Regeneration Instruction Accumulation

`InteractiveSession` MUST maintain a `_regen_instructions: dict[int, list[str]]` field, keyed by section index (0-based). Each free-text or `/regenerate <text>` input MUST append the instruction text to the list for the current section index.

#### REQ-203: Instructions Persist Across Navigation

Navigating away from a section (`/goto`, `/accept`, `/skip`) MUST NOT clear the accumulated regeneration instructions for that section. The user may return to the section and continue refining.

#### REQ-204: Instructions Clear on Accept

When a section is accepted via `/accept`, its regeneration instructions MUST be cleared from `_regen_instructions`. This prevents stale instructions from affecting a future regeneration if the user navigates back and then regenerates again.

#### REQ-205: Regeneration Service Dependency

`InteractiveSession.__init__` MUST accept an optional `regeneration_service: RegenerationService | None` parameter (default `None`). When `None`, free-text and `/regenerate` MUST print a message: "Regeneration is not available (no LLM service configured)." and return without error.

#### REQ-206: Regeneration Flow

When regeneration is triggered (free-text or `/regenerate`) and `regeneration_service` is not None, the session MUST:
1. Append the instruction text to `_regen_instructions[current_index]`.
2. Call `self._regeneration_service.regenerate_section()` with the current content, section kind, section metadata (e.g. `role_index`), accumulated instructions, and pipeline context.
3. On success, replace the relevant portion of `self._content` with the returned model.
4. Print a confirmation message including the section label.
5. The section is re-rendered on the next loop iteration.

#### REQ-207: Regeneration Async Integration

The `regenerate_section()` call is async. The session MUST call it via `asyncio.run()`, matching the existing pattern used in `_run_interactive_pipeline` for stages 4-5.

#### REQ-208: Regeneration Error Handling

If `regenerate_section()` raises any exception, the session MUST catch it, print a user-friendly error message (including the exception's message), and return to the REPL without crashing. The content MUST remain unchanged.

#### REQ-209: Regeneration Hint Message

When bare text triggers `FREE_TEXT`, the session MUST print a hint: "Regenerating [section label] with your instructions..." before invoking the LLM. This clarifies to the user that their text is being used as regeneration input rather than being discarded.

#### REQ-210: `/regenerate` With No Args and No Accumulated Instructions

If the user types `/regenerate` with no args and there are no accumulated instructions for the current section, the session MUST print "No regeneration instructions provided. Type your feedback as free text or use /regenerate <instructions>." and return.

#### REQ-211: `/regenerate` With No Args But Existing Instructions

If the user types `/regenerate` with no args but there ARE accumulated instructions for the current section, the session MUST re-run regeneration using the existing accumulated instructions (a retry).

#### REQ-212: Regeneration Spinner

During the async LLM call, the session MUST display a Rich spinner/status indicator ("Regenerating...") so the user knows the system is working.

### RegenerationService Requirements

#### REQ-220: RegenerationService Class

A new `RegenerationService` class MUST be created at `src/mkcv/core/services/regeneration.py`. It MUST NOT import from `cli/`, `adapters/`, or `config/` (core layer rule).

#### REQ-221: RegenerationService Constructor

```python
class RegenerationService:
    def __init__(
        self,
        llm: LLMPort,
        prompts: PromptLoaderPort,
        model: str,
        temperature: float = 0.5,
    ) -> None:
```

The service depends only on ports (LLMPort, PromptLoaderPort), never on concrete adapters.

#### REQ-222: regenerate_section Method Signature

```python
async def regenerate_section(
    self,
    content: TailoredContent,
    section_kind: SectionKind,
    instructions: list[str],
    *,
    role_index: int | None = None,
    jd_analysis: JDAnalysis | None = None,
    ats_keywords: list[str] | None = None,
    kb_text: str | None = None,
) -> TailoredContent:
```

The method MUST return a new `TailoredContent` with only the targeted section replaced.

#### REQ-223: Section-Specific Prompt Building

The service MUST build a focused prompt containing:
1. The current content of the targeted section (serialized).
2. A "User Feedback" block with all accumulated instructions (joined with newlines).
3. The original pipeline context (JD analysis, ATS keywords, KB text) if available, to maintain quality.
4. Instructions specific to the section type (e.g., for experience bullets: maintain the `original` field, use XYZ formula).

#### REQ-224: Prompt Template

A new Jinja2 template `src/mkcv/prompts/regenerate_section.j2` MUST be created. It MUST accept:
- `section_kind`: string (mission, skills, experience, earlier_experience, languages)
- `current_content`: dict (serialized section content)
- `instructions`: list[str]
- `jd_analysis`: dict | None
- `ats_keywords`: list[str] | None
- `kb_text`: str | None
- `role_index`: int | None (for experience sections)

#### REQ-225: Structured Output Per Section Type

The LLM call MUST use `complete_structured` with the appropriate Pydantic model per section kind:

| Section Kind | Response Model |
|-------------|---------------|
| MISSION | `MissionStatement` |
| SKILLS | `list[SkillGroup]` (wrapped in a helper model `SkillsSection`) |
| EXPERIENCE | `TailoredRole` |
| EARLIER_EXPERIENCE | `EarlierExperienceSection` (new wrapper) |
| LANGUAGES | `LanguagesSection` (new wrapper) |

#### REQ-226: Content Merging

After receiving the LLM response, the service MUST merge the result into the provided `TailoredContent` via `model_copy(update=...)` and return the updated content. For experience, only the role at `role_index` is replaced.

#### REQ-227: Token Usage Reporting

After regeneration, the session SHOULD print the token usage (input/output tokens) from `llm.get_last_usage()` in a dim style, so the user is aware of the cost.

### Acceptance Criteria

#### AC-200: Bare Text Triggers Regeneration

```
Given the current section is Mission
And regeneration_service is configured
When the user types "make it more concise and focused on cloud infrastructure"
Then the system prints "Regenerating Mission with your instructions..."
And the system calls regenerate_section with instructions=["make it more concise and focused on cloud infrastructure"]
And the mission text is replaced with the LLM response
And the system prints "Mission regenerated."
And the section is re-displayed on the next loop iteration
```

#### AC-201: `/regenerate` With Instructions

```
Given the current section is Skills
And regeneration_service is configured
When the user types "/regenerate add more emphasis on Kubernetes and container orchestration"
Then the system appends the instruction and calls regenerate_section
And the skills section is replaced with the LLM response
And the system prints "Skills regenerated."
```

#### AC-202: Instruction Accumulation

```
Given the current section is Experience (role_index=0)
When the user types "emphasize leadership and team growth"
Then _regen_instructions[2] == ["emphasize leadership and team growth"]
When the user types "also mention the migration project"
Then _regen_instructions[2] == ["emphasize leadership and team growth", "also mention the migration project"]
And the regeneration call receives both instructions
```

#### AC-203: Instructions Survive Navigation

```
Given the current section index is 0 (Mission) with instructions ["be concise"]
When the user types "/goto 3"
And the user types "/goto 1"
Then _regen_instructions[0] still contains ["be concise"]
```

#### AC-204: Instructions Clear on Accept

```
Given section 0 has accumulated instructions ["be concise"]
When the user types "/accept" on section 0
Then _regen_instructions[0] is removed or set to []
```

#### AC-205: No Regeneration Service Configured

```
Given regeneration_service is None
When the user types "make it better"
Then the system prints "Regeneration is not available (no LLM service configured)."
And the REPL continues on the same section
```

#### AC-206: Regeneration Error Recovery

```
Given regeneration_service is configured
And the LLM call raises a PipelineStageError
When the user types "rewrite the bullets"
Then the system prints "Regeneration failed: <error message>"
And the content remains unchanged
And the REPL continues on the same section
```

#### AC-207: `/regenerate` With No Args, No History

```
Given the current section is Mission with no accumulated instructions
When the user types "/regenerate"
Then the system prints "No regeneration instructions provided..."
And no LLM call is made
```

#### AC-208: `/regenerate` With No Args, Existing History

```
Given the current section is Mission with instructions ["be concise"]
When the user types "/regenerate"
Then the system re-runs regeneration with instructions=["be concise"]
```

### Edge Cases

| ID | Scenario | Expected Behavior |
|----|----------|-------------------|
| EC-200 | Bare text that looks like a typo'd command (e.g., "accept") | Treated as `FREE_TEXT` regeneration instruction. The hint message clarifies: "Regenerating Mission with your instructions..." |
| EC-201 | Very long instruction text (>2000 chars) | Pass through to LLM; no client-side truncation. LLM context limits will be the natural bound. |
| EC-202 | Multiple rapid regeneration requests | Each is sequential (synchronous REPL). No concurrency issues. Instructions accumulate across all attempts. |
| EC-203 | Regeneration returns content that fails Pydantic validation | Caught by REQ-208 error handling. Print error, keep original content. |
| EC-204 | `asyncio.run()` called when event loop is already running | Unlikely in the synchronous REPL. If it occurs, catch `RuntimeError` and fall back to `loop.run_until_complete()`. |
| EC-205 | Regeneration on a section that was already edited via `/edit` | Works normally. Regeneration sees the current (edited) content and uses it plus instructions to produce a new version. |
| EC-206 | Empty free text (only whitespace, no `/`) | Already handled: empty/whitespace input returns `CommandKind.DISPLAY` (re-renders). Only non-empty bare text triggers `FREE_TEXT`. |

### API Contracts

#### New File: `src/mkcv/core/services/regeneration.py`

```python
class RegenerationService:
    """Service for regenerating individual resume sections via LLM."""

    def __init__(
        self,
        llm: LLMPort,
        prompts: PromptLoaderPort,
        model: str,
        temperature: float = 0.5,
    ) -> None: ...

    async def regenerate_section(
        self,
        content: TailoredContent,
        section_kind: SectionKind,
        instructions: list[str],
        *,
        role_index: int | None = None,
        jd_analysis: JDAnalysis | None = None,
        ats_keywords: list[str] | None = None,
        kb_text: str | None = None,
    ) -> TailoredContent:
        """Regenerate a single section of the tailored content.

        Args:
            content: The current full TailoredContent.
            section_kind: Which section to regenerate.
            instructions: Accumulated user instructions for this section.
            role_index: For EXPERIENCE sections, which role to regenerate.
            jd_analysis: Optional JD analysis for context.
            ats_keywords: Optional ATS keywords for the LLM.
            kb_text: Optional knowledge base text for accuracy grounding.

        Returns:
            A new TailoredContent with the targeted section replaced.

        Raises:
            PipelineStageError: If the LLM call fails after retries.
            ValidationError: If the LLM output fails Pydantic validation.
        """
```

#### New File: `src/mkcv/core/ports/regeneration.py` (optional, for testability)

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class RegenerationPort(Protocol):
    """Interface for section regeneration."""

    async def regenerate_section(
        self,
        content: TailoredContent,
        section_kind: SectionKind,
        instructions: list[str],
        *,
        role_index: int | None = None,
        jd_analysis: JDAnalysis | None = None,
        ats_keywords: list[str] | None = None,
        kb_text: str | None = None,
    ) -> TailoredContent: ...
```

#### Modified: `commands.py`

```python
class CommandKind(Enum):
    # ... existing ...
    FREE_TEXT = auto()   # NEW

def parse(raw: str) -> ParsedCommand:
    # ...
    if not stripped.startswith("/"):
        return ParsedCommand(kind=CommandKind.FREE_TEXT, args=stripped)  # CHANGED from UNKNOWN
    # ...
```

#### Modified: `InteractiveSession.__init__`

```python
def __init__(
    self,
    content: TailoredContent,
    console: Console,
    *,
    regeneration_service: RegenerationService | None = None,
    pipeline_context: PipelineContext | None = None,
) -> None:
    self._content = content
    self._console = console
    self._sections = build_sections(content)
    self._current_index = 0
    self._regeneration_service = regeneration_service
    self._pipeline_context = pipeline_context
    self._regen_instructions: dict[int, list[str]] = {}
```

#### New Dataclass: `PipelineContext`

```python
@dataclass(frozen=True)
class PipelineContext:
    """Context from earlier pipeline stages needed for regeneration."""
    jd_analysis: JDAnalysis | None = None
    ats_keywords: list[str] | None = None
    kb_text: str | None = None
```

This lives in `src/mkcv/cli/interactive/session.py` (or a shared types module) since it is a data carrier for the CLI layer. It is NOT a core model -- it is a CLI-layer convenience for passing pipeline context into the session.

### Data Models

#### New Wrapper Models (in `src/mkcv/core/models/`)

These are needed because `complete_structured` requires a single Pydantic model as the response type, but Skills and Languages are list types on `TailoredContent`.

```python
# src/mkcv/core/models/skills_section.py
class SkillsSection(BaseModel):
    """Wrapper for structured LLM output of a skills section."""
    skills: list[SkillGroup]

# src/mkcv/core/models/languages_section.py
class LanguagesSection(BaseModel):
    """Wrapper for structured LLM output of a languages section."""
    languages: list[str]

# src/mkcv/core/models/earlier_experience_section.py
class EarlierExperienceSection(BaseModel):
    """Wrapper for structured LLM output of an earlier experience section."""
    earlier_experience: str
```

---

## Feature 3: Tab Completion via `prompt_toolkit`

### Background

The current REPL uses `rich.prompt.Prompt.ask` for all user input. There is no tab completion. This feature introduces `prompt_toolkit` for input handling with prefix-matching completion for all slash commands and contextual completions for `/goto`.

### Requirements

#### REQ-300: New Dependency

`prompt_toolkit>=3.0` MUST be added to `pyproject.toml` under `[project.dependencies]`.

#### REQ-301: CommandCompleter Class

A new `CommandCompleter` class MUST be implemented that extends `prompt_toolkit.completion.Completer` and provides prefix-matching completions for all keys in `_COMMAND_MAP` from `commands.py`.

#### REQ-302: Slash Command Completions

When the user types `/` followed by any prefix (e.g., `/ac`), the completer MUST suggest all matching commands (e.g., `/accept`). Completions MUST include a short description from a display metadata mapping.

#### REQ-303: `/goto` Section Number Completions

When the user has typed `/goto ` (with trailing space), the completer MUST suggest section numbers `1` through `N` (where N is the total section count), each annotated with the section label.

#### REQ-304: Pluggable Prompt Function

`InteractiveSession.__init__` MUST accept an optional `prompt_fn: Callable[[str], str] | None` parameter. When provided, it replaces the default `Prompt.ask` call. When `None`, the session falls back to `Prompt.ask`.

#### REQ-305: prompt_toolkit Wrapper Module

A new module `src/mkcv/cli/interactive/prompt_input.py` MUST provide:
- `create_prompt_session(sections: list[SectionInfo]) -> PromptSession` -- factory function
- `CommandCompleter` -- the completer class
- `prompt_with_completion(session: PromptSession, label: str) -> str` -- wrapper that calls `session.prompt()` and returns the result

#### REQ-306: Graceful Fallback

If `prompt_toolkit` is not importable (e.g., optional dependency not installed) or if stdin is not a TTY (`not sys.stdin.isatty()`), the system MUST fall back to `rich.prompt.Prompt.ask` silently. No error or warning is printed.

#### REQ-307: Prompt Styling

The `prompt_toolkit` prompt MUST display the same `[N/M] SectionLabel` format as the current `Prompt.ask` label. The prompt MUST use a style consistent with the existing Rich-based UI (cyan for section labels).

#### REQ-308: Integration in `_run_interactive_pipeline`

The `_run_interactive_pipeline` function in `generate.py` MUST construct the `prompt_toolkit`-based prompt function and pass it to `InteractiveSession` via the `prompt_fn` parameter.

#### REQ-309: Free-Text Input Not Completed

The completer MUST NOT suggest completions when the input does not start with `/`. Free text (for regeneration) should have no completions interfering.

#### REQ-310: Completion After Edit/Regenerate Subcommands

When inside an edit or regeneration sub-prompt (e.g., "New bullet text:"), tab completion MUST NOT be active. Sub-prompts use plain `Prompt.ask` or `prompt_toolkit` without the command completer.

### Acceptance Criteria

#### AC-300: Tab Completes Slash Commands

```
Given the user is at the interactive prompt
When the user types "/ac" and presses Tab
Then the input is completed to "/accept"
```

#### AC-301: Tab Shows Multiple Matches

```
Given the user is at the interactive prompt
When the user types "/s" and presses Tab
Then the completer shows ["/skip", "/sections"] as options
```

#### AC-302: `/goto` Section Number Completion

```
Given there are 5 sections
When the user types "/goto " and presses Tab
Then the completer shows ["1", "2", "3", "4", "5"] with section labels as descriptions
```

#### AC-303: Fallback When Not TTY

```
Given stdin is not a TTY (e.g., piped input)
When the interactive session starts
Then the session uses Prompt.ask instead of prompt_toolkit
And no error is raised
```

#### AC-304: No Completions for Free Text

```
Given the user is at the interactive prompt
When the user types "make the" and presses Tab
Then no completions are shown (input does not start with "/")
```

#### AC-305: Tests Use Mock Prompt Function

```
Given a test creates InteractiveSession with prompt_fn=mock_fn
When the session runs
Then mock_fn is called instead of Prompt.ask or prompt_toolkit
And no import of prompt_toolkit is required
```

### Edge Cases

| ID | Scenario | Expected Behavior |
|----|----------|-------------------|
| EC-300 | `prompt_toolkit` installed but terminal does not support it | Falls back to `Prompt.ask` |
| EC-301 | User presses Tab on empty input | Shows all slash commands |
| EC-302 | User types `/` then Tab | Shows all slash commands |
| EC-303 | User types `/goto 1` then Tab (number already complete) | No additional completions |
| EC-304 | Section count changes during session (theoretically via regeneration adding/removing) | Section count is fixed at session start per `build_sections`. Completer uses the initial count. |
| EC-305 | User presses Ctrl+C during prompt_toolkit prompt | `prompt_toolkit` raises `KeyboardInterrupt`, caught by existing handler in `run()` |
| EC-306 | User presses Ctrl+D (EOF) during prompt_toolkit prompt | `prompt_toolkit` raises `EOFError`. Session should catch and treat as `/cancel`. |

### API Contracts

#### New File: `src/mkcv/cli/interactive/prompt_input.py`

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mkcv.cli.interactive.sections import SectionInfo

def create_prompt_fn(
    sections: list[SectionInfo],
) -> Callable[[str], str] | None:
    """Create a prompt_toolkit-based prompt function.

    Returns None if prompt_toolkit is unavailable or stdin is not a TTY.
    In that case, the caller should fall back to Prompt.ask.
    """

class CommandCompleter(Completer):
    """Prefix-matching completer for interactive slash commands.

    Args:
        sections: List of section metadata for /goto number completions.
    """

    def __init__(self, sections: list[SectionInfo]) -> None: ...

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,
    ) -> Iterable[Completion]: ...
```

#### Modified: `InteractiveSession.__init__`

```python
def __init__(
    self,
    content: TailoredContent,
    console: Console,
    *,
    regeneration_service: RegenerationService | None = None,
    pipeline_context: PipelineContext | None = None,
    prompt_fn: Callable[[str], str] | None = None,
) -> None:
```

#### Modified: `InteractiveSession._repl` (prompt call)

```python
# Before:
raw = Prompt.ask(prompt_label)

# After:
raw = self._prompt_fn(prompt_label) if self._prompt_fn else Prompt.ask(prompt_label)
```

### Data Models

No new data models for this feature.

---

## Cross-Cutting Concerns

### Testing Strategy

#### Unit Tests: `tests/test_cli/test_interactive/test_commands.py`

- Add tests for `CommandKind.FREE_TEXT` returned on bare text input.
- Update existing `test_bare_text_without_slash` to assert `FREE_TEXT` instead of `UNKNOWN`.
- Add test that unknown `/` commands still return `UNKNOWN`.

#### Unit Tests: `tests/test_cli/test_interactive/test_session.py`

- Add test class `TestEditSkills` with tests for group selection, label edit, skills edit, add, remove.
- Add test class `TestEditExperience` with tests for bullet selection, text edit, add, remove, summary, tech_stack.
- Add test class `TestEditEarlierExperience` with tests for text replacement and empty input.
- Add test class `TestEditLanguages` with tests for list replacement and empty input.
- Add test class `TestFreeTextRegeneration` with tests for instruction accumulation, regeneration call, error handling, no-service fallback.
- Add test class `TestRegenerateCommand` with tests for with-args, no-args-no-history, no-args-with-history.
- Update `TestUnknownCommand.test_bare_text_is_treated_as_unknown` -- this test must change since bare text is now `FREE_TEXT`, not `UNKNOWN`.

#### Unit Tests: `tests/test_core/test_regeneration_service.py`

- Test each section kind with a mock LLM that returns valid Pydantic models.
- Test error handling (LLM raises, validation fails).
- Test that prompt includes accumulated instructions.
- Test that pipeline context (JD, ATS keywords, KB) is passed through to the prompt.

#### Unit Tests: `tests/test_cli/test_interactive/test_prompt_input.py`

- Test `CommandCompleter` returns correct completions for command prefixes.
- Test `/goto` number completions with section labels.
- Test no completions for non-slash input.
- Test `create_prompt_fn` returns `None` when `prompt_toolkit` is unavailable (mock the import).
- Test `create_prompt_fn` returns `None` when stdin is not a TTY.

### Integration Points

#### `src/mkcv/cli/commands/generate.py` -- `_run_interactive_pipeline`

Must be updated to:
1. Create a `RegenerationService` using the same LLM provider and prompt loader used for stage 3.
2. Build a `PipelineContext` from the stage-1 JD analysis artifact and the KB text.
3. Create the `prompt_toolkit`-based prompt function via `create_prompt_fn`.
4. Pass all three to `InteractiveSession`.

```python
# In _run_interactive_pipeline, after loading stage3 content:
from mkcv.cli.interactive.prompt_input import create_prompt_fn
from mkcv.core.services.regeneration import RegenerationService

# Build regeneration service from same providers used in pipeline
regen_service = RegenerationService(
    llm=pipeline._resolve_llm(3),
    prompts=pipeline._prompts,
    model=pipeline._stage_configs[3].model,
    temperature=pipeline._stage_configs[3].temperature,
)

# Load JD analysis for context
jd_analysis_data = json.loads(
    (artifact_dir / "stage1_analysis.json").read_text(encoding="utf-8")
)
jd_analysis = JDAnalysis.model_validate(jd_analysis_data)

pipeline_context = PipelineContext(
    jd_analysis=jd_analysis,
    ats_keywords=jd_analysis.ats_keywords,
    kb_text=kb.read_text(encoding="utf-8"),
)

prompt_fn = create_prompt_fn(build_sections(content))

session = InteractiveSession(
    content,
    console,
    regeneration_service=regen_service,
    pipeline_context=pipeline_context,
    prompt_fn=prompt_fn,
)
```

Note: Accessing `pipeline._resolve_llm(3)` and `pipeline._prompts` requires either making those accessible (e.g., via properties) or reconstructing the LLM and prompt loader from the factory. The design phase should determine the cleanest approach -- likely the factory approach, since `_resolve_llm` is a private method.

### Backward Compatibility

- `InteractiveSession.__init__` new parameters are all keyword-only with defaults (`None`). Existing callers (including tests) continue to work without changes.
- The `FREE_TEXT` change in `parse()` is a behavioral change: bare text previously returned `UNKNOWN`, now returns `FREE_TEXT`. Tests asserting `UNKNOWN` for bare text must be updated. However, the user experience strictly improves (bare text was useless before).
- The `/regenerate` stub message is replaced with actual functionality. Tests asserting the stub message must be updated.

---

## Dependency Summary

| New Dependency | Version | Purpose | Layer |
|---------------|---------|---------|-------|
| `prompt_toolkit` | `>=3.0` | Tab completion and input handling | CLI |

| New File | Layer | Purpose |
|----------|-------|---------|
| `src/mkcv/core/services/regeneration.py` | Core | `RegenerationService` |
| `src/mkcv/core/ports/regeneration.py` | Core | `RegenerationPort` protocol (optional) |
| `src/mkcv/core/models/skills_section.py` | Core | Wrapper for structured LLM skills output |
| `src/mkcv/core/models/languages_section.py` | Core | Wrapper for structured LLM languages output |
| `src/mkcv/core/models/earlier_experience_section.py` | Core | Wrapper for structured LLM earlier experience output |
| `src/mkcv/cli/interactive/prompt_input.py` | CLI | `prompt_toolkit` wrapper and `CommandCompleter` |
| `src/mkcv/prompts/regenerate_section.j2` | Prompts | Jinja2 template for regeneration |
| `tests/test_core/test_regeneration_service.py` | Tests | Unit tests for RegenerationService |
| `tests/test_cli/test_interactive/test_prompt_input.py` | Tests | Unit tests for completer and prompt function |

| Modified File | Changes |
|--------------|---------|
| `src/mkcv/cli/interactive/commands.py` | Add `FREE_TEXT` enum, change bare-text parsing |
| `src/mkcv/cli/interactive/session.py` | Add edit handlers, regeneration dispatch, regen state, new constructor params |
| `src/mkcv/cli/interactive/display.py` | Update help table descriptions |
| `src/mkcv/cli/commands/generate.py` | Wire `RegenerationService`, `PipelineContext`, `prompt_fn` |
| `pyproject.toml` | Add `prompt_toolkit>=3.0` |
| `tests/test_cli/test_interactive/test_commands.py` | Update bare-text tests for `FREE_TEXT` |
| `tests/test_cli/test_interactive/test_session.py` | Add edit/regeneration tests, update bare-text test |

---

## Requirement Traceability Matrix

| Requirement | Feature | Test Coverage |
|------------|---------|--------------|
| REQ-100..105 | F1: Edit Skills | `TestEditSkills` |
| REQ-110..115 | F1: Edit Experience | `TestEditExperience` |
| REQ-120 | F1: Edit Earlier Exp | `TestEditEarlierExperience` |
| REQ-130 | F1: Edit Languages | `TestEditLanguages` |
| REQ-140..141 | F1: Edit Behavior | All edit test classes |
| REQ-200..201 | F2: Command Parsing | `test_commands.py` |
| REQ-202..204 | F2: Instruction State | `TestFreeTextRegeneration` |
| REQ-205..212 | F2: Regen Session | `TestFreeTextRegeneration`, `TestRegenerateCommand` |
| REQ-220..227 | F2: Regen Service | `test_regeneration_service.py` |
| REQ-300..310 | F3: Tab Completion | `test_prompt_input.py` |
