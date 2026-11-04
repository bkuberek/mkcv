"""Tests for ProviderRegistry (REQ-PR-1 to PR-6, REQ-CAT-4, REQ-OC-10)."""

import logging
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from dynaconf import Dynaconf

from mkcv.adapters.llm.google import GoogleGeminiAdapter
from mkcv.adapters.llm.model_catalog_loader import load_model_catalog
from mkcv.adapters.llm.openai import OpenAIAdapter
from mkcv.adapters.llm.openai_compatible import OpenAICompatibleAdapter
from mkcv.adapters.llm.provider_registry import ProviderRegistry
from mkcv.adapters.llm.retry import RetryingLLMAdapter
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.core.exceptions.configuration import ConfigurationError
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.model_tier import ModelTier
from mkcv.core.models.provider_kind import ProviderKind
from mkcv.core.models.structured_output_mode import StructuredOutputMode
from mkcv.core.models.token_param import TokenParam

_KEY_VARIABLES = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",
)

GROQ_CONFIG = """
[default.providers.groq]
type = "openai-compatible"
base_url = "https://api.groq.com/openai/v1"
api_key_env = "GROQ_API_KEY"
structured_output = "json_object"
"""


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in _KEY_VARIABLES:
        monkeypatch.delenv(variable, raising=False)


def _config(tmp_path: Path, *layers: str) -> Dynaconf:
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


def _registry(tmp_path: Path, *layers: str) -> ProviderRegistry:
    config = _config(tmp_path, *layers)
    return ProviderRegistry.from_config(config, load_model_catalog(config))


class TestBuiltinProviders:
    """REQ-PR-1."""

    def test_names_are_the_sorted_builtin_names(self, tmp_path: Path) -> None:
        assert _registry(tmp_path).names() == (
            "anthropic",
            "google",
            "ollama",
            "openai",
            "openrouter",
            "stub",
        )

    def test_ollama_is_a_keyless_openai_compatible_provider(
        self, tmp_path: Path
    ) -> None:
        spec = _registry(tmp_path).get("ollama")
        assert (
            spec.kind,
            spec.base_url,
            spec.requires_api_key,
            spec.defaults.structured_output,
        ) == (
            ProviderKind.OPENAI_COMPATIBLE,
            "http://localhost:11434/v1",
            False,
            StructuredOutputMode.JSON_OBJECT,
        )

    def test_catalog_is_exposed(self, tmp_path: Path) -> None:
        config = _config(tmp_path)
        catalog = ModelCatalog.builtin()
        registry = ProviderRegistry.from_config(config, catalog)
        assert registry.catalog is catalog


class TestUnknownProvider:
    """REQ-PR-2."""

    def test_unknown_provider_raises_a_configuration_error(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ConfigurationError) as caught:
            _registry(tmp_path).get("groq")
        assert caught.value.exit_code == 3

    def test_message_names_the_provider_and_every_known_provider(
        self, tmp_path: Path
    ) -> None:
        registry = _registry(tmp_path)
        with pytest.raises(ConfigurationError) as caught:
            registry.get("groq")
        message = str(caught.value)
        assert "Unknown LLM provider 'groq'" in message
        for name in registry.names():
            assert name in message
        assert "[default.providers.<name>]" in message

    def test_names_are_case_sensitive(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError):
            _registry(tmp_path).get("Anthropic")

    def test_create_adapter_rejects_unknown_providers(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="Unknown LLM provider"):
            _registry(tmp_path).create_adapter("nope")


