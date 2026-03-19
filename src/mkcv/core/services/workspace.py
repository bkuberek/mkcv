"""Workspace management service."""

from pathlib import Path

from mkcv.core.ports.workspace import WorkspacePort


class WorkspaceService:
    """Manages workspace initialization and application directory creation.

    Delegates filesystem operations to a WorkspacePort adapter.
    """

    def __init__(self, workspace: WorkspacePort) -> None:
        self._workspace = workspace

    def init_workspace(self, path: Path) -> Path:
        """Initialize a new mkcv workspace at the given path.

        Creates the workspace directory structure:
            - mkcv.toml (workspace config)
            - knowledge-base/ (KB directory with starter template)
            - applications/ (empty applications directory)
            - .gitignore

        Args:
            path: Directory to initialize as a workspace.

        Returns:
            Path to the workspace root.

        Raises:
            WorkspaceExistsError: If path already contains mkcv.toml.
        """
        return self._workspace.create_workspace(path)

    def setup_application(
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

        Creates: applications/{company}/{YYYY-MM-position-preset-vN}/
        With: application.toml, jd.txt (copied), .mkcv/

        Args:
            workspace_root: Path to workspace root.
            company: Company name (will be slugified).
            position: Position title (will be slugified).
            jd_source: Path to job description file (will be copied).
            preset_name: Preset name included in directory naming.
            url: Optional job posting URL.

        Returns:
            Path to the created application directory.
        """
        return self._workspace.create_application(
            workspace_root=workspace_root,
            company=company,
            position=position,
            jd_source=jd_source,
            preset_name=preset_name,
            url=url,
        )

    def list_applications(self, workspace_root: Path) -> list[Path]:
        """List all application directories in the workspace.

        Args:
            workspace_root: Workspace root path.

        Returns:
            Sorted list of application directory paths.
        """
        return self._workspace.list_applications(workspace_root)
