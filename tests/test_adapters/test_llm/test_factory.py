"""Tests for factory provider selection logic."""

from unittest.mock import MagicMock

import pytest

from mkcv.adapters.factory import _create_llm_adapter
from mkcv.adapters.llm.anthropic import AnthropicAdapter
from mkcv.adapters.llm.openai import OpenAIAdapter
from mkcv.adapters.llm.retry import RetryingLLMAdapter
from mkcv.adapters.llm.stub import StubLLMAdapter


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

    def test_falls_back_to_stub_when_no_api_key(self) -> None:
        config = _make_config(provider="anthropic")
        adapter = _create_llm_adapter("anthropic", config)
        assert isinstance(adapter, StubLLMAdapter)

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
