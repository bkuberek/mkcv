"""Where the user config file lives."""

from pathlib import Path

USER_CONFIG_DISPLAY_PATH = "~/.config/mkcv/settings.toml"
"""The user config path as written in messages and docs."""


def user_config_path() -> Path:
    """Return the user config file path under the current home directory."""
    return Path.home() / ".config" / "mkcv" / "settings.toml"
