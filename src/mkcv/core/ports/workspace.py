"""Port interface for workspace filesystem operations."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from mkcv.core.models.jd_document import JDDocument


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
        jd_source: Path | str,
        *,
        preset_name: str = "standard",
        url: str | None = None,
        jd_document: JDDocument | None = None,
    ) -> Path:
        """Create an application directory within the workspace.

        Args:
            workspace_root: Workspace root path.
            company: Company name (will be slugified).
            position: Position title (will be slugified).
            jd_source: Path to JD file (copied in) or raw text.
            preset_name: Preset name stored in metadata.
            url: Optional job posting URL.
            jd_document: Optional parsed JD for frontmatter writing.

        Returns:
            Path to the created application directory.
        """
        ...

    def create_output_version(
        self,
        app_dir: Path,
        output_type: str,
    ) -> Path:
        """Create a new versioned output subdirectory.

        Args:
            app_dir: Application directory path.
            output_type: One of ``"resumes"``, ``"cover-letter"``.

        Returns:
            Path to the new version directory.
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

    def resolve_cover_letter_path(self, app_dir: Path) -> Path | None:
        """Find the latest cover letter in an application directory.

        Args:
            app_dir: Path to the application directory.

        Returns:
            Path to cover_letter.md or .pdf if it exists, or None.
        """
        ...
