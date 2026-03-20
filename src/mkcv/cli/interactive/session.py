"""Interactive REPL session for section-by-section resume review."""

import logging

from rich.console import Console
from rich.prompt import Prompt

from mkcv.cli.interactive.commands import CommandKind, ParsedCommand, parse
from mkcv.cli.interactive.display import (
    render_final_review,
    render_help,
    render_section,
    render_status_grid,
)
from mkcv.cli.interactive.sections import (
    SectionKind,
    SectionState,
    build_sections,
)
from mkcv.core.models.tailored_content import TailoredContent

logger = logging.getLogger(__name__)


class _CancelledError(Exception):
    """Raised internally when the user types /cancel."""


class InteractiveSession:
    """Section-by-section interactive resume review session.

    Presents each section of a ``TailoredContent`` for the user to accept,
    skip, or edit.  Returns the (possibly modified) content on ``/done``,
    or ``None`` on ``/cancel`` / ``KeyboardInterrupt``.
    """

    def __init__(self, content: TailoredContent, console: Console) -> None:
        self._content = content
        self._console = console
        self._sections = build_sections(content)
        self._current_index = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> TailoredContent | None:
        """Run the interactive REPL. Returns edited content, or None if cancelled."""
        self._show_welcome()

        try:
            return self._repl()
        except (KeyboardInterrupt, _CancelledError):
            self._console.print("\n[yellow]Cancelled.[/yellow]")
            return None

    # ------------------------------------------------------------------
    # REPL loop
    # ------------------------------------------------------------------

    def _repl(self) -> TailoredContent | None:
        while True:
            # Auto-finish when all sections have been visited
            if self._current_index >= len(self._sections):
                done_result = self._handle_done()
                if done_result is not None:
                    return done_result
                # User declined; reset to first section so they can navigate
                self._current_index = 0
                continue

            section = self._sections[self._current_index]
            render_section(self._console, section, self._content)

            prompt_label = (
                f"[{self._current_index + 1}/{len(self._sections)}] {section.label}"
            )
            raw = Prompt.ask(prompt_label)
            cmd = parse(raw)

            result = self._dispatch(cmd)
            if result is not None:
                return result

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, cmd: ParsedCommand) -> TailoredContent | None:
        """Dispatch a parsed command. Returns content to exit, or None to continue."""
        match cmd.kind:
            case CommandKind.ACCEPT:
                self._handle_accept()
            case CommandKind.SKIP:
                self._handle_skip()
            case CommandKind.EDIT:
                self._handle_edit(cmd.args)
            case CommandKind.DISPLAY:
                pass  # section is re-rendered at top of loop
            case CommandKind.SECTIONS:
                render_status_grid(
                    self._console,
                    self._sections,
                    self._current_index,
                )
            case CommandKind.GOTO:
                self._handle_goto(cmd.args)
            case CommandKind.DONE:
                return self._handle_done()
            case CommandKind.CANCEL:
                raise _CancelledError
            case CommandKind.HELP:
                render_help(self._console)
            case CommandKind.REGENERATE:
                self._console.print(
                    "[dim]Regeneration will be available in a future release.[/dim]",
                )
            case CommandKind.UNKNOWN:
                self._console.print(
                    "[red]Unknown command.[/red] "
                    "Type [bold]/help[/bold] for a list of commands.",
                )
        return None  # continue REPL

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _handle_accept(self) -> None:
        self._sections[self._current_index].state = SectionState.ACCEPTED
        self._console.print("[green]Accepted.[/green]")
        self._advance()

    def _handle_skip(self) -> None:
        self._sections[self._current_index].state = SectionState.SKIPPED
        self._console.print("[dim]Skipped.[/dim]")
        self._advance()

    def _handle_edit(self, args: str) -> None:
        section = self._sections[self._current_index]
        match section.kind:
            case SectionKind.MISSION:
                self._edit_mission(args)
            case _:
                self._console.print(
                    "[dim]Editing this section type is not supported in this release. "
                    "Use /regenerate in a future version.[/dim]",
                )

    def _edit_mission(self, prefilled: str) -> None:
        new_text = prefilled or Prompt.ask("New mission text")

        if not new_text.strip():
            self._console.print("[red]Empty text; mission unchanged.[/red]")
            return

        updated_mission = self._content.mission.model_copy(
            update={"text": new_text.strip()},
        )
        self._content = self._content.model_copy(update={"mission": updated_mission})
        self._console.print("[green]Mission updated.[/green]")

    def _handle_goto(self, args: str) -> None:
        try:
            target = int(args)
        except (ValueError, TypeError):
            self._console.print(
                "[red]Usage: /goto N  (where N is a section number)[/red]",
            )
            return

        total = len(self._sections)
        if target < 1 or target > total:
            self._console.print(
                f"[red]Section number must be between 1 and {total}.[/red]",
            )
            return

        self._current_index = target - 1

    def _handle_done(self) -> TailoredContent | None:
        pending = [s for s in self._sections if s.state == SectionState.PENDING]
        if pending:
            labels = ", ".join(s.label for s in pending)
            self._console.print(
                f"[red]Cannot finish: {len(pending)} section(s) still pending: "
                f"{labels}[/red]\n"
                "Accept or skip all sections before using /done.",
            )
            return None  # stay in REPL

        # Show the final review using the *original* content so that
        # role_index references in section metadata remain valid.
        render_final_review(self._console, self._content, self._sections)
        final_content = self._build_final_content()

        confirm = Prompt.ask("Finalize this resume?", choices=["y", "n"], default="y")
        if confirm.lower() == "y":
            return final_content

        self._console.print("[yellow]Returning to review.[/yellow]")
        return None  # stay in REPL

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def _advance(self) -> None:
        """Move to the next section that is still PENDING."""
        start = self._current_index + 1
        for i in range(start, len(self._sections)):
            if self._sections[i].state == SectionState.PENDING:
                self._current_index = i
                return
        # All remaining are non-pending; set past end to trigger auto-finish
        self._current_index = len(self._sections)

    # ------------------------------------------------------------------
    # Content building
    # ------------------------------------------------------------------

    def _build_final_content(self) -> TailoredContent:
        """Build a TailoredContent excluding skipped sections."""
        updates: dict[str, object] = {}

        for section in self._sections:
            if section.state != SectionState.SKIPPED:
                continue
            match section.kind:
                case SectionKind.MISSION:
                    # Cannot remove mission entirely; use an empty-ish fallback
                    # In practice the user likely would not skip mission
                    pass
                case SectionKind.SKILLS:
                    updates["skills"] = []
                case SectionKind.EXPERIENCE:
                    # Collect indices to remove
                    pass
                case SectionKind.EARLIER_EXPERIENCE:
                    updates["earlier_experience"] = None
                case SectionKind.LANGUAGES:
                    updates["languages"] = None

        # Handle skipped experience roles
        skipped_indices: set[int] = {
            s.role_index
            for s in self._sections
            if s.kind == SectionKind.EXPERIENCE
            and s.state == SectionState.SKIPPED
            and s.role_index is not None
        }
        if skipped_indices:
            updates["roles"] = [
                role
                for idx, role in enumerate(self._content.roles)
                if idx not in skipped_indices
            ]

        return self._content.model_copy(update=updates)

    # ------------------------------------------------------------------
    # Welcome
    # ------------------------------------------------------------------

    def _show_welcome(self) -> None:
        self._console.print()
        self._console.rule("[bold cyan]Interactive Resume Review[/bold cyan]")
        self._console.print(
            "Review each section. Use [bold]/accept[/bold] or [bold]/skip[/bold] "
            "to proceed, [bold]/help[/bold] for all commands.\n",
        )