class TestUserDefinedProvider:
    """REQ-PR-3."""

    def test_spec_reflects_the_config(self, tmp_path: Path) -> None:
        spec = _registry(tmp_path, GROQ_CONFIG).get("groq")
        assert (
            spec.kind,
            spec.base_url,
            spec.api_key_env,
            spec.requires_api_key,
            spec.defaults.structured_output,
            spec.builtin,
        ) == (
            ProviderKind.OPENAI_COMPATIBLE,
            "https://api.groq.com/openai/v1",
            ("GROQ_API_KEY",),
            True,
            StructuredOutputMode.JSON_OBJECT,
            False,
        )

    def test_api_key_env_accepts_a_list(self, tmp_path: Path) -> None:
        config = GROQ_CONFIG.replace('"GROQ_API_KEY"', '["GROQ_KEY_1", "GROQ_KEY_2"]')
        spec = _registry(tmp_path, config).get("groq")
        assert spec.api_key_env == ("GROQ_KEY_1", "GROQ_KEY_2")

    def test_user_provider_is_listed_among_the_names(self, tmp_path: Path) -> None:
        assert "groq" in _registry(tmp_path, GROQ_CONFIG).names()

    def test_adapter_is_openai_compatible_with_the_configured_endpoint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "gk-test")
        adapter = _registry(tmp_path, GROQ_CONFIG).create_adapter(
            "groq", with_retry=False
        )
        assert isinstance(adapter, OpenAICompatibleAdapter)
        assert str(adapter._client.base_url).startswith(
            "https://api.groq.com/openai/v1"
        )

    def test_adapter_reports_the_provider_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "gk-test")
        adapter = _registry(tmp_path, GROQ_CONFIG).create_adapter(
            "groq", with_retry=False
        )
        assert isinstance(adapter, OpenAICompatibleAdapter)
        assert adapter._provider_name == "groq"

    def test_adapter_resolves_models_with_the_provider_defaults(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "gk-test")
        adapter = _registry(tmp_path, GROQ_CONFIG).create_adapter(
            "groq", with_retry=False
        )
        assert isinstance(adapter, OpenAICompatibleAdapter)
        resolved = adapter._resolver("groq", "some-model")
        assert resolved.structured_output is StructuredOutputMode.JSON_OBJECT

    def test_adapter_sees_user_catalog_overrides(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "gk-test")
        config = (
            GROQ_CONFIG
            + """
[[default.model_catalog]]
provider = "groq"
match = "llama-3.3-70b-versatile"
tier = "efficient"
"""
        )
        adapter = _registry(tmp_path, config).create_adapter("groq", with_retry=False)
        assert isinstance(adapter, OpenAICompatibleAdapter)
        resolved = adapter._resolver("groq", "llama-3.3-70b-versatile")
        assert (resolved.known, resolved.tier) == (True, ModelTier.EFFICIENT)

    def test_user_provider_of_a_native_kind_inherits_that_providers_models(
        self, tmp_path: Path
    ) -> None:
        config = """
[default.providers.my-proxy]
type = "openai"
base_url = "https://proxy.example/v1"
api_key = "k"
"""
        registry = _registry(tmp_path, config)
        resolved = registry.resolve_model("my-proxy", "gpt-6.1-sol")
        assert (resolved.known, resolved.tier) == (True, ModelTier.STRONG)

    def test_native_kind_provider_uses_the_native_adapter(self, tmp_path: Path) -> None:
        config = """
[default.providers.my-proxy]
type = "openai"
base_url = "https://proxy.example/v1"
api_key = "k"
"""
        adapter = _registry(tmp_path, config).create_adapter(
            "my-proxy", with_retry=False
        )
        assert isinstance(adapter, OpenAIAdapter)
        assert str(adapter._client.base_url).startswith("https://proxy.example/v1")

    def test_later_layer_overrides_the_provider_endpoint(self, tmp_path: Path) -> None:
        workspace = """
[default.providers.groq]
base_url = "https://groq.example/v1"
"""
        spec = _registry(tmp_path, GROQ_CONFIG, workspace).get("groq")
        assert spec.base_url == "https://groq.example/v1"
        assert spec.kind is ProviderKind.OPENAI_COMPATIBLE


