"""Create the commented config files on first run.

The user file (``~/.config/mkcv/settings.toml``) is created when missing or
empty. A workspace ``mkcv.toml`` is only filled when it exists and is empty;
its presence marks a workspace, so it is never created here. A file with any
non-whitespace content is never touched, and no failure here reaches the user.
"""

import logging
import os
from collections.abc import Mapping
from pathlib import Path
from typing import TextIO

from mkcv import __version__
from mkcv.adapters.filesystem.config_scope import ConfigScope
from mkcv.adapters.filesystem.config_template import render_config_template

logger = logging.getLogger(__name__)

OPT_OUT_VARIABLE = "MKCV_NO_USER_CONFIG"
_TRUTHY = frozenset({"1", "true", "yes", "on"})
_PRIVATE_FILE_MODE = 0o600
_WORKSPACE_CONFIG_NAME = "mkcv.toml"


class ConfigBootstrap:
    """Writes the settings templates where mkcv expects its config files."""

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = os.environ if environ is None else environ

    def ensure_user_config(self, path: Path) -> bool:
        """Create the user config at ``path`` if it is missing or blank.

        The file is created with mode 0600 from the start; an existing blank
        file keeps its permissions.

        Returns:
            True if the file was written.
        """
        if self._opted_out():
            return False
        return self._write_blank_file(
            path, render_config_template(ConfigScope.USER), create=True
        )

    def ensure_workspace_config(self, workspace_root: Path) -> bool:
        """Fill ``workspace_root/mkcv.toml`` if it exists and is blank.

        Returns:
            True if the file was written.
        """
        path = workspace_root / _WORKSPACE_CONFIG_NAME
        if self._opted_out() or not path.is_file():
            return False
        template = render_config_template(ConfigScope.WORKSPACE, version=__version__)
        return self._write_blank_file(path, template, create=False)

    def _opted_out(self) -> bool:
        return self._environ.get(OPT_OUT_VARIABLE, "").strip().lower() in _TRUTHY

    @staticmethod
    def _write_blank_file(path: Path, content: str, *, create: bool) -> bool:
        try:
            if create:
                path.parent.mkdir(parents=True, exist_ok=True)
            with _open_for_filling(path, create=create) as handle:
                if handle.read().strip():
                    return False
                handle.seek(0)
                handle.write(content)
                handle.truncate()
        except (OSError, UnicodeDecodeError) as error:
            logger.debug("Left %s as it is: %s", path, error)
            return False
        logger.debug("Wrote the settings template to %s", path)
        return True


def _open_for_filling(path: Path, *, create: bool) -> TextIO:
    """Open ``path`` for reading and writing, creating it private when allowed."""
    if create:
        try:
            descriptor = os.open(
                path, os.O_RDWR | os.O_CREAT | os.O_EXCL, _PRIVATE_FILE_MODE
            )
        except FileExistsError:
            descriptor = os.open(path, os.O_RDWR)
    else:
        descriptor = os.open(path, os.O_RDWR)
    return os.fdopen(descriptor, "r+", encoding="utf-8", newline="")
