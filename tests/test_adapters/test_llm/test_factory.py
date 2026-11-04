"""Tests for factory provider selection logic."""

from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import MagicMock

import pytest
from dynaconf import Dynaconf

from mkcv.adapters import factory as factory_module
from mkcv.adapters.factory import (
    _create_llm_adapter,
    create_cover_letter_service,
    create_pipeline_service,
    create_regeneration_service,
    create_validation_service,
    create_workspace_service,
)
from mkcv.adapters.llm.anthropic import AnthropicAdapter
from mkcv.adapters.llm.openai import OpenAIAdapter
from mkcv.adapters.llm.openai_compatible import OpenAICompatibleAdapter
from mkcv.adapters.llm.provider_registry import ProviderRegistry
from mkcv.adapters.llm.retry import RetryingLLMAdapter
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.core.exceptions.configuration import ConfigurationError
from mkcv.core.models.profile_preset import ContentDensity
from mkcv.core.services.regeneration import RegenerationService
from mkcv.core.services.workspace import WorkspaceService


def _blank_config(**values: Any) -> MagicMock:
    """Build a mock Configuration whose ``get`` resolves ``values`` by key.

    Keys that are not given resolve to the caller's default, like a Dynaconf
    object with nothing configured. The attribute pattern the legacy stage
    resolution used (``config.pipeline.stages...``) is gone: stage sections are
    read with ``config.get("pipeline.stages.tailor")``, so give those as
    ``**{"pipeline.stages.tailor": {...}}``.
    """
    config = MagicMock()
    config.get.side_effect = lambda key, default=None: values.get(key, default)
    config.providers = None
    config.in_workspace = False
    config.workspace_root = None
    return config


def _make_config(
    api_key: str | None = None,
    provider: str = "stub",
) -> MagicMock:
    """Build a mock Configuration with an optional config-file API key."""
    if api_key is None:
        return _blank_config()
    return _blank_config(providers={provider: {"api_key": api_key}})


def _unwrap(adapter: object) -> object:
    """Unwrap a RetryingLLMAdapter to get the inner adapter."""
    if isinstance(adapter, RetryingLLMAdapter):
        return adapter._inner
    return adapter


