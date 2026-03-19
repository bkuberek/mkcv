"""Workspace management service."""

from pathlib import Path

from mkcv.core.models.jd_document import JDDocument
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

    def update_readme(self, workspace_root: Path) -> bool:
        """Regenerate the workspace README.md with the latest mkcv content.

        Args:
            workspace_root: Path to the workspace root.

        Returns:
            True if the README was updated, False if already current.
        """
        return self._workspace.update_readme(workspace_root)

    def setup_application(
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
            workspace_root: Path to workspace root.
            company: Company name (will be slugified).
            position: Position title (will be slugified).
            jd_source: Path to JD file (copied in) or raw text.
            preset_name: Preset name stored in metadata.
            url: Optional job posting URL.
            jd_document: Optional parsed JD for frontmatter writing.

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
            jd_document=jd_document,
        )

    def list_applications(self, workspace_root: Path) -> list[Path]:
        """List all application directories in the workspace.

        Args:
            workspace_root: Workspace root path.

        Returns:
            Sorted list of application directory paths.
        """
        return self._workspace.list_applications(workspace_root)

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
        return self._workspace.find_latest_application(workspace_root, company=company)

    def resolve_resume_path(self, app_dir: Path) -> Path | None:
        """Find resume.yaml within an application directory.

        Args:
            app_dir: Path to the application directory.

        Returns:
            Path to resume.yaml if it exists, or None.
        """
        return self._workspace.resolve_resume_path(app_dir)

    def resolve_cover_letter_path(self, app_dir: Path) -> Path | None:
        """Find the latest cover letter in an application directory.

        Args:
            app_dir: Path to the application directory.

        Returns:
            Path to cover_letter.md or .pdf if it exists, or None.
        """
        return self._workspace.resolve_cover_letter_path(app_dir)

    def create_output_version(self, app_dir: Path, output_type: str) -> Path:
        """Create a new versioned output subdirectory.

        Args:
            app_dir: Application directory path.
            output_type: One of ``"resumes"``, ``"cover-letter"``.

        Returns:
            Path to the new version directory.
        """
        return self._workspace.create_output_version(app_dir, output_type)
