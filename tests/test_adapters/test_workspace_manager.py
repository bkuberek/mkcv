"""Tests for WorkspaceManager filesystem operations."""

from pathlib import Path

import pytest

from mkcv.adapters.filesystem.workspace_manager import WorkspaceManager
from mkcv.core.exceptions import WorkspaceExistsError


class TestCreateWorkspace:
    """Tests for WorkspaceManager.create_workspace."""

    def test_creates_mkcv_toml(self, tmp_path: Path) -> None:
        mgr = WorkspaceManager()
        target = tmp_path / "ws"
        mgr.create_workspace(target)
        assert (target / "mkcv.toml").is_file()

    def test_creates_knowledge_base_dir(self, tmp_path: Path) -> None:
        mgr = WorkspaceManager()
        target = tmp_path / "ws"
        mgr.create_workspace(target)
        assert (target / "knowledge-base").is_dir()

    def test_creates_career_md(self, tmp_path: Path) -> None:
        mgr = WorkspaceManager()
        target = tmp_path / "ws"
        mgr.create_workspace(target)
        assert (target / "knowledge-base" / "career.md").is_file()

    def test_creates_voice_md(self, tmp_path: Path) -> None:
        mgr = WorkspaceManager()
        target = tmp_path / "ws"
        mgr.create_workspace(target)
        assert (target / "knowledge-base" / "voice.md").is_file()

    def test_creates_applications_dir(self, tmp_path: Path) -> None:
        mgr = WorkspaceManager()
        target = tmp_path / "ws"
        mgr.create_workspace(target)
        assert (target / "applications").is_dir()

    def test_creates_templates_dir(self, tmp_path: Path) -> None:
        mgr = WorkspaceManager()
        target = tmp_path / "ws"
        mgr.create_workspace(target)
        assert (target / "templates").is_dir()

    def test_creates_gitignore(self, tmp_path: Path) -> None:
        mgr = WorkspaceManager()
        target = tmp_path / "ws"
        mgr.create_workspace(target)
        assert (target / ".gitignore").is_file()

    def test_raises_workspace_exists_error_if_exists(self, tmp_path: Path) -> None:
        mgr = WorkspaceManager()
        target = tmp_path / "ws"
        mgr.create_workspace(target)
        with pytest.raises(WorkspaceExistsError):
            mgr.create_workspace(target)

    def test_returns_workspace_root_path(self, tmp_path: Path) -> None:
        mgr = WorkspaceManager()
        target = tmp_path / "ws"
        result = mgr.create_workspace(target)
        assert result == target.resolve()


class TestCreateApplication:
    """Tests for WorkspaceManager.create_application."""

    def test_creates_application_directory(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        mgr = WorkspaceManager()
        app_dir = mgr.create_application(
            workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
        )
        assert app_dir.is_dir()

    def test_creates_application_toml(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        mgr = WorkspaceManager()
        app_dir = mgr.create_application(
            workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
        )
        assert (app_dir / "application.toml").is_file()

    def test_copies_jd_file(self, workspace_dir: Path, sample_jd_file: Path) -> None:
        mgr = WorkspaceManager()
        app_dir = mgr.create_application(
            workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
        )
        assert (app_dir / "jd.txt").is_file()

    def test_jd_file_content_matches_source(
        self,
        workspace_dir: Path,
        sample_jd_file: Path,
        sample_jd_text: str,
    ) -> None:
        mgr = WorkspaceManager()
        app_dir = mgr.create_application(
            workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
        )
        assert (app_dir / "jd.txt").read_text() == sample_jd_text

    def test_creates_mkcv_subdir(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        mgr = WorkspaceManager()
        app_dir = mgr.create_application(
            workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
        )
        assert (app_dir / ".mkcv").is_dir()

    def test_application_dir_uses_company_slug(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        mgr = WorkspaceManager()
        app_dir = mgr.create_application(
            workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
        )
        assert "deepl" in str(app_dir)

    def test_handles_name_collisions_with_versioning(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        mgr = WorkspaceManager()
        app_dir_1 = mgr.create_application(
            workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
        )
        app_dir_2 = mgr.create_application(
            workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
        )
        assert app_dir_1 != app_dir_2
        assert app_dir_2.is_dir()
        assert "-v1" in app_dir_1.name
        assert "-v2" in app_dir_2.name

    def test_preset_name_in_directory_name(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        mgr = WorkspaceManager()
        app_dir = mgr.create_application(
            workspace_dir,
            "DeepL",
            "Staff Engineer",
            sample_jd_file,
            preset_name="comprehensive",
        )
        assert "comprehensive" in app_dir.name

    def test_different_presets_get_separate_versioning(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        mgr = WorkspaceManager()
        app_dir_1 = mgr.create_application(
            workspace_dir,
            "DeepL",
            "Staff Engineer",
            sample_jd_file,
            preset_name="standard",
        )
        app_dir_2 = mgr.create_application(
            workspace_dir,
            "DeepL",
            "Staff Engineer",
            sample_jd_file,
            preset_name="comprehensive",
        )
        assert "-standard-v1" in app_dir_1.name
        assert "-comprehensive-v1" in app_dir_2.name

    def test_version_increments_correctly(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        mgr = WorkspaceManager()
        dirs = []
        for _ in range(3):
            d = mgr.create_application(
                workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
            )
            dirs.append(d)
        assert "-v1" in dirs[0].name
        assert "-v2" in dirs[1].name
        assert "-v3" in dirs[2].name


class TestSlugify:
    """Tests for WorkspaceManager.slugify."""

    def test_converts_to_lowercase(self) -> None:
        mgr = WorkspaceManager()
        assert mgr.slugify("DeepL") == "deepl"

    def test_replaces_spaces_with_hyphens(self) -> None:
        mgr = WorkspaceManager()
        assert mgr.slugify("Staff Engineer") == "staff-engineer"

    def test_removes_special_characters(self) -> None:
        mgr = WorkspaceManager()
        result = mgr.slugify("DeepL (GmbH)")
        assert "(" not in result
        assert ")" not in result

    def test_collapses_consecutive_hyphens(self) -> None:
        mgr = WorkspaceManager()
        result = mgr.slugify("Foo - - Bar")
        assert "--" not in result

    def test_strips_leading_trailing_hyphens(self) -> None:
        mgr = WorkspaceManager()
        result = mgr.slugify(" --hello-- ")
        assert not result.startswith("-")
        assert not result.endswith("-")

    def test_handles_unicode(self) -> None:
        mgr = WorkspaceManager()
        result = mgr.slugify("Muller Buro")
        assert result == "muller-buro"

    def test_empty_special_chars_only(self) -> None:
        mgr = WorkspaceManager()
        result = mgr.slugify("!!!")
        assert result == ""


class TestListApplications:
    """Tests for WorkspaceManager.list_applications."""

    def test_returns_empty_list_when_no_applications(self, workspace_dir: Path) -> None:
        mgr = WorkspaceManager()
        result = mgr.list_applications(workspace_dir)
        assert result == []

    def test_returns_application_dirs(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        mgr = WorkspaceManager()
        mgr.create_application(workspace_dir, "DeepL", "Staff Engineer", sample_jd_file)
        result = mgr.list_applications(workspace_dir)
        assert len(result) == 1

    def test_returns_sorted_list(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        mgr = WorkspaceManager()
        mgr.create_application(workspace_dir, "Zeta Corp", "Engineer", sample_jd_file)
        mgr.create_application(workspace_dir, "Alpha Inc", "Developer", sample_jd_file)
        result = mgr.list_applications(workspace_dir)
        assert result == sorted(result)
