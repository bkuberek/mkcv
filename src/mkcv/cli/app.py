"""mkcv CLI application.

Cyclopts-based CLI with global options (--verbose, --workspace, --version)
and subcommands: generate, render, validate, init, themes, status, cover-letter,
kb, models.
"""

import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import cyclopts
from rich.console import Console
from rich.markup import escape

from mkcv import __version__
from mkcv.config import find_workspace_root, settings
from mkcv.config.user_config_path import USER_CONFIG_DISPLAY_PATH, user_config_path
from mkcv.core.exceptions import MkcvError

if TYPE_CHECKING:
    from mkcv.adapters.filesystem.config_bootstrap import ConfigBootstrap

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
app.command("mkcv.cli.commands.kb:kb_app", name="kb")
app.command("mkcv.cli.commands.models:models_command", name="models")


# Invocations that only print something and must never write config files.
_QUIET_FLAGS = frozenset(
    {*app.version_flags, "--install-completion", "--show-completion"}
)


def _is_quiet_invocation(tokens: Sequence[str]) -> bool:
    return any(token in _QUIET_FLAGS for token in tokens)


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

    # ---- Workspace config file ----
    bootstrap = None if _is_quiet_invocation(tokens) else _create_config_bootstrap()

    # ---- Workspace discovery ----
    if workspace is not None:
        workspace_path = workspace.resolve()
        if not workspace_path.is_dir():
            console.print(
                f"[red]Error:[/red] Workspace path does not exist: {workspace_path}"
            )
            sys.exit(2)
        _fill_empty_workspace_config(bootstrap, workspace_path)
        settings.load_workspace_config(workspace_path)
        logger.debug("Workspace loaded from --workspace flag: %s", workspace_path)
    else:
        discovered = find_workspace_root()
        if discovered is not None:
            _fill_empty_workspace_config(bootstrap, discovered)
            settings.load_workspace_config(discovered)
            logger.debug("Workspace auto-discovered: %s", discovered)
        else:
            logger.debug("No workspace found")

    # ---- Dispatch to subcommand ----
    try:
        app(tokens)
    except MkcvError as exc:
        console.print(f"[red]Error:[/red] {escape(str(exc))}")
        sys.exit(exc.exit_code)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(130)


def _ensure_user_config(arguments: Sequence[str]) -> None:
    """Create the user config on first run, before any command or help prints.

    Runs from ``main`` because ``--help`` is answered before the meta handler.
    """
    if _is_quiet_invocation(arguments):
        return
    if _create_config_bootstrap().ensure_user_config(user_config_path()):
        console.print(
            f"Created {USER_CONFIG_DISPLAY_PATH} \u2014 add your API key there "
            "(see docs/models.md#api-keys).",
            soft_wrap=True,
        )
        settings.load_user_config()


def _create_config_bootstrap() -> "ConfigBootstrap":
    from mkcv.adapters.factory import create_config_bootstrap

    return create_config_bootstrap()


def _fill_empty_workspace_config(
    bootstrap: "ConfigBootstrap | None", workspace_root: Path
) -> None:
    if bootstrap is not None and bootstrap.ensure_workspace_config(workspace_root):
        console.print(
            f"Filled the empty {escape(str(workspace_root / 'mkcv.toml'))} with "
            "commented options (see docs/models.md).",
            soft_wrap=True,
        )


# ---------------------------------------------------------------------------
# Entry point (registered in pyproject.toml as mkcv = "mkcv.cli.app:main")
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the mkcv CLI."""
    _ensure_user_config(sys.argv[1:])
    app.meta()
