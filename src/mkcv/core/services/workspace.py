"""Workspace management service."""

from pathlib import Path

from mkcv.core.models.application_metadata import ApplicationMetadata
from mkcv.core.models.workspace_config import WorkspaceConfig


class WorkspaceService:
    """Manages workspace initialization and application directory creation.

    This service encapsulates workspace business logic. It delegates
    filesystem operations to the WorkspaceManager adapter (injected
    via the constructor in a future task).
    """

    def init_workspace(self, path: Path) -> WorkspaceConfig:
        """Initialize a new mkcv workspace at the given path.

        Creates the workspace directory structure:
            - mkcv.toml (workspace config)
            - knowledge-base/ (KB directory with starter template)
            - applications/ (empty applications directory)
            - .gitignore

        Args:
            path: Directory to initialize as a workspace.

        Returns:
            The generated WorkspaceConfig.

        Raises:
            WorkspaceExistsError: If path already contains mkcv.toml.
        """
        raise NotImplementedError("Workspace initialization not yet implemented")

    def setup_application(
        self,
        workspace_root: Path,
        company: str,
        position: str,
        jd_path: Path,
    ) -> ApplicationMetadata:
        """Create an application directory within the workspace.

        Creates: applications/{company}/{YYYY-MM-position}/
        With: application.toml, jd.txt (copied), .mkcv/

        Args:
            workspace_root: Path to workspace root.
            company: Company name (will be slugified).
            position: Position title (will be slugified).
            jd_path: Path to job description file (will be copied).

        Returns:
            ApplicationMetadata for the new application.
        """
        raise NotImplementedError("Application setup not yet implemented")
