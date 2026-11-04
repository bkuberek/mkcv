"""Tests for loading user catalog overrides from configuration (REQ-CAT-6)."""

from pathlib import Path

import pytest
from dynaconf import Dynaconf

from mkcv.adapters.llm.model_catalog_loader import load_model_catalog
from mkcv.core.exceptions.configuration import ConfigurationError
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.model_tier import ModelTier


def _config(tmp_path: Path, *layers: str) -> Dynaconf:
    """Build a real Dynaconf from TOML layers, later layers overriding earlier."""
    paths: list[str] = []
    for index, text in enumerate(layers):
        path = tmp_path / f"layer{index}.toml"
        path.write_text(text)
        paths.append(str(path))
    return Dynaconf(
        settings_files=paths,
        environments=True,
        default_env="default",
        merge_enabled=True,
    )


class TestNoOverrides:
    def test_empty_config_returns_the_builtin_entries(self, tmp_path: Path) -> None:
        catalog = load_model_catalog(_config(tmp_path, "[default]\n"))
        assert catalog.entries == ModelCatalog.builtin().entries

    def test_config_with_no_layers_returns_the_builtin_entries(
        self, tmp_path: Path
    ) -> None:
        catalog = load_model_catalog(_config(tmp_path))
        assert catalog.entries == ModelCatalog.builtin().entries

    def test_empty_array_returns_the_builtin_entries(self, tmp_path: Path) -> None:
        catalog = load_model_catalog(
            _config(tmp_path, "[default]\nmodel_catalog = []\n")
        )
        assert catalog.entries == ModelCatalog.builtin().entries


class TestOverlayOfExistingEntries:
    CONFIG = """
[[default.model_catalog]]
provider = "openai"
match = "gpt-6.1-sol"
input_price_per_mtok = 1.8
"""

    def test_override_replaces_only_the_field_it_sets(self, tmp_path: Path) -> None:
        catalog = load_model_catalog(_config(tmp_path, self.CONFIG))
        found = catalog.lookup("openai", "gpt-6.1-sol")
        assert found is not None
        assert (
            found.input_price_per_mtok,
            found.output_price_per_mtok,
            found.tier,
        ) == (1.8, 10.0, ModelTier.STRONG)

    def test_override_does_not_add_an_entry(self, tmp_path: Path) -> None:
        catalog = load_model_catalog(_config(tmp_path, self.CONFIG))
        assert len(catalog.entries) == len(ModelCatalog.builtin().entries)

    def test_builtin_catalog_is_not_modified(self, tmp_path: Path) -> None:
        load_model_catalog(_config(tmp_path, self.CONFIG))
        found = ModelCatalog.builtin().lookup("openai", "gpt-6.1-sol")
        assert found is not None
        assert found.input_price_per_mtok == 2.0


class TestNewEntries:
    CONFIG = """
[[default.model_catalog]]
provider = "groq"
match = "llama-3.3-70b-versatile"
tier = "efficient"
structured_output = "json_object"
input_price_per_mtok = 0.59
output_price_per_mtok = 0.79
"""

    def test_new_entry_is_found(self, tmp_path: Path) -> None:
        catalog = load_model_catalog(_config(tmp_path, self.CONFIG))
        found = catalog.lookup("groq", "llama-3.3-70b-versatile")
        assert found is not None
        assert found.tier is ModelTier.EFFICIENT

    def test_new_entry_is_priced(self, tmp_path: Path) -> None:
        catalog = load_model_catalog(_config(tmp_path, self.CONFIG))
        price = catalog.price_for("llama-3.3-70b-versatile", provider="groq")
        assert price == (0.59, 0.79)

    def test_match_type_prefix_is_honoured(self, tmp_path: Path) -> None:
        config = """
[[default.model_catalog]]
provider = "groq"
match = "llama-"
match_type = "prefix"
tier = "minimal"
"""
        catalog = load_model_catalog(_config(tmp_path, config))
        assert catalog.lookup("groq", "llama-3.3-70b-versatile") is not None

    def test_dotted_model_ids_need_no_quoting(self, tmp_path: Path) -> None:
        config = """
[[default.model_catalog]]
provider = "ollama"
match = "qwen2.5:7b"
tier = "efficient"
"""
        catalog = load_model_catalog(_config(tmp_path, config))
        assert catalog.lookup("ollama", "qwen2.5:7b") is not None