class TestOverridingBuiltinProviders:
    def test_builtin_endpoint_can_be_overridden(self, tmp_path: Path) -> None:
        config = """
[default.providers.ollama]
base_url = "http://remote:11434/v1"
"""
        spec = _registry(tmp_path, config).get("ollama")
        assert spec.base_url == "http://remote:11434/v1"
        assert spec.builtin is True
        assert spec.requires_api_key is False

    def test_builtin_capability_defaults_overlay_the_builtin_ones(
        self, tmp_path: Path
    ) -> None:
        config = """
[default.providers.ollama]
accepts_sampling_params = false
"""
        spec = _registry(tmp_path, config).get("ollama")
        assert spec.defaults.accepts_sampling_params is False
        assert spec.defaults.structured_output is StructuredOutputMode.JSON_OBJECT

    def test_same_type_as_the_builtin_is_accepted(self, tmp_path: Path) -> None:
        config = """
[default.providers.anthropic]
type = "anthropic"
api_key = "from-config"
"""
        assert (
            _registry(tmp_path, config).get("anthropic").kind is ProviderKind.ANTHROPIC
        )

    def test_builtin_can_require_an_api_key(self, tmp_path: Path) -> None:
        config = """
[default.providers.ollama]
requires_api_key = true
"""
        registry = _registry(tmp_path, config)
        assert registry.has_credentials("ollama") is False


class TestCompatibleBaseUrlNormalisation:
    @pytest.mark.parametrize(
        "given",
        ["http://localhost:11434", "http://localhost:11434/"],
    )
    def test_bare_host_gets_the_v1_path(self, tmp_path: Path, given: str) -> None:
        config = f'[default.providers.ollama]\nbase_url = "{given}"\n'
        spec = _registry(tmp_path, config).get("ollama")
        assert spec.base_url == "http://localhost:11434/v1"

    def test_explicit_path_is_left_alone(self, tmp_path: Path) -> None:
        config = '[default.providers.ollama]\nbase_url = "http://host:1/custom"\n'
        assert _registry(tmp_path, config).get("ollama").base_url == (
            "http://host:1/custom"
        )

    def test_explicit_v1_path_is_left_alone(self, tmp_path: Path) -> None:
        config = '[default.providers.ollama]\nbase_url = "http://host:1/v1/"\n'
        assert _registry(tmp_path, config).get("ollama").base_url == (
            "http://host:1/v1/"
        )

    def test_user_defined_compatible_provider_is_normalised(
        self, tmp_path: Path
    ) -> None:
        config = """
[default.providers.local]
type = "openai-compatible"
base_url = "http://gpu-box:8000"
requires_api_key = false
"""
        assert _registry(tmp_path, config).get("local").base_url == (
            "http://gpu-box:8000/v1"
        )

    def test_native_kind_endpoint_is_not_touched(self, tmp_path: Path) -> None:
        config = '[default.providers.openai]\nbase_url = "https://proxy.example"\n'
        assert _registry(tmp_path, config).get("openai").base_url == (
            "https://proxy.example"
        )

    def test_adapter_client_uses_the_normalised_url(self, tmp_path: Path) -> None:
        config = '[default.providers.ollama]\nbase_url = "http://localhost:11434"\n'
        adapter = _registry(tmp_path, config).create_adapter("ollama", with_retry=False)
        assert isinstance(adapter, OpenAICompatibleAdapter)
        assert str(adapter._client.base_url).startswith("http://localhost:11434/v1")

    def test_normalisation_is_logged(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO)
        config = '[default.providers.ollama]\nbase_url = "http://localhost:11434"\n'
        _registry(tmp_path, config)
        assert "http://localhost:11434/v1" in caplog.text


