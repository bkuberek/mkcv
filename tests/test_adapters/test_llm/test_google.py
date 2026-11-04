"""Tests for GoogleGeminiAdapter (REQ-GG-1 to GG-8, GG-10)."""

import json
import logging
import tomllib
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from google.genai import errors, types
from pydantic import BaseModel, Field

from mkcv.adapters.llm._utils import resolve_schema_refs
from mkcv.adapters.llm.builtin_providers import CANONICAL_PROVIDER, KIND_DEFAULTS
from mkcv.adapters.llm.google import REPAIR_PROMPT as GOOGLE_REPAIR_PROMPT
from mkcv.adapters.llm.google import GoogleGeminiAdapter
from mkcv.adapters.llm.model_resolver import ModelResolver, builtin_resolver
from mkcv.adapters.llm.openai_compatible import REPAIR_PROMPT as OPENAI_REPAIR_PROMPT
from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.exceptions.context_length import ContextLengthError
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.exceptions.rate_limit import RateLimitError
from mkcv.core.exceptions.validation import ValidationError
from mkcv.core.models.model_capability import ModelCapability
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.provider_kind import ProviderKind
from mkcv.core.models.resolved_model import ResolvedModel
from mkcv.core.models.token_usage import TokenUsage
from mkcv.core.ports.llm import LLMPort

MODEL = "gemini-3.8-flash"
MESSAGES = [
    {"role": "system", "content": "You are an analyst."},
    {"role": "user", "content": "Describe it."},
]
VALID_REPLY = json.dumps({"name": "n", "items": [{"label": "a"}]})
REPO_ROOT = Path(__file__).resolve().parents[3]


class Item(BaseModel):
    label: str


class M(BaseModel):
    name: str
    note: str = "x"
    count: int | None = None
    items: list[Item] = Field(default_factory=list)


def _response(
    text: str | None = VALID_REPLY,
    *,
    prompt_tokens: int | None = 120,
    candidate_tokens: int | None = 40,
    thought_tokens: int | None = 300,
    block_reason: str | None = None,
    finish_reason: str | None = "STOP",
) -> types.GenerateContentResponse:
    content = (
        types.Content(role="model", parts=[types.Part(text=text)]) if text else None
    )
    feedback = (
        types.GenerateContentResponsePromptFeedback(block_reason=block_reason)
        if block_reason
        else None
    )
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=content, finish_reason=finish_reason)],
        prompt_feedback=feedback,
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=prompt_tokens,
            candidates_token_count=candidate_tokens,
            thoughts_token_count=thought_tokens,
        ),
    )


def _client_error(code: int, message: str) -> errors.ClientError:
    return errors.ClientError(code, {"error": {"message": message}})


def _adapter(
    *responses: Any, resolver: ModelResolver | None = None
) -> tuple[GoogleGeminiAdapter, AsyncMock]:
    adapter = (
        GoogleGeminiAdapter(api_key="g", resolver=resolver)
        if resolver
        else GoogleGeminiAdapter(api_key="g")
    )
    generate = AsyncMock(side_effect=list(responses))
    adapter._client.aio.models.generate_content = generate  # type: ignore[method-assign]
    return adapter, generate


def _kwargs(generate: AsyncMock, call: int = 0) -> dict[str, Any]:
    kwargs: dict[str, Any] = generate.call_args_list[call].kwargs
    return kwargs


def _config(generate: AsyncMock, call: int = 0) -> types.GenerateContentConfig:
    config = _kwargs(generate, call)["config"]
    assert isinstance(config, types.GenerateContentConfig)
    return config


def _contents(generate: AsyncMock, call: int = 0) -> list[types.Content]:
    contents: list[types.Content] = _kwargs(generate, call)["contents"]
    return contents


def _roles(contents: list[types.Content]) -> list[str | None]:
    return [content.role for content in contents]


def _text_of(content: types.Content) -> str | None:
    assert content.parts is not None
    return content.parts[0].text