class TestLayerPrecedence:
    GLOBAL = """
[[default.model_catalog]]
provider = "groq"
match = "m"
tier = "minimal"
notes = "from global"
"""
    WORKSPACE = """
[[default.model_catalog]]
provider = "groq"
match = "m"
tier = "strong"
"""

    def test_workspace_entry_wins_over_global_entry(self, tmp_path: Path) -> None:
        catalog = load_model_catalog(_config(tmp_path, self.GLOBAL, self.WORKSPACE))
        found = catalog.lookup("groq", "m")
        assert found is not None
        assert found.tier is ModelTier.STRONG

    def test_global_fields_the_workspace_leaves_unset_are_kept(
        self, tmp_path: Path
    ) -> None:
        catalog = load_model_catalog(_config(tmp_path, self.GLOBAL, self.WORKSPACE))
        found = catalog.lookup("groq", "m")
        assert found is not None
        assert found.notes == "from global"

    def test_workspace_loaded_after_startup_also_wins(self, tmp_path: Path) -> None:
        """Mirrors ``Configuration.load_workspace_config`` (``load_file``)."""
        config = _config(tmp_path, self.GLOBAL)
        workspace = tmp_path / "mkcv.toml"
        workspace.write_text(self.WORKSPACE)
        config.load_file(path=str(workspace))

        found = load_model_catalog(config).lookup("groq", "m")
        assert found is not None
        assert found.tier is ModelTier.STRONG


class TestInvalidConfiguration:
    def test_invalid_tier_names_the_entry_number(self, tmp_path: Path) -> None:
        config = """
[[default.model_catalog]]
provider = "groq"
match = "m"
tier = "great"
"""
        with pytest.raises(
            ConfigurationError, match=r"Invalid \[\[default\.model_catalog\]\] entry #1"
        ):
            load_model_catalog(_config(tmp_path, config))

    def test_entry_numbers_are_one_based_and_count_valid_entries(
        self, tmp_path: Path
    ) -> None:
        config = """
[[default.model_catalog]]
provider = "groq"
match = "ok"

[[default.model_catalog]]
provider = "groq"
match = "bad"
tier = "great"
"""
        with pytest.raises(ConfigurationError, match="entry #2"):
            load_model_catalog(_config(tmp_path, config))

    def test_error_includes_the_validation_detail(self, tmp_path: Path) -> None:
        config = """
[[default.model_catalog]]
provider = "groq"
match = "m"
tier = "great"
"""
        with pytest.raises(ConfigurationError, match="tier"):
            load_model_catalog(_config(tmp_path, config))

    def test_non_list_catalog_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="must be an array of tables"):
            load_model_catalog(_config(tmp_path, '[default]\nmodel_catalog = "x"\n'))

    def test_single_table_instead_of_array_is_rejected(self, tmp_path: Path) -> None:
        config = """
[default.model_catalog]
provider = "groq"
match = "m"
"""
        with pytest.raises(ConfigurationError, match="must be an array of tables"):
            load_model_catalog(_config(tmp_path, config))

    def test_unknown_field_is_rejected(self, tmp_path: Path) -> None:
        config = """
[[default.model_catalog]]
provider = "groq"
match = "m"
colour = "red"
"""
        with pytest.raises(ConfigurationError, match="colour"):
            load_model_catalog(_config(tmp_path, config))

    def test_missing_match_is_rejected(self, tmp_path: Path) -> None:
        config = """
[[default.model_catalog]]
provider = "groq"
tier = "strong"
"""
        with pytest.raises(ConfigurationError, match="match"):
            load_model_catalog(_config(tmp_path, config))

    def test_non_table_entry_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="entry #1"):
            load_model_catalog(_config(tmp_path, '[default]\nmodel_catalog = ["x"]\n'))

    def test_error_is_a_configuration_error_with_exit_code_three(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ConfigurationError) as caught:
            load_model_catalog(_config(tmp_path, '[default]\nmodel_catalog = "x"\n'))
        assert caught.value.exit_code == 3
