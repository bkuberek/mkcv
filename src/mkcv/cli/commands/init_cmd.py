"""mkcv init — initialize a new workspace."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import cyclopts
from rich.console import Console

from mkcv.adapters.factory import create_workspace_service
from mkcv.core.exceptions import WorkspaceExistsError

if TYPE_CHECKING:
    from mkcv.core.services.workspace import WorkspaceService

logger = logging.getLogger(__name__)

console = Console()


@cyclopts.Parameter(name="init")
def init_command(
    path: Annotated[
        Path,
        cyclopts.Parameter(
            help="Directory to initialize as an mkcv workspace.",
            show_default="current directory",
        ),
    ] = Path("."),
    *,
    update_readme: Annotated[
        bool,
        cyclopts.Parameter(
            help=(
                "Update the workspace README.md to the latest version. "
                "Works on existing workspaces without touching other files."
            ),
        ),
    ] = False,
) -> None:
    """Initialize a new mkcv workspace.

    Creates the workspace directory structure with configuration files,
    knowledge base templates, and a themes/ directory with an example
    custom theme.

    On an existing workspace, use --update-readme to regenerate the
    README.md with the latest mkcv documentation without affecting
    any other files.
    """
    target = path.resolve()

    workspace_service = create_workspace_service()

    # Handle --update-readme on existing workspace
    if update_readme:
        _update_readme(workspace_service, target)
        return

    console.print(f"\n  Initializing mkcv workspace at [bold]{target}/[/bold]\n")

    try:
        workspace_root = workspace_service.init_workspace(target)
    except WorkspaceExistsError:
        console.print(
            f"  [yellow]Workspace already exists at {target}/[/yellow]\n"
            "  To reinitialize, remove mkcv.toml first.\n"
            "  Existing files will not be overwritten.\n"
            "\n"
            "  [dim]Tip: run [cyan]mkcv init --update-readme[/cyan] to "
            "update the README.md to the latest version.[/dim]\n"
        )
        return

    # Print summary of created files
    _print_created_summary(workspace_root)

    # Print next steps
    console.print("  [bold]Next steps:[/bold]")
    console.print("    1. Edit knowledge-base/career.md with your career history")
    console.print("    2. Save a job description to a .txt file")
    console.print("    3. Run: [cyan]mkcv generate --jd <job-description.txt>[/cyan]\n")


def _update_readme(workspace_service: WorkspaceService, target: Path) -> None:
    """Update the workspace README.md to the latest version."""
    toml_path = target / "mkcv.toml"
    if not toml_path.is_file():
        console.print(
            f"\n  [red]Not a workspace:[/red] {target}/\n"
            "  No mkcv.toml found. Run [cyan]mkcv init[/cyan] first.\n"
        )
        return

    updated = workspace_service.update_readme(target)
    if updated:
        console.print(
            "\n  [green]\u2713[/green] README.md updated to latest version.\n"
        )
    else:
        console.print("\n  [blue]\u2714[/blue] README.md is already up to date.\n")


def _print_created_summary(workspace_root: Path) -> None:
    """Print a summary of the files and directories created or preserved."""
    # Track which files existed before init ran. Files written by init
    # will have an mtime >= the mkcv.toml (which is always freshly created).
    toml_mtime = (workspace_root / "mkcv.toml").stat().st_mtime

    items = [
        ("mkcv.toml", True),
        ("knowledge-base/career.md", True),
        ("knowledge-base/voice.md", True),
        ("applications/", False),
        ("resumes/", False),
        ("templates/", False),
        ("themes/", False),
        ("themes/example.yaml", True),
        (".gitignore", True),
        ("README.md", True),
    ]

    for name, is_file in items:
        full_path = workspace_root / name.rstrip("/")
        exists = (is_file and full_path.is_file()) or (
            not is_file and full_path.is_dir()
        )
        if not exists:
            console.print(f"  [red]\u2717[/red] Missing {name}")
        elif is_file and full_path.stat().st_mtime < toml_mtime:
            console.print(f"  [blue]\u2714[/blue] Kept existing {name}")
        else:
            console.print(f"  [green]\u2713[/green] Created {name}")

    console.print()
