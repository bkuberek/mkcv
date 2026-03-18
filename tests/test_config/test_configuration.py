"""Tests for Configuration (dynaconf-based settings)."""

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

    def test_load_workspace_config_sets_root(self, workspace_dir) -> None:
        config = Configuration()
        config.load_workspace_config(workspace_dir)
        assert config.workspace_root == workspace_dir

    def test_in_workspace_is_true_after_load(self, workspace_dir) -> None:
        config = Configuration()
        config.load_workspace_config(workspace_dir)
        assert config.in_workspace is True
