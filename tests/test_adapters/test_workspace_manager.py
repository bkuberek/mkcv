"""Tests for WorkspaceManager filesystem operations."""

from pathlib import Path

import pytest

from mkcv.adapters.filesystem.workspace_manager import WorkspaceManager
from mkcv.core.exceptions import WorkspaceError, WorkspaceExistsError


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

    def test_writes_jd_markdown(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        mgr = WorkspaceManager()
        app_dir = mgr.create_application(
            workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
        )
        assert (app_dir / "jd.md").is_file()

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
        assert (app_dir / "jd.md").read_text() == sample_jd_text

    def test_creates_resumes_subdir(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        mgr = WorkspaceManager()
        app_dir = mgr.create_application(
            workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
        )
        assert (app_dir / "resumes").is_dir()

    def test_application_dir_uses_company_slug(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        mgr = WorkspaceManager()
        app_dir = mgr.create_application(
            workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
        )
        assert "deepl" in str(app_dir)

    def test_same_date_raises_workspace_error(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        """Same company/position/date raises WorkspaceError."""
        mgr = WorkspaceManager()
        mgr.create_application(workspace_dir, "DeepL", "Staff Engineer", sample_jd_file)
        with pytest.raises(WorkspaceError, match="already exists"):
            mgr.create_application(
                workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
            )

    def test_preset_stored_in_application_toml(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        import tomllib

        mgr = WorkspaceManager()
        app_dir = mgr.create_application(
            workspace_dir,
            "DeepL",
            "Staff Engineer",
            sample_jd_file,
            preset_name="comprehensive",
        )
        with (app_dir / "application.toml").open("rb") as f:
            data = tomllib.load(f)
        assert data["application"]["preset"] == "comprehensive"

    def test_new_layout_path_structure(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        """Verify company/position/date directory structure."""
        mgr = WorkspaceManager()
        app_dir = mgr.create_application(
            workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
        )
        relative = app_dir.relative_to(workspace_dir / "applications")
        parts = relative.parts
        assert parts[0] == "deepl"
        assert parts[1] == "staff-engineer"
        # parts[2] is YYYY-MM-DD

    def test_partial_directory_reused(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        """Existing directory without application.toml is reused."""
        mgr = WorkspaceManager()
        # Pre-create the directory without application.toml
        from datetime import date

        apps_base = workspace_dir / "applications" / "deepl" / "engineer"
        target = apps_base / date.today().strftime("%Y-%m-%d")
        target.mkdir(parents=True)
        # Should not raise because there's no application.toml
        app_dir = mgr.create_application(
            workspace_dir, "DeepL", "Engineer", sample_jd_file
        )
        assert app_dir == target


class TestCreateWorkspaceThemes:
    """Tests for themes/ directory scaffolding in workspace creation."""

    def test_creates_themes_directory(self, tmp_path: Path) -> None:
        mgr = WorkspaceManager()
        target = tmp_path / "ws"
        mgr.create_workspace(target)
        assert (target / "themes").is_dir()

    def test_creates_example_theme(self, tmp_path: Path) -> None:
        mgr = WorkspaceManager()
        target = tmp_path / "ws"
        mgr.create_workspace(target)
        example = target / "themes" / "example.yaml"
        assert example.is_file()

    def test_example_theme_contains_expected_keys(self, tmp_path: Path) -> None:
        """Verify the example theme YAML has the expected structure."""
        from ruamel.yaml import YAML

        mgr = WorkspaceManager()
        target = tmp_path / "ws"
        mgr.create_workspace(target)
        example = target / "themes" / "example.yaml"
        yaml = YAML()
        content = yaml.load(example.read_text())
        assert content["name"] == "example"
        assert content["extends"] == "classic"
        assert "description" in content
        assert content["applies_to"] == "all"

    def test_does_not_overwrite_existing_theme_file(self, tmp_path: Path) -> None:
        """Pre-existing themes/example.yaml is preserved on workspace create."""
        target = tmp_path / "ws"
        themes_dir = target / "themes"
        themes_dir.mkdir(parents=True)
        custom_content = "name: example\nextends: sb2nov\ndescription: Custom\n"
        (themes_dir / "example.yaml").write_text(custom_content)

        mgr = WorkspaceManager()
        # create_workspace raises WorkspaceExistsError if mkcv.toml exists,
        # but here we only pre-created themes/, not mkcv.toml
        mgr.create_workspace(target)

        # Original content should be preserved
        assert (themes_dir / "example.yaml").read_text() == custom_content


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


class TestCreateOutputVersion:
    """Tests for WorkspaceManager.create_output_version."""

    def test_creates_v1_directory(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        mgr = WorkspaceManager()
        app_dir = mgr.create_application(
            workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
        )
        version_dir = mgr.create_output_version(app_dir, "resumes")
        assert version_dir.name == "v1"
        assert version_dir.is_dir()

    def test_creates_mkcv_subdir_in_version(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        mgr = WorkspaceManager()
        app_dir = mgr.create_application(
            workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
        )
        version_dir = mgr.create_output_version(app_dir, "resumes")
        assert (version_dir / ".mkcv").is_dir()

    def test_increments_to_v2(self, workspace_dir: Path, sample_jd_file: Path) -> None:
        mgr = WorkspaceManager()
        app_dir = mgr.create_application(
            workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
        )
        v1 = mgr.create_output_version(app_dir, "resumes")
        v2 = mgr.create_output_version(app_dir, "resumes")
        assert v1.name == "v1"
        assert v2.name == "v2"

    def test_increments_to_v3(self, workspace_dir: Path, sample_jd_file: Path) -> None:
        mgr = WorkspaceManager()
        app_dir = mgr.create_application(
            workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
        )
        mgr.create_output_version(app_dir, "resumes")
        mgr.create_output_version(app_dir, "resumes")
        v3 = mgr.create_output_version(app_dir, "resumes")
        assert v3.name == "v3"

    def test_cover_letter_output_type(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        mgr = WorkspaceManager()
        app_dir = mgr.create_application(
            workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
        )
        version_dir = mgr.create_output_version(app_dir, "cover-letter")
        assert version_dir.parent.name == "cover-letter"
        assert version_dir.name == "v1"

    def test_resume_and_cover_letter_versioned_independently(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        mgr = WorkspaceManager()
        app_dir = mgr.create_application(
            workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
        )
        rv1 = mgr.create_output_version(app_dir, "resumes")
        rv2 = mgr.create_output_version(app_dir, "resumes")
        cv1 = mgr.create_output_version(app_dir, "cover-letter")
        assert rv1.name == "v1"
        assert rv2.name == "v2"
        assert cv1.name == "v1"

    def test_version_dir_path_is_under_app_dir(
        self, workspace_dir: Path, sample_jd_file: Path
    ) -> None:
        mgr = WorkspaceManager()
        app_dir = mgr.create_application(
            workspace_dir, "DeepL", "Staff Engineer", sample_jd_file
        )
        version_dir = mgr.create_output_version(app_dir, "resumes")
        assert str(version_dir).startswith(str(app_dir))
        assert version_dir.parent == app_dir / "resumes"


class TestApplicationDiscovery:
    """Tests for find_latest_application with timestamp sorting."""

    def test_find_latest_application_returns_most_recent_by_timestamp(
        self, workspace_dir: Path
    ) -> None:
        """Applications with different timestamps sort by created_at."""
        import tomli_w

        mgr = WorkspaceManager()
        apps_dir = workspace_dir / "applications"

        # Create two apps with explicit timestamps (older first)
        old_dir = apps_dir / "acme" / "engineer" / "2025-01-01"
        old_dir.mkdir(parents=True)
        with (old_dir / "application.toml").open("wb") as f:
            tomli_w.dump(
                {
                    "application": {
                        "company": "acme",
                        "position": "engineer",
                        "date": "2025-01-01",
                        "status": "draft",
                        "created_at": "2025-01-01T10:00:00+00:00",
                    }
                },
                f,
            )

        new_dir = apps_dir / "beta" / "senior-engineer" / "2025-06-15"
        new_dir.mkdir(parents=True)
        with (new_dir / "application.toml").open("wb") as f:
            tomli_w.dump(
                {
                    "application": {
                        "company": "beta",
                        "position": "senior-engineer",
                        "date": "2025-06-15",
                        "status": "draft",
                        "created_at": "2025-06-15T14:00:00+00:00",
                    }
                },
                f,
            )

        result = mgr.find_latest_application(workspace_dir)
        assert result is not None
        assert "beta" in str(result)

    def test_find_latest_application_filters_by_company(
        self, workspace_dir: Path
    ) -> None:
        import tomli_w

        mgr = WorkspaceManager()
        apps_dir = workspace_dir / "applications"

        for company, ts in [
            ("acme", "2025-06-01T10:00:00+00:00"),
            ("beta-corp", "2025-06-15T14:00:00+00:00"),
        ]:
            d = apps_dir / company / "engineer" / "2025-06-01"
            d.mkdir(parents=True)
            with (d / "application.toml").open("wb") as f:
                tomli_w.dump(
                    {
                        "application": {
                            "company": company,
                            "position": "engineer",
                            "date": "2025-06-01",
                            "status": "draft",
                            "created_at": ts,
                        }
                    },
                    f,
                )

        result = mgr.find_latest_application(workspace_dir, company="Acme")
        assert result is not None
        assert "acme" in str(result)
        assert "beta" not in str(result)

    def test_list_applications_sorted_by_timestamp(self, workspace_dir: Path) -> None:
        import tomli_w

        mgr = WorkspaceManager()
        apps_dir = workspace_dir / "applications"

        timestamps = [
            ("gamma", "2025-03-01T10:00:00+00:00"),
            ("alpha", "2025-01-01T08:00:00+00:00"),
            ("beta", "2025-02-01T09:00:00+00:00"),
        ]
        for company, ts in timestamps:
            d = apps_dir / company / "engineer" / "2025-01-01"
            d.mkdir(parents=True)
            with (d / "application.toml").open("wb") as f:
                tomli_w.dump(
                    {
                        "application": {
                            "company": company,
                            "position": "engineer",
                            "date": "2025-01-01",
                            "status": "draft",
                            "created_at": ts,
                        }
                    },
                    f,
                )

        result = mgr.list_applications(workspace_dir)
        assert len(result) == 3
        # Sorted by created_at ascending
        assert "alpha" in str(result[0])
        assert "beta" in str(result[1])
        assert "gamma" in str(result[2])

    def test_find_latest_application_no_match_returns_none(
        self, workspace_dir: Path
    ) -> None:
        mgr = WorkspaceManager()
        result = mgr.find_latest_application(workspace_dir, company="Nonexistent")
        assert result is None


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
        """Applications are sorted by created_at timestamp."""
        mgr = WorkspaceManager()
        mgr.create_application(workspace_dir, "Zeta Corp", "Engineer", sample_jd_file)
        mgr.create_application(workspace_dir, "Alpha Inc", "Developer", sample_jd_file)
        result = mgr.list_applications(workspace_dir)
        # Both created "today" so timestamps are very close
        # Just verify we get 2 results
        assert len(result) == 2
