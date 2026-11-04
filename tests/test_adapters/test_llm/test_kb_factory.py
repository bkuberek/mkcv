"""Tests for create_kb_generation_service factory function."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from mkcv.adapters.factory import create_kb_generation_service
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.core.exceptions.configuration import ConfigurationError
from mkcv.core.services.kb_generation_service import KBGenerationService


def _make_config(
    provider: str = "stub",
    api_key: str | None = None,
    **values: Any,
) -> MagicMock:
    """Build a mock Configuration for KB generation tests.

    Lookups go through ``config.get``; nothing is configured except an
    optional config-file API key and whatever ``values`` names (for example
    ``kb={...}`` for the ``[kb]`` section).
    """
    config = MagicMock()

    configured: dict[str, Any] = dict(values)
    if api_key is not None:
        configured["providers"] = {provider: {"api_key": api_key}}
    config.get.side_effect = lambda key, default=None: configured.get(key, default)
    config.providers = None
    config.in_workspace = False
    config.workspace_root = None

    return config


class TestCreateKBGenerationService:
    """Tests for the create_kb_generation_service factory."""

    def test_returns_kb_generation_service(self) -> None:
        config = _make_config()
        service = create_kb_generation_service(config)
        assert isinstance(service, KBGenerationService)

    def test_uses_stub_when_no_api_key(self) -> None:
        config = _make_config()
        service = create_kb_generation_service(config)
        # When no API key, anthropic falls back to stub
        assert isinstance(service._llm, StubLLMAdapter) or hasattr(
            service._llm, "_inner"
        )

    def test_provider_override(self) -> None:
        config = _make_config()
        service = create_kb_generation_service(config, provider_override="stub")
        assert isinstance(service, KBGenerationService)
        assert isinstance(service._llm, StubLLMAdapter)

    def test_model_override(self) -> None:
        config = _make_config()
        service = create_kb_generation_service(config, model_override="test-model-xyz")
        assert service._model == "test-model-xyz"

    def test_default_model_comes_from_the_default_profile(self) -> None:
        config = _make_config()
        service = create_kb_generation_service(config)
        assert service._model == "claude-sonnet-5-5"

    def test_default_sampling_and_limits(self) -> None:
        service = create_kb_generation_service(_make_config())
        assert (
            service._temperature,
            service._max_tokens,
            service._chunk_threshold,
        ) == (0.3, 8192, 100000)

    def test_provider_override_uses_that_providers_recommended_model(self) -> None:
        service = create_kb_generation_service(
            _make_config(), provider_override="google"
        )
        assert service._model == "gemini-3.8-flash"

    def test_provider_and_model_override_together(self) -> None:
        service = create_kb_generation_service(
            _make_config(),
            provider_override="stub",
            model_override="test-model-xyz",
        )
        assert isinstance(service._llm, StubLLMAdapter)
        assert service._model == "test-model-xyz"

    def test_unknown_provider_override_is_a_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError, match="Unknown LLM provider"):
            create_kb_generation_service(_make_config(), provider_override="nope")

    def test_non_numeric_limits_are_a_configuration_error(self) -> None:
        config = _make_config(kb={"max_tokens": "lots"})
        with pytest.raises(ConfigurationError, match="max_tokens"):
            create_kb_generation_service(config)

    def test_has_document_reader(self) -> None:
        config = _make_config()
        service = create_kb_generation_service(config)
        assert service._reader is not None

    def test_has_prompt_loader(self) -> None:
        config = _make_config()
        service = create_kb_generation_service(config)
        assert service._prompts is not None

    def test_kb_config_section_used(self) -> None:
        """When [kb] section exists in config, its values are used."""
        config = _make_config(
            kb={
                "provider": "stub",
                "model": "custom-kb-model",
                "temperature": 0.5,
                "max_tokens": 4096,
                "chunk_threshold": 50000,
            }
        )

        service = create_kb_generation_service(config)
        assert service._model == "custom-kb-model"
        assert service._temperature == 0.5
        assert service._max_tokens == 4096
        assert service._chunk_threshold == 50000
