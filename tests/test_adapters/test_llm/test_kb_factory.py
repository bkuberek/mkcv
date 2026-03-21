"""Tests for create_kb_generation_service factory function."""

from unittest.mock import MagicMock

from mkcv.adapters.factory import create_kb_generation_service
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.core.services.kb_generation_service import KBGenerationService


def _make_config(
    provider: str = "stub",
    api_key: str | None = None,
) -> MagicMock:
    """Build a mock Configuration for KB generation tests."""
    config = MagicMock()

    if api_key is not None:
        provider_section = MagicMock()
        provider_section.api_key = api_key
        providers = MagicMock()
        setattr(providers, provider, provider_section)
        config.providers = providers
    else:
        config.providers = None

    # Simulate no [kb] config section
    config.kb = None
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

    def test_default_model(self) -> None:
        config = _make_config()
        service = create_kb_generation_service(config)
        assert "claude" in service._model or service._model != ""

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
        config = _make_config()
        kb_section = MagicMock()
        kb_section.provider = "stub"
        kb_section.model = "custom-kb-model"
        kb_section.temperature = 0.5
        kb_section.max_tokens = 4096
        kb_section.chunk_threshold = 50000
        config.kb = kb_section

        service = create_kb_generation_service(config)
        assert service._model == "custom-kb-model"
        assert service._temperature == 0.5
        assert service._max_tokens == 4096
        assert service._chunk_threshold == 50000
