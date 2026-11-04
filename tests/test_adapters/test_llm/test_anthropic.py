"""Tests for AnthropicAdapter with mocked SDK."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import anthropic
import pytest

from mkcv.adapters.llm.anthropic import AnthropicAdapter, is_claude_5_family
from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.exceptions.rate_limit import RateLimitError
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.requirement import Requirement

_JD_ANALYSIS_DATA: dict[str, Any] = {
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

_MESSAGES = [
    {"role": "system", "content": "You are precise."},
    {"role": "user", "content": "analyze this JD"},
]


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


def _make_text_block(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_thinking_block() -> MagicMock:
    block = MagicMock()
    block.type = "thinking"
    block.thinking = ""
    return block


def _make_final_message(content: list[Any], stop_reason: str = "end_turn") -> MagicMock:
    final = MagicMock()
    final.content = content
    final.stop_reason = stop_reason
    final.usage = _make_usage()
    return final


def _mock_final_message_stream(final_message: Any) -> MagicMock:
    """Create a stream mock that only exposes the final assembled message."""
    return _mock_tool_stream_with_events([], final_message)


def _sent_kwargs(stream_mock: MagicMock) -> dict[str, Any]:
    kwargs: dict[str, Any] = stream_mock.call_args.kwargs
    return kwargs


class TestIsClaude5Family:
    """Tests for the Claude 5.x model-family check."""

    @pytest.mark.parametrize(
        "model",
        [
            "claude-opus-5-5",
            "claude-sonnet-5-5",
            "claude-haiku-5-5",
            "claude-opus-5",
            "claude-sonnet-5",
            "claude-fable-5-1",
        ],
    )
    def test_claude_5_models_match(self, model: str) -> None:
        assert is_claude_5_family(model)

    @pytest.mark.parametrize(
        "model",
        [
            "claude-opus-4-6",
            "claude-sonnet-4-6",
            "claude-haiku-4-5",
            "claude-sonnet-4-5",
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022",
        ],
    )
    def test_older_models_do_not_match(self, model: str) -> None:
        assert not is_claude_5_family(model)


class TestAnthropicRequestShape:
    """Exact request kwargs per model family."""

    async def test_complete_claude_5_omits_sampling_and_floors_max_tokens(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        stream = _mock_final_message_stream(
            _make_final_message([_make_text_block("ok")])
        )
        anthropic_adapter._client.messages.stream = stream

        await anthropic_adapter.complete(
            _MESSAGES, model="claude-opus-5-5", temperature=0.7, max_tokens=4096
        )

        assert _sent_kwargs(stream) == {
            "model": "claude-opus-5-5",
            "messages": [{"role": "user", "content": "analyze this JD"}],
            "max_tokens": 16000,
            "system": "You are precise.",
        }

    async def test_complete_claude_5_keeps_larger_max_tokens(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        stream = _mock_final_message_stream(
            _make_final_message([_make_text_block("ok")])
        )
        anthropic_adapter._client.messages.stream = stream

        await anthropic_adapter.complete(
            _MESSAGES, model="claude-sonnet-5-5", max_tokens=32000
        )

        assert _sent_kwargs(stream)["max_tokens"] == 32000

    async def test_complete_claude_4_request_is_unchanged(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        stream = _mock_final_message_stream(
            _make_final_message([_make_text_block("ok")])
        )
        anthropic_adapter._client.messages.stream = stream

        await anthropic_adapter.complete(
            _MESSAGES, model="claude-sonnet-4-6", temperature=0.7, max_tokens=4096
        )

        assert _sent_kwargs(stream) == {
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "analyze this JD"}],
            "temperature": 0.7,
            "max_tokens": 4096,
            "system": "You are precise.",
        }

    async def test_structured_claude_5_uses_output_config(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        stream = _mock_final_message_stream(
            _make_final_message([_make_text_block(json.dumps(_JD_ANALYSIS_DATA))])
        )
        anthropic_adapter._client.messages.stream = stream

        await anthropic_adapter.complete_structured(
            _MESSAGES,
            model="claude-sonnet-5-5",
            response_model=JDAnalysis,
            temperature=0.2,
            max_tokens=8192,
        )

        assert _sent_kwargs(stream) == {
            "model": "claude-sonnet-5-5",
            "messages": [{"role": "user", "content": "analyze this JD"}],
            "max_tokens": 16000,
            "system": "You are precise.",
            "output_config": {
                "format": {
                    "type": "json_schema",
                    "schema": anthropic.transform_schema(JDAnalysis),
                }
            },
        }

    async def test_structured_claude_4_keeps_forced_tool_and_temperature(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        final = _make_final_message([])
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "extract_jdanalysis"
        tool_block.input = _JD_ANALYSIS_DATA
        final.content = [tool_block]
        stream = _mock_final_message_stream(final)
        anthropic_adapter._client.messages.stream = stream

        await anthropic_adapter.complete_structured(
            _MESSAGES,
            model="claude-opus-4-6",
            response_model=JDAnalysis,
            temperature=0.2,
            max_tokens=8192,
        )

        sent = _sent_kwargs(stream)
        assert {k: v for k, v in sent.items() if k != "tools"} == {
            "model": "claude-opus-4-6",
            "messages": [{"role": "user", "content": "analyze this JD"}],
            "temperature": 0.2,
            "max_tokens": 8192,
            "system": "You are precise.",
            "tool_choice": {"type": "tool", "name": "extract_jdanalysis"},
        }
        assert [tool["name"] for tool in sent["tools"]] == ["extract_jdanalysis"]


class TestAnthropicThinkingBlocks:
    """Claude 5.x responses carry thinking blocks before the text."""

    async def test_complete_ignores_thinking_blocks(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        final = _make_final_message(
            [_make_thinking_block(), _make_text_block("Hello from Claude 5.5")]
        )
        anthropic_adapter._client.messages.stream = _mock_final_message_stream(final)

        result = await anthropic_adapter.complete(_MESSAGES, model="claude-opus-5-5")

        assert result == "Hello from Claude 5.5"

    async def test_structured_parses_text_after_thinking_block(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        final = _make_final_message(
            [
                _make_thinking_block(),
                _make_text_block(json.dumps(_JD_ANALYSIS_DATA)),
            ]
        )
        anthropic_adapter._client.messages.stream = _mock_final_message_stream(final)

        result = await anthropic_adapter.complete_structured(
            _MESSAGES, model="claude-opus-5-5", response_model=JDAnalysis
        )

        assert isinstance(result, JDAnalysis)
        assert result.company == "TestCo"

    async def test_structured_claude_5_without_text_raises_provider_error(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        final = _make_final_message([_make_thinking_block()])
        anthropic_adapter._client.messages.stream = _mock_final_message_stream(final)

        with pytest.raises(ProviderError):
            await anthropic_adapter.complete_structured(
                _MESSAGES, model="claude-opus-5-5", response_model=JDAnalysis
            )

    async def test_structured_claude_5_truncated_json_raises_provider_error(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        final = _make_final_message(
            [_make_text_block('{"company": "Trunc')], stop_reason="max_tokens"
        )
        anthropic_adapter._client.messages.stream = _mock_final_message_stream(final)

        with pytest.raises(ProviderError, match="max_tokens"):
            await anthropic_adapter.complete_structured(
                _MESSAGES, model="claude-opus-5-5", response_model=JDAnalysis
            )


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
