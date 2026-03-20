"""mkcv render — render a resume YAML file to PDF."""

import logging
import platform
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import cyclopts
from rich.console import Console

from mkcv.adapters.factory import create_render_service
from mkcv.config import settings
from mkcv.core.services.theme import parse_theme_argument, resolve_theme

logger = logging.getLogger(__name__)

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
            help=(
                "Visual theme override (fonts, colors, layout). "
                "Comma-separated for multi-theme: 'sb2nov,classic'. "
                "Use 'all' to render every theme. "
                "Default: from YAML design section. "
                "Run 'mkcv themes' to list options."
            ),
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
    requested_formats = [f.strip() for f in format.split(",") if f.strip()]

    # Multi-theme path: comma-separated themes or "all" keyword
    if theme is not None and ("," in theme or theme.strip().lower() == "all"):
        workspace_root = settings.workspace_root if settings.in_workspace else None
        themes = parse_theme_argument(theme, workspace_root)
        _render_multi_theme(
            resolved_yaml, effective_output_dir, themes, requested_formats, open
        )
        return

    # Single-theme path (existing behavior, unchanged)
    effective_theme = resolve_theme(theme, settings.rendering.theme)

    # Apply workspace design config if available
    yaml_content = _apply_workspace_design(resolved_yaml, effective_theme)

    service = create_render_service(settings)

    result = service.render_resume(
        resolved_yaml,
        effective_output_dir,
        theme=effective_theme,
        formats=requested_formats,
        yaml_content=yaml_content,
    )

    console.print()
    if result.pdf_path and result.pdf_path.exists():
        console.print(f"  [green]PDF:[/green]  {result.pdf_path}")
    if result.png_path:
        console.print(f"  [green]PNG:[/green]  {result.png_path}")
    if result.md_path:
        console.print(f"  [green]MD:[/green]   {result.md_path}")
    if result.html_path:
        console.print(f"  [green]HTML:[/green] {result.html_path}")
    console.print()

    if open and result.pdf_path.exists():
        _open_file(result.pdf_path)


def _apply_workspace_design(yaml_path: Path, theme: str) -> str | None:
    """Build design from workspace config and inject into YAML content.

    When running inside a workspace, reads the design settings from
    mkcv.toml and merges them into the YAML file content so that
    workspace config overrides the baked-in design section.

    Args:
        yaml_path: Resolved path to the resume YAML file.
        theme: Effective theme name to use.

    Returns:
        Modified YAML content with workspace design applied, or None
        if not in a workspace or no design overrides are configured.
    """
    if not settings.in_workspace:
        return None

    from mkcv.adapters.factory import _build_resume_design
    from mkcv.core.services.yaml_postprocessor import YamlPostProcessor

    design = _build_resume_design(settings, theme)
    if not design.has_overrides():
        return None

    logger.info("Applying workspace design config to render")

    try:
        yaml_str = yaml_path.read_text(encoding="utf-8")
    except OSError:
        logger.warning("Could not read YAML file for design injection")
        return None

    try:
        postprocessor = YamlPostProcessor()
        return postprocessor.inject_design(yaml_str, design)
    except (ValueError, OSError):
        logger.warning(
            "Failed to inject workspace design; rendering with baked-in design",
            exc_info=True,
        )
        return None


def _render_multi_theme(
    yaml_path: Path,
    output_dir: Path,
    themes: list[str],
    formats: list[str],
    open_pdf: bool,
) -> None:
    """Render across multiple themes and print summary table."""
    from rich.table import Table

    from mkcv.adapters.factory import create_batch_render_service

    console.print()
    total = len(themes)
    for n, theme_name in enumerate(themes, 1):
        console.print(
            f"  Rendering theme {n}/{total}: {theme_name}...",
        )

    service = create_batch_render_service(settings)
    batch_result = service.render_multi_theme(
        yaml_path,
        output_dir,
        themes,
        formats=formats,
    )

    # Print Rich summary table
    table = Table(title="Multi-Theme Render Results")
    table.add_column("Theme", style="cyan")
    table.add_column("Status")
    table.add_column("PDF Path")

    for r in batch_result.results:
        if r.status == "success" and r.output and r.output.pdf_path:
            table.add_row(
                r.theme,
                "[green]OK[/green]",
                str(r.output.pdf_path),
            )
        else:
            table.add_row(
                r.theme,
                "[red]FAIL[/red]",
                r.error_message or "Unknown error",
            )

    console.print()
    console.print(table)
    console.print(
        f"\n  [bold]{batch_result.succeeded}/{batch_result.total}[/bold] "
        f"themes rendered successfully."
    )

    if batch_result.failed > 0:
        console.print(f"  [yellow]{batch_result.failed} theme(s) failed.[/yellow]")
        console.print()
        sys.exit(6)

    console.print()

    # Open first successful PDF if --open was requested
    if open_pdf:
        first_success = next(
            (
                r
                for r in batch_result.results
                if r.status == "success" and r.output and r.output.pdf_path.exists()
            ),
            None,
        )
        if first_success and first_success.output:
            _open_file(first_success.output.pdf_path)


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
