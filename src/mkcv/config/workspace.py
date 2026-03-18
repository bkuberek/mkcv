"""Workspace discovery and loading utilities."""

from pathlib import Path

WORKSPACE_CONFIG_FILENAME = "mkcv.toml"


def find_workspace_root(start: Path | None = None) -> Path | None:
    """Walk up from `start` looking for mkcv.toml.

    Similar to how git finds .git/ by walking up the directory tree.

    Args:
        start: Directory to start searching from. Defaults to CWD.

    Returns:
        Path to the workspace root directory, or None if not found.
    """
    current = (start or Path.cwd()).resolve()

    while True:
        if (current / WORKSPACE_CONFIG_FILENAME).is_file():
            return current

        parent = current.parent
        if parent == current:
            # Reached filesystem root
            return None
        current = parent


def is_workspace(path: Path) -> bool:
    """Check if a directory is an mkcv workspace.

    Args:
        path: Directory to check.

    Returns:
        True if the directory contains mkcv.toml.
    """
    return (path / WORKSPACE_CONFIG_FILENAME).is_file()