class TestInvalidProviderConfig:
    """REQ-PR-4."""

    def test_missing_type_on_a_new_provider(self, tmp_path: Path) -> None:
        config = '[default.providers.groq]\nbase_url = "https://x"\n'
        with pytest.raises(ConfigurationError, match="needs type") as caught:
            _registry(tmp_path, config)
        assert "openai-compatible" in str(caught.value)

    def test_missing_base_url_on_a_new_compatible_provider(
        self, tmp_path: Path
    ) -> None:
        config = '[default.providers.groq]\ntype = "openai-compatible"\n'
        with pytest.raises(ConfigurationError, match="needs base_url"):
            _registry(tmp_path, config)

    def test_changing_the_type_of_a_builtin_provider(self, tmp_path: Path) -> None:
        config = '[default.providers.anthropic]\ntype = "openai"\n'
        with pytest.raises(ConfigurationError, match="cannot be changed"):
            _registry(tmp_path, config)

    def test_stub_cannot_be_a_user_provider_type(self, tmp_path: Path) -> None:
        config = '[default.providers.groq]\ntype = "stub"\n'
        with pytest.raises(ConfigurationError):
            _registry(tmp_path, config)

    def test_unknown_provider_type(self, tmp_path: Path) -> None:
        config = '[default.providers.groq]\ntype = "carrier-pigeon"\n'
        with pytest.raises(ConfigurationError, match="carrier-pigeon"):
            _registry(tmp_path, config)

    def test_unknown_key_is_ignored_with_a_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING)
        config = """
[default.providers.groq]
type = "openai-compatible"
base_url = "https://x"
colour = "red"
"""
        spec = _registry(tmp_path, config).get("groq")
        assert spec.kind is ProviderKind.OPENAI_COMPATIBLE
        assert "colour" in caplog.text

    def test_unknown_key_warning_names_the_section(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING)
        config = """
[default.providers.groq]
type = "openai-compatible"
base_url = "https://x"
colour = "red"
"""
        _registry(tmp_path, config)
        assert "[default.providers.groq]" in caplog.text

    def test_unknown_key_on_a_builtin_provider_does_not_abort(
        self, tmp_path: Path
    ) -> None:
        config = '[default.providers.ollama]\nmodels = ["llama3.1"]\n'
        assert _registry(tmp_path, config).get("ollama").builtin is True

    def test_invalid_capability_value(self, tmp_path: Path) -> None:
        config = """
[default.providers.groq]
type = "openai-compatible"
base_url = "https://x"
structured_output = "telepathy"
"""
        with pytest.raises(ConfigurationError, match="groq"):
            _registry(tmp_path, config)

    def test_invalid_api_key_env_type(self, tmp_path: Path) -> None:
        config = """
[default.providers.groq]
type = "openai-compatible"
base_url = "https://x"
api_key_env = 5
"""
        with pytest.raises(ConfigurationError, match="api_key_env"):
            _registry(tmp_path, config)

    def test_provider_section_must_be_a_table(self, tmp_path: Path) -> None:
        config = '[default.providers]\ngroq = "x"\n'
        with pytest.raises(ConfigurationError, match="groq"):
            _registry(tmp_path, config)

    def test_errors_use_exit_code_three(self, tmp_path: Path) -> None:
        config = '[default.providers.groq]\nbase_url = "https://x"\n'
        with pytest.raises(ConfigurationError) as caught:
            _registry(tmp_path, config)
        assert caught.value.exit_code == 3


