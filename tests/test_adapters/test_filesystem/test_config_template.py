"""Tests for the one config template behind the user and workspace files."""

import logging
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest
from dynaconf import Dynaconf

from mkcv import __version__
from mkcv.adapters.filesystem.config_scope import ConfigScope
from mkcv.adapters.filesystem.config_template import render_config_template
from mkcv.adapters.llm.builtin_providers import BUILTIN_PROVIDERS
from mkcv.adapters.llm.model_catalog_loader import load_model_catalog
from mkcv.adapters.llm.provider_registry import ProviderRegistry
from mkcv.config.configuration import Configuration
from mkcv.core.catalog.builtin_model_profiles import BUILTIN_MODEL_PROFILES

KEYED_PROVIDERS = ("anthropic", "openai", "google", "openrouter")
BOTH_SCOPES = [ConfigScope.USER, ConfigScope.WORKSPACE]
WORKSPACE_ONLY_SECTIONS = {"workspace", "paths", "naming", "defaults"}

_SECTION = re.compile(r"^#? ?\[{1,2}(?P<name>[\w.]+)\]{1,2}")
_KEY = re.compile(r"^#? ?(?P<key>[a-z_]+) = ")
_COMMENTED_TOML = re.compile(r"^# (\[|[a-z_]+ = )")


def _render(scope: ConfigScope) -> str:
    return render_config_template(scope, version=__version__)


def _option_keys(text: str) -> set[tuple[str, str]]:
    """Every (section, key) the text documents, commented or not."""
    section = ""
    found: set[tuple[str, str]] = set()
    for line in text.splitlines():
        if match := _SECTION.match(line):
            section = match.group("name")
            found.add((section, ""))
        elif section and (match := _KEY.match(line)):
            found.add((section, match.group("key")))
    return found


def _uncomment_everything(text: str) -> str:
    return "\n".join(
        line[2:] if _COMMENTED_TOML.match(line) else line for line in text.splitlines()
    )


