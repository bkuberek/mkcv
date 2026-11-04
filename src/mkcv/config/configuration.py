"""Dynaconf-based configuration for mkcv."""

from pathlib import Path

from dynaconf import Dynaconf, Validator
from dynaconf.loaders import env_loader  # type: ignore[import-untyped]

from mkcv.config.user_config_path import user_config_path

_CONFIG_DIR = Path(__file__).parent


class Configuration(Dynaconf):  # type: ignore[misc]  # Dynaconf has no type stubs
    """mkcv configuration management.

    Loads settings from (in order, later overrides earlier):
        1. Built-in defaults (settings.toml bundled with package)
        2. Global user config (~/.config/mkcv/settings.toml)
        3. Workspace config (mkcv.toml — loaded dynamically)
        4. Environment variables (MKCV_ prefix)
        5. CLI flags (applied at runtime via set())

    Usage:
        from mkcv.config import settings
        theme = settings.rendering.theme
    """

    def __init__(self) -> None:
        settings_files = [
            str(_CONFIG_DIR / "settings.toml"),
            str(_CONFIG_DIR / ".secrets.toml"),
        ]

        # Add global user config if it exists
        global_config = user_config_path()
        if global_config.is_file():
            settings_files.append(str(global_config))

        super().__init__(
            settings_files=settings_files,
            envvar_prefix="MKCV",
            environments=True,
            default_env="default",
            merge_enabled=True,
        )

        self._register_validators()
        self._workspace_root: Path | None = None

    def _register_validators(self) -> None:
        """Register validators for critical settings."""
        self.validators.register(
            Validator("rendering.theme", default="sb2nov"),
            Validator("general.verbose", default=False, is_type_of=bool),
            Validator("general.log_level", default="WARNING"),
        )
        self.validators.validate()

    def load_user_config(self) -> None:
        """Load the user config file into the settings chain, if it exists.

        The file is read when the settings are created. Call this after
        creating the file mid-run, so the same run sees it.
        """
        path = user_config_path()
        if path.is_file():
            self.load_file(path=str(path))
            # A file loaded after startup would otherwise sit above the
            # environment variables, which must stay above every file.
            self.execute_loaders(loaders=[env_loader])

    def load_workspace_config(self, workspace_root: Path) -> None:
        """Load workspace-level mkcv.toml into the settings chain.

        This is called when a workspace is discovered (either via
        CLI --workspace flag or auto-discovery from CWD).

        Args:
            workspace_root: Path to the workspace root containing mkcv.toml.
        """
        workspace_config = workspace_root / "mkcv.toml"
        if workspace_config.is_file():
            self.load_file(path=str(workspace_config))
            self._workspace_root = workspace_root

    @property
    def workspace_root(self) -> Path | None:
        """The active workspace root, if any."""
        return self._workspace_root

    @property
    def in_workspace(self) -> bool:
        """Whether a workspace is currently active."""
        return self._workspace_root is not None
