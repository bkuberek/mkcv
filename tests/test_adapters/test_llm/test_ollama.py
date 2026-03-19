"""Tests for OllamaAdapter."""

from unittest.mock import MagicMock

from mkcv.adapters.factory import _create_llm_adapter
from mkcv.adapters.llm.ollama import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    OllamaAdapter,
    _augment_with_schema,
)
from mkcv.adapters.llm.retry import RetryingLLMAdapter


class TestOllamaAdapter:
    """Tests for OllamaAdapter construction."""

    def test_creates_with_defaults(self) -> None:
        adapter = OllamaAdapter()
        assert adapter._default_model == DEFAULT_OLLAMA_MODEL

    def test_creates_with_custom_model(self) -> None:
        adapter = OllamaAdapter(model="mistral")
        assert adapter._default_model == "mistral"

    def test_creates_with_custom_base_url(self) -> None:
        adapter = OllamaAdapter(base_url="http://remote:11434/v1")
        assert str(adapter._client.base_url) == "http://remote:11434/v1/"

    def test_default_base_url(self) -> None:
        adapter = OllamaAdapter()
        assert DEFAULT_OLLAMA_BASE_URL in str(adapter._client.base_url)


class TestOllamaFactory:
    """Tests for Ollama adapter creation via factory."""

    def test_factory_creates_ollama_adapter(self) -> None:
        config = MagicMock()
        config.providers = None
        adapter = _create_llm_adapter("ollama", config)
        inner = adapter
        if isinstance(adapter, RetryingLLMAdapter):
            inner = adapter._inner
        assert isinstance(inner, OllamaAdapter)

    def test_factory_wraps_ollama_with_retry(self) -> None:
        config = MagicMock()
        config.providers = None
        adapter = _create_llm_adapter("ollama", config)
        assert isinstance(adapter, RetryingLLMAdapter)

    def test_factory_without_retry(self) -> None:
        config = MagicMock()
        config.providers = None
        adapter = _create_llm_adapter("ollama", config, with_retry=False)
        assert isinstance(adapter, OllamaAdapter)


class TestAugmentWithSchema:
    """Tests for the _augment_with_schema helper."""

    def test_adds_schema_to_existing_system_message(self) -> None:
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi"},
        ]
        result = _augment_with_schema(messages, "\nSCHEMA")
        assert result[0]["content"] == "You are helpful.\nSCHEMA"
        assert len(result) == 2

    def test_prepends_system_message_if_missing(self) -> None:
        messages = [{"role": "user", "content": "Hi"}]
        result = _augment_with_schema(messages, "\nSCHEMA")
        assert result[0]["role"] == "system"
        assert "SCHEMA" in result[0]["content"]
        assert len(result) == 2

    def test_preserves_user_messages(self) -> None:
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        result = _augment_with_schema(messages, "\nS")
        assert result[1]["content"] == "Hello"
        assert result[2]["content"] == "Hi"
