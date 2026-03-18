"""Dynaconf-based configuration for mkcv."""

from pathlib import Path

from dynaconf import Dynaconf, Validator

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
        global_config = Path.home() / ".config" / "mkcv" / "settings.toml"
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
