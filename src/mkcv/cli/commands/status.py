"""mkcv status — show workspace overview and application listing."""

import logging
import tomllib
from pathlib import Path

from rich.console import Console
from rich.table import Table

from mkcv.adapters.factory import create_workspace_service
from mkcv.config.workspace import find_workspace_root
from mkcv.core.models.application_metadata import ApplicationMetadata

logger = logging.getLogger(__name__)

console = Console()


def status_command() -> None:
    """Show workspace status, configuration, and application listing."""
    workspace_root = find_workspace_root()

    if workspace_root is None:
        _print_no_workspace()
        return

    _print_workspace_overview(workspace_root)
    _print_application_listing(workspace_root)


def _print_no_workspace(
    *,
    _console: Console | None = None,
) -> None:
    """Print a message when no workspace is found."""
    out = _console or console
    out.print(
        "\n  [yellow]No mkcv workspace found.[/yellow]\n"
        "\n"
        "  Run [cyan]mkcv init <path>[/cyan] to create one.\n"
    )


def _print_workspace_overview(
    workspace_root: Path,
    *,
    _console: Console | None = None,
) -> None:
    """Print workspace root, config, and knowledge base info."""
    out = _console or console
    config_path = workspace_root / "mkcv.toml"
    kb_path = workspace_root / "knowledge-base" / "career.md"

    service = create_workspace_service()
    applications = service.list_applications(workspace_root)

    out.print()
    out.print("  [bold]mkcv workspace[/bold]")
    out.print(f"  Root:           {workspace_root}")
    out.print(f"  Config:         {config_path}")

    kb_status = "[green]exists[/green]" if kb_path.is_file() else "[red]missing[/red]"
    out.print(f"  Knowledge base: {kb_path} ({kb_status})")
    out.print(f"  Applications:   {len(applications)}")
    out.print()


def _print_application_listing(
    workspace_root: Path,
    *,
    _console: Console | None = None,
) -> None:
    """Print a table of applications found in the workspace."""
    out = _console or console
    service = create_workspace_service()
    app_dirs = service.list_applications(workspace_root)

    if not app_dirs:
        out.print(
            "  No applications yet. Run [cyan]mkcv generate[/cyan] to create one.\n"
        )
        return

    table = _build_application_table(app_dirs)
    out.print(table)

    most_recent = app_dirs[-1]
    out.print(f"\n  Most recent: [bold]{most_recent.name}[/bold]")
    out.print()


def _build_application_table(app_dirs: list[Path]) -> Table:
    """Build a rich Table showing application details."""
    table = Table(
        show_header=True,
        header_style="bold",
        padding=(0, 2),
        expand=False,
    )
    table.add_column("Company", style="cyan", no_wrap=True)
    table.add_column("Position")
    table.add_column("Date")
    table.add_column("Status")
    table.add_column("Resume YAML", justify="center")
    table.add_column("PDF", justify="center")

    for app_dir in app_dirs:
        metadata = _read_application_metadata(app_dir)
        has_yaml = (app_dir / "resume.yaml").is_file()
        has_pdf = any(app_dir.glob("*.pdf"))

        company: str
        position: str
        date_str: str
        status: str
        if metadata is not None:
            company = metadata.company
            position = metadata.position
            date_str = metadata.date.isoformat()
            status = metadata.status
        else:
            company = app_dir.parent.name
            position = app_dir.name
            date_str = "?"
            status = "?"

        yaml_mark = "[green]\u2713[/green]" if has_yaml else "[dim]\u2717[/dim]"
        pdf_mark = "[green]\u2713[/green]" if has_pdf else "[dim]\u2717[/dim]"

        table.add_row(company, position, date_str, status, yaml_mark, pdf_mark)

    return table


def _read_application_metadata(app_dir: Path) -> ApplicationMetadata | None:
    """Read and parse application.toml from an application directory.

    Returns None if the file is missing or malformed.
    """
    toml_path = app_dir / "application.toml"
    if not toml_path.is_file():
        return None

    try:
        with toml_path.open("rb") as f:
            data = tomllib.load(f)

        app_data = data.get("application", {})
        return ApplicationMetadata(**app_data)
    except (tomllib.TOMLDecodeError, KeyError, ValueError, TypeError):
        logger.warning("Failed to parse %s", toml_path)
        return None
