# Design: Interactive Resume Generation

## Technical Approach

Transform `--interactive` from a stage-gate prompt into a section-by-section editing session. Pipeline stages 1-3 run non-interactively to produce `TailoredContent`. A new `InteractiveSession` in `src/mkcv/cli/interactive/` presents each section for review via a synchronous REPL loop with slash commands. On `/done`, control returns to `generate.py` which runs stages 4-5 and renders the PDF. All new code lives in the CLI layer -- zero core changes.

## Architecture Decisions

### Decision: Synchronous REPL in CLI layer, not a core service

**Choice**: `InteractiveSession` is a plain class in `cli/interactive/session.py` that owns a `TailoredContent` instance and mutates it based on user commands. No Protocol, no port.

**Alternatives considered**: Adding an `InteractivePort` protocol in core; embedding session logic in `generate.py`.

**Rationale**: The session is pure UI orchestration (prompt, display, navigate). It has no business logic that core needs to abstract over. A protocol would add indirection with no second implementation. Keeping it out of `generate.py` avoids bloating that already-large file (~1400 lines).

### Decision: Enum-based section identifiers, not index-based

**Choice**: A `SectionKind` enum (`MISSION`, `SKILLS`, `EXPERIENCE_0..N`, `EDUCATION`, `LANGUAGES`, `EARLIER_EXPERIENCE`) identifies sections. Each section has a `SectionState` enum (`PENDING`, `ACCEPTED`, `SKIPPED`).

**Alternatives considered**: Integer indexing; free-form string keys.

**Rationale**: Enum gives type safety and exhaustiveness checks. `EXPERIENCE_0..N` uses a dynamic suffix because the number of roles varies per run. The state enum maps cleanly to the status grid display.

### Decision: Single-file command parser with dataclass result

**Choice**: `commands.py` parses raw input into a `ParsedCommand(kind: CommandKind, args: str)` dataclass. `CommandKind` is an enum of all slash commands plus `UNKNOWN` and `TEXT` (for bare input treated as implicit `/edit`).

**Alternatives considered**: Registry/plugin pattern; regex-based dispatch.

**Rationale**: There are ~10 commands with trivial parsing. A registry pattern is overbuilt. A single `parse()` function and an enum keep it testable and discoverable.

### Decision: Mutate `TailoredContent` in place via model_copy

**Choice**: When the user edits a section (e.g., changes mission text), the session calls `content.model_copy(update={...})` to produce a new `TailoredContent` with the edit applied.

**Alternatives considered**: Deep-copy and patch; mutable wrapper.

**Rationale**: Pydantic v2 `model_copy` is idiomatic, immutable-friendly, and preserves validation. The session holds the latest copy as its state.

## Data Flow

```
generate_command
  |
  |-- asyncio.run(pipeline.generate(..., stages 1-3))
  |        |
  |        +-> TailoredContent
  |
  |-- InteractiveSession(content, console)
  |        |
  |        +-> REPL loop: display section -> prompt -> parse command -> dispatch
  |        |       |
  |        |       +-> /accept  -> mark ACCEPTED, advance
  |        |       +-> /skip    -> mark SKIPPED, advance
  |        |       +-> /edit    -> prompt for text, apply to content, re-display
  |        |       +-> /sections -> show status grid
  |        |       +-> /display -> re-render current section
  |        |       +-> /goto N  -> jump to section N
  |        |       +-> /done    -> break if all non-PENDING
  |        |       +-> /cancel  -> sys.exit(130)
  |        |       +-> /help    -> show command list
  |        |
  |        +-> returns edited TailoredContent (or None if cancelled)
  |
  |-- (if not cancelled) write updated stage3_content.json
  |-- asyncio.run(pipeline.generate(..., from_stage=4))
  |-- render PDF
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/mkcv/cli/interactive/__init__.py` | Create | Package init, exports `InteractiveSession` |
| `src/mkcv/cli/interactive/session.py` | Create | `InteractiveSession` class -- REPL loop, section navigation, state tracking |
| `src/mkcv/cli/interactive/commands.py` | Create | `CommandKind` enum, `ParsedCommand` dataclass, `parse()` function |
| `src/mkcv/cli/interactive/display.py` | Create | Rich rendering: `render_section()`, `render_status_grid()`, `render_help()`, `render_final_review()` |
| `src/mkcv/cli/interactive/sections.py` | Create | `SectionKind` enum, `SectionState` enum, `SectionInfo` dataclass, `build_sections()` from TailoredContent |
| `src/mkcv/cli/commands/generate.py` | Modify | Replace `_InteractiveProgressCallback` usage with `InteractiveSession` after stage 3; add `_run_interactive_pipeline()` |
| `tests/test_cli/test_interactive/__init__.py` | Create | Test package |
| `tests/test_cli/test_interactive/test_commands.py` | Create | Tests for command parsing |
| `tests/test_cli/test_interactive/test_session.py` | Create | Tests for session state machine |
| `tests/test_cli/test_interactive/test_display.py` | Create | Tests for display rendering |
| `tests/test_cli/test_interactive/test_sections.py` | Create | Tests for section building |

