"""Tests for OllamaAdapter with mocked SDK."""

import json
from unittest.mock import AsyncMock, MagicMock

import openai
import pytest

from mkcv.adapters.factory import _create_llm_adapter
from mkcv.adapters.llm.ollama import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    OllamaAdapter,
    _augment_with_schema,
)
from mkcv.adapters.llm.retry import RetryingLLMAdapter
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.exceptions.validation import ValidationError
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.requirement import Requirement
from mkcv.core.models.token_usage import TokenUsage


@pytest.fixture
def ollama_adapter() -> OllamaAdapter:
    return OllamaAdapter()


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


def _mock_chat_response(
    content: str,
    *,
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
) -> MagicMock:
    """Build a mock OpenAI-style chat completion response."""
    mock_message = MagicMock()
    mock_message.content = content

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = prompt_tokens
    mock_usage.completion_tokens = completion_tokens

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage
    return mock_response


JD_DATA = {
    "company": "TestCo",
    "role_title": "Engineer",
    "seniority_level": "Senior",
    "core_requirements": [
        {
            "skill": "Python",
            "importance": "must_have",
            "context": "Backend development",
        }
    ],
    "technical_stack": ["Python"],
    "soft_skills": ["Communication"],
    "leadership_signals": [],
    "culture_keywords": [],
    "ats_keywords": ["Python"],
    "hidden_requirements": [],
    "role_summary": "A senior engineer role.",
}


class TestOllamaComplete:
    """Tests for OllamaAdapter.complete."""

    async def test_complete_returns_text(self, ollama_adapter: OllamaAdapter) -> None:
        mock_response = _mock_chat_response("Hello from Llama")
        ollama_adapter._client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        result = await ollama_adapter.complete(
            [{"role": "user", "content": "hi"}],
            model="llama3.1",
        )
        assert result == "Hello from Llama"

    async def test_complete_tracks_token_usage(
        self, ollama_adapter: OllamaAdapter
    ) -> None:
        mock_response = _mock_chat_response(
            "response", prompt_tokens=15, completion_tokens=25
        )
        ollama_adapter._client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        await ollama_adapter.complete(
            [{"role": "user", "content": "hi"}],
            model="llama3.1",
        )

        usage = ollama_adapter.get_last_usage()
        assert isinstance(usage, TokenUsage)
        assert usage.input_tokens == 15
        assert usage.output_tokens == 25

    async def test_complete_handles_connection_error(
        self, ollama_adapter: OllamaAdapter
    ) -> None:
        ollama_adapter._client.chat.completions.create = AsyncMock(
            side_effect=openai.APIConnectionError(request=MagicMock())
        )

        with pytest.raises(ProviderError, match="Cannot connect to Ollama"):
            await ollama_adapter.complete(
                [{"role": "user", "content": "hi"}],
                model="llama3.1",
            )

    async def test_complete_handles_api_error(
        self, ollama_adapter: OllamaAdapter
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = {}

        ollama_adapter._client.chat.completions.create = AsyncMock(
            side_effect=openai.APIStatusError(
                message="internal server error",
                response=mock_response,
                body=None,
            )
        )

        with pytest.raises(ProviderError):
            await ollama_adapter.complete(
                [{"role": "user", "content": "hi"}],
                model="llama3.1",
            )


class TestOllamaCompleteStructured:
    """Tests for OllamaAdapter.complete_structured."""

    async def test_complete_structured_returns_model(
        self, ollama_adapter: OllamaAdapter
    ) -> None:
        mock_response = _mock_chat_response(json.dumps(JD_DATA))
        ollama_adapter._client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        result = await ollama_adapter.complete_structured(
            [{"role": "user", "content": "analyze this JD"}],
            model="llama3.1",
            response_model=JDAnalysis,
        )

        assert isinstance(result, JDAnalysis)
        assert result.company == "TestCo"
        assert result.role_title == "Engineer"
        assert len(result.core_requirements) == 1
        assert isinstance(result.core_requirements[0], Requirement)

    async def test_complete_structured_tracks_token_usage(
        self, ollama_adapter: OllamaAdapter
    ) -> None:
        mock_response = _mock_chat_response(
            json.dumps(JD_DATA), prompt_tokens=50, completion_tokens=100
        )
        ollama_adapter._client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        await ollama_adapter.complete_structured(
            [{"role": "user", "content": "analyze this JD"}],
            model="llama3.1",
            response_model=JDAnalysis,
        )

        usage = ollama_adapter.get_last_usage()
        assert usage.input_tokens == 50
        assert usage.output_tokens == 100

    async def test_complete_structured_handles_parse_error(
        self, ollama_adapter: OllamaAdapter
    ) -> None:
        mock_response = _mock_chat_response("not valid json at all {{{")
        ollama_adapter._client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        with pytest.raises((ProviderError, ValidationError, ValueError)):
            await ollama_adapter.complete_structured(
                [{"role": "user", "content": "analyze this JD"}],
                model="llama3.1",
                response_model=JDAnalysis,
            )

    async def test_complete_structured_handles_connection_error(
        self, ollama_adapter: OllamaAdapter
    ) -> None:
        ollama_adapter._client.chat.completions.create = AsyncMock(
            side_effect=openai.APIConnectionError(request=MagicMock())
        )

        with pytest.raises(ProviderError, match="Cannot connect to Ollama"):
            await ollama_adapter.complete_structured(
                [{"role": "user", "content": "analyze"}],
                model="llama3.1",
                response_model=JDAnalysis,
            )

    async def test_complete_structured_handles_validation_error(
        self, ollama_adapter: OllamaAdapter
    ) -> None:
        incomplete_data = {"company": "TestCo"}
        mock_response = _mock_chat_response(json.dumps(incomplete_data))
        ollama_adapter._client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        with pytest.raises(ValidationError):
            await ollama_adapter.complete_structured(
                [{"role": "user", "content": "analyze this JD"}],
                model="llama3.1",
                response_model=JDAnalysis,
            )
