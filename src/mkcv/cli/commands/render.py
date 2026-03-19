"""mkcv render — render a resume YAML file to PDF."""

import platform
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import cyclopts
from rich.console import Console

from mkcv.adapters.factory import create_render_service
from mkcv.config import settings
from mkcv.core.exceptions.render import RenderError

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
    output formats using RenderCV.
    """
    resolved_yaml = yaml_file.resolve()
    if not resolved_yaml.is_file():
        console.print(f"[red]Error:[/red] File not found: {resolved_yaml}")
        sys.exit(2)

    effective_output_dir = (
        output_dir if output_dir is not None else resolved_yaml.parent
    )
    effective_theme = theme if theme is not None else "sb2nov"

    service = create_render_service(settings)

    try:
        result = service.render_resume(
            resolved_yaml,
            effective_output_dir,
            theme=effective_theme,
        )
    except RenderError as exc:
        raise exc

    console.print(f"\n  [green]PDF:[/green]  {result.pdf_path}")
    if result.png_path:
        console.print(f"  [green]PNG:[/green]  {result.png_path}")
    if result.md_path:
        console.print(f"  [green]MD:[/green]   {result.md_path}")
    if result.html_path:
        console.print(f"  [green]HTML:[/green] {result.html_path}")
    console.print()

    if open:
        _open_file(result.pdf_path)


def _open_file(path: Path) -> None:
    """Open a file with the system default application."""
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["open", str(path)], check=True)
        elif system == "Linux":
            subprocess.run(["xdg-open", str(path)], check=True)
        elif system == "Windows":
            subprocess.run(["start", str(path)], check=True, shell=True)
        else:
            console.print(
                f"  [yellow]Cannot auto-open on {system}. "
                f"Open manually:[/yellow] {path}"
            )
    except (subprocess.CalledProcessError, FileNotFoundError):
        console.print(
            f"  [yellow]Could not open file automatically.[/yellow] "
            f"Open manually: {path}"
        )