class TestCreateLLMAdapter:
    """Tests for _create_llm_adapter factory function."""

    def test_creates_stub_adapter(self) -> None:
        config = _make_config()
        adapter = _create_llm_adapter("stub", config)
        assert isinstance(adapter, StubLLMAdapter)

    def test_creates_anthropic_adapter_with_key(self) -> None:
        config = _make_config(provider="anthropic", api_key="sk-ant-test123")
        adapter = _create_llm_adapter("anthropic", config)
        assert isinstance(adapter, RetryingLLMAdapter)
        assert isinstance(_unwrap(adapter), AnthropicAdapter)

    def test_creates_openai_adapter_with_key(self) -> None:
        config = _make_config(provider="openai", api_key="sk-openai-test123")
        adapter = _create_llm_adapter("openai", config)
        assert isinstance(adapter, RetryingLLMAdapter)
        assert isinstance(_unwrap(adapter), OpenAIAdapter)

    def test_falls_back_to_stub_when_no_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        config = _make_config(provider="anthropic")
        adapter = _create_llm_adapter("anthropic", config)
        assert isinstance(_unwrap(adapter), StubLLMAdapter)

    def test_uses_env_var_for_anthropic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env-key")
        config = _make_config(provider="anthropic")
        adapter = _create_llm_adapter("anthropic", config)
        assert isinstance(_unwrap(adapter), AnthropicAdapter)

    def test_uses_env_var_for_openai(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-env-key")
        config = _make_config(provider="openai")
        adapter = _create_llm_adapter("openai", config)
        assert isinstance(_unwrap(adapter), OpenAIAdapter)

    def test_config_key_takes_precedence_over_env_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
        config = _make_config(provider="anthropic", api_key="sk-from-config")
        adapter = _create_llm_adapter("anthropic", config)
        assert isinstance(_unwrap(adapter), AnthropicAdapter)

    def test_stub_is_not_wrapped_with_retry(self) -> None:
        config = _make_config()
        adapter = _create_llm_adapter("stub", config)
        assert not isinstance(adapter, RetryingLLMAdapter)

    def test_without_retry_returns_raw_adapter(self) -> None:
        config = _make_config(provider="anthropic", api_key="sk-test")
        adapter = _create_llm_adapter("anthropic", config, with_retry=False)
        assert isinstance(adapter, AnthropicAdapter)

    def test_ollama_is_an_openai_compatible_adapter(self) -> None:
        adapter = _create_llm_adapter("ollama", _make_config())
        assert isinstance(adapter, RetryingLLMAdapter)
        assert type(_unwrap(adapter)) is OpenAICompatibleAdapter

    def test_ollama_without_retry_returns_raw_adapter(self) -> None:
        adapter = _create_llm_adapter("ollama", _make_config(), with_retry=False)
        assert type(adapter) is OpenAICompatibleAdapter

    def test_openrouter_is_an_openai_compatible_adapter(self) -> None:
        config = _make_config(provider="openrouter", api_key="sk-or-test")
        adapter = _create_llm_adapter("openrouter", config, with_retry=False)
        assert type(adapter) is OpenAICompatibleAdapter

    def test_openrouter_without_a_key_falls_back_to_the_stub(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        adapter = _create_llm_adapter("openrouter", _make_config())
        assert isinstance(adapter, StubLLMAdapter)

    def test_unknown_provider_is_a_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError, match="Unknown LLM provider 'nope'"):
            _create_llm_adapter("nope", _make_config())

    def test_provider_defined_in_config_is_created(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "gk-test")
        config = _blank_config(
            providers={
                "groq": {
                    "type": "openai-compatible",
                    "base_url": "https://api.groq.com/openai/v1",
                    "api_key_env": "GROQ_API_KEY",
                }
            }
        )
        adapter = _create_llm_adapter("groq", config, with_retry=False)
        assert type(adapter) is OpenAICompatibleAdapter

    def test_legacy_key_helpers_are_gone(self) -> None:
        assert not hasattr(factory_module, "_PROVIDER_ENV_KEYS")
        assert not hasattr(factory_module, "_resolve_api_key")


_PIPELINE_STAGE_NAMES = ("analyze", "select", "tailor", "structure", "review")
_SMART_MIX = [
    "claude-haiku-5-5",
    "claude-opus-5-5",
    "claude-opus-5-5",
    "claude-sonnet-5-5",
    "claude-opus-5-5",
]
_DEFAULT_TEMPERATURES = [0.2, 0.3, 0.5, 0.1, 0.3]


def _stub_pipeline_config(**extra: Any) -> MagicMock:
    """A config whose five pipeline stages all run on the offline stub."""
    stages = {
        f"pipeline.stages.{name}": {
            "provider": "stub",
            "model": "stub-model",
            "temperature": 0.3,
        }
        for name in _PIPELINE_STAGE_NAMES
    }
    return _blank_config(**{**stages, **extra})


def _models(service: Any) -> list[str]:
    return [sc.model for sc in service._stage_configs.values()]


def _providers(service: Any) -> set[str]:
    return {sc.provider for sc in service._stage_configs.values()}


class TestRemovedHelpers:
    @pytest.mark.parametrize(
        "name",
        [
            "_resolve_preset",
            "_resolve_stage_configs",
            "_resolve_cl_stage_configs",
            "_STAGE_CONFIG_KEYS",
            "_CL_STAGE_CONFIG_KEYS",
        ],
    )
    def test_legacy_stage_resolution_is_gone(self, name: str) -> None:
        assert not hasattr(factory_module, name)


class TestPipelineStageModels:
    """The resolver decides models; presets only decide density and economy."""

    def test_standard_preset_gives_the_smart_claude_mix(self) -> None:
        service = create_pipeline_service(_blank_config(), preset_name="standard")
        assert _models(service) == _SMART_MIX

    def test_stages_are_numbered_one_to_five(self) -> None:
        service = create_pipeline_service(_blank_config(), preset_name="standard")
        assert list(service._stage_configs) == [1, 2, 3, 4, 5]

    def test_every_stage_keeps_todays_temperature(self) -> None:
        service = create_pipeline_service(_blank_config(), preset_name="standard")
        temperatures = [sc.temperature for sc in service._stage_configs.values()]
        assert temperatures == _DEFAULT_TEMPERATURES

    def test_concise_preset_uses_haiku_everywhere(self) -> None:
        service = create_pipeline_service(_blank_config(), preset_name="concise")
        assert set(_models(service)) == {"claude-haiku-5-5"}

    @pytest.mark.parametrize("preset", ["comprehensive", "premium", "default"])
    def test_other_presets_use_the_smart_mix(self, preset: str) -> None:
        service = create_pipeline_service(_blank_config(), preset_name=preset)
        assert _models(service) == _SMART_MIX

    def test_budget_preset_runs_every_stage_on_ollama(self) -> None:
        service = create_pipeline_service(_blank_config(), preset_name="budget")
        assert set(_models(service)) == {"llama3.1:8b"}
        assert _providers(service) == {"ollama"}

    def test_budget_preset_creates_the_ollama_provider(self) -> None:
        service = create_pipeline_service(_blank_config(), preset_name="budget")
        assert set(service._providers) == {"ollama"}

    def test_budget_preset_still_yields_ollama_when_config_names_another_provider(
        self,
    ) -> None:
        config = _blank_config(
            **{
                "pipeline.stages.analyze": {
                    "provider": "openai",
                    "model": "gpt-6-luna",
                    "temperature": 0.9,
                }
            }
        )
        service = create_pipeline_service(config, preset_name="budget")
        assert service._stage_configs[1].provider == "ollama"
        assert service._stage_configs[1].model == "llama3.1:8b"

    def test_default_preset_uses_the_stage_sections_from_config(self) -> None:
        service = create_pipeline_service(
            _stub_pipeline_config(), preset_name="default"
        )
        assert set(service._providers) == {"stub"}

    def test_provider_override_runs_every_stage_on_that_provider(self) -> None:
        service = create_pipeline_service(
            _blank_config(), preset_name="standard", provider_override="openai"
        )
        assert _providers(service) == {"openai"}
        assert _models(service) == [
            "gpt-6-luna",
            "gpt-6.1-sol",
            "gpt-6-astra",
            "gpt-6.1-terra",
            "gpt-6.1-sol",
        ]

    def test_provider_override_without_a_profile_needs_configured_models(self) -> None:
        with pytest.raises(ConfigurationError, match=r"^Cannot resolve models:"):
            create_pipeline_service(
                _blank_config(), preset_name="standard", provider_override="openrouter"
            )

    def test_model_profile_runs_every_stage_on_that_profile(self) -> None:
        service = create_pipeline_service(
            _blank_config(), preset_name="standard", model_profile="google"
        )
        assert _providers(service) == {"google"}
        assert _models(service)[1] == "gemini-4-argon"

    def test_model_profile_creates_only_that_providers_adapter(self) -> None:
        service = create_pipeline_service(
            _blank_config(), preset_name="standard", model_profile="google"
        )
        assert set(service._providers) == {"google"}

    def test_model_profile_and_provider_override_are_mutually_exclusive(self) -> None:
        with pytest.raises(ConfigurationError, match="cannot be used together"):
            create_pipeline_service(
                _blank_config(),
                model_profile="google",
                provider_override="openai",
            )

    def test_unknown_model_profile_is_a_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError, match="Unknown model profile 'nope'"):
            create_pipeline_service(_blank_config(), model_profile="nope")

    def test_resolution_errors_surface_before_any_adapter_is_created(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail(*args: object, **kwargs: object) -> None:
            raise AssertionError("an adapter was created")

        monkeypatch.setattr(ProviderRegistry, "create_adapter", fail)
        with pytest.raises(ConfigurationError):
            create_pipeline_service(
                _blank_config(), preset_name="standard", provider_override="openrouter"
            )


class TestPerStageConfigBeatsThePreset:
    """REQ-SR-2 end to end: this used to be ignored by ``generate``."""

    TAILOR_ON_OPENAI: ClassVar[dict[str, Any]] = {
        "pipeline.stages.tailor": {"provider": "openai", "model": "gpt-6.1-sol"}
    }

    def test_standard_preset_honours_a_tailor_override(self) -> None:
        service = create_pipeline_service(
            _blank_config(**self.TAILOR_ON_OPENAI), preset_name="standard"
        )
        assert service._stage_configs[3].model == "gpt-6.1-sol"
        assert service._stage_configs[3].provider == "openai"

    def test_the_other_stages_keep_the_presets_models(self) -> None:
        service = create_pipeline_service(
            _blank_config(**self.TAILOR_ON_OPENAI), preset_name="standard"
        )
        models = _models(service)
        assert models[:2] + models[3:] == _SMART_MIX[:2] + _SMART_MIX[3:]

    @pytest.mark.parametrize(
        "preset", ["concise", "standard", "comprehensive", "premium", "default"]
    )
    def test_every_preset_honours_the_override(self, preset: str) -> None:
        service = create_pipeline_service(
            _blank_config(**self.TAILOR_ON_OPENAI), preset_name=preset
        )
        assert service._stage_configs[3].model == "gpt-6.1-sol"

    def test_the_override_still_creates_its_provider(self) -> None:
        service = create_pipeline_service(
            _blank_config(**self.TAILOR_ON_OPENAI), preset_name="standard"
        )
        assert set(service._providers) == {"anthropic", "openai"}

    def test_a_model_profile_on_the_command_line_beats_the_override(self) -> None:
        service = create_pipeline_service(
            _blank_config(**self.TAILOR_ON_OPENAI),
            preset_name="standard",
            model_profile="google",
        )
        assert service._stage_configs[3].provider == "google"

    def test_a_configured_temperature_is_applied(self) -> None:
        config = _blank_config(**{"pipeline.stages.tailor": {"temperature": 0.9}})
        service = create_pipeline_service(config, preset_name="standard")
        assert service._stage_configs[3].temperature == 0.9
        assert service._stage_configs[3].model == "claude-opus-5-5"

    def test_an_unresolvable_config_is_a_configuration_error(self) -> None:
        config = _blank_config(**{"pipeline.stages.tailor": {"provider": "nope"}})
        with pytest.raises(ConfigurationError, match="Unknown LLM provider 'nope'"):
            create_pipeline_service(config, preset_name="standard")


class TestCreatePipelineServiceWithPreset:
    """The preset still controls content density on the service."""

    def test_concise_preset_sets_preset_on_service(self) -> None:
        config = _blank_config()
        service = create_pipeline_service(config, preset_name="concise")
        assert service._preset is not None
        assert service._preset.density == ContentDensity.CONCISE

    def test_standard_preset_sets_preset_on_service(self) -> None:
        config = _blank_config()
        service = create_pipeline_service(config, preset_name="standard")
        assert service._preset is not None
        assert service._preset.density == ContentDensity.STANDARD

    def test_comprehensive_preset_sets_preset_on_service(self) -> None:
        config = _blank_config()
        service = create_pipeline_service(config, preset_name="comprehensive")
        assert service._preset is not None
        assert service._preset.density == ContentDensity.COMPREHENSIVE

    def test_budget_preset_sets_the_legacy_preset_on_service(self) -> None:
        service = create_pipeline_service(_blank_config(), preset_name="budget")
        assert service._preset is not None
        assert service._preset.name == "budget"

    def test_default_preset_has_no_preset(self) -> None:
        service = create_pipeline_service(
            _stub_pipeline_config(), preset_name="default"
        )
        assert service._preset is None

    def test_unknown_preset_name_has_no_preset(self) -> None:
        service = create_pipeline_service(_blank_config(), preset_name="nonexistent")
        assert service._preset is None


def _real_config(tmp_path: Path, toml_text: str) -> Dynaconf:
    """A real Dynaconf, so ``get`` and attribute access behave as in production."""
    path = tmp_path / "settings.toml"
    path.write_text(toml_text)
    config = Dynaconf(
        settings_files=[str(path)],
        environments=True,
        default_env="default",
        merge_enabled=True,
    )
    config.set("in_workspace", False)
    config.set("workspace_root", None)
    return config


class TestBuiltinCompatibleProvidersEndToEnd:
    """REQ-OC-10: ``ollama`` and ``openrouter`` keep working by name."""

    def test_ollama_stage_uses_a_compatible_adapter_on_the_local_endpoint(
        self, tmp_path: Path
    ) -> None:
        config = _real_config(
            tmp_path,
            """
[default.pipeline.stages.analyze]
provider = "ollama"
model = "llama3.1:8b"
temperature = 0.2
""",
        )
        service = create_pipeline_service(config, preset_name="default")
        adapter = _unwrap(service._providers["ollama"])
        assert type(adapter) is OpenAICompatibleAdapter
        assert str(adapter._client.base_url).startswith("http://localhost:11434/v1")

    def test_openrouter_stage_uses_a_compatible_adapter_on_the_openrouter_endpoint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "k")
        config = _real_config(
            tmp_path,
            """
[default.pipeline.stages.analyze]
provider = "openrouter"
model = "openai/gpt-4o"
temperature = 0.2
""",
        )
        service = create_pipeline_service(config, preset_name="default")
        adapter = _unwrap(service._providers["openrouter"])
        assert type(adapter) is OpenAICompatibleAdapter
        assert str(adapter._client.base_url).startswith("https://openrouter.ai/api/v1")

    def test_user_defined_provider_can_serve_a_stage(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "gk")
        config = _real_config(
            tmp_path,
            """
[default.providers.groq]
type = "openai-compatible"
base_url = "https://api.groq.com/openai/v1"
api_key_env = "GROQ_API_KEY"

[default.pipeline.stages.analyze]
provider = "groq"
model = "llama-3.3-70b-versatile"
temperature = 0.2
""",
        )
        service = create_pipeline_service(config, preset_name="default")
        adapter = _unwrap(service._providers["groq"])
        assert type(adapter) is OpenAICompatibleAdapter
        assert str(adapter._client.base_url).startswith(
            "https://api.groq.com/openai/v1"
        )


