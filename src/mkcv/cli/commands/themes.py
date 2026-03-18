"""mkcv themes — list available resume themes."""

from typing import Annotated

import cyclopts
from rich.console import Console

console = Console()

# Theme registry — will be replaced by dynamic discovery later
_THEMES: dict[str, str] = {
    "sb2nov": "Single-column, minimal, industry standard for tech",
    "classic": "Traditional professional layout",
    "moderncv": "Classic academic/professional CV style",
    "engineeringresumes": "Optimized for engineering roles",
    "markdown": "Plain text with minimal formatting",
}


def themes_command(
    *,
    preview: Annotated[
        str | None,
        cyclopts.Parameter(
            help="Generate a preview PDF for a specific theme.",
        ),
    ] = None,
) -> None:
    """List and preview available resume themes."""
    if preview is not None:
        console.print(
            f"\n  [yellow]Theme preview not yet implemented for: {preview}[/yellow]\n"
        )
        return

    console.print("\n  [bold]Available Themes[/bold]")
    console.print("  " + "\u2500" * 30)

    for name, description in _THEMES.items():
        console.print(f"  [cyan]{name:<22}[/cyan]{description}")

    console.print("\n  Preview: [cyan]mkcv themes --preview sb2nov[/cyan]\n")
