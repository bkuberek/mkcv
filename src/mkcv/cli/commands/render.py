"""mkcv render — render a resume YAML file to PDF."""

from pathlib import Path
from typing import Annotated

import cyclopts
from rich.console import Console

console = Console()


def render_command(
    yaml_file: Annotated[
        Path,
        cyclopts.Parameter(
            help="RenderCV YAML file to render.",
        ),
    ],
    *,
    output_dir: Annotated[
        Path | None,
        cyclopts.Parameter(
            name="--output-dir",
            help="Output directory (default: same as input file).",
        ),
    ] = None,
    theme: Annotated[
        str | None,
        cyclopts.Parameter(
            help="Override theme (default: from YAML).",
        ),
    ] = None,
    format: Annotated[
        str,
        cyclopts.Parameter(
            name="--format",
            help="Output formats, comma-separated (pdf,png,md,html).",
        ),
    ] = "pdf,png",
    open: Annotated[
        bool,
        cyclopts.Parameter(
            name="--open",
            help="Open PDF after rendering.",
        ),
    ] = False,
) -> None:
    """Render an existing resume YAML file to PDF/PNG/MD.

    Takes a RenderCV-compatible YAML file and produces the specified
    output formats.
    """
    console.print(
        "\n  [yellow]Resume rendering not yet implemented.[/yellow]\n"
        f"  File:   {yaml_file}\n"
        f"  Format: {format}\n"
    )