class TestCatalogInjection:
    """The factory loads the catalog once and hands it to the services."""

    OVERRIDE: ClassVar[list[dict[str, Any]]] = [
        {
            "provider": "anthropic",
            "match": "claude-opus-5-5",
            "input_price_per_mtok": 100.0,
        }
    ]

    def test_pipeline_service_receives_the_loaded_catalog(self) -> None:
        config = _blank_config(model_catalog=self.OVERRIDE)
        service = create_pipeline_service(config, preset_name="standard")
        assert service._catalog is not None
        assert service._catalog.price_for("claude-opus-5-5", provider="anthropic") == (
            100.0,
            20.0,
        )

    def test_pipeline_service_catalog_defaults_to_the_builtin_entries(self) -> None:
        service = create_pipeline_service(_blank_config(), preset_name="standard")
        assert service._catalog is not None
        assert service._catalog.price_for("claude-opus-5-5", provider="anthropic") == (
            4.0,
            20.0,
        )

    def test_cover_letter_service_receives_the_loaded_catalog(self) -> None:
        config = _blank_config(model_catalog=self.OVERRIDE)
        service = create_cover_letter_service(config)
        assert service._catalog is not None
        assert service._catalog.price_for("claude-opus-5-5", provider="anthropic") == (
            100.0,
            20.0,
        )

    def test_invalid_catalog_override_fails_before_any_llm_call(self) -> None:
        config = _blank_config(model_catalog="not a list")
        with pytest.raises(ConfigurationError, match="array of tables"):
            create_pipeline_service(config, preset_name="standard")

    def test_unknown_provider_override_is_a_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError, match="Unknown LLM provider"):
            create_pipeline_service(
                _blank_config(), preset_name="standard", provider_override="nope"
            )


