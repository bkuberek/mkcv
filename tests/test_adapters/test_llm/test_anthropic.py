"""Tests for AnthropicAdapter with mocked SDK."""

import json
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import anthropic
import httpx
import pytest

from mkcv.adapters.llm.anthropic import (
    CLAUDE_5_MIN_MAX_TOKENS,
    AnthropicAdapter,
    uses_strict_request_rules,
)
from mkcv.adapters.llm.builtin_providers import KIND_DEFAULTS
from mkcv.adapters.llm.model_resolver import ModelResolver, builtin_resolver
from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.exceptions.context_length import ContextLengthError
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.exceptions.rate_limit import RateLimitError
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.model_capability import ModelCapability
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.provider_kind import ProviderKind
from mkcv.core.models.requirement import Requirement
from mkcv.core.models.resolved_model import ResolvedModel
from mkcv.core.models.structured_output_mode import StructuredOutputMode

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
            "claude-mythos-5-1",
            "claude-opus-4-7",
            "claude-opus-4-8",
        ],
    )
    def test_strict_rule_models_match(self, model: str) -> None:
        assert uses_strict_request_rules(model)

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
        assert not uses_strict_request_rules(model)


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


# ---------------------------------------------------------------------------
# Capability-driven request shaping (REQ-CAT-9, design section 7.1)
# ---------------------------------------------------------------------------

_FICTIONAL_MODEL = "claude-test-1"


def _resolver_for(*entries: ModelCapability) -> ModelResolver:
    """Resolve against a catalog holding only ``entries`` plus Anthropic defaults."""
    catalog = ModelCatalog(entries)

    def resolve(provider: str, model: str) -> ResolvedModel:
        return catalog.resolve(
            provider,
            model,
            defaults=KIND_DEFAULTS[ProviderKind.ANTHROPIC],
            canonical_provider="anthropic",
        )

    return resolve


def _fictional(**fields: Any) -> ModelCapability:
    return ModelCapability(provider="anthropic", match=_FICTIONAL_MODEL, **fields)


def _tool_final_message() -> MagicMock:
    final = _make_final_message([])
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "extract_jdanalysis"
    tool_block.input = _JD_ANALYSIS_DATA
    final.content = [tool_block]
    return final


def _text_final_message() -> MagicMock:
    return _make_final_message([_make_text_block(json.dumps(_JD_ANALYSIS_DATA))])


def _bad_request(message: str) -> anthropic.BadRequestError:
    response = httpx.Response(
        400, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    )
    return anthropic.BadRequestError(message, response=response, body=None)