## Interfaces / Contracts

```python
# src/mkcv/cli/interactive/sections.py
from enum import Enum, auto
from dataclasses import dataclass

class SectionKind(Enum):
    MISSION = auto()
    SKILLS = auto()
    EXPERIENCE = auto()  # paired with role_index
    EARLIER_EXPERIENCE = auto()
    LANGUAGES = auto()

class SectionState(Enum):
    PENDING = auto()
    ACCEPTED = auto()
    SKIPPED = auto()

@dataclass
class SectionInfo:
    kind: SectionKind
    label: str              # e.g. "Experience: Acme Corp, Staff Engineer"
    state: SectionState
    role_index: int | None  # only for EXPERIENCE sections

def build_sections(content: TailoredContent) -> list[SectionInfo]: ...
```

```python
# src/mkcv/cli/interactive/commands.py
from enum import Enum, auto
from dataclasses import dataclass

class CommandKind(Enum):
    ACCEPT = auto()
    SKIP = auto()
    EDIT = auto()
    DISPLAY = auto()
    SECTIONS = auto()
    GOTO = auto()
    DONE = auto()
    CANCEL = auto()
    HELP = auto()
    UNKNOWN = auto()

@dataclass
class ParsedCommand:
    kind: CommandKind
    args: str  # e.g. "2" for /goto 2

def parse(raw: str) -> ParsedCommand: ...
```

```python
# src/mkcv/cli/interactive/session.py
from mkcv.core.models.tailored_content import TailoredContent
from rich.console import Console

class InteractiveSession:
    def __init__(
        self,
        content: TailoredContent,
        console: Console,
    ) -> None: ...

    def run(self) -> TailoredContent | None:
        """Run the interactive REPL. Returns edited content, or None if cancelled."""
        ...
```

```python
# Integration point in generate.py
def _run_interactive_pipeline(
    *,
    jd: Path,
    kb: Path,
    output_dir: Path,
    preset_name: str,
    provider_override: str | None,
    render_pdf: bool,
    theme: str,
    jd_text: str,
    chain_cover_letter: bool,
    cl_preset: str,
    app_dir: Path | None,
) -> None:
    """Run stages 1-3, interactive session, then stages 4-5."""
    ...
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `parse()` returns correct `ParsedCommand` for all slash commands, bare text, edge cases | Direct function calls, parametrized pytest |
| Unit | `build_sections()` maps `TailoredContent` to correct `SectionInfo` list | Construct minimal `TailoredContent` fixtures |
| Unit | `InteractiveSession` state transitions: accept, skip, goto, done validation | Mock `Console` and `input()`, verify `SectionState` changes and return value |
| Unit | Display functions produce expected Rich output | `Console(file=StringIO)` capture, assert substrings |
| Integration | `_run_interactive_pipeline` calls pipeline then session then pipeline | Mock `create_pipeline_service`, `InteractiveSession`, verify call sequence |

All tests mock I/O via `unittest.mock.patch` on `rich.prompt.Prompt.ask` (or `builtins.input`), consistent with existing `test_generate_callbacks.py` patterns.

## Migration / Rollout

No migration required. The `--interactive` flag already exists; its behavior changes from stage-gate to section-editor. The `_InteractiveProgressCallback` class becomes unused and can be removed or kept as a fallback (recommend removal to avoid dead code).

## Open Questions

- [x] All resolved -- no blocking questions. Phase 2 (per-section LLM regeneration via `/regenerate`) is explicitly out of scope per the proposal.
