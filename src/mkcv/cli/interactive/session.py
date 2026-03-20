"""Interactive REPL session for section-by-section resume review."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from collections.abc import Callable

    from rich.console import Console

    from mkcv.core.models.regeneration_context import RegenerationContext
    from mkcv.core.models.tailored_content import TailoredContent
    from mkcv.core.services.regeneration import RegenerationService

from mkcv.core.models.skill_group import SkillGroup
from mkcv.core.models.tailored_bullet import TailoredBullet

logger = logging.getLogger(__name__)

# Maps SectionKind enum values to the string identifiers expected by
# RegenerationService.regenerate_section().
_SECTION_KIND_TO_TYPE: dict[SectionKind, str] = {
    SectionKind.MISSION: "mission",
    SectionKind.SKILLS: "skills",
    SectionKind.EXPERIENCE: "experience",
    SectionKind.EARLIER_EXPERIENCE: "earlier_experience",
    SectionKind.LANGUAGES: "languages",
}


class _CancelledError(Exception):
    """Raised internally when the user types /cancel."""


class InteractiveSession:
    """Section-by-section interactive resume review session.

    Presents each section of a ``TailoredContent`` for the user to accept,
    skip, or edit.  Returns the (possibly modified) content on ``/done``,
    or ``None`` on ``/cancel`` / ``KeyboardInterrupt``.
    """

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
        # Regeneration support
        self._regen_service = regeneration_service
        self._regen_context = regeneration_context
        self._prompt_fn = prompt_fn
        # Per-section instruction accumulation, keyed by section index.
        # Instructions persist across navigation and are cleared on /accept.
        self._regen_instructions: dict[int, list[str]] = {}

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
    # Input helpers
    # ------------------------------------------------------------------

    def _ask(self, label: str) -> str:
        """Prompt the user for input, using prompt_fn if configured."""
        if self._prompt_fn is not None:
            return self._prompt_fn(label)
        return Prompt.ask(label)

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
            raw = self._ask(prompt_label)
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
            case CommandKind.FREE_TEXT:
                self._handle_free_text(cmd.args)
            case CommandKind.REGENERATE:
                self._handle_regenerate(cmd.args)
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
        idx = self._current_index
        self._sections[idx].state = SectionState.ACCEPTED
        # Clear regeneration instructions for the accepted section (REQ-204)
        self._regen_instructions.pop(idx, None)
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
            case SectionKind.SKILLS:
                self._edit_skills()
            case SectionKind.EXPERIENCE:
                assert section.role_index is not None
                self._edit_experience(section.role_index)
            case SectionKind.EARLIER_EXPERIENCE:
                self._edit_earlier_experience(args)
            case SectionKind.LANGUAGES:
                self._edit_languages(args)
            case _:
                self._console.print(
                    "[dim]Editing this section type is not supported in this release. "
                    "Use /regenerate in a future version.[/dim]",
                )

    def _edit_mission(self, prefilled: str) -> None:
        new_text = prefilled or self._ask("New mission text")

        if not new_text.strip():
            self._console.print("[red]Empty text; mission unchanged.[/red]")
            return

        updated_mission = self._content.mission.model_copy(
            update={"text": new_text.strip()},
        )
        self._content = self._content.model_copy(update={"mission": updated_mission})
        self._console.print("[green]Mission updated.[/green]")

    def _edit_skills(self) -> None:
        """Edit skill groups: select, add, remove, or modify a group."""
        skills = list(self._content.skills)

        if not skills:
            self._console.print("[red]No skill groups to edit.[/red]")
            return

        # Display numbered skill groups
        self._console.print("[bold]Skill groups:[/bold]")
        for i, group in enumerate(skills, 1):
            self._console.print(f"  {i}. {group.label}: {', '.join(group.skills)}")
        self._console.print("  [dim][add | remove N | cancel][/dim]")

        choice = self._ask("Edit skills").strip()

        if not choice:
            self._console.print("[dim]No selection; skills unchanged.[/dim]")
            return

        if choice.lower() == "cancel":
            self._console.print("[dim]Cancelled; skills unchanged.[/dim]")
            return

        # --- Add a new group ---
        if choice.lower() == "add":
            label = self._ask("New group label").strip()
            if not label:
                self._console.print("[red]Empty label; cancelled.[/red]")
                return
            raw_skills = self._ask("Skills (comma-separated)").strip()
            if not raw_skills:
                self._console.print("[red]Empty skills list; cancelled.[/red]")
                return
            new_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
            if not new_skills:
                self._console.print("[red]No valid skills; cancelled.[/red]")
                return
            skills.append(SkillGroup(label=label, skills=new_skills))
            self._content = self._content.model_copy(update={"skills": skills})
            self._console.print("[green]Skills updated.[/green]")
            return

        # --- Remove a group ---
        if choice.lower().startswith("remove"):
            parts = choice.split(maxsplit=1)
            if len(parts) < 2:
                self._console.print(
                    "[red]Usage: remove N  (where N is a group number)[/red]",
                )
                return
            try:
                idx = int(parts[1])
            except ValueError:
                self._console.print("[red]Invalid group number.[/red]")
                return
            if idx < 1 or idx > len(skills):
                self._console.print(
                    f"[red]Group number must be between 1 and {len(skills)}.[/red]",
                )
                return
            group_to_remove = skills[idx - 1]
            confirm = self._ask(
                f"Remove group '{group_to_remove.label}'? [y/n]",
            ).strip().lower()
            if confirm != "y":
                self._console.print("[dim]Removal cancelled.[/dim]")
                return
            skills.pop(idx - 1)
            self._content = self._content.model_copy(update={"skills": skills})
            self._console.print("[green]Skills updated.[/green]")
            return

        # --- Select a group by number to edit ---
        try:
            idx = int(choice)
        except ValueError:
            self._console.print("[red]Invalid selection.[/red]")
            return

        if idx < 1 or idx > len(skills):
            self._console.print(
                f"[red]Group number must be between 1 and {len(skills)}.[/red]",
            )
            return

        group = skills[idx - 1]

        # Prompt for new label (empty keeps existing)
        new_label = self._ask(f"Label [{group.label}]").strip()
        if not new_label:
            new_label = group.label

        # Prompt for new skills list (empty keeps existing)
        current_skills_str = ", ".join(group.skills)
        new_skills_raw = self._ask(
            f"Skills (comma-separated) [{current_skills_str}]",
        ).strip()
        if new_skills_raw:
            new_skills_list = [
                s.strip() for s in new_skills_raw.split(",") if s.strip()
            ]
        else:
            new_skills_list = list(group.skills)

        updated_group = group.model_copy(
            update={"label": new_label, "skills": new_skills_list},
        )
        skills[idx - 1] = updated_group
        self._content = self._content.model_copy(update={"skills": skills})
        self._console.print("[green]Skills updated.[/green]")

    def _edit_experience(self, role_index: int) -> None:
        """Interactive editor for an Experience section.

        Args:
            role_index: Index into self._content.roles for the role to edit.

        Displays numbered bullets, prompts for bullet selection,
        then allows editing the rewritten text, or adding/removing bullets.
        Also supports editing summary and tech_stack.
        """
        role = self._content.roles[role_index]
        bullets = list(role.bullets)

        if not bullets:
            self._console.print("[red]No bullets to edit.[/red]")
            return

        # Display numbered bullets
        self._console.print(
            f"[bold]{role.company}, {role.position}[/bold]",
        )
        for i, bullet in enumerate(bullets, 1):
            self._console.print(
                f"  {i}. {bullet.rewritten} [{bullet.confidence}]",
            )
        self._console.print(
            "  [dim][add | remove N | summary | tech | cancel][/dim]",
        )

        choice = self._ask("Edit experience").strip()

        if not choice:
            self._console.print("[dim]No selection; experience unchanged.[/dim]")
            return

        if choice.lower() == "cancel":
            self._console.print("[dim]Edit cancelled.[/dim]")
            return

        # --- Add a new bullet ---
        if choice.lower() == "add":
            text = self._ask("New bullet text").strip()
            if not text:
                self._console.print(
                    "[red]Empty text; bullet not added.[/red]",
                )
                return
            new_bullet = TailoredBullet(
                original="[user-added]",
                rewritten=text,
                keywords_incorporated=[],
                confidence="medium",
            )
            bullets.append(new_bullet)
            updated_role = role.model_copy(update={"bullets": bullets})
            roles = list(self._content.roles)
            roles[role_index] = updated_role
            self._content = self._content.model_copy(update={"roles": roles})
            self._console.print("[green]Bullet added.[/green]")
            return

        # --- Remove a bullet ---
        if choice.lower().startswith("remove"):
            parts = choice.split(maxsplit=1)
            if len(parts) < 2:
                self._console.print(
                    "[red]Usage: remove N  (where N is a bullet number)[/red]",
                )
                return
            try:
                bullet_idx = int(parts[1])
            except ValueError:
                self._console.print("[red]Invalid bullet number.[/red]")
                return
            if bullet_idx < 1 or bullet_idx > len(bullets):
                self._console.print(
                    f"[red]Bullet number must be between 1 and {len(bullets)}.[/red]",
                )
                return
            if len(bullets) == 1:
                self._console.print(
                    "[red]Cannot remove the only bullet.[/red]",
                )
                return
            confirm = self._ask(
                f"Remove bullet {bullet_idx}? [y/n]",
            ).strip().lower()
            if confirm != "y":
                self._console.print("[dim]Removal cancelled.[/dim]")
                return
            bullets.pop(bullet_idx - 1)
            updated_role = role.model_copy(update={"bullets": bullets})
            roles = list(self._content.roles)
            roles[role_index] = updated_role
            self._content = self._content.model_copy(update={"roles": roles})
            self._console.print("[green]Bullet removed.[/green]")
            return

        # --- Edit summary ---
        if choice.lower() == "summary":
            current_summary = role.summary or ""
            new_summary = self._ask(
                f"Summary [{current_summary}]",
            ).strip()
            if not new_summary:
                self._console.print(
                    "[dim]Empty input; summary unchanged.[/dim]",
                )
                return
            updated_role = role.model_copy(update={"summary": new_summary})
            roles = list(self._content.roles)
            roles[role_index] = updated_role
            self._content = self._content.model_copy(update={"roles": roles})
            self._console.print("[green]Summary updated.[/green]")
            return

        # --- Edit tech stack ---
        if choice.lower() == "tech":
            current_tech = role.tech_stack or ""
            new_tech = self._ask(
                f"Tech stack [{current_tech}]",
            ).strip()
            if not new_tech:
                self._console.print(
                    "[dim]Empty input; tech stack unchanged.[/dim]",
                )
                return
            updated_role = role.model_copy(update={"tech_stack": new_tech})
            roles = list(self._content.roles)
            roles[role_index] = updated_role
            self._content = self._content.model_copy(update={"roles": roles})
            self._console.print("[green]Tech stack updated.[/green]")
            return

        # --- Select a bullet by number to edit ---
        try:
            bullet_idx = int(choice)
        except ValueError:
            self._console.print("[red]Invalid selection.[/red]")
            return

        if bullet_idx < 1 or bullet_idx > len(bullets):
            self._console.print(
                f"[red]Bullet number must be between 1 and {len(bullets)}.[/red]",
            )
            return

        bullet = bullets[bullet_idx - 1]
        new_text = self._ask("New bullet text").strip()

        if not new_text:
            self._console.print("[red]Empty text; bullet unchanged.[/red]")
            return

        updated_bullet = bullet.model_copy(
            update={"rewritten": new_text, "confidence": "medium"},
        )
        bullets[bullet_idx - 1] = updated_bullet
        updated_role = role.model_copy(update={"bullets": bullets})
        roles = list(self._content.roles)
        roles[role_index] = updated_role
        self._content = self._content.model_copy(update={"roles": roles})
        self._console.print("[green]Bullet updated.[/green]")

    def _edit_earlier_experience(self, prefilled: str) -> None:
        new_text = prefilled or self._ask("New earlier experience text")

        if not new_text.strip():
            self._console.print("[red]Empty text; earlier experience unchanged.[/red]")
            return

        self._content = self._content.model_copy(
            update={"earlier_experience": new_text.strip()},
        )
        self._console.print("[green]Earlier experience updated.[/green]")

    def _edit_languages(self, prefilled: str) -> None:
        """Edit the languages list via comma-separated input."""
        current = self._content.languages or []

        # Display current languages
        if current:
            self._console.print(
                "[bold]Current languages:[/bold] " + ", ".join(current),
            )
        else:
            self._console.print("[dim]No languages set.[/dim]")

        raw = prefilled or self._ask(
            "Languages (comma-separated, or empty to cancel)",
        )

        if not raw.strip():
            self._console.print("[dim]No input; languages unchanged.[/dim]")
            return

        new_languages = [lang.strip() for lang in raw.split(",") if lang.strip()]

        if not new_languages:
            self._console.print("[red]No valid languages; unchanged.[/red]")
            return

        self._content = self._content.model_copy(
            update={"languages": new_languages},
        )
        self._console.print("[green]Languages updated.[/green]")

    def _handle_free_text(self, text: str) -> None:
        """Handle bare text input as a regeneration instruction.

        Appends the text to accumulated instructions for the current section
        and immediately triggers regeneration via the LLM service.
        """
        if self._regen_service is None or self._regen_context is None:
            self._console.print(
                "[dim]Regeneration is not available in this session.[/dim]",
            )
            return
        self._do_regenerate(text)

    def _handle_regenerate(self, args: str) -> None:
        """Handle /regenerate command.

        With args: appends args as instruction and triggers regeneration.
        Without args and existing instructions: retries with accumulated instructions.
        Without args and no instructions: shows usage hint.
        """
        if self._regen_service is None or self._regen_context is None:
            self._console.print(
                "[dim]Regeneration is not available in this session.[/dim]",
            )
            return
        if args:
            self._do_regenerate(args)
            return
        # No args provided — check for existing instructions
        idx = self._current_index
        existing = self._regen_instructions.get(idx, [])
        if not existing:
            self._console.print(
                "[dim]Provide instructions: /regenerate <what to change>[/dim]",
            )
            return
        # Retry with existing accumulated instructions (REQ-211)
        self._do_regenerate_with_existing()

    def _do_regenerate(self, instruction: str) -> None:
        """Accumulate instruction and invoke the regeneration service."""
        assert self._regen_service is not None
        assert self._regen_context is not None

        idx = self._current_index
        section = self._sections[idx]

        # Accumulate the instruction
        self._regen_instructions.setdefault(idx, []).append(instruction)

        self._console.print(
            f"[cyan]Regenerating {section.label}...[/cyan]",
        )

        section_type = _SECTION_KIND_TO_TYPE[section.kind]

        try:
            updated = asyncio.run(
                self._regen_service.regenerate_section(
                    content=self._content,
                    section_type=section_type,
                    instructions=self._regen_instructions[idx],
                    context=self._regen_context,
                    role_index=section.role_index,
                ),
            )
        except Exception as exc:
            self._console.print(f"[red]Regeneration failed: {exc}[/red]")
            return

        self._content = updated
        self._rebuild_sections()
        self._console.print("[green]Section regenerated.[/green]")

    def _do_regenerate_with_existing(self) -> None:
        """Re-run regeneration using only existing accumulated instructions."""
        assert self._regen_service is not None
        assert self._regen_context is not None

        idx = self._current_index
        section = self._sections[idx]
        instructions = self._regen_instructions.get(idx, [])

        self._console.print(
            f"[cyan]Regenerating {section.label}...[/cyan]",
        )

        section_type = _SECTION_KIND_TO_TYPE[section.kind]

        try:
            updated = asyncio.run(
                self._regen_service.regenerate_section(
                    content=self._content,
                    section_type=section_type,
                    instructions=instructions,
                    context=self._regen_context,
                    role_index=section.role_index,
                ),
            )
        except Exception as exc:
            self._console.print(f"[red]Regeneration failed: {exc}[/red]")
            return

        self._content = updated
        self._rebuild_sections()
        self._console.print("[green]Section regenerated.[/green]")

    def _rebuild_sections(self) -> None:
        """Rebuild sections from current content, preserving existing states."""
        old_states = {i: s.state for i, s in enumerate(self._sections)}
        self._sections = build_sections(self._content)
        for i, section in enumerate(self._sections):
            if i in old_states:
                section.state = old_states[i]

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