class _FailingStream:
    """A stream whose request is rejected when it is entered (as the SDK does)."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def __aenter__(self) -> "_FailingStream":
        raise self._error

    async def __aexit__(self, *args: object) -> None:
        pass


def _stream_sequence(*streams: Any) -> MagicMock:
    """A ``messages.stream`` mock that hands out ``streams`` one per call."""
    return MagicMock(side_effect=list(streams))


def _ok_stream(final: Any) -> Any:
    return _mock_final_message_stream(final).return_value


class TestStrictRulesComeFromTheCatalog:
    """REQ-CAT-9: ``uses_strict_request_rules`` keeps its pre-catalog answers."""

    @pytest.mark.parametrize(
        ("model", "expected"),
        [
            ("claude-opus-5-5", True),
            ("claude-sonnet-5-5", True),
            ("claude-haiku-5-5", True),
            ("claude-fable-5-1", True),
            ("claude-mythos-5-1", True),
            ("claude-opus-4-7", True),
            ("claude-opus-4-8", True),
            ("claude-sonnet-5", True),
            ("claude-opus-4-6", False),
            ("claude-sonnet-4-6", False),
            ("claude-haiku-4-5", False),
            ("claude-sonnet-4-20250514", False),
        ],
    )
    def test_strict_rules_table(self, model: str, expected: bool) -> None:
        assert uses_strict_request_rules(model) is expected

    def test_unknown_claude_model_gets_the_conservative_strict_defaults(self) -> None:
        assert uses_strict_request_rules("claude-future-9") is True

    def test_output_floor_constant_is_still_exported(self) -> None:
        assert CLAUDE_5_MIN_MAX_TOKENS == 16_000


class TestAdapterConstruction:
    def test_default_resolver_is_the_builtin_anthropic_resolver(self) -> None:
        adapter = AnthropicAdapter(api_key="k")
        expected = builtin_resolver(ProviderKind.ANTHROPIC)(
            "anthropic", "claude-opus-5-5"
        )
        assert adapter._resolver("anthropic", "claude-opus-5-5") == expected

    def test_base_url_is_passed_to_the_client(self) -> None:
        adapter = AnthropicAdapter(api_key="k", base_url="https://proxy.example")
        assert str(adapter._client.base_url).startswith("https://proxy.example")

    @pytest.mark.parametrize(
        ("kwargs", "expected_provider"),
        [({}, "anthropic"), ({"provider_name": "my-claude"}, "my-claude")],
    )
    async def test_errors_carry_the_provider_name(
        self, kwargs: dict[str, str], expected_provider: str
    ) -> None:
        adapter = AnthropicAdapter(api_key="k", **kwargs)
        response = httpx.Response(
            429, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        )
        adapter._client.messages.stream = MagicMock(
            side_effect=anthropic.RateLimitError("slow", response=response, body=None)
        )
        with pytest.raises(RateLimitError) as caught:
            await adapter.complete(_MESSAGES, model="claude-sonnet-4-6")
        assert caught.value.provider == expected_provider


class TestCapabilityDrivenRequests:
    """The catalog, not model-name prefixes, decides how a request is shaped."""

    async def test_forced_tool_with_temperature_for_a_tool_mode_model(self) -> None:
        resolver = _resolver_for(
            _fictional(
                structured_output=StructuredOutputMode.TOOL,
                accepts_sampling_params=True,
                min_output_tokens=0,
            )
        )
        adapter = AnthropicAdapter(api_key="k", resolver=resolver)
        stream = _mock_final_message_stream(_tool_final_message())
        adapter._client.messages.stream = stream

        await adapter.complete_structured(
            _MESSAGES,
            model=_FICTIONAL_MODEL,
            response_model=JDAnalysis,
            temperature=0.2,
            max_tokens=8192,
        )

        sent = _sent_kwargs(stream)
        assert sent["temperature"] == 0.2
        assert sent["max_tokens"] == 8192
        assert sent["tool_choice"] == {"type": "tool", "name": "extract_jdanalysis"}
        assert "output_config" not in sent

    async def test_output_config_without_temperature_for_a_json_schema_model(
        self,
    ) -> None:
        resolver = _resolver_for(
            _fictional(
                structured_output=StructuredOutputMode.JSON_SCHEMA,
                accepts_sampling_params=False,
                min_output_tokens=16000,
            )
        )
        adapter = AnthropicAdapter(api_key="k", resolver=resolver)
        stream = _mock_final_message_stream(_text_final_message())
        adapter._client.messages.stream = stream

        await adapter.complete_structured(
            _MESSAGES,
            model=_FICTIONAL_MODEL,
            response_model=JDAnalysis,
            temperature=0.2,
            max_tokens=4096,
        )

        sent = _sent_kwargs(stream)
        assert "temperature" not in sent
        assert sent["max_tokens"] == 16000
        assert sent["output_config"]["format"]["type"] == "json_schema"
        assert "tools" not in sent

    @pytest.mark.parametrize(
        "mode", [StructuredOutputMode.JSON_OBJECT, StructuredOutputMode.PROMPT]
    )
    async def test_non_schema_modes_use_the_forced_tool(
        self, mode: StructuredOutputMode
    ) -> None:
        resolver = _resolver_for(
            _fictional(
                structured_output=mode,
                accepts_sampling_params=True,
                min_output_tokens=0,
            )
        )
        adapter = AnthropicAdapter(api_key="k", resolver=resolver)
        stream = _mock_final_message_stream(_tool_final_message())
        adapter._client.messages.stream = stream

        await adapter.complete_structured(
            _MESSAGES, model=_FICTIONAL_MODEL, response_model=JDAnalysis
        )

        assert "tool_choice" in _sent_kwargs(stream)

    async def test_unknown_model_defaults_to_strict_output_config_rules(self) -> None:
        adapter = AnthropicAdapter(api_key="k")
        stream = _mock_final_message_stream(_text_final_message())
        adapter._client.messages.stream = stream

        await adapter.complete_structured(
            _MESSAGES,
            model="claude-future-9",
            response_model=JDAnalysis,
            temperature=0.2,
            max_tokens=4096,
        )

        sent = _sent_kwargs(stream)
        assert "temperature" not in sent
        assert sent["max_tokens"] == 16000
        assert "output_config" in sent

    async def test_complete_sends_temperature_only_when_the_catalog_allows_it(
        self,
    ) -> None:
        resolver = _resolver_for(
            _fictional(accepts_sampling_params=True, min_output_tokens=0)
        )
        adapter = AnthropicAdapter(api_key="k", resolver=resolver)
        stream = _mock_final_message_stream(
            _make_final_message([_make_text_block("ok")])
        )
        adapter._client.messages.stream = stream

        await adapter.complete(
            _MESSAGES, model=_FICTIONAL_MODEL, temperature=0.9, max_tokens=1000
        )

        sent = _sent_kwargs(stream)
        assert (sent["temperature"], sent["max_tokens"]) == (0.9, 1000)

    async def test_catalog_ceiling_caps_the_output_limit(self) -> None:
        resolver = _resolver_for(
            _fictional(accepts_sampling_params=False, max_output_tokens=8000)
        )
        adapter = AnthropicAdapter(api_key="k", resolver=resolver)
        stream = _mock_final_message_stream(
            _make_final_message([_make_text_block("ok")])
        )
        adapter._client.messages.stream = stream

        await adapter.complete(_MESSAGES, model=_FICTIONAL_MODEL, max_tokens=4096)

        assert _sent_kwargs(stream)["max_tokens"] == 8000

    async def test_resolver_receives_the_provider_name_and_model(self) -> None:
        seen: list[tuple[str, str]] = []
        inner = builtin_resolver(ProviderKind.ANTHROPIC)

        def resolver(provider: str, model: str) -> ResolvedModel:
            seen.append((provider, model))
            return inner(provider, model)

        adapter = AnthropicAdapter(api_key="k", resolver=resolver, provider_name="mine")
        adapter._client.messages.stream = _mock_final_message_stream(
            _make_final_message([_make_text_block("ok")])
        )
        await adapter.complete(_MESSAGES, model="claude-opus-5-5")
        assert seen == [("mine", "claude-opus-5-5")]


class TestTemperatureAdaptation:
    """A 400 that names ``temperature`` is retried once without it."""

    REJECTION = "`temperature` is not supported for this model"

    async def test_complete_retries_once_without_temperature(self) -> None:
        adapter = AnthropicAdapter(api_key="k")
        final = _make_final_message([_make_text_block("ok")])
        stream = _stream_sequence(
            _FailingStream(_bad_request(self.REJECTION)), _ok_stream(final)
        )
        adapter._client.messages.stream = stream

        result = await adapter.complete(
            _MESSAGES, model="claude-sonnet-4-6", temperature=0.7
        )

        assert result == "ok"
        assert stream.call_count == 2
        assert stream.call_args_list[0].kwargs["temperature"] == 0.7
        assert "temperature" not in stream.call_args_list[1].kwargs

    async def test_forced_tool_structured_call_adapts_too(self) -> None:
        adapter = AnthropicAdapter(api_key="k")
        stream = _stream_sequence(
            _FailingStream(_bad_request(self.REJECTION)),
            _ok_stream(_tool_final_message()),
        )
        adapter._client.messages.stream = stream

        result = await adapter.complete_structured(
            _MESSAGES, model="claude-opus-4-6", response_model=JDAnalysis
        )

        assert isinstance(result, JDAnalysis)
        retry = stream.call_args_list[1].kwargs
        assert "temperature" not in retry
        assert "tool_choice" in retry

    async def test_output_config_structured_call_adapts_too(self) -> None:
        resolver = _resolver_for(
            _fictional(
                structured_output=StructuredOutputMode.JSON_SCHEMA,
                accepts_sampling_params=True,
                min_output_tokens=0,
            )
        )
        adapter = AnthropicAdapter(api_key="k", resolver=resolver)
        stream = _stream_sequence(
            _FailingStream(_bad_request(self.REJECTION)),
            _ok_stream(_text_final_message()),
        )
        adapter._client.messages.stream = stream

        await adapter.complete_structured(
            _MESSAGES, model=_FICTIONAL_MODEL, response_model=JDAnalysis
        )

        retry = stream.call_args_list[1].kwargs
        assert "temperature" not in retry
        assert "output_config" in retry

    async def test_adaptation_is_remembered_for_the_model(self) -> None:
        adapter = AnthropicAdapter(api_key="k")
        final = _make_final_message([_make_text_block("ok")])
        stream = _stream_sequence(
            _FailingStream(_bad_request(self.REJECTION)),
            _ok_stream(final),
            _ok_stream(final),
        )
        adapter._client.messages.stream = stream

        await adapter.complete(_MESSAGES, model="claude-sonnet-4-6")
        await adapter.complete(_MESSAGES, model="claude-sonnet-4-6")

        assert "temperature" not in stream.call_args_list[2].kwargs

    async def test_adaptation_does_not_leak_to_other_models(self) -> None:
        adapter = AnthropicAdapter(api_key="k")
        final = _make_final_message([_make_text_block("ok")])
        stream = _stream_sequence(
            _FailingStream(_bad_request(self.REJECTION)),
            _ok_stream(final),
            _ok_stream(final),
        )
        adapter._client.messages.stream = stream

        await adapter.complete(_MESSAGES, model="claude-sonnet-4-6")
        await adapter.complete(_MESSAGES, model="claude-opus-4-6")

        assert "temperature" in stream.call_args_list[2].kwargs

    async def test_second_rejection_raises_after_two_calls(self) -> None:
        adapter = AnthropicAdapter(api_key="k")
        stream = _stream_sequence(
            _FailingStream(_bad_request(self.REJECTION)),
            _FailingStream(_bad_request(self.REJECTION)),
        )
        adapter._client.messages.stream = stream

        with pytest.raises(ProviderError):
            await adapter.complete(_MESSAGES, model="claude-sonnet-4-6")
        assert stream.call_count == 2

    async def test_rejection_is_not_retried_when_no_temperature_was_sent(self) -> None:
        adapter = AnthropicAdapter(api_key="k")
        stream = _stream_sequence(_FailingStream(_bad_request(self.REJECTION)))
        adapter._client.messages.stream = stream

        with pytest.raises(ProviderError):
            await adapter.complete(_MESSAGES, model="claude-opus-5-5")
        assert stream.call_count == 1

    async def test_unrelated_bad_request_is_not_retried(self) -> None:
        adapter = AnthropicAdapter(api_key="k")
        stream = _stream_sequence(_FailingStream(_bad_request("model not found")))
        adapter._client.messages.stream = stream

        with pytest.raises(ProviderError):
            await adapter.complete(_MESSAGES, model="claude-sonnet-4-6")
        assert stream.call_count == 1

    async def test_context_length_errors_still_map_in_complete(self) -> None:
        adapter = AnthropicAdapter(api_key="k")
        adapter._client.messages.stream = _stream_sequence(
            _FailingStream(_bad_request("prompt is too long: 300000 tokens"))
        )
        with pytest.raises(ContextLengthError):
            await adapter.complete(_MESSAGES, model="claude-sonnet-4-6")

    async def test_adaptation_is_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING)
        adapter = AnthropicAdapter(api_key="k")
        final = _make_final_message([_make_text_block("ok")])
        adapter._client.messages.stream = _stream_sequence(
            _FailingStream(_bad_request(self.REJECTION)), _ok_stream(final)
        )

        await adapter.complete(_MESSAGES, model="claude-sonnet-4-6")

        assert (
            "anthropic rejected 'temperature' for model claude-sonnet-4-6; "
            "retrying without it"
        ) in caplog.text
