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

    def update_readme(self, workspace_root: Path) -> bool:
        """Regenerate the workspace README.md with the latest mkcv content.

        Args:
            workspace_root: Path to the workspace root.

        Returns:
            True if the README was updated, False if already current.
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

    def find_latest_application(
        self,
        workspace_root: Path,
        *,
        company: str | None = None,
    ) -> Path | None:
        """Find the most recent application directory.

        Scans application directories sorted lexicographically (which
        produces chronological order due to the YYYY-MM prefix) and
        returns the last entry. Only considers directories containing
        an ``application.toml`` file.

        Args:
            workspace_root: Workspace root path.
            company: Optional company name filter (will be slugified).

        Returns:
            Path to the latest application directory, or None.
        """
        ...

    def resolve_resume_path(self, app_dir: Path) -> Path | None:
        """Find resume.yaml within an application directory.

        Args:
            app_dir: Path to the application directory.

        Returns:
            Path to resume.yaml if it exists, or None.
        """
        ...
