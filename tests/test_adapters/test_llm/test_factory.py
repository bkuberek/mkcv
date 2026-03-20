"""Tests for factory provider selection logic."""

from unittest.mock import MagicMock

import pytest

from mkcv.adapters.factory import (
    _create_llm_adapter,
    _resolve_preset,
    _resolve_stage_configs,
    create_pipeline_service,
    create_workspace_service,
)
from mkcv.adapters.llm.anthropic import AnthropicAdapter
from mkcv.adapters.llm.openai import OpenAIAdapter
from mkcv.adapters.llm.retry import RetryingLLMAdapter
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.core.models.profile_preset import ContentDensity
from mkcv.core.services.workspace import WorkspaceService


def _make_config(
    api_key: str | None = None,
    provider: str = "stub",
) -> MagicMock:
    """Build a mock Configuration with optional API key.

    Simulates Dynaconf's attribute access pattern.
    """
    config = MagicMock()

    # config.providers.<provider>.api_key — only set when api_key is given
    if api_key is not None:
        provider_section = MagicMock()
        provider_section.api_key = api_key
        providers = MagicMock()
        setattr(providers, provider, provider_section)
        config.providers = providers
    else:
        # Simulate missing providers section
        config.providers = None

    return config


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


class TestResolvePreset:
    """Tests for _resolve_preset factory helper."""

    def test_returns_none_for_default(self) -> None:
        config = MagicMock()
        assert _resolve_preset("default", config) is None

    def test_returns_none_for_unknown(self) -> None:
        config = MagicMock()
        assert _resolve_preset("nonexistent", config) is None

    def test_resolves_concise(self) -> None:
        config = MagicMock()
        preset = _resolve_preset("concise", config)
        assert preset is not None
        assert preset.density == ContentDensity.CONCISE

    def test_resolves_standard(self) -> None:
        config = MagicMock()
        preset = _resolve_preset("standard", config)
        assert preset is not None
        assert preset.density == ContentDensity.STANDARD

    def test_resolves_comprehensive(self) -> None:
        config = MagicMock()
        preset = _resolve_preset("comprehensive", config)
        assert preset is not None
        assert preset.density == ContentDensity.COMPREHENSIVE

    def test_resolves_budget_legacy(self) -> None:
        config = MagicMock()
        preset = _resolve_preset("budget", config)
        assert preset is not None
        for sc in preset.stage_configs.values():
            assert sc.provider == "ollama"

    def test_resolves_premium_legacy(self) -> None:
        config = MagicMock()
        preset = _resolve_preset("premium", config)
        assert preset is not None
        assert preset.density == ContentDensity.STANDARD


class TestResolveStageConfigs:
    """Tests for _resolve_stage_configs with preset names."""

    def test_default_preset_reads_from_config(self) -> None:
        config = MagicMock()
        analyze = MagicMock()
        analyze.provider = "anthropic"
        analyze.model = "claude-sonnet-4-20250514"
        analyze.temperature = 0.2
        config.pipeline.stages.analyze = analyze
        config.pipeline.stages.select = analyze
        config.pipeline.stages.tailor = analyze
        config.pipeline.stages.structure = analyze
        config.pipeline.stages.review = analyze

        configs = _resolve_stage_configs(config, preset_name="default")
        assert configs[1].provider == "anthropic"
        assert configs[1].model == "claude-sonnet-4-20250514"

    def test_budget_preset_uses_ollama(self) -> None:
        config = MagicMock()
        configs = _resolve_stage_configs(config, preset_name="budget")
        for stage_num in range(1, 6):
            assert configs[stage_num].provider == "ollama"
            assert configs[stage_num].model == "llama3.1:8b"

    def test_premium_preset_uses_anthropic(self) -> None:
        config = MagicMock()
        configs = _resolve_stage_configs(config, preset_name="premium")
        for stage_num in range(1, 6):
            assert configs[stage_num].provider == "anthropic"
        # Premium maps to standard which uses smart Haiku/Sonnet/Opus mix
        assert "haiku" in configs[1].model
        assert "opus" in configs[2].model
        assert "opus" in configs[3].model
        assert "sonnet" in configs[4].model
        assert "opus" in configs[5].model

    def test_budget_preset_ignores_config_settings(self) -> None:
        config = MagicMock()
        analyze = MagicMock()
        analyze.provider = "openai"
        analyze.model = "gpt-4o"
        analyze.temperature = 0.9
        config.pipeline.stages.analyze = analyze

        configs = _resolve_stage_configs(config, preset_name="budget")
        assert configs[1].provider == "ollama"

    def test_premium_preset_preserves_per_stage_temperatures(self) -> None:
        config = MagicMock()
        configs = _resolve_stage_configs(config, preset_name="premium")
        assert configs[1].temperature == 0.2
        assert configs[3].temperature == 0.5
        assert configs[4].temperature == 0.1

    def test_concise_preset_uses_haiku(self) -> None:
        config = MagicMock()
        configs = _resolve_stage_configs(config, preset_name="concise")
        for stage_num in range(1, 6):
            assert configs[stage_num].provider == "anthropic"
            assert "haiku" in configs[stage_num].model

    def test_standard_preset_uses_smart_mix(self) -> None:
        config = MagicMock()
        configs = _resolve_stage_configs(config, preset_name="standard")
        for stage_num in range(1, 6):
            assert configs[stage_num].provider == "anthropic"
        # Smart mix: stage 1 = Haiku; stages 2,3,5 = Opus; stage 4 = Sonnet
        assert "haiku" in configs[1].model
        assert "opus" in configs[2].model
        assert "opus" in configs[3].model
        assert "sonnet" in configs[4].model
        assert "opus" in configs[5].model

    def test_comprehensive_preset_uses_smart_mix(self) -> None:
        config = MagicMock()
        configs = _resolve_stage_configs(config, preset_name="comprehensive")
        for stage_num in range(1, 6):
            assert configs[stage_num].provider == "anthropic"
        # Smart mix: stage 1 = Haiku; stages 2,3,5 = Opus; stage 4 = Sonnet
        assert "haiku" in configs[1].model
        assert "opus" in configs[2].model
        assert "opus" in configs[3].model
        assert "sonnet" in configs[4].model
        assert "opus" in configs[5].model