class TestApiKeyResolution:
    """REQ-PR-5."""

    def test_config_key_beats_the_environment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
        config = '[default.providers.anthropic]\napi_key = "from-config"\n'
        assert _registry(tmp_path, config).resolve_api_key("anthropic") == "from-config"

    def test_environment_is_used_without_a_config_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
        assert _registry(tmp_path).resolve_api_key("anthropic") == "from-env"

    def test_first_environment_variable_wins_for_google(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "g1")
        monkeypatch.setenv("GOOGLE_API_KEY", "g2")
        assert _registry(tmp_path).resolve_api_key("google") == "g1"

    def test_second_environment_variable_is_a_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_API_KEY", "g2")
        assert _registry(tmp_path).resolve_api_key("google") == "g2"

    def test_empty_environment_variable_is_skipped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "")
        monkeypatch.setenv("GOOGLE_API_KEY", "g2")
        assert _registry(tmp_path).resolve_api_key("google") == "g2"

    def test_no_key_resolves_to_none(self, tmp_path: Path) -> None:
        assert _registry(tmp_path).resolve_api_key("openai") is None

    def test_keyless_provider_has_credentials(self, tmp_path: Path) -> None:
        assert _registry(tmp_path).has_credentials("ollama") is True

    def test_keyed_provider_without_a_key_has_no_credentials(
        self, tmp_path: Path
    ) -> None:
        assert _registry(tmp_path).has_credentials("openai") is False

    def test_keyed_provider_with_a_key_has_credentials(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        assert _registry(tmp_path).has_credentials("openai") is True

    def test_stub_has_credentials(self, tmp_path: Path) -> None:
        assert _registry(tmp_path).has_credentials("stub") is True

    def test_literal_key_for_a_user_provider(self, tmp_path: Path) -> None:
        config = """
[default.providers.groq]
type = "openai-compatible"
base_url = "https://x"
api_key = "literal"
"""
        assert _registry(tmp_path, config).resolve_api_key("groq") == "literal"

    def test_resolving_the_key_of_an_unknown_provider_fails(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ConfigurationError):
            _registry(tmp_path).resolve_api_key("nope")


class TestAdapterCreation:
    """REQ-PR-6 and REQ-OC-10."""

    def test_openai_is_wrapped_with_retry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        adapter = _registry(tmp_path).create_adapter("openai")
        assert isinstance(adapter, RetryingLLMAdapter)
        assert isinstance(adapter._inner, OpenAIAdapter)

    def test_retry_can_be_disabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        adapter = _registry(tmp_path).create_adapter("openai", with_retry=False)
        assert isinstance(adapter, OpenAIAdapter)

    def test_anthropic_adapter_is_built_from_the_registry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from mkcv.adapters.llm.anthropic import AnthropicAdapter

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        adapter = _registry(tmp_path).create_adapter("anthropic", with_retry=False)
        assert isinstance(adapter, AnthropicAdapter)
        assert adapter._provider_name == "anthropic"

    def test_adapter_resolves_models_through_the_registry_catalog(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from mkcv.adapters.llm.anthropic import AnthropicAdapter

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        config = """
[[default.model_catalog]]
provider = "anthropic"
match = "claude-opus-5-5"
tier = "minimal"
"""
        adapter = _registry(tmp_path, config).create_adapter(
            "anthropic", with_retry=False
        )
        assert isinstance(adapter, AnthropicAdapter)
        assert (
            adapter._resolver("anthropic", "claude-opus-5-5").tier is ModelTier.MINIMAL
        )

    def test_missing_key_raises_a_configuration_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="OPENROUTER_API_KEY"):
            _registry(tmp_path).create_adapter("openrouter")

    def test_missing_key_error_names_the_provider(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="openrouter"):
            _registry(tmp_path).create_adapter("openrouter")

    def test_missing_key_error_uses_exit_code_three(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError) as raised:
            _registry(tmp_path).create_adapter("openai")
        assert raised.value.exit_code == 3

    def test_missing_key_error_names_every_google_variable(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ConfigurationError, match=r"GEMINI_API_KEY.*GOOGLE_API_KEY"):
            _registry(tmp_path).create_adapter("google")

    def test_missing_key_error_points_at_config_without_a_variable(
        self, tmp_path: Path
    ) -> None:
        config = """
[default.providers.vault]
type = "openai-compatible"
base_url = "https://vault.example/v1"
requires_api_key = true
"""
        with pytest.raises(ConfigurationError, match=r"api_key in \[default.providers"):
            _registry(tmp_path, config).create_adapter("vault")

    def test_keyless_provider_gets_a_compatible_adapter(self, tmp_path: Path) -> None:
        adapter = _registry(tmp_path).create_adapter("ollama", with_retry=False)
        assert isinstance(adapter, OpenAICompatibleAdapter)

    def test_stub_is_not_wrapped(self, tmp_path: Path) -> None:
        adapter = _registry(tmp_path).create_adapter("stub")
        assert isinstance(adapter, StubLLMAdapter)

    def test_ollama_uses_the_compatible_adapter_not_the_native_one(
        self, tmp_path: Path
    ) -> None:
        adapter = _registry(tmp_path).create_adapter("ollama", with_retry=False)
        assert type(adapter) is OpenAICompatibleAdapter

    def test_ollama_points_at_the_local_endpoint(self, tmp_path: Path) -> None:
        adapter = _registry(tmp_path).create_adapter("ollama", with_retry=False)
        assert isinstance(adapter, OpenAICompatibleAdapter)
        assert str(adapter._client.base_url).startswith("http://localhost:11434/v1")

    def test_ollama_adapter_starts_in_json_object_mode(self, tmp_path: Path) -> None:
        adapter = _registry(tmp_path).create_adapter("ollama", with_retry=False)
        assert isinstance(adapter, OpenAICompatibleAdapter)
        resolved = adapter._resolver("ollama", "llama3.1:8b")
        assert resolved.structured_output is StructuredOutputMode.JSON_OBJECT
        assert resolved.accepts_sampling_params is True
        assert resolved.token_param is TokenParam.MAX_TOKENS

    def test_ollama_models_are_free(self, tmp_path: Path) -> None:
        resolved = _registry(tmp_path).resolve_model("ollama", "llama3.1:8b")
        assert (resolved.input_price_per_mtok, resolved.output_price_per_mtok) == (
            0.0,
            0.0,
        )

    def test_openrouter_with_a_key_points_at_openrouter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        adapter = _registry(tmp_path).create_adapter("openrouter", with_retry=False)
        assert type(adapter) is OpenAICompatibleAdapter
        assert str(adapter._client.base_url).startswith("https://openrouter.ai/api/v1")

    def test_key_from_config_reaches_the_client(self, tmp_path: Path) -> None:
        config = '[default.providers.openai]\napi_key = "sk-from-config"\n'
        adapter = _registry(tmp_path, config).create_adapter("openai", with_retry=False)
        assert isinstance(adapter, OpenAIAdapter)
        assert adapter._client.api_key == "sk-from-config"


class TestGoogleAdapterCreation:
    """REQ-GG-9."""

    def test_google_adapter_is_built_from_the_registry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "g")
        adapter = _registry(tmp_path).create_adapter("google", with_retry=False)
        assert isinstance(adapter, GoogleGeminiAdapter)

    def test_google_is_wrapped_with_retry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "g")
        adapter = _registry(tmp_path).create_adapter("google")
        assert isinstance(adapter, RetryingLLMAdapter)
        assert isinstance(adapter._inner, GoogleGeminiAdapter)

    def test_google_api_key_variable_is_accepted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_API_KEY", "g2")
        adapter = _registry(tmp_path).create_adapter("google", with_retry=False)
        assert isinstance(adapter, GoogleGeminiAdapter)

    def test_key_resolved_by_the_registry_reaches_the_client(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "g1")
        monkeypatch.setenv("GOOGLE_API_KEY", "g2")
        with patch("mkcv.adapters.llm.google.genai.Client") as client:
            _registry(tmp_path).create_adapter("google", with_retry=False)
        assert client.call_args.kwargs["api_key"] == "g1"

    def test_missing_key_raises_a_configuration_error(self, tmp_path: Path) -> None:
        with pytest.raises(
            ConfigurationError, match="No API key for provider 'google'"
        ):
            _registry(tmp_path).create_adapter("google")

    def test_adapter_resolves_models_through_the_registry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "g")
        config = """
[[default.model_catalog]]
provider = "google"
match = "gemini-3.8-flash"
tier = "minimal"
"""
        adapter = _registry(tmp_path, config).create_adapter("google", with_retry=False)
        assert isinstance(adapter, GoogleGeminiAdapter)
        assert adapter._resolver("google", "gemini-3.8-flash").tier is ModelTier.MINIMAL

    def test_adapter_carries_the_provider_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "g")
        adapter = _registry(tmp_path).create_adapter("google", with_retry=False)
        assert isinstance(adapter, GoogleGeminiAdapter)
        assert adapter._provider_name == "google"

    def test_base_url_from_config_reaches_the_client(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "g")
        config = '[default.providers.google]\nbase_url = "https://proxy.example.com"\n'
        with patch("mkcv.adapters.llm.google.genai.Client") as client:
            _registry(tmp_path, config).create_adapter("google", with_retry=False)
        options = client.call_args.kwargs["http_options"]
        assert options.base_url == "https://proxy.example.com"

    def test_base_url_from_config_reaches_the_real_sdk_client(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "g")
        config = '[default.providers.google]\nbase_url = "https://proxy.example.com"\n'
        adapter = _registry(tmp_path, config).create_adapter("google", with_retry=False)
        assert isinstance(adapter, GoogleGeminiAdapter)
        sdk_options = adapter._client._api_client._http_options
        assert sdk_options.base_url == "https://proxy.example.com"

    def test_user_defined_google_provider_uses_the_google_adapter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_PROXY_KEY", "gk")
        config = """
[default.providers.gemini-proxy]
type = "google"
base_url = "https://proxy.example.com"
api_key_env = "GEMINI_PROXY_KEY"
"""
        adapter = _registry(tmp_path, config).create_adapter(
            "gemini-proxy", with_retry=False
        )
        assert isinstance(adapter, GoogleGeminiAdapter)
        assert adapter._provider_name == "gemini-proxy"


