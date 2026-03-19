"""mkcv themes — list and preview available resume themes."""

import sys
from typing import Annotated

import cyclopts
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from mkcv.config import settings
from mkcv.core.models.theme_info import ThemeInfo
from mkcv.core.services.theme import discover_themes, get_theme

console = Console()


def _render_theme_table(themes: list[ThemeInfo]) -> Table:
    """Build a rich Table showing all available themes."""
    default_theme = str(getattr(settings.rendering, "theme", "sb2nov"))

    table = Table(
        show_header=True,
        header_style="bold",
        padding=(0, 2),
        expand=False,
    )
    table.add_column("Theme", style="cyan", no_wrap=True)
    table.add_column("Source", style="dim")
    table.add_column("Description")
    table.add_column("Font", style="dim")

    for theme in themes:
        name_display = theme.name
        if theme.name == default_theme:
            name_display = f"{theme.name} (default)"
        source_badge = "[custom]" if theme.source == "custom" else ""
        table.add_row(name_display, source_badge, theme.description, theme.font_family)

    return table


def _render_preview_panel(theme: ThemeInfo) -> Panel:
    """Build a rich Panel showing detailed theme preview."""
    body = Text()

    body.append("Font Family:     ", style="bold")
    body.append(f"{theme.font_family}\n")

    body.append("Primary Color:   ", style="bold")
    body.append(f"{theme.primary_color}\n", style=theme.primary_color)

    body.append("Accent Color:    ", style="bold")
    body.append(f"{theme.accent_color}\n", style=theme.accent_color)

    body.append("Page Size:       ", style="bold")
    body.append(f"{theme.page_size}\n")

    body.append("\n")
    body.append("Sample Layout", style=f"bold {theme.primary_color}")
    body.append("\n")
    body.append("\u2500" * 40 + "\n", style=theme.accent_color)

    body.append("John Doe\n", style=f"bold {theme.primary_color}")
    body.append("Senior Software Engineer\n", style="dim")
    body.append("john@example.com | github.com/johndoe\n\n", style="dim")

    body.append("Experience", style=f"bold {theme.accent_color}")
    body.append("\n")
    body.append("\u2500" * 40 + "\n", style=theme.accent_color)
    body.append("Acme Corp", style="bold")
    body.append(" — Staff Engineer\n")
    body.append("  \u2022 Led migration of monolith to microservices\n")
    body.append("  \u2022 Reduced CI/CD pipeline latency by 60%\n")

    return Panel(
        body,
        title=f"[bold]{theme.name}[/bold]",
        subtitle=theme.description,
        border_style=theme.primary_color,
        padding=(1, 2),
    )


def themes_command(
    *,
    preview: Annotated[
        str | None,
        cyclopts.Parameter(
            help="Show a styled preview for a specific theme.",
        ),
    ] = None,
) -> None:
    """List and preview available resume themes.

    Themes control the visual design of your resume: fonts, colors,
    margins, and page layout. They do NOT control AI content generation
    (that's handled by prompt templates in the templates/ directory).
    """
    workspace_root = settings.workspace_root
    themes = discover_themes(workspace_root=workspace_root)

    if not themes:
        console.print(
            "\n  [yellow]No themes available. "
            "Install rendercv:[/yellow] "
            'uv add "rendercv[full]"\n'
        )
        return

    if preview is not None:
        theme = get_theme(preview, workspace_root=workspace_root)
        if theme is None:
            available = ", ".join(t.name for t in themes)
            console.print(
                f"\n  [red]Error:[/red] Unknown theme "
                f"[bold]{preview}[/bold]\n"
                f"  Available: {available}\n"
            )
            sys.exit(2)

        console.print()
        console.print(_render_preview_panel(theme))
        _show_config_overrides()
        console.print(
            f"\n  Render with: [cyan]mkcv render resume.yaml "
            f"--theme {theme.name}[/cyan]\n"
        )
        return

    console.print()
    console.print(_render_theme_table(themes))
    console.print("\n  Preview: [cyan]mkcv themes --preview THEME_NAME[/cyan]\n")


def _show_config_overrides() -> None:
    """Show active config overrides if any are set."""
    try:
        overrides = getattr(settings.rendering, "overrides", None)
        if overrides is None:
            return

        override_lines: list[str] = []
        for key in ("font", "font_size", "page_size", "primary_color"):
            value = getattr(overrides, key, None)
            if value:
                override_lines.append(
                    f"    {key.replace('_', ' ').title()}: {value} [override]"
                )

        if override_lines:
            console.print()
            console.print("  [bold]Overrides (from config):[/bold]")
            for line in override_lines:
                console.print(line)
    except AttributeError:
        pass
