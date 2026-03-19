"""Tests for Configuration (dynaconf-based settings)."""

from pathlib import Path

from mkcv.config.configuration import Configuration


class TestConfiguration:
    """Tests for Configuration settings loading."""

    def test_settings_loads_with_defaults(self) -> None:
        config = Configuration()
        assert config.general.verbose is False

    def test_rendering_theme_default(self) -> None:
        config = Configuration()
        assert config.rendering.theme == "sb2nov"

    def test_general_log_level_default(self) -> None:
        config = Configuration()
        assert config.general.log_level == "WARNING"

    def test_pipeline_from_stage_default(self) -> None:
        config = Configuration()
        assert config.pipeline.from_stage == 1

    def test_pipeline_auto_render_default(self) -> None:
        config = Configuration()
        assert config.pipeline.auto_render is True

    def test_pipeline_analyze_stage_has_provider(self) -> None:
        config = Configuration()
        assert config.pipeline.stages.analyze.provider == "anthropic"

    def test_in_workspace_is_false_by_default(self) -> None:
        config = Configuration()
        assert config.in_workspace is False

    def test_workspace_root_is_none_by_default(self) -> None:
        config = Configuration()
        assert config.workspace_root is None

    def test_load_workspace_config_sets_root(self, workspace_dir: Path) -> None:
        config = Configuration()
        config.load_workspace_config(workspace_dir)
        assert config.workspace_root == workspace_dir

    def test_in_workspace_is_true_after_load(self, workspace_dir: Path) -> None:
        config = Configuration()
        config.load_workspace_config(workspace_dir)
        assert config.in_workspace is True


class TestRenderingOverrides:
    """Tests for [rendering.overrides] config section.

    Note: Dynaconf with environments=True and default_env="default"
    requires workspace TOML to use [default.rendering] prefix to merge
    into the correct environment layer.
    """

    def test_rendering_overrides_absent_by_default(self) -> None:
        """Verify no error when overrides section is missing from defaults."""
        config = Configuration()
        # The overrides section is commented out in settings.toml,
        # so accessing it should not raise but may return Box/empty.
        theme = config.rendering.theme
        assert theme == "sb2nov"

    def test_rendering_overrides_loaded_from_workspace(self, tmp_path: Path) -> None:
        """Verify a TOML with [rendering.overrides] section is parsed."""
        ws = tmp_path / "ws-overrides"
        ws.mkdir()
        toml_content = """\
[default.rendering]
theme = "classic"

[default.rendering.overrides]
font = "Charter"
font_size = "11pt"
page_size = "a4paper"
primary_color = "004080"
"""
        (ws / "mkcv.toml").write_text(toml_content)

        config = Configuration()
        config.load_workspace_config(ws)

        assert config.rendering.theme == "classic"
        assert config.rendering.overrides.font == "Charter"
        assert config.rendering.overrides.font_size == "11pt"
        assert config.rendering.overrides.page_size == "a4paper"
        assert config.rendering.overrides.primary_color == "004080"

    def test_rendering_theme_override_from_workspace(self, tmp_path: Path) -> None:
        """Verify workspace mkcv.toml overrides built-in theme default."""
        ws = tmp_path / "ws-theme"
        ws.mkdir()
        toml_content = """\
[default.rendering]
theme = "moderncv"
"""
        (ws / "mkcv.toml").write_text(toml_content)

        config = Configuration()
        config.load_workspace_config(ws)

        assert config.rendering.theme == "moderncv"

    def test_rendering_overrides_partial(self, tmp_path: Path) -> None:
        """Verify partial overrides work — only specified fields are set."""
        ws = tmp_path / "ws-partial"
        ws.mkdir()
        toml_content = """\
[default.rendering.overrides]
primary_color = "FF0000"
"""
        (ws / "mkcv.toml").write_text(toml_content)

        config = Configuration()
        config.load_workspace_config(ws)

        assert config.rendering.overrides.primary_color == "FF0000"
        # Theme should still be the default since we didn't override it
        assert config.rendering.theme == "sb2nov"