class TestCreateWorkspaceService:
    """Tests for create_workspace_service factory function."""

    def test_returns_workspace_service(self) -> None:
        svc = create_workspace_service()
        assert isinstance(svc, WorkspaceService)

    def test_workspace_service_can_init(self, tmp_path: MagicMock) -> None:
        svc = create_workspace_service()
        assert hasattr(svc, "init_workspace")
        assert hasattr(svc, "setup_application")
        assert hasattr(svc, "list_applications")


class TestCreateRegenerationService:
    """Tests for create_regeneration_service factory function."""

    def _make_stub_config(self, **extra: Any) -> MagicMock:
        """Build a config that resolves to stub provider for all stages."""
        return _stub_pipeline_config(**extra)

    def test_returns_regeneration_service(self) -> None:
        config = self._make_stub_config()
        svc = create_regeneration_service(config)
        assert isinstance(svc, RegenerationService)

    def test_uses_stage3_config(self) -> None:
        config = self._make_stub_config(
            **{
                "pipeline.stages.tailor": {
                    "provider": "stub",
                    "model": "tailor-model-x",
                    "temperature": 0.7,
                }
            }
        )

        svc = create_regeneration_service(config)
        assert svc._model == "tailor-model-x"
        assert svc._temperature == 0.7

    def test_preset_uses_stage3_model(self) -> None:
        config = _blank_config()

        svc = create_regeneration_service(config, preset_name="standard")
        # Standard preset stage 3 uses Opus
        assert "opus" in svc._model
        assert svc._temperature == 0.5

    def test_tailor_config_beats_the_preset(self) -> None:
        config = _blank_config(
            **{
                "pipeline.stages.tailor": {
                    "provider": "stub",
                    "model": "tailor-model-x",
                }
            }
        )
        svc = create_regeneration_service(config, preset_name="standard")
        assert svc._model == "tailor-model-x"

    def test_provider_override_changes_provider(self) -> None:
        config = _blank_config()

        svc = create_regeneration_service(
            config, preset_name="standard", provider_override="stub"
        )
        assert isinstance(svc, RegenerationService)
        # The LLM adapter should be a StubLLMAdapter
        assert isinstance(svc._llm, StubLLMAdapter)

    def test_provider_override_uses_that_providers_tailor_model(self) -> None:
        svc = create_regeneration_service(
            _blank_config(), preset_name="standard", provider_override="openai"
        )
        assert svc._model == "gpt-6-astra"

    def test_model_profile_selects_the_tailor_model(self) -> None:
        svc = create_regeneration_service(
            _blank_config(), preset_name="standard", model_profile="google"
        )
        assert svc._model == "gemini-4-argon"

    def test_only_the_tailor_stage_has_to_resolve(self) -> None:
        config = _blank_config(
            **{"pipeline.stages.analyze": {"provider": "nope"}},
        )
        svc = create_regeneration_service(config, preset_name="standard")
        assert isinstance(svc, RegenerationService)

    def test_default_preset_reads_from_config(self) -> None:
        config = self._make_stub_config()
        svc = create_regeneration_service(config, preset_name="default")
        assert isinstance(svc, RegenerationService)
        assert svc._model == "stub-model"

    def test_has_prompt_loader(self) -> None:
        config = self._make_stub_config()
        svc = create_regeneration_service(config)
        assert svc._prompts is not None