async def _structured(
    adapter: GoogleGeminiAdapter,
    *,
    messages: list[dict[str, str]] | None = None,
    model: str = MODEL,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> BaseModel:
    return await adapter.complete_structured(
        messages or MESSAGES,
        model=model,
        response_model=M,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _sampling_resolver() -> ModelResolver:
    """A resolver whose catalog says ``MODEL`` accepts sampling parameters."""
    catalog = ModelCatalog.builtin().with_overrides(
        [
            ModelCapability(
                provider="google",
                match=MODEL,
                accepts_sampling_params=True,
            )
        ]
    )

    def resolve(provider: str, model: str) -> ResolvedModel:
        return catalog.resolve(
            provider,
            model,
            defaults=KIND_DEFAULTS[ProviderKind.GOOGLE],
            canonical_provider=CANONICAL_PROVIDER[ProviderKind.GOOGLE],
        )

    return resolve


class TestConstruction:
    def test_adapter_satisfies_the_llm_port(self) -> None:
        assert isinstance(GoogleGeminiAdapter(api_key="g"), LLMPort)

    def test_api_key_reaches_the_client(self) -> None:
        with patch("mkcv.adapters.llm.google.genai.Client") as client:
            GoogleGeminiAdapter(api_key="secret")
        assert client.call_args.kwargs["api_key"] == "secret"

    def test_base_url_becomes_the_client_http_option(self) -> None:
        with patch("mkcv.adapters.llm.google.genai.Client") as client:
            GoogleGeminiAdapter(api_key="g", base_url="https://proxy.example.com")
        options = client.call_args.kwargs["http_options"]
        assert options.base_url == "https://proxy.example.com"

    def test_no_base_url_leaves_the_http_options_unset(self) -> None:
        with patch("mkcv.adapters.llm.google.genai.Client") as client:
            GoogleGeminiAdapter(api_key="g")
        assert client.call_args.kwargs["http_options"] is None

    def test_default_resolver_is_the_native_google_resolver(self) -> None:
        adapter = GoogleGeminiAdapter(api_key="g")
        expected = builtin_resolver(ProviderKind.GOOGLE)("google", MODEL)
        assert adapter._resolver("google", MODEL) == expected

    async def test_default_provider_name_is_google(self) -> None:
        adapter, _ = _adapter(_client_error(404, "no such model"))
        with pytest.raises(ProviderError) as caught:
            await adapter.complete(MESSAGES, model=MODEL)
        assert caught.value.provider == "google"

    async def test_provider_name_can_be_overridden(self) -> None:
        adapter = GoogleGeminiAdapter(api_key="g", provider_name="my-gemini")
        adapter._client.aio.models.generate_content = AsyncMock(  # type: ignore[method-assign]
            side_effect=_client_error(404, "no such model")
        )
        with pytest.raises(ProviderError) as caught:
            await adapter.complete(MESSAGES, model=MODEL)
        assert caught.value.provider == "my-gemini"

    async def test_custom_resolver_is_honoured(self) -> None:
        def resolver(provider: str, model: str) -> ResolvedModel:
            return builtin_resolver(ProviderKind.GOOGLE)(provider, model).model_copy(
                update={"min_output_tokens": 123}
            )

        adapter, generate = _adapter(_response(), resolver=resolver)
        await _structured(adapter, max_tokens=10)
        assert _config(generate).max_output_tokens == 123


class TestStructuredRequest:
    """REQ-GG-1."""

    async def test_model_is_passed_through(self) -> None:
        adapter, generate = _adapter(_response())
        await _structured(adapter)
        assert _kwargs(generate)["model"] == MODEL

    async def test_conversation_is_one_user_turn(self) -> None:
        adapter, generate = _adapter(_response())
        await _structured(adapter)
        contents = _contents(generate)
        assert (_roles(contents), _text_of(contents[0])) == (["user"], "Describe it.")

    async def test_system_message_becomes_the_system_instruction(self) -> None:
        adapter, generate = _adapter(_response())
        await _structured(adapter)
        assert _config(generate).system_instruction == "You are an analyst."

    async def test_response_is_requested_as_json(self) -> None:
        adapter, generate = _adapter(_response())
        await _structured(adapter)
        assert _config(generate).response_mime_type == "application/json"

    async def test_schema_is_the_inlined_model_schema(self) -> None:
        adapter, generate = _adapter(_response())
        await _structured(adapter)
        expected = resolve_schema_refs(M.model_json_schema())
        assert _config(generate).response_json_schema == expected

    async def test_schema_has_no_references(self) -> None:
        adapter, generate = _adapter(_response())
        await _structured(adapter)
        schema = json.dumps(_config(generate).response_json_schema)
        assert "$ref" not in schema and "$defs" not in schema

    async def test_output_limit_is_raised_to_the_floor(self) -> None:
        adapter, generate = _adapter(_response())
        await _structured(adapter, max_tokens=4096)
        assert _config(generate).max_output_tokens == 16000

    async def test_larger_requests_exceed_the_floor(self) -> None:
        adapter, generate = _adapter(_response())
        await _structured(adapter, max_tokens=20000)
        assert _config(generate).max_output_tokens == 20000

    async def test_temperature_is_omitted_for_models_that_reject_sampling(
        self,
    ) -> None:
        adapter, generate = _adapter(_response())
        await _structured(adapter, temperature=0.3)
        assert _config(generate).temperature is None

    async def test_temperature_is_sent_when_the_catalog_allows_it(self) -> None:
        adapter, generate = _adapter(_response(), resolver=_sampling_resolver())
        await _structured(adapter, temperature=0.3)
        assert _config(generate).temperature == 0.3

    async def test_unknown_models_still_get_a_request(self) -> None:
        adapter, generate = _adapter(_response())
        await _structured(adapter, model="gemini-9-unknown")
        config = _config(generate)
        assert (config.temperature, config.max_output_tokens) == (None, 16000)

    async def test_only_one_call_is_made(self) -> None:
        adapter, generate = _adapter(_response())
        await _structured(adapter)
        assert generate.await_count == 1


class TestRoleMapping:
    """REQ-GG-2."""

    async def test_assistant_turns_become_model_turns(self) -> None:
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": "two"},
            {"role": "user", "content": "three"},
        ]
        adapter, generate = _adapter(_response())
        await _structured(adapter, messages=messages)
        assert _roles(_contents(generate)) == ["user", "model", "user"]

    async def test_turn_texts_are_preserved_in_order(self) -> None:
        messages = [
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": "two"},
        ]
        adapter, generate = _adapter(_response())
        await _structured(adapter, messages=messages)
        assert [_text_of(c) for c in _contents(generate)] == ["one", "two"]

    async def test_system_text_is_not_a_conversation_turn(self) -> None:
        adapter, generate = _adapter(_response())
        await _structured(adapter)
        texts = [_text_of(content) for content in _contents(generate)]
        assert "You are an analyst." not in texts

    async def test_two_system_messages_are_joined_by_a_blank_line(self) -> None:
        messages = [
            {"role": "system", "content": "first"},
            {"role": "system", "content": "second"},
            {"role": "user", "content": "go"},
        ]
        adapter, generate = _adapter(_response())
        await _structured(adapter, messages=messages)
        assert _config(generate).system_instruction == "first\n\nsecond"

    async def test_no_system_message_means_no_system_instruction(self) -> None:
        adapter, generate = _adapter(_response())
        await _structured(adapter, messages=[{"role": "user", "content": "go"}])
        assert _config(generate).system_instruction is None


class TestParsingAndUsage:
    """REQ-GG-3."""

    async def test_valid_json_becomes_the_response_model(self) -> None:
        adapter, _ = _adapter(_response())
        result = await _structured(adapter)
        assert result == M(name="n", items=[Item(label="a")])

    async def test_thinking_tokens_are_billed_as_output(self) -> None:
        adapter, _ = _adapter(_response())
        await _structured(adapter)
        assert adapter.get_last_usage() == TokenUsage(
            input_tokens=120, output_tokens=340
        )

    async def test_missing_thinking_tokens_count_as_zero(self) -> None:
        adapter, _ = _adapter(_response(thought_tokens=None))
        await _structured(adapter)
        assert adapter.get_last_usage() == TokenUsage(
            input_tokens=120, output_tokens=40
        )

    async def test_missing_counts_count_as_zero(self) -> None:
        adapter, _ = _adapter(
            _response(prompt_tokens=None, candidate_tokens=None, thought_tokens=None)
        )
        await _structured(adapter)
        assert adapter.get_last_usage() == TokenUsage()

    async def test_missing_usage_metadata_records_zero_usage(self) -> None:
        response = _response()
        response.usage_metadata = None
        adapter, _ = _adapter(_response(), response)
        await _structured(adapter)
        await _structured(adapter)
        assert adapter.get_last_usage() == TokenUsage()

    async def test_json_in_a_code_fence_is_extracted(self) -> None:
        adapter, _ = _adapter(_response(f"```json\n{VALID_REPLY}\n```"))
        result = await _structured(adapter)
        assert isinstance(result, M)

    async def test_wrapped_payload_is_unwrapped_like_other_adapters(self) -> None:
        adapter, _ = _adapter(_response(json.dumps({"result": {"name": "n"}})))
        result = await _structured(adapter)
        assert isinstance(result, M)


class TestEmptyOrBlockedResponses:
    """REQ-GG-4."""

    async def test_blocked_prompt_raises_a_provider_error(self) -> None:
        adapter, _ = _adapter(_response(text=None, block_reason="SAFETY"))
        with pytest.raises(ProviderError, match="Gemini blocked the prompt"):
            await _structured(adapter)

    async def test_block_reason_is_included(self) -> None:
        adapter, _ = _adapter(_response(text=None, block_reason="SAFETY"))
        with pytest.raises(ProviderError, match="SAFETY"):
            await _structured(adapter)

    async def test_truncated_reply_raises_a_provider_error(self) -> None:
        adapter, _ = _adapter(_response(text=None, finish_reason="MAX_TOKENS"))
        with pytest.raises(ProviderError, match="truncated"):
            await _structured(adapter)

    async def test_truncation_error_names_the_limit_and_the_model(self) -> None:
        adapter, _ = _adapter(_response(text=None, finish_reason="MAX_TOKENS"))
        with pytest.raises(ProviderError, match=rf"16000 tokens for {MODEL}"):
            await _structured(adapter)

    async def test_empty_reply_without_a_signal_raises(self) -> None:
        adapter, _ = _adapter(_response(text=None))
        with pytest.raises(ProviderError, match="Gemini returned no text"):
            await _structured(adapter)

    async def test_no_candidates_means_no_text(self) -> None:
        response = types.GenerateContentResponse(candidates=None)
        adapter, _ = _adapter(response)
        with pytest.raises(ProviderError, match="Gemini returned no text"):
            await _structured(adapter)

    async def test_empty_replies_are_not_repaired(self) -> None:
        adapter, generate = _adapter(_response(text=None))
        with pytest.raises(ProviderError):
            await _structured(adapter)
        assert generate.await_count == 1

    async def test_errors_carry_the_provider_label(self) -> None:
        adapter, _ = _adapter(_response(text=None))
        with pytest.raises(ProviderError) as caught:
            await _structured(adapter)
        assert caught.value.provider == "google"

    async def test_unspecified_block_reason_is_not_a_block(self) -> None:
        adapter, _ = _adapter(
            _response(text=None, block_reason="BLOCKED_REASON_UNSPECIFIED")
        )
        with pytest.raises(ProviderError, match=r"^Gemini returned no text$"):
            await _structured(adapter)

    async def test_unexpected_finish_reason_is_named_in_the_error(self) -> None:
        adapter, _ = _adapter(_response(text=None, finish_reason="SAFETY"))
        with pytest.raises(ProviderError, match=r"no text \(finish reason: SAFETY\)"):
            await _structured(adapter)

    async def test_any_block_reason_is_named_in_the_error(self) -> None:
        adapter, _ = _adapter(_response(text=None, block_reason="OTHER"))
        with pytest.raises(ProviderError, match="blocked the prompt: OTHER"):
            await _structured(adapter)


class TestRepairRetry:
    """REQ-GG-5."""

    async def test_second_response_repairs_the_first(self) -> None:
        adapter, generate = _adapter(_response("nope"), _response())
        result = await _structured(adapter)
        assert (isinstance(result, M), generate.await_count) == (True, 2)

    async def test_repair_call_appends_the_failed_reply_as_a_model_turn(self) -> None:
        adapter, generate = _adapter(_response("nope"), _response())
        await _structured(adapter)
        contents = _contents(generate, 1)
        assert (contents[-2].role, _text_of(contents[-2])) == ("model", "nope")

    async def test_repair_call_ends_with_the_repair_prompt_as_a_user_turn(self) -> None:
        adapter, generate = _adapter(_response("nope"), _response())
        await _structured(adapter)
        last = _contents(generate, 1)[-1]
        assert last.role == "user"
        assert (_text_of(last) or "").startswith(
            "Your previous reply was not valid JSON"
        )

    async def test_repair_call_keeps_the_original_conversation(self) -> None:
        adapter, generate = _adapter(_response("nope"), _response())
        await _structured(adapter)
        first, second = _contents(generate, 0), _contents(generate, 1)
        assert second[: len(first)] == first

    def test_repair_prompt_matches_the_openai_compatible_adapter(self) -> None:
        assert GOOGLE_REPAIR_PROMPT == OPENAI_REPAIR_PROMPT

    async def test_repair_call_keeps_the_structured_config(self) -> None:
        adapter, generate = _adapter(_response("nope"), _response())
        await _structured(adapter)
        assert _config(generate, 1) == _config(generate, 0)

    async def test_usage_is_the_sum_of_both_calls(self) -> None:
        adapter, _ = _adapter(
            _response("nope", prompt_tokens=100, candidate_tokens=10, thought_tokens=0),
            _response(prompt_tokens=130, candidate_tokens=20, thought_tokens=5),
        )
        await _structured(adapter)
        assert adapter.get_last_usage() == TokenUsage(
            input_tokens=230, output_tokens=35
        )

    async def test_two_invalid_responses_raise_a_validation_error(self) -> None:
        adapter, generate = _adapter(_response("nope"), _response("still no"))
        with pytest.raises(ValidationError, match="after one repair attempt"):
            await _structured(adapter)
        assert generate.await_count == 2

    async def test_a_json_array_is_repaired_instead_of_crashing(self) -> None:
        adapter, generate = _adapter(_response('[{"name": "n"}]'), _response())
        await _structured(adapter)
        assert generate.await_count == 2

    async def test_schema_violations_are_repaired_too(self) -> None:
        adapter, generate = _adapter(_response('{"wrong": 1}'), _response())
        await _structured(adapter)
        assert generate.await_count == 2

    async def test_blocked_repair_reply_raises_a_provider_error(self) -> None:
        adapter, _ = _adapter(_response("nope"), _response(None, block_reason="SAFETY"))
        with pytest.raises(ProviderError, match="blocked the prompt"):
            await _structured(adapter)


class TestPlainCompletion:
    """REQ-GG-6."""

    async def test_returns_the_response_text(self) -> None:
        adapter, _ = _adapter(_response("hello"))
        assert await adapter.complete(MESSAGES, model="gemini-4-argon") == "hello"

    async def test_structured_output_fields_are_unset(self) -> None:
        adapter, generate = _adapter(_response("hello"))
        await adapter.complete(MESSAGES, model="gemini-4-argon")
        config = _config(generate)
        assert (config.response_mime_type, config.response_json_schema) == (None, None)

    async def test_system_message_and_limits_are_shaped_like_structured_calls(
        self,
    ) -> None:
        adapter, generate = _adapter(_response("hello"))
        await adapter.complete(MESSAGES, model="gemini-4-argon", max_tokens=100)
        config = _config(generate)
        assert (config.system_instruction, config.max_output_tokens) == (
            "You are an analyst.",
            16000,
        )

    async def test_usage_is_recorded(self) -> None:
        adapter, _ = _adapter(_response("hello"))
        await adapter.complete(MESSAGES, model="gemini-4-argon")
        assert adapter.get_last_usage() == TokenUsage(
            input_tokens=120, output_tokens=340
        )

    async def test_blocked_prompt_raises_instead_of_returning_nothing(self) -> None:
        adapter, _ = _adapter(_response(None, block_reason="SAFETY"))
        with pytest.raises(ProviderError, match="blocked the prompt"):
            await adapter.complete(MESSAGES, model="gemini-4-argon")


class TestErrorMapping:
    """REQ-GG-7."""

    async def test_rate_limit(self) -> None:
        adapter, _ = _adapter(_client_error(429, "quota exceeded"))
        with pytest.raises(RateLimitError) as caught:
            await _structured(adapter)
        assert caught.value.provider == "google"

    @pytest.mark.parametrize("code", [401, 403])
    async def test_authentication_errors(self, code: int) -> None:
        adapter, _ = _adapter(_client_error(code, "bad key"))
        with pytest.raises(AuthenticationError):
            await _structured(adapter)

    @pytest.mark.parametrize(
        "message",
        [
            "The input token count exceeds the maximum number of tokens allowed",
            "Request exceeds the context window",
        ],
    )
    async def test_context_length_errors(self, message: str) -> None:
        adapter, _ = _adapter(_client_error(400, message))
        with pytest.raises(ContextLengthError):
            await _structured(adapter)

    async def test_other_bad_requests_are_plain_provider_errors(self) -> None:
        adapter, _ = _adapter(_client_error(400, "Request contains a bad argument"))
        with pytest.raises(ProviderError) as caught:
            await _structured(adapter)
        assert type(caught.value) is ProviderError

    async def test_server_errors(self) -> None:
        adapter, _ = _adapter(errors.ServerError(500, {"error": {"message": "boom"}}))
        with pytest.raises(ProviderError) as caught:
            await _structured(adapter)
        assert type(caught.value) is ProviderError

    async def test_unlisted_client_errors(self) -> None:
        adapter, _ = _adapter(_client_error(404, "model not found"))
        with pytest.raises(ProviderError) as caught:
            await _structured(adapter)
        assert type(caught.value) is ProviderError

    async def test_message_of_the_sdk_error_is_kept(self) -> None:
        adapter, _ = _adapter(_client_error(404, "model not found"))
        with pytest.raises(ProviderError, match="model not found"):
            await _structured(adapter)

    async def test_original_error_is_chained(self) -> None:
        error = _client_error(429, "quota exceeded")
        adapter, _ = _adapter(error)
        with pytest.raises(RateLimitError) as caught:
            await _structured(adapter)
        assert caught.value.__cause__ is error

    async def test_complete_maps_errors_too(self) -> None:
        adapter, _ = _adapter(_client_error(401, "bad key"))
        with pytest.raises(AuthenticationError):
            await adapter.complete(MESSAGES, model=MODEL)

    async def test_connection_failures_become_provider_errors(self) -> None:
        adapter, _ = _adapter(httpx.ConnectError("name resolution failed"))
        with pytest.raises(ProviderError, match="Cannot connect to google"):
            await _structured(adapter)

    async def test_errors_during_the_repair_call_are_mapped(self) -> None:
        adapter, _ = _adapter(_response("nope"), _client_error(429, "quota exceeded"))
        with pytest.raises(RateLimitError):
            await _structured(adapter)


class TestRequestAdaptation:
    """REQ-GG-8."""

    TEMPERATURE_REJECTION = "Unsupported value: temperature is not supported here."

    async def test_temperature_rejection_is_retried_without_temperature(self) -> None:
        adapter, generate = _adapter(
            _client_error(400, self.TEMPERATURE_REJECTION),
            _response(),
            resolver=_sampling_resolver(),
        )
        result = await _structured(adapter, temperature=0.3)
        assert isinstance(result, M)
        assert (_config(generate, 0).temperature, _config(generate, 1).temperature) == (
            0.3,
            None,
        )

    async def test_adaptation_is_remembered_for_the_model(self) -> None:
        adapter, generate = _adapter(
            _client_error(400, self.TEMPERATURE_REJECTION),
            _response(),
            _response(),
            resolver=_sampling_resolver(),
        )
        await _structured(adapter)
        await _structured(adapter)
        assert _config(generate, 2).temperature is None

    async def test_adaptation_is_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING)
        adapter, _ = _adapter(
            _client_error(400, self.TEMPERATURE_REJECTION),
            _response(),
            resolver=_sampling_resolver(),
        )
        await _structured(adapter)
        assert f"rejected 'temperature' for model {MODEL}" in caplog.text

    async def test_adaptation_applies_to_plain_completions(self) -> None:
        adapter, generate = _adapter(
            _client_error(400, self.TEMPERATURE_REJECTION),
            _response("hi"),
            resolver=_sampling_resolver(),
        )
        assert await adapter.complete(MESSAGES, model=MODEL) == "hi"
        assert _config(generate, 1).temperature is None

    async def test_other_models_keep_their_temperature(self) -> None:
        resolver = _sampling_resolver()
        adapter, generate = _adapter(
            _client_error(400, self.TEMPERATURE_REJECTION),
            _response(),
            _response(),
            resolver=lambda provider, model: resolver(provider, MODEL),
        )
        await _structured(adapter, model=MODEL)
        await _structured(adapter, model="other-model")
        assert _config(generate, 2).temperature == 0.3

    async def test_second_rejection_raises_after_two_calls(self) -> None:
        adapter, generate = _adapter(
            _client_error(400, self.TEMPERATURE_REJECTION),
            _client_error(400, self.TEMPERATURE_REJECTION),
            resolver=_sampling_resolver(),
        )
        with pytest.raises(ProviderError):
            await _structured(adapter)
        assert generate.await_count == 2

    async def test_rejection_of_a_parameter_that_was_not_sent_is_not_retried(
        self,
    ) -> None:
        adapter, generate = _adapter(_client_error(400, self.TEMPERATURE_REJECTION))
        with pytest.raises(ProviderError):
            await _structured(adapter)
        assert generate.await_count == 1

    async def test_the_status_name_alone_does_not_trigger_adaptation(self) -> None:
        error = errors.ClientError(
            400,
            {
                "error": {
                    "message": "temperature is out of range",
                    "status": "INVALID_ARGUMENT",
                }
            },
        )
        adapter, generate = _adapter(error, resolver=_sampling_resolver())
        with pytest.raises(ProviderError):
            await _structured(adapter)
        assert generate.await_count == 1

    async def test_non_400_errors_are_never_adapted(self) -> None:
        adapter, generate = _adapter(
            _client_error(429, self.TEMPERATURE_REJECTION),
            resolver=_sampling_resolver(),
        )
        with pytest.raises(RateLimitError):
            await _structured(adapter)
        assert generate.await_count == 1


class TestDependency:
    """REQ-GG-10."""

    def test_pyproject_requires_google_genai(self) -> None:
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
        assert "google-genai>=2.34.0" in pyproject["project"]["dependencies"]

    def test_lock_file_resolves_google_genai(self) -> None:
        lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text())
        versions = [
            p["version"] for p in lock["package"] if p["name"] == "google-genai"
        ]
        assert versions
        assert tuple(int(part) for part in versions[0].split(".")) >= (2, 34, 0)