class TestLazyImports:
    """REQ-GG-9: the Google SDK is imported only when Google is used."""

    CREATE_ADAPTER = """
import os, sys
os.environ["{variable}"] = "key"
from dynaconf import Dynaconf
from mkcv.adapters.llm.model_catalog_loader import load_model_catalog
from mkcv.adapters.llm.provider_registry import ProviderRegistry

config = Dynaconf(environments=True, default_env="default")
registry = ProviderRegistry.from_config(config, load_model_catalog(config))
registry.create_adapter("{provider}")
assert ("google.genai" in sys.modules) is {imported}
"""

    @staticmethod
    def _run(code: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_importing_the_factory_does_not_import_the_google_sdk(self) -> None:
        result = self._run(
            "import sys, mkcv.adapters.factory; "
            "assert 'google.genai' not in sys.modules"
        )
        assert result.returncode == 0, result.stderr

    def test_importing_the_registry_does_not_import_the_google_sdk(self) -> None:
        result = self._run(
            "import sys, mkcv.adapters.llm.provider_registry; "
            "assert 'google.genai' not in sys.modules"
        )
        assert result.returncode == 0, result.stderr

    def test_creating_a_non_google_adapter_does_not_import_the_google_sdk(
        self,
    ) -> None:
        result = self._run(
            self.CREATE_ADAPTER.format(
                variable="OPENAI_API_KEY", provider="openai", imported=False
            )
        )
        assert result.returncode == 0, result.stderr

    def test_creating_a_google_adapter_imports_the_google_sdk(self) -> None:
        result = self._run(
            self.CREATE_ADAPTER.format(
                variable="GEMINI_API_KEY", provider="google", imported=True
            )
        )
        assert result.returncode == 0, result.stderr


class TestModelResolution:
    """REQ-CAT-4 as used by the registry."""

    def test_provider_defaults_overlay_the_kind_defaults(self, tmp_path: Path) -> None:
        registry = _registry(tmp_path)
        defaults = registry.defaults_for("ollama")
        assert defaults.structured_output is StructuredOutputMode.JSON_OBJECT
        assert defaults.allow_structured_fallback is True

    def test_native_provider_resolves_catalog_models(self, tmp_path: Path) -> None:
        resolved = _registry(tmp_path).resolve_model("openai", "gpt-6.1-sol")
        assert (resolved.known, resolved.accepts_sampling_params) == (True, False)

    def test_unknown_native_model_resolves_conservatively(self, tmp_path: Path) -> None:
        resolved = _registry(tmp_path).resolve_model("openai", "gpt-7-nova")
        assert (resolved.known, resolved.min_output_tokens) == (False, 16000)

    def test_aggregator_models_borrow_vendor_neutral_facts(
        self, tmp_path: Path
    ) -> None:
        resolved = _registry(tmp_path).resolve_model("openrouter", "openai/gpt-6.1-sol")
        assert resolved.tier is ModelTier.STRONG
        assert resolved.input_price_per_mtok is None

    def test_resolving_for_an_unknown_provider_fails(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError):
            _registry(tmp_path).resolve_model("nope", "m")