class TestCreateValidationService:
    """REQ-SR-9: validation resolves its own stage."""

    def test_validate_stage_provider_and_model_are_used(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        config = _blank_config(
            validate={"provider": "openai", "model": "gpt-6.1-terra"}
        )
        service = create_validation_service(config)
        assert isinstance(_unwrap(service._llm), OpenAIAdapter)
        assert service._model == "gpt-6.1-terra"

    def test_default_model_comes_from_the_default_profile(self) -> None:
        service = create_validation_service(_blank_config())
        assert service._model == "claude-sonnet-5-5"

    def test_pipeline_analyze_stage_is_not_borrowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        config = _blank_config(
            **{
                "pipeline.stages.analyze": {
                    "provider": "openai",
                    "model": "gpt-6-luna",
                }
            }
        )
        service = create_validation_service(config)
        assert service._model == "claude-sonnet-5-5"
        assert not isinstance(_unwrap(service._llm), OpenAIAdapter)

    def test_model_alone_infers_the_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        config = _blank_config(validate={"model": "gpt-6.1-terra"})
        service = create_validation_service(config)
        assert isinstance(_unwrap(service._llm), OpenAIAdapter)

    def test_unknown_provider_is_a_configuration_error(self) -> None:
        config = _blank_config(validate={"provider": "nope", "model": "m"})
        with pytest.raises(ConfigurationError, match="Unknown LLM provider 'nope'"):
            create_validation_service(config)


class TestCreateCoverLetterService:
    def test_defaults_reproduce_todays_cover_letter_models(self) -> None:
        service = create_cover_letter_service(_blank_config())
        configs = service._stage_configs
        assert [(sc.model, sc.temperature) for sc in configs.values()] == [
            ("claude-opus-5-5", 0.6),
            ("claude-haiku-5-5", 0.2),
        ]

    def test_stages_are_numbered_generate_then_review(self) -> None:
        service = create_cover_letter_service(_blank_config())
        assert list(service._stage_configs) == [1, 2]

    def test_stage_config_is_read_from_the_cover_letter_sections(self) -> None:
        config = _blank_config(
            **{
                "cover_letter.stages.generate": {
                    "provider": "stub",
                    "model": "letter-model",
                    "temperature": 0.4,
                }
            }
        )
        service = create_cover_letter_service(config)
        generate = service._stage_configs[1]
        assert (generate.provider, generate.model, generate.temperature) == (
            "stub",
            "letter-model",
            0.4,
        )
        assert service._stage_configs[2].model == "claude-haiku-5-5"

    def test_provider_override_runs_both_stages_on_that_provider(self) -> None:
        service = create_cover_letter_service(
            _blank_config(), provider_override="openai"
        )
        assert [sc.model for sc in service._stage_configs.values()] == [
            "gpt-6-astra",
            "gpt-6-luna",
        ]

    def test_model_profile_runs_both_stages_on_that_profile(self) -> None:
        service = create_cover_letter_service(_blank_config(), model_profile="google")
        assert [sc.model for sc in service._stage_configs.values()] == [
            "gemini-4-argon",
            "gemini-3.5-flash-lite",
        ]

    def test_economy_preset_keeps_the_cover_letter_models_of_the_base_profile(
        self,
    ) -> None:
        service = create_cover_letter_service(
            _blank_config(), provider_override="openai", preset_name="concise"
        )
        assert service._stage_configs[1].model == "gpt-6-astra"

    def test_unknown_profile_is_a_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError, match="Unknown model profile"):
            create_cover_letter_service(_blank_config(), model_profile="nope")
