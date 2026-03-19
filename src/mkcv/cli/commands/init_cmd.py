"""mkcv init — initialize a new workspace."""

import logging
from pathlib import Path
from typing import Annotated

import cyclopts
from rich.console import Console

from mkcv.adapters.factory import create_workspace_service
from mkcv.core.exceptions import WorkspaceExistsError

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
) -> None:
    """Initialize a new mkcv workspace.

    Creates the workspace directory structure with configuration files
    and knowledge base templates.
    """
    target = path.resolve()
    console.print(f"\n  Initializing mkcv workspace at [bold]{target}/[/bold]\n")

    workspace_service = create_workspace_service()

    try:
        workspace_root = workspace_service.init_workspace(target)
    except WorkspaceExistsError:
        console.print(
            f"  [yellow]Workspace already exists at {target}/[/yellow]\n"
            "  To reinitialize, remove mkcv.toml first.\n"
            "  Existing files will not be overwritten.\n"
        )
        return

    # Print summary of created files
    _print_created_summary(workspace_root)

    # Print next steps
    console.print("  [bold]Next steps:[/bold]")
    console.print("    1. Edit knowledge-base/career.md with your career history")
    console.print("    2. Save a job description to a .txt file")
    console.print("    3. Run: [cyan]mkcv generate --jd <job-description.txt>[/cyan]\n")


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
