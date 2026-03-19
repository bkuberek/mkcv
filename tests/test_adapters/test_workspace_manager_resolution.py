"""Tests for WorkspaceManager version resolution methods.

Tests the new find_latest_application, resolve_resume_path,
and find_latest_resume methods.
"""

from pathlib import Path

import tomli_w

from mkcv.adapters.filesystem.workspace_manager import WorkspaceManager


def _create_application_dir(
    workspace: Path,
    company_slug: str,
    dir_name: str,
    *,
    with_resume: bool = False,
) -> Path:
    """Create a mock application directory with application.toml.

    Args:
        workspace: Workspace root.
        company_slug: Company slug (e.g., 'testcorp').
        dir_name: Directory name (e.g., '2025-01-swe-standard-v1').
        with_resume: Whether to also create a resume.yaml.

    Returns:
        Path to the created application directory.
    """
    app_dir = workspace / "applications" / company_slug / dir_name
    app_dir.mkdir(parents=True, exist_ok=True)

    # Write application.toml (required for list_applications to find it)
    toml_data = {
        "application": {
            "company": company_slug,
            "position": "Software Engineer",
            "date": "2025-01-15",
            "status": "draft",
            "url": "",
            "created_at": "2025-01-15T12:00:00+00:00",
        },
    }
    with (app_dir / "application.toml").open("wb") as f:
        tomli_w.dump(toml_data, f)

    if with_resume:
        (app_dir / "resume.yaml").write_text(
            "cv:\n  name: Test User\n", encoding="utf-8"
        )

    return app_dir


# ------------------------------------------------------------------
# find_latest_application
# ------------------------------------------------------------------


class TestFindLatestApplication:
    """Tests for WorkspaceManager.find_latest_application."""

    def test_find_latest_application_multiple_apps(self, workspace_dir: Path) -> None:
        mgr = WorkspaceManager()
        _create_application_dir(workspace_dir, "testcorp", "2025-01-swe-standard-v1")
        _create_application_dir(workspace_dir, "testcorp", "2025-03-swe-standard-v2")

        result = mgr.find_latest_application(workspace_dir)
        assert result is not None
        assert "2025-03" in result.name

    def test_find_latest_application_with_company_filter(
        self, workspace_dir: Path
    ) -> None:
        mgr = WorkspaceManager()
        _create_application_dir(workspace_dir, "alpha-inc", "2025-01-swe-standard-v1")
        _create_application_dir(workspace_dir, "beta-corp", "2025-03-swe-standard-v1")

        result = mgr.find_latest_application(workspace_dir, company="Alpha Inc")
        assert result is not None
        assert result.parent.name == "alpha-inc"

    def test_find_latest_application_company_filter_no_match(
        self, workspace_dir: Path
    ) -> None:
        mgr = WorkspaceManager()
        _create_application_dir(workspace_dir, "alpha-inc", "2025-01-swe-standard-v1")

        result = mgr.find_latest_application(workspace_dir, company="Nonexistent Corp")
        assert result is None

    def test_find_latest_application_no_apps_returns_none(
        self, workspace_dir: Path
    ) -> None:
        mgr = WorkspaceManager()
        result = mgr.find_latest_application(workspace_dir)
        assert result is None

    def test_find_latest_application_returns_last_sorted(
        self, workspace_dir: Path
    ) -> None:
        mgr = WorkspaceManager()
        _create_application_dir(workspace_dir, "testcorp", "2024-06-swe-standard-v1")
        _create_application_dir(workspace_dir, "testcorp", "2025-01-swe-standard-v1")
        _create_application_dir(workspace_dir, "testcorp", "2024-12-swe-standard-v1")

        result = mgr.find_latest_application(workspace_dir)
        assert result is not None
        assert "2025-01" in result.name


# ------------------------------------------------------------------
# resolve_resume_path
# ------------------------------------------------------------------


class TestResolveResumePath:
    """Tests for WorkspaceManager.resolve_resume_path."""

    def test_resolve_resume_path_exists(self, workspace_dir: Path) -> None:
        mgr = WorkspaceManager()
        app_dir = _create_application_dir(
            workspace_dir, "testcorp", "2025-01-swe-v1", with_resume=True
        )

        result = mgr.resolve_resume_path(app_dir)
        assert result is not None
        assert result.name == "resume.yaml"
        assert result.is_file()

    def test_resolve_resume_path_missing_returns_none(
        self, workspace_dir: Path
    ) -> None:
        mgr = WorkspaceManager()
        app_dir = _create_application_dir(
            workspace_dir, "testcorp", "2025-01-swe-v1", with_resume=False
        )

        result = mgr.resolve_resume_path(app_dir)
        assert result is None


# ------------------------------------------------------------------
# find_latest_resume
# ------------------------------------------------------------------


class TestFindLatestResume:
    """Tests for WorkspaceManager.find_latest_resume."""

    def test_find_latest_resume_in_resumes_dir(self, workspace_dir: Path) -> None:
        mgr = WorkspaceManager()

        resumes_dir = workspace_dir / "resumes"
        resumes_dir.mkdir(exist_ok=True)

        # Create two versioned resume directories
        dir1 = resumes_dir / "2025-01-general"
        dir1.mkdir()
        (dir1 / "resume.yaml").write_text("cv:\n  name: Old\n", encoding="utf-8")

        dir2 = resumes_dir / "2025-03-general"
        dir2.mkdir()
        (dir2 / "resume.yaml").write_text("cv:\n  name: New\n", encoding="utf-8")

        result = mgr.find_latest_resume(workspace_dir)
        assert result is not None
        assert "2025-03" in str(result)

    def test_find_latest_resume_empty_returns_none(self, workspace_dir: Path) -> None:
        mgr = WorkspaceManager()

        resumes_dir = workspace_dir / "resumes"
        resumes_dir.mkdir(exist_ok=True)

        result = mgr.find_latest_resume(workspace_dir)
        assert result is None

    def test_find_latest_resume_no_resumes_dir_returns_none(
        self, workspace_dir: Path
    ) -> None:
        mgr = WorkspaceManager()
        result = mgr.find_latest_resume(workspace_dir)
        assert result is None

    def test_find_latest_resume_skips_dirs_without_yaml(
        self, workspace_dir: Path
    ) -> None:
        mgr = WorkspaceManager()

        resumes_dir = workspace_dir / "resumes"
        resumes_dir.mkdir(exist_ok=True)

        # Dir with resume.yaml
        dir1 = resumes_dir / "2025-01-general"
        dir1.mkdir()
        (dir1 / "resume.yaml").write_text("cv:\n  name: Test\n", encoding="utf-8")

        # Dir without resume.yaml (should be skipped)
        dir2 = resumes_dir / "2025-03-empty"
        dir2.mkdir()

        result = mgr.find_latest_resume(workspace_dir)
        assert result is not None
        assert "2025-01" in str(result)
