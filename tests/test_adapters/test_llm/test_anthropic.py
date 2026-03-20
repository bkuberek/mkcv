"""Tests for AnthropicAdapter with mocked SDK."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import anthropic
import pytest

from mkcv.adapters.llm.anthropic import AnthropicAdapter
from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.exceptions.rate_limit import RateLimitError
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.requirement import Requirement


@pytest.fixture
def anthropic_adapter() -> AnthropicAdapter:
    return AnthropicAdapter(api_key="test-key")


def _mock_text_stream(
    text: str,
    final_message: Any,
) -> AsyncMock:
    """Create a mock for client.messages.stream() that yields text."""

    class _FakeStream:
        async def __aenter__(self) -> "_FakeStream":
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        @property
        def text_stream(self) -> "_FakeTextIter":
            return _FakeTextIter(text)

        async def __aiter__(self) -> Any:
            return self

        async def get_final_message(self) -> Any:
            return final_message

    class _FakeTextIter:
        def __init__(self, t: str) -> None:
            self._text = t

        def __aiter__(self) -> "_FakeTextIter":
            return self

        async def __anext__(self) -> str:
            if self._text:
                chunk = self._text
                self._text = ""
                return chunk
            raise StopAsyncIteration

    return MagicMock(return_value=_FakeStream())


def _mock_tool_stream(
    tool_input: dict[str, Any],
    final_message: Any,
) -> AsyncMock:
    """Create a mock for client.messages.stream() with tool_use output."""

    class _FakeStream:
        async def __aenter__(self) -> "_FakeStream":
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        def __aiter__(self) -> "_FakeStream":
            return self

        async def __anext__(self) -> Any:
            raise StopAsyncIteration

        async def get_final_message(self) -> Any:
            return final_message

    return MagicMock(return_value=_FakeStream())


def _mock_tool_stream_with_events(
    events: list[Any],
    final_message: Any,
) -> MagicMock:
    """Create a mock for client.messages.stream() that yields arbitrary events."""

    class _FakeStream:
        async def __aenter__(self) -> "_FakeStream":
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        def __aiter__(self) -> "_FakeStream":
            self._iter = iter(events)
            return self

        async def __anext__(self) -> Any:
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration from None

        async def get_final_message(self) -> Any:
            return final_message

    return MagicMock(return_value=_FakeStream())


def _make_input_json_delta_event(partial_json: str) -> MagicMock:
    """Create a fake content_block_delta event with input_json_delta."""
    event = MagicMock()
    event.type = "content_block_delta"
    event.delta.type = "input_json_delta"
    event.delta.partial_json = partial_json
    return event


def _make_usage(input_tokens: int = 100, output_tokens: int = 50) -> MagicMock:
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    return usage


class TestAnthropicComplete:
    """Tests for AnthropicAdapter.complete (streaming)."""

    async def test_complete_returns_text(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = "Hello from Claude"

        mock_final = MagicMock()
        mock_final.content = [mock_block]
        mock_final.usage = _make_usage()

        anthropic_adapter._client.messages.stream = _mock_text_stream(
            "Hello from Claude", mock_final
        )

        result = await anthropic_adapter.complete(
            [{"role": "user", "content": "hi"}],
            model="claude-sonnet-4-20250514",
        )
        assert result == "Hello from Claude"

    async def test_complete_maps_rate_limit_error(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}

        anthropic_adapter._client.messages.stream = MagicMock(
            side_effect=anthropic.RateLimitError(
                message="rate limited",
                response=mock_response,
                body=None,
            )
        )

        with pytest.raises(RateLimitError):
            await anthropic_adapter.complete(
                [{"role": "user", "content": "hi"}],
                model="claude-sonnet-4-20250514",
            )

    async def test_complete_maps_auth_error(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.headers = {}

        anthropic_adapter._client.messages.stream = MagicMock(
            side_effect=anthropic.AuthenticationError(
                message="invalid api key",
                response=mock_response,
                body=None,
            )
        )

        with pytest.raises(AuthenticationError):
            await anthropic_adapter.complete(
                [{"role": "user", "content": "hi"}],
                model="claude-sonnet-4-20250514",
            )

    async def test_complete_tracks_token_usage(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        mock_final = MagicMock()
        mock_final.content = []
        mock_final.usage = _make_usage(input_tokens=200, output_tokens=75)

        anthropic_adapter._client.messages.stream = _mock_text_stream(
            "response", mock_final
        )

        await anthropic_adapter.complete(
            [{"role": "user", "content": "hi"}],
            model="claude-sonnet-4-20250514",
        )
        usage = anthropic_adapter.get_last_usage()
        assert usage.input_tokens == 200
        assert usage.output_tokens == 75


class TestAnthropicCompleteStructured:
    """Tests for AnthropicAdapter.complete_structured (streaming)."""

    async def test_complete_structured_with_tool_use(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        tool_input = {
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

        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.name = "extract_jdanalysis"
        mock_block.input = tool_input

        mock_final = MagicMock()
        mock_final.content = [mock_block]
        mock_final.usage = _make_usage()

        anthropic_adapter._client.messages.stream = _mock_tool_stream(
            tool_input, mock_final
        )

        result = await anthropic_adapter.complete_structured(
            [{"role": "user", "content": "analyze this JD"}],
            model="claude-sonnet-4-20250514",
            response_model=JDAnalysis,
        )

        assert isinstance(result, JDAnalysis)
        assert result.company == "TestCo"
        assert result.role_title == "Engineer"
        assert len(result.core_requirements) == 1
        assert isinstance(result.core_requirements[0], Requirement)

    async def test_complete_structured_maps_errors(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}

        anthropic_adapter._client.messages.stream = MagicMock(
            side_effect=anthropic.RateLimitError(
                message="rate limited",
                response=mock_response,
                body=None,
            )
        )

        with pytest.raises(RateLimitError):
            await anthropic_adapter.complete_structured(
                [{"role": "user", "content": "analyze"}],
                model="claude-sonnet-4-20250514",
                response_model=JDAnalysis,
            )

    async def test_complete_structured_skips_schema_in_stream(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        """When streamed JSON is the tool schema, fall back to final message."""
        # The actual tool input data we expect
        tool_input = {
            "company": "SchemaCo",
            "role_title": "Developer",
            "seniority_level": "Mid",
            "core_requirements": [
                {
                    "skill": "Go",
                    "importance": "must_have",
                    "context": "Backend",
                }
            ],
            "technical_stack": ["Go"],
            "soft_skills": ["Teamwork"],
            "leadership_signals": [],
            "culture_keywords": [],
            "ats_keywords": ["Go"],
            "hidden_requirements": [],
            "role_summary": "A mid-level developer role.",
        }

        # Simulate streamed fragments assembling into a JSON schema
        schema_data = JDAnalysis.model_json_schema()
        schema_json = json.dumps(schema_data)
        events = [_make_input_json_delta_event(schema_json)]

        # Final message contains the correct tool_use block
        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.name = "extract_jdanalysis"
        mock_block.input = tool_input

        mock_final = MagicMock()
        mock_final.content = [mock_block]
        mock_final.usage = _make_usage()

        anthropic_adapter._client.messages.stream = _mock_tool_stream_with_events(
            events, mock_final
        )

        result = await anthropic_adapter.complete_structured(
            [{"role": "user", "content": "analyze this JD"}],
            model="claude-opus-4-20250514",
            response_model=JDAnalysis,
        )

        assert isinstance(result, JDAnalysis)
        assert result.company == "SchemaCo"
        assert result.role_title == "Developer"

    async def test_complete_structured_accepts_valid_streamed_json(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        """When streamed JSON is valid tool input, use it directly."""
        tool_input = {
            "company": "StreamCo",
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

        tool_json = json.dumps(tool_input)
        events = [_make_input_json_delta_event(tool_json)]

        mock_final = MagicMock()
        mock_final.content = []
        mock_final.usage = _make_usage()

        anthropic_adapter._client.messages.stream = _mock_tool_stream_with_events(
            events, mock_final
        )

        result = await anthropic_adapter.complete_structured(
            [{"role": "user", "content": "analyze this JD"}],
            model="claude-opus-4-20250514",
            response_model=JDAnalysis,
        )

        assert isinstance(result, JDAnalysis)
        assert result.company == "StreamCo"
