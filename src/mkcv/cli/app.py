"""mkcv CLI application.

Cyclopts-based CLI with global options (--verbose, --workspace, --version)
and subcommands: generate, render, validate, init, themes.
"""

import logging
import sys
from pathlib import Path
from typing import Annotated

import cyclopts
from rich.console import Console

from mkcv import __version__
from mkcv.config import find_workspace_root, settings
from mkcv.core.exceptions import MkcvError

logger = logging.getLogger(__name__)

console = Console(stderr=True)
output_console = Console()

app = cyclopts.App(
    name="mkcv",
    help=(
        "AI-powered resume generator — create ATS-compliant resumes "
        "tailored to job descriptions."
    ),
    version=__version__,
)

# ---------------------------------------------------------------------------
# Register subcommands (lazy imports via import-path strings)
# ---------------------------------------------------------------------------
app.command("mkcv.cli.commands.generate:generate_command", name="generate")
app.command("mkcv.cli.commands.render:render_command", name="render")
app.command("mkcv.cli.commands.validate:validate_command", name="validate")
app.command("mkcv.cli.commands.init_cmd:init_command", name="init")
app.command("mkcv.cli.commands.themes:themes_command", name="themes")
app.command("mkcv.cli.commands.status:status_command", name="status")
app.command("mkcv.cli.commands.cover_letter:cover_letter_command", name="cover-letter")


# ---------------------------------------------------------------------------
# Meta handler — global options applied before any subcommand
# ---------------------------------------------------------------------------


@app.meta.default
def meta_handler(
    *tokens: Annotated[str, cyclopts.Parameter(show=False, allow_leading_hyphen=True)],
    verbose: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--verbose", "-v"],
            help="Enable verbose (DEBUG) logging.",
        ),
    ] = False,
    workspace: Annotated[
        Path | None,
        cyclopts.Parameter(
            name="--workspace",
            help="Path to workspace root (overrides auto-discovery).",
        ),
    ] = None,
) -> None:
    """Process global options and dispatch to the appropriate subcommand."""
    # ---- Logging setup ----
    log_level = logging.DEBUG if verbose else logging.WARNING
    log_format = settings.general.log_format
    logging.basicConfig(level=log_level, format=log_format, force=True)

    if verbose:
        settings.set("general.verbose", True)
        settings.set("general.log_level", "DEBUG")
        logger.debug("Verbose mode enabled")

    # ---- Workspace discovery ----
    if workspace is not None:
        workspace_path = workspace.resolve()
        if not workspace_path.is_dir():
            console.print(
                f"[red]Error:[/red] Workspace path does not exist: {workspace_path}"
            )
            sys.exit(2)
        settings.load_workspace_config(workspace_path)
        logger.debug("Workspace loaded from --workspace flag: %s", workspace_path)
    else:
        discovered = find_workspace_root()
        if discovered is not None:
            settings.load_workspace_config(discovered)
            logger.debug("Workspace auto-discovered: %s", discovered)
        else:
            logger.debug("No workspace found")

    # ---- Dispatch to subcommand ----
    try:
        app(tokens)
    except MkcvError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(exc.exit_code)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(130)


# ---------------------------------------------------------------------------
# Entry point (registered in pyproject.toml as mkcv = "mkcv.cli.app:main")
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the mkcv CLI."""
    app.meta()