def _flatten(node: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(node, dict):
        return {prefix: node}
    flat: dict[str, Any] = {}
    for key, value in node.items():
        flat.update(_flatten(value, f"{prefix}.{str(key).lower()}".lstrip(".")))
    return flat


def _settings(config: Dynaconf) -> dict[str, Any]:
    """Resolved settings, without runtime attributes and the providers table.

    A developer checkout may carry a git-ignored ``.secrets.toml`` that fills
    ``providers``; the providers table is asserted on separately.
    """
    return {
        key: value
        for key, value in _flatten(config.as_dict()).items()
        if not key.startswith(("_", "providers"))
    }


def _dynaconf(path: Path) -> Dynaconf:
    return Dynaconf(
        settings_files=[str(path)],
        environments=True,
        default_env="default",
        merge_enabled=True,
    )


@pytest.mark.parametrize("scope", BOTH_SCOPES)
class TestBothFiles:
    def test_is_valid_toml(self, scope: ConfigScope) -> None:
        assert tomllib.loads(_render(scope))

    def test_every_built_in_profile_is_named(self, scope: ConfigScope) -> None:
        template = _render(scope)
        assert [n for n in BUILTIN_MODEL_PROFILES if n not in template] == []

    def test_the_pipeline_options_are_documented(self, scope: ConfigScope) -> None:
        keys = _option_keys(_render(scope))
        assert {
            ("default.pipeline", "model_profile"),
            ("default.pipeline", "provider"),
            ("default.pipeline", "model_warnings"),
        } <= keys

    def test_the_preset_is_a_command_line_choice_not_a_config_key(
        self, scope: ConfigScope
    ) -> None:
        template = _render(scope)
        assert "--preset" in template
        assert ("default.pipeline", "preset") not in _option_keys(template)

    def test_the_rendering_theme_is_documented(self, scope: ConfigScope) -> None:
        assert ("default.rendering", "theme") in _option_keys(_render(scope))

    def test_a_per_stage_override_is_shown(self, scope: ConfigScope) -> None:
        keys = _option_keys(_render(scope))
        assert {
            ("default.pipeline.stages.tailor", "provider"),
            ("default.pipeline.stages.tailor", "model"),
        } <= keys

    def test_the_vertex_options_sit_under_google(self, scope: ConfigScope) -> None:
        keys = _option_keys(_render(scope))
        assert {
            ("default.providers.google", key)
            for key in ("vertexai", "project", "location", "credentials_file")
        } <= keys

    def test_ollama_shows_its_base_url(self, scope: ConfigScope) -> None:
        template = _render(scope)
        assert f'# base_url = "{BUILTIN_PROVIDERS["ollama"].base_url}"' in template

    def test_each_keyed_provider_names_its_environment_variable(
        self, scope: ConfigScope
    ) -> None:
        template = _render(scope)
        variables = [
            v for p in KEYED_PROVIDERS for v in BUILTIN_PROVIDERS[p].api_key_env
        ]
        assert [v for v in variables if v not in template] == []

    def test_the_commented_examples_are_valid_toml(self, scope: ConfigScope) -> None:
        assert tomllib.loads(_uncomment_everything(_render(scope)))

    def test_the_commented_examples_use_known_sections(
        self, scope: ConfigScope
    ) -> None:
        enabled = tomllib.loads(_uncomment_everything(_render(scope)))["default"]
        known = {
            *tomllib.loads(
                (
                    Path(__file__).parents[3] / "src/mkcv/config/settings.toml"
                ).read_text()
            )["default"],
            "providers",
            "model_catalog",
            *WORKSPACE_ONLY_SECTIONS,
        }
        assert set(enabled) <= known

    def test_the_commented_providers_are_accepted_by_the_registry(
        self, scope: ConfigScope, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        path = tmp_path / "all.toml"
        path.write_text(_uncomment_everything(_render(scope)))
        config = _dynaconf(path)
        with caplog.at_level(logging.WARNING):
            registry = ProviderRegistry.from_config(config, load_model_catalog(config))
        assert "Ignoring unknown key" not in caplog.text
        assert registry.get("groq").kind.value == "openai-compatible"

    def test_the_stage_examples_match_the_built_in_defaults(
        self, scope: ConfigScope, tmp_path: Path
    ) -> None:
        path = tmp_path / "all.toml"
        path.write_text(_uncomment_everything(_render(scope)))
        shown = _settings(_dynaconf(path))
        defaults = _settings(Configuration())
        temperatures = {k: v for k, v in shown.items() if k.endswith(".temperature")}
        assert {k: v for k, v in temperatures.items() if defaults.get(k) != v} == {}


class TestOneSourceForBothFiles:
    def test_the_two_files_document_the_same_options(self) -> None:
        user = _option_keys(_render(ConfigScope.USER))
        workspace = _option_keys(_render(ConfigScope.WORKSPACE))
        assert {
            (s, k)
            for s, k in workspace
            if s.split(".")[-1] not in WORKSPACE_ONLY_SECTIONS
        } == user

    def test_the_two_files_share_the_option_explanations(self) -> None:
        def prose(scope: ConfigScope) -> set[str]:
            return {
                line
                for line in _render(scope).splitlines()
                if line.startswith("# ") and not _COMMENTED_TOML.match(line)
            }

        assert len(prose(ConfigScope.USER) & prose(ConfigScope.WORKSPACE)) > 40


class TestUserFile:
    def test_names_the_file_and_that_it_applies_to_every_workspace(self) -> None:
        template = _render(ConfigScope.USER)
        assert "~/.config/mkcv/settings.toml" in template
        assert "every workspace" in template

    def test_states_the_layer_order(self) -> None:
        assert (
            "built-in defaults < this file < workspace mkcv.toml"
            " < environment variables < command-line flags"
        ) in _render(ConfigScope.USER)

    def test_asks_to_keep_the_file_private(self) -> None:
        template = _render(ConfigScope.USER)
        assert "chmod 600" in template
        assert "never put keys in a committed mkcv.toml" in template.lower()

    def test_links_the_models_guide(self) -> None:
        assert "docs/models.md" in _render(ConfigScope.USER)

    @pytest.mark.parametrize("provider", KEYED_PROVIDERS)
    def test_each_keyed_provider_has_an_empty_key_placeholder(
        self, provider: str
    ) -> None:
        loaded = tomllib.loads(_render(ConfigScope.USER))
        assert loaded["default"]["providers"][provider] == {"api_key": ""}

    def test_only_the_keyed_providers_are_live(self) -> None:
        loaded = tomllib.loads(_render(ConfigScope.USER))
        assert sorted(loaded["default"]["providers"]) == sorted(KEYED_PROVIDERS)

    def test_the_only_live_section_is_providers(self) -> None:
        assert list(tomllib.loads(_render(ConfigScope.USER))["default"]) == [
            "providers"
        ]

    def test_ollama_needs_no_key(self) -> None:
        keys = _option_keys(_render(ConfigScope.USER))
        assert ("default.providers.ollama", "api_key") not in keys

    def test_loads_through_the_real_configuration_and_changes_no_default(
        self, _isolated_home: Path
    ) -> None:
        baseline = _settings(Configuration())
        path = _isolated_home / ".config" / "mkcv" / "settings.toml"
        path.parent.mkdir(parents=True)
        path.write_text(_render(ConfigScope.USER))
        config = Configuration()
        assert _settings(config) == baseline
        assert {
            p: config.providers[p].api_key for p in KEYED_PROVIDERS
        } == dict.fromkeys(KEYED_PROVIDERS, "")


class TestWorkspaceFile:
    def test_keeps_the_live_workspace_settings(self) -> None:
        live = tomllib.loads(_render(ConfigScope.WORKSPACE))["default"]
        assert live == {
            "workspace": {"version": __version__},
            "paths": {
                "knowledge_base_dir": "knowledge-base",
                "applications_dir": "applications",
                "templates_dir": "templates",
            },
            "naming": {
                "company_slug": True,
                "application_pattern": "{company}/{position}/{date}",
            },
            "defaults": {"theme": "sb2nov", "profile": "standard"},
        }

    def test_every_api_key_line_is_commented(self) -> None:
        lines = [
            line
            for line in _render(ConfigScope.WORKSPACE).splitlines()
            if "api_key =" in line
        ]
        assert lines
        assert [line for line in lines if not line.startswith("#")] == []

    def test_warns_about_keys_in_a_committed_file(self) -> None:
        template = " ".join(_render(ConfigScope.WORKSPACE).replace("# ", "").split())
        assert (
            "keys here are read only for this workspace; if this directory is a git "
            "repo, keep keys in ~/.config/mkcv/settings.toml instead or make sure "
            "mkcv.toml is not committed."
        ) in template

    def test_states_the_layer_order(self) -> None:
        assert (
            "built-in defaults < ~/.config/mkcv/settings.toml < this file"
            " < environment variables < command-line flags"
        ) in _render(ConfigScope.WORKSPACE)

    def test_documents_a_custom_openai_compatible_provider(self) -> None:
        template = _render(ConfigScope.WORKSPACE)
        assert "# [default.providers.groq]" in template
        assert '# type = "openai-compatible"' in template

    def test_documents_the_model_catalog(self) -> None:
        assert "# [[default.model_catalog]]" in _render(ConfigScope.WORKSPACE)

    def test_loads_through_the_real_configuration_and_changes_no_default(
        self, tmp_path: Path
    ) -> None:
        baseline = _settings(Configuration())
        (tmp_path / "mkcv.toml").write_text(_render(ConfigScope.WORKSPACE))
        config = Configuration()
        config.load_workspace_config(tmp_path)
        loaded = _settings(config)
        assert {k: v for k, v in loaded.items() if baseline.get(k, v) != v} == {}
        assert {k.split(".")[0] for k in loaded if k not in baseline} == {
            "workspace",
            "paths",
            "naming",
            "defaults",
        }
