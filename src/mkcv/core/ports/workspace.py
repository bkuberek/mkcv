"""Port interface for workspace filesystem operations."""

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class WorkspacePort(Protocol):
    """Interface for workspace and application directory management.

    Implementations: WorkspaceManager (filesystem adapter).
    """

    def create_workspace(self, path: Path) -> Path:
        """Create a new mkcv workspace at the given path.

        Args:
            path: Directory to initialize as a workspace.

        Returns:
            Path to the workspace root.

        Raises:
            WorkspaceExistsError: If the workspace already exists.
        """
        ...

    def create_application(
        self,
        workspace_root: Path,
        company: str,
        position: str,
        jd_source: Path,
        *,
        preset_name: str = "standard",
        url: str | None = None,
    ) -> Path:
        """Create an application directory within the workspace.

        Args:
            workspace_root: Workspace root path.
            company: Company name (will be slugified).
            position: Position title (will be slugified).
            jd_source: Path to the JD file (will be copied in).
            preset_name: Preset name included in directory naming.
            url: Optional job posting URL.

        Returns:
            Path to the created application directory.
        """
        ...

    def list_applications(self, workspace_root: Path) -> list[Path]:
        """List all application directories in the workspace.

        Args:
            workspace_root: Workspace root path.

        Returns:
            Sorted list of application directory paths.
        """
        ...