class TestCreatePipelineServiceWithPreset:
    """Tests for create_pipeline_service preset_name parameter."""

    def test_budget_preset_creates_ollama_provider(self) -> None:
        config = MagicMock()
        config.providers = None
        config.in_workspace = False
        config.workspace_root = None
        service = create_pipeline_service(config, preset_name="budget")
        assert "ollama" in service._providers

    def test_default_preset_uses_config_providers(self) -> None:
        config = MagicMock()
        config.providers = None
        config.in_workspace = False
        config.workspace_root = None
        analyze = MagicMock()
        analyze.provider = "stub"
        analyze.model = "stub-model"
        analyze.temperature = 0.3
        config.pipeline.stages.analyze = analyze
        config.pipeline.stages.select = analyze
        config.pipeline.stages.tailor = analyze
        config.pipeline.stages.structure = analyze
        config.pipeline.stages.review = analyze

        service = create_pipeline_service(config, preset_name="default")
        assert "stub" in service._providers

    def test_concise_preset_sets_preset_on_service(self) -> None:
        config = MagicMock()
        config.providers = None
        config.in_workspace = False
        config.workspace_root = None
        service = create_pipeline_service(config, preset_name="concise")
        assert service._preset is not None
        assert service._preset.density == ContentDensity.CONCISE

    def test_standard_preset_sets_preset_on_service(self) -> None:
        config = MagicMock()
        config.providers = None
        config.in_workspace = False
        config.workspace_root = None
        service = create_pipeline_service(config, preset_name="standard")
        assert service._preset is not None
        assert service._preset.density == ContentDensity.STANDARD

    def test_comprehensive_preset_sets_preset_on_service(self) -> None:
        config = MagicMock()
        config.providers = None
        config.in_workspace = False
        config.workspace_root = None
        service = create_pipeline_service(config, preset_name="comprehensive")
        assert service._preset is not None
        assert service._preset.density == ContentDensity.COMPREHENSIVE

    def test_default_preset_has_no_preset(self) -> None:
        config = MagicMock()
        config.providers = None
        config.in_workspace = False
        config.workspace_root = None
        analyze = MagicMock()
        analyze.provider = "stub"
        analyze.model = "stub-model"
        analyze.temperature = 0.3
        config.pipeline.stages.analyze = analyze
        config.pipeline.stages.select = analyze
        config.pipeline.stages.tailor = analyze
        config.pipeline.stages.structure = analyze
        config.pipeline.stages.review = analyze

        service = create_pipeline_service(config, preset_name="default")
        assert service._preset is None

    def test_provider_override_changes_all_stages(self) -> None:
        config = MagicMock()
        config.providers = None
        config.in_workspace = False
        config.workspace_root = None
        service = create_pipeline_service(
            config, preset_name="standard", provider_override="openrouter"
        )
        for sc in service._stage_configs.values():
            assert sc.provider == "openrouter"


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
