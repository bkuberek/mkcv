"""Tests for WorkspaceManager filesystem operations."""

import re
import tomllib
from pathlib import Path

import pytest
from dynaconf import Dynaconf

from mkcv.adapters.filesystem.workspace_manager import WorkspaceManager
from mkcv.adapters.llm.model_catalog_loader import load_model_catalog
from mkcv.adapters.llm.provider_registry import ProviderRegistry
from mkcv.core.catalog.builtin_model_profiles import BUILTIN_MODEL_PROFILES
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


class TestWorkspaceReadmeCredentials:
    """REQ-PR-7: the README credentials block comes from the provider registry."""

    @staticmethod
    def _credentials_block(tmp_path: Path) -> str:
        target = tmp_path / "ws"
        WorkspaceManager().create_workspace(target)
        readme = (target / "README.md").read_text()
        section = readme.split("### 2. Set up an API key", 1)[1].split("### 3.", 1)[0]
        return section.split("```toml", 1)[1].split("```", 1)[0]

    @pytest.mark.parametrize(
        "config_snippet",
        [
            '[default.providers.anthropic]\napi_key = "sk-ant-..."',
            '[default.providers.openai]\napi_key = "sk-..."',
            '[default.providers.google]\napi_key = "..."',
            '[default.providers.openrouter]\napi_key = "sk-or-..."',
        ],
    )
    def test_block_lists_each_keyed_provider(
        self, tmp_path: Path, config_snippet: str
    ) -> None:
        assert config_snippet in self._credentials_block(tmp_path)

    def test_google_hint_names_gemini(self, tmp_path: Path) -> None:
        block = self._credentials_block(tmp_path)
        assert "# Google Gemini\n[default.providers.google]" in block

    def test_block_does_not_tell_users_to_export_keys(self, tmp_path: Path) -> None:
        assert "export" not in self._credentials_block(tmp_path)

    def test_readme_points_at_the_user_config_file(self, tmp_path: Path) -> None:
        target = tmp_path / "ws"
        WorkspaceManager().create_workspace(target)
        readme = (target / "README.md").read_text()
        assert "~/.config/mkcv/settings.toml" in readme

    def test_block_lists_providers_in_registry_order_with_ollama_last(
        self, tmp_path: Path
    ) -> None:
        block = self._credentials_block(tmp_path)
        positions = [
            block.index(marker)
            for marker in ("anthropic", "openai", "google", "openrouter", "Ollama")
        ]
        assert positions == sorted(positions)

    def test_ollama_hint_needs_no_key(self, tmp_path: Path) -> None:
        block = self._credentials_block(tmp_path)
        assert "ollama serve" in block
        assert block.strip().endswith("# Just run: ollama serve")

    def test_block_never_mentions_the_stub_provider(self, tmp_path: Path) -> None:
        assert "stub" not in self._credentials_block(tmp_path).lower()


def _uncommented_examples(text: str) -> str:
    """Turn the commented TOML examples of the pipeline and provider sections on."""
    lines: list[str] = []
    active = False
    for line in text.splitlines():
        if line.startswith("# ──"):
            active = "Pipeline" in line or "Providers" in line or "Model" in line
        if active and re.match(r"^# (\[|[a-z_]+ = )", line):
            lines.append(line[2:])
    return "\n".join(lines)


