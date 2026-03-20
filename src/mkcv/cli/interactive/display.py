"""Rich rendering helpers for interactive resume review."""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from mkcv.cli.interactive.sections import (
    SectionInfo,
    SectionKind,
    SectionState,
)
from mkcv.core.models.tailored_content import TailoredContent

# ---------------------------------------------------------------------------
# Section rendering
# ---------------------------------------------------------------------------


def render_section(
    console: Console,
    section: SectionInfo,
    content: TailoredContent,
) -> None:
    """Render the content of a single section inside a Rich panel."""
    match section.kind:
        case SectionKind.MISSION:
            _render_mission(console, content)
        case SectionKind.SKILLS:
            _render_skills(console, content)
        case SectionKind.EXPERIENCE:
            assert section.role_index is not None
            _render_experience(console, content, section.role_index)
        case SectionKind.EARLIER_EXPERIENCE:
            _render_earlier_experience(console, content)
        case SectionKind.LANGUAGES:
            _render_languages(console, content)


def _render_mission(console: Console, content: TailoredContent) -> None:
    body = Text(content.mission.text)
    panel = Panel(body, title="Mission Statement", border_style="cyan")
    console.print(panel)
    console.print(
        Text(f"Rationale: {content.mission.rationale}", style="dim italic"),
    )


def _render_skills(console: Console, content: TailoredContent) -> None:
    table = Table(title="Skills", show_header=True, header_style="bold cyan")
    table.add_column("Category", style="bold")
    table.add_column("Skills")
    for group in content.skills:
        table.add_row(group.label, ", ".join(group.skills))
    console.print(table)


def _render_experience(
    console: Console,
    content: TailoredContent,
    role_index: int,
) -> None:
    role = content.roles[role_index]
    header_parts: list[str] = [
        f"**{role.position}** at **{role.company}**",
        f"{role.start_date} -- {role.end_date}",
    ]
    if role.location:
        header_parts.append(role.location)

    header_md = "  \n".join(header_parts)

    bullet_lines: list[str] = []
    for bullet in role.bullets:
        confidence_tag = f" [{bullet.confidence}]"
        bullet_lines.append(f"- {bullet.rewritten}{confidence_tag}")

    body_parts: list[str] = [header_md, ""]
    if role.summary:
        body_parts.append(f"*{role.summary}*\n")
    body_parts.extend(bullet_lines)
    if role.tech_stack:
        body_parts.append(f"\n**Tech:** {role.tech_stack}")

    panel = Panel(
        Markdown("\n".join(body_parts)),
        title=f"Experience: {role.company}",
        border_style="green",
    )
    console.print(panel)


def _render_earlier_experience(console: Console, content: TailoredContent) -> None:
    if content.earlier_experience:
        panel = Panel(
            Markdown(content.earlier_experience),
            title="Earlier Experience",
            border_style="yellow",
        )
        console.print(panel)


def _render_languages(console: Console, content: TailoredContent) -> None:
    if content.languages:
        panel = Panel(
            Text(", ".join(content.languages)),
            title="Languages",
            border_style="magenta",
        )
        console.print(panel)


# ---------------------------------------------------------------------------
# Status grid
# ---------------------------------------------------------------------------

_STATE_STYLES: dict[SectionState, str] = {
    SectionState.PENDING: "yellow",
    SectionState.ACCEPTED: "green",
    SectionState.SKIPPED: "dim",
}

_STATE_LABELS: dict[SectionState, str] = {
    SectionState.PENDING: "PENDING",
    SectionState.ACCEPTED: "ACCEPTED",
    SectionState.SKIPPED: "SKIPPED",
}


def render_status_grid(
    console: Console,
    sections: list[SectionInfo],
    current_index: int,
) -> None:
    """Show all sections with their review states; highlight current."""
    table = Table(title="Sections", show_header=True, header_style="bold")
    table.add_column("#", justify="right", style="bold")
    table.add_column("Section")
    table.add_column("Status")

    for idx, sec in enumerate(sections):
        number = str(idx + 1)
        label = sec.label
        state_label = _STATE_LABELS[sec.state]
        style = _STATE_STYLES[sec.state]

        if idx == current_index:
            label = f"> {label}"
            style = f"bold {style}"

        table.add_row(number, Text(label, style=style), Text(state_label, style=style))

    console.print(table)


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------


def render_help(console: Console) -> None:
    """Display the command reference table."""
    table = Table(title="Commands", show_header=True, header_style="bold cyan")
    table.add_column("Command", style="bold")
    table.add_column("Alias", style="dim")
    table.add_column("Description")

    rows: list[tuple[str, str, str]] = [
        ("/accept", "/a", "Accept this section and advance"),
        ("/skip", "/s", "Skip this section and advance"),
        ("/edit", "/e", "Edit this section (mission text only in MVP)"),
        ("/display", "/d", "Re-display the current section"),
        ("/sections", "", "Show all sections with their status"),
        ("/goto N", "/g N", "Jump to section number N"),
        ("/done", "", "Finish review (all sections must be accepted or skipped)"),
        ("/cancel", "", "Cancel and discard all changes"),
        ("/regenerate", "/regen", "Regenerate section with a prompt (future)"),
        ("/help", "/h", "Show this help"),
        ("(empty)", "", "Re-display the current section"),
    ]

    for cmd, alias, desc in rows:
        table.add_row(cmd, alias, desc)

    console.print(table)


# ---------------------------------------------------------------------------
# Final review
# ---------------------------------------------------------------------------


def render_final_review(
    console: Console,
    content: TailoredContent,
    sections: list[SectionInfo],
) -> None:
    """Render a full resume preview showing accepted sections."""
    console.rule("[bold]Final Review[/bold]")

    for section in sections:
        if section.state == SectionState.SKIPPED:
            console.print(
                Text(f"  [{section.label}] — SKIPPED", style="dim strikethrough"),
            )
            continue
        render_section(console, section, content)
        console.print()

    console.rule()