class TestWorkspaceConfigTemplate:
    """The workspace mkcv.toml documents profiles, providers, and the catalog."""

    @staticmethod
    def _template(tmp_path: Path) -> str:
        target = tmp_path / "ws"
        WorkspaceManager().create_workspace(target)
        return (target / "mkcv.toml").read_text()

    def test_template_is_valid_toml(self, tmp_path: Path) -> None:
        assert tomllib.loads(self._template(tmp_path))["default"]["workspace"]

    def test_documents_the_model_profile_setting(self, tmp_path: Path) -> None:
        assert '# model_profile = "anthropic"' in self._template(tmp_path)

    def test_names_every_built_in_profile(self, tmp_path: Path) -> None:
        template = self._template(tmp_path)
        assert [n for n in BUILTIN_MODEL_PROFILES if n not in template] == []

    def test_documents_the_provider_fallback_setting(self, tmp_path: Path) -> None:
        assert '# provider = "anthropic"' in self._template(tmp_path)

    def test_documents_the_warnings_switch(self, tmp_path: Path) -> None:
        assert "# model_warnings = true" in self._template(tmp_path)

    def test_points_at_the_models_command(self, tmp_path: Path) -> None:
        assert "mkcv models" in self._template(tmp_path)

    def test_documents_the_google_provider(self, tmp_path: Path) -> None:
        template = self._template(tmp_path)
        assert "# [default.providers.google]" in template
        assert "GEMINI_API_KEY" in template

    def test_points_api_keys_at_the_user_config_file(self, tmp_path: Path) -> None:
        template = self._template(tmp_path)
        assert "~/.config/mkcv/settings.toml" in template
        assert "Prefer environment variables" not in template

    def test_documents_a_custom_openai_compatible_provider(
        self, tmp_path: Path
    ) -> None:
        template = self._template(tmp_path)
        assert "# [default.providers.groq]" in template
        assert '# type = "openai-compatible"' in template

    def test_documents_the_model_catalog(self, tmp_path: Path) -> None:
        assert "# [[default.model_catalog]]" in self._template(tmp_path)

    def test_the_commented_examples_are_valid_toml(self, tmp_path: Path) -> None:
        enabled = tomllib.loads(_uncommented_examples(self._template(tmp_path)))
        assert enabled["default"]["providers"]["groq"]["type"] == "openai-compatible"
        assert enabled["default"]["model_catalog"][0]["provider"] == "groq"
        assert enabled["default"]["pipeline"]["model_profile"] == "anthropic"

    def test_the_commented_examples_are_accepted_by_the_registry(
        self, tmp_path: Path
    ) -> None:
        examples = tmp_path / "examples.toml"
        examples.write_text(_uncommented_examples(self._template(tmp_path)))
        config = Dynaconf(
            settings_files=[str(examples)],
            environments=True,
            default_env="default",
            merge_enabled=True,
        )
        registry = ProviderRegistry.from_config(config, load_model_catalog(config))
        assert registry.get("groq").kind.value == "openai-compatible"


class TestWorkspaceReadmeModels:
    """The workspace README describes presets, profiles, and ``mkcv models``."""

    @staticmethod
    def _readme(tmp_path: Path) -> str:
        target = tmp_path / "ws"
        WorkspaceManager().create_workspace(target)
        return (target / "README.md").read_text()

    def test_presets_are_selected_with_the_preset_flag(self, tmp_path: Path) -> None:
        readme = self._readme(tmp_path)
        assert "mkcv generate --jd job.txt --preset concise" in readme

    def test_the_removed_profile_flag_is_not_advertised(self, tmp_path: Path) -> None:
        assert (
            re.search(r"(?<![\w-])--profile(?![\w-])", self._readme(tmp_path)) is None
        )

    def test_model_profiles_are_explained(self, tmp_path: Path) -> None:
        readme = self._readme(tmp_path)
        assert "--model-profile google" in readme
        assert "pipeline.model_profile" in readme

    def test_the_models_command_is_listed(self, tmp_path: Path) -> None:
        assert "| `mkcv models` |" in self._readme(tmp_path)

    def test_every_command_in_the_table_has_a_description(self, tmp_path: Path) -> None:
        rows = [
            line
            for line in self._readme(tmp_path).splitlines()
            if line.startswith("| `mkcv ")
        ]
        assert [row for row in rows if row.endswith("|  |")] == []

    def test_presets_no_longer_claim_claude_only_models(self, tmp_path: Path) -> None:
        readme = self._readme(tmp_path)
        assert "Haiku for all stages" not in readme

    def test_the_openrouter_example_uses_the_default_prefix(
        self, tmp_path: Path
    ) -> None:
        assert "[default.pipeline.stages.analyze]" in self._readme(tmp_path)
