"""Tests for OpenAICompatibleAdapter and its structured-output fallback chain."""

import json
import logging
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock

import httpx
import openai
import pytest
from openai.types.chat import ChatCompletion
from pydantic import BaseModel, Field

from mkcv.adapters.llm._utils import build_schema_prompt
from mkcv.adapters.llm.builtin_providers import BUILTIN_PROVIDERS, KIND_DEFAULTS
from mkcv.adapters.llm.model_resolver import ModelResolver, builtin_resolver
from mkcv.adapters.llm.openai_compatible import (
    REPAIR_PROMPT,
    OpenAICompatibleAdapter,
    _augment_with_schema,
)
from mkcv.adapters.llm.strict_schema import to_strict_json_schema
from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.exceptions.context_length import ContextLengthError
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.exceptions.rate_limit import RateLimitError
from mkcv.core.exceptions.validation import ValidationError
from mkcv.core.models.capability_overlay import CapabilityOverlay
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.model_capability import ModelCapability
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.provider_kind import ProviderKind
from mkcv.core.models.requirement import Requirement
from mkcv.core.models.resolved_model import ResolvedModel
from mkcv.core.models.structured_output_mode import StructuredOutputMode
from mkcv.core.models.token_param import TokenParam
from mkcv.core.models.token_usage import TokenUsage

BASE_URL = "http://localhost:9999/v1"
PROVIDER = "local-test"
MODEL = "unknown-model"
COMPATIBLE_DEFAULTS = KIND_DEFAULTS[ProviderKind.OPENAI_COMPATIBLE]
MESSAGES = [
    {"role": "system", "content": "You are an analyst."},
    {"role": "user", "content": "Describe it."},
]
VALID_REPLY = json.dumps({"name": "n", "items": [{"label": "a"}]})


class Item(BaseModel):
    label: str


class Sample(BaseModel):
    name: str
    note: str = "x"
    count: int | None = None
    items: list[Item] = Field(default_factory=list)


def _resolver(
    *entries: ModelCapability, defaults: CapabilityOverlay = COMPATIBLE_DEFAULTS
) -> ModelResolver:
    catalog = ModelCatalog(entries)

    def resolve(provider: str, model: str) -> ResolvedModel:
        return catalog.resolve(provider, model, defaults=defaults)

    return resolve


def _entry(model: str = MODEL, **fields: Any) -> ModelCapability:
    return ModelCapability(provider=PROVIDER, match=model, **fields)


def _adapter(
    *responses: Any,
    resolver: ModelResolver | None = None,
) -> tuple[OpenAICompatibleAdapter, AsyncMock]:
    """Build an adapter whose ``create`` returns/raises ``responses`` in order."""
    adapter = OpenAICompatibleAdapter(
        api_key="k",
        base_url=BASE_URL,
        resolver=resolver or _resolver(),
        provider_name=PROVIDER,
    )
    create = AsyncMock(side_effect=list(responses))
    adapter._client.chat.completions.create = create  # type: ignore[method-assign]
    return adapter, create


def _completion(
    content: str | None = VALID_REPLY,
    *,
    finish_reason: str = "stop",
    refusal: str | None = None,
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> ChatCompletion:
    return ChatCompletion.model_validate(
        {
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 0,
            "model": MODEL,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": finish_reason,
                    "message": {
                        "role": "assistant",
                        "content": content,
                        "refusal": refusal,
                    },
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }
    )


def _http_response(status: int) -> httpx.Response:
    return httpx.Response(
        status, request=httpx.Request("POST", f"{BASE_URL}/chat/completions")
    )


def _bad_request(message: str) -> openai.BadRequestError:
    return openai.BadRequestError(message, response=_http_response(400), body=None)


def _kwargs(create: AsyncMock, call: int) -> dict[str, Any]:
    kwargs: dict[str, Any] = create.call_args_list[call].kwargs
    return kwargs


async def _structured(
    adapter: OpenAICompatibleAdapter,
    *,
    model: str = MODEL,
    messages: list[dict[str, str]] | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> BaseModel:
    return await adapter.complete_structured(
        messages if messages is not None else MESSAGES,
        model=model,
        response_model=Sample,
        temperature=temperature,
        max_tokens=max_tokens,
    )


class TestConstruction:
    def test_client_uses_the_given_base_url(self) -> None:
        adapter, _ = _adapter()
        assert str(adapter._client.base_url).startswith(BASE_URL)

    def test_base_url_is_optional(self) -> None:
        adapter = OpenAICompatibleAdapter(api_key="k")
        assert "api.openai.com" in str(adapter._client.base_url)

    def test_default_resolver_is_the_builtin_compatible_resolver(self) -> None:
        adapter = OpenAICompatibleAdapter(api_key="k")
        assert adapter._resolver("x", "m") == builtin_resolver(
            ProviderKind.OPENAI_COMPATIBLE
        )("x", "m")

    async def test_default_provider_name_is_openai_compatible(self) -> None:
        adapter = OpenAICompatibleAdapter(api_key="k", base_url=BASE_URL)
        adapter._client.chat.completions.create = AsyncMock(  # type: ignore[method-assign]
            side_effect=_bad_request("nope")
        )
        with pytest.raises(ProviderError) as caught:
            await adapter.complete(MESSAGES, model="m")
        assert caught.value.provider == "openai-compatible"

    def test_usage_starts_at_zero(self) -> None:
        adapter, _ = _adapter()
        assert adapter.get_last_usage() == TokenUsage()


class TestStructuredJsonSchemaStart:
    """REQ-OC-1: an unknown model starts at strict JSON schema."""

    async def test_makes_exactly_one_call(self) -> None:
        adapter, create = _adapter(_completion())
        await _structured(adapter)
        assert create.await_count == 1

    async def test_requests_strict_json_schema_output(self) -> None:
        adapter, create = _adapter(_completion())
        await _structured(adapter)
        assert _kwargs(create, 0)["response_format"] == {
            "type": "json_schema",
            "json_schema": {
                "name": "Sample",
                "schema": to_strict_json_schema(Sample),
                "strict": True,
            },
        }

    async def test_sends_temperature(self) -> None:
        adapter, create = _adapter(_completion())
        await _structured(adapter, temperature=0.7)
        assert _kwargs(create, 0)["temperature"] == 0.7

    async def test_sends_max_tokens_not_max_completion_tokens(self) -> None:
        adapter, create = _adapter(_completion())
        await _structured(adapter, max_tokens=1234)
        kwargs = _kwargs(create, 0)
        assert kwargs["max_tokens"] == 1234
        assert "max_completion_tokens" not in kwargs

    async def test_sends_model_and_unmodified_messages(self) -> None:
        adapter, create = _adapter(_completion())
        await _structured(adapter)
        kwargs = _kwargs(create, 0)
        assert (kwargs["model"], kwargs["messages"]) == (MODEL, MESSAGES)

    async def test_caller_messages_are_not_mutated(self) -> None:
        messages = [dict(message) for message in MESSAGES]
        adapter, _ = _adapter(_completion())
        await _structured(adapter, messages=messages)
        assert messages == MESSAGES

    async def test_returns_the_validated_model(self) -> None:
        adapter, _ = _adapter(_completion())
        result = await _structured(adapter)
        assert result == Sample(name="n", items=[Item(label="a")])

    async def test_null_for_a_defaulted_field_falls_back_to_the_default(self) -> None:
        reply = json.dumps({"name": "n", "note": None, "items": None})
        adapter, _ = _adapter(_completion(reply))
        result = await _structured(adapter)
        assert isinstance(result, Sample)
        assert (result.note, result.items) == ("x", [])

    async def test_usage_of_the_call_is_recorded(self) -> None:
        adapter, _ = _adapter(_completion(prompt_tokens=100, completion_tokens=50))
        await _structured(adapter)
        assert adapter.get_last_usage() == TokenUsage(
            input_tokens=100, output_tokens=50
        )

    async def test_missing_usage_is_recorded_as_zero(self) -> None:
        response = _completion()
        response.usage = None
        adapter, _ = _adapter(response)
        await _structured(adapter)
        assert adapter.get_last_usage() == TokenUsage()

    async def test_tool_mode_counts_as_json_schema(self) -> None:
        resolver = _resolver(_entry(structured_output=StructuredOutputMode.TOOL))
        adapter, create = _adapter(_completion(), resolver=resolver)
        await _structured(adapter)
        assert _kwargs(create, 0)["response_format"]["type"] == "json_schema"


class TestDegradeToJsonObject:
    """REQ-OC-2."""

    SCHEMA_REJECTION = "response_format json_schema is not supported by this backend"

    async def test_two_calls_are_made(self) -> None:
        adapter, create = _adapter(_bad_request(self.SCHEMA_REJECTION), _completion())
        await _structured(adapter)
        assert create.await_count == 2

    async def test_second_call_uses_json_object(self) -> None:
        adapter, create = _adapter(_bad_request(self.SCHEMA_REJECTION), _completion())
        await _structured(adapter)
        assert _kwargs(create, 1)["response_format"] == {"type": "json_object"}

    async def test_second_call_appends_the_schema_instruction(self) -> None:
        adapter, create = _adapter(_bad_request(self.SCHEMA_REJECTION), _completion())
        await _structured(adapter)
        system = _kwargs(create, 1)["messages"][0]
        assert system["content"] == "You are an analyst." + build_schema_prompt(Sample)

    async def test_first_call_is_not_augmented(self) -> None:
        adapter, create = _adapter(_bad_request(self.SCHEMA_REJECTION), _completion())
        await _structured(adapter)
        assert _kwargs(create, 0)["messages"] == MESSAGES

    async def test_degradation_is_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING)
        adapter, _ = _adapter(_bad_request(self.SCHEMA_REJECTION), _completion())
        await _structured(adapter)
        assert "falling back to json_object" in caplog.text

    async def test_log_names_provider_mode_and_model(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING)
        adapter, _ = _adapter(_bad_request(self.SCHEMA_REJECTION), _completion())
        await _structured(adapter)
        assert f"{PROVIDER} rejected json_schema structured output for {MODEL}" in (
            caplog.text
        )

    async def test_later_calls_start_at_the_degraded_mode(self) -> None:
        adapter, create = _adapter(
            _bad_request(self.SCHEMA_REJECTION), _completion(), _completion()
        )
        await _structured(adapter)
        await _structured(adapter)
        assert _kwargs(create, 2)["response_format"] == {"type": "json_object"}
        assert create.await_count == 3

    async def test_degradation_is_remembered_per_model(self) -> None:
        adapter, create = _adapter(
            _bad_request(self.SCHEMA_REJECTION), _completion(), _completion()
        )
        await _structured(adapter)
        await _structured(adapter, model="other-model")
        assert _kwargs(create, 2)["response_format"]["type"] == "json_schema"

    async def test_degradation_is_per_adapter_instance(self) -> None:
        first, _ = _adapter(_bad_request(self.SCHEMA_REJECTION), _completion())
        second, create = _adapter(_completion())
        await _structured(first)
        await _structured(second)
        assert _kwargs(create, 0)["response_format"]["type"] == "json_schema"

    async def test_unprocessable_entity_also_degrades(self) -> None:
        rejection = openai.UnprocessableEntityError(
            self.SCHEMA_REJECTION, response=_http_response(422), body=None
        )
        adapter, create = _adapter(rejection, _completion())
        await _structured(adapter)
        assert _kwargs(create, 1)["response_format"] == {"type": "json_object"}

    async def test_unrelated_bad_request_does_not_degrade(self) -> None:
        adapter, create = _adapter(_bad_request("model not found"))
        with pytest.raises(ProviderError):
            await _structured(adapter)
        assert create.await_count == 1


class TestDegradeToPromptOnly:
    """REQ-OC-3."""

    async def test_third_call_is_prompt_only(self) -> None:
        fenced = f"```json\n{VALID_REPLY}\n```"
        adapter, create = _adapter(
            _bad_request("response_format json_schema is not supported"),
            _bad_request("response_format is not supported"),
            _completion(fenced),
        )
        result = await _structured(adapter)
        assert create.await_count == 3
        assert "response_format" not in _kwargs(create, 2)
        assert _kwargs(create, 2)["messages"][0]["content"].endswith(
            build_schema_prompt(Sample)
        )
        assert result == Sample(name="n", items=[Item(label="a")])

    async def test_prompt_mode_is_remembered(self) -> None:
        adapter, create = _adapter(
            _bad_request("response_format json_schema is not supported"),
            _bad_request("response_format is not supported"),
            _completion(),
            _completion(),
        )
        await _structured(adapter)
        await _structured(adapter)
        assert "response_format" not in _kwargs(create, 3)

    async def test_json_object_start_degrades_straight_to_prompt(self) -> None:
        resolver = _resolver(_entry(structured_output=StructuredOutputMode.JSON_OBJECT))
        adapter, create = _adapter(
            _bad_request("response_format is not supported"),
            _completion(),
            resolver=resolver,
        )
        await _structured(adapter)
        assert "response_format" not in _kwargs(create, 1)


class TestNoDegradationPastTheLastMode:
    """REQ-OC-4."""

    async def test_prompt_start_raises_after_one_call(self) -> None:
        resolver = _resolver(_entry(structured_output=StructuredOutputMode.PROMPT))
        adapter, create = _adapter(
            _bad_request("response_format is not supported"), resolver=resolver
        )
        with pytest.raises(ProviderError):
            await _structured(adapter)
        assert create.await_count == 1

    async def test_exhausted_chain_raises_after_three_calls(self) -> None:
        rejection = "response_format is not supported"
        adapter, create = _adapter(
            _bad_request(rejection), _bad_request(rejection), _bad_request(rejection)
        )
        with pytest.raises(ProviderError):
            await _structured(adapter)
        assert create.await_count == 3

    async def test_fallback_can_be_disabled_by_the_provider(self) -> None:
        defaults = COMPATIBLE_DEFAULTS.overlay(
            CapabilityOverlay(allow_structured_fallback=False)
        )
        adapter, create = _adapter(
            _bad_request("response_format json_schema is not supported"),
            resolver=_resolver(defaults=defaults),
        )
        with pytest.raises(ProviderError):
            await _structured(adapter)
        assert create.await_count == 1


class TestOllamaStyleJsonObjectProvider:
    """REQ-OC-5: the built-in ollama provider starts in JSON object mode."""

    @staticmethod
    def _ollama_resolver() -> ModelResolver:
        catalog = ModelCatalog.builtin()
        defaults = COMPATIBLE_DEFAULTS.overlay(BUILTIN_PROVIDERS["ollama"].defaults)

        def resolve(provider: str, model: str) -> ResolvedModel:
            return catalog.resolve(provider, model, defaults=defaults)

        return resolve

    def _adapter(self, *responses: Any) -> tuple[OpenAICompatibleAdapter, AsyncMock]:
        adapter = OpenAICompatibleAdapter(
            api_key="not-needed",
            base_url="http://localhost:11434/v1",
            resolver=self._ollama_resolver(),
            provider_name="ollama",
        )
        create = AsyncMock(side_effect=list(responses))
        adapter._client.chat.completions.create = create  # type: ignore[method-assign]
        return adapter, create

    async def test_first_call_uses_json_object_with_the_schema_instruction(
        self,
    ) -> None:
        adapter, create = self._adapter(_completion())
        await _structured(adapter, model="llama3.1:8b")
        kwargs = _kwargs(create, 0)
        assert kwargs["response_format"] == {"type": "json_object"}
        assert kwargs["messages"][0]["content"].endswith(build_schema_prompt(Sample))

    async def test_temperature_and_max_tokens_are_sent(self) -> None:
        adapter, create = self._adapter(_completion())
        await _structured(adapter, model="llama3.1:8b", temperature=0.4, max_tokens=900)
        kwargs = _kwargs(create, 0)
        assert (kwargs["temperature"], kwargs["max_tokens"]) == (0.4, 900)

    async def test_a_system_message_is_prepended_when_missing(self) -> None:
        user_only = [{"role": "user", "content": "Describe it."}]
        adapter, create = self._adapter(_completion())
        await _structured(adapter, model="llama3.1:8b", messages=user_only)
        sent = _kwargs(create, 0)["messages"]
        assert sent[0] == {
            "role": "system",
            "content": "You are a helpful assistant." + build_schema_prompt(Sample),
        }
        assert sent[1:] == user_only

    async def test_connection_error_names_the_provider_and_url(self) -> None:
        error = openai.APIConnectionError(
            request=httpx.Request("POST", "http://localhost:11434/v1/chat/completions")
        )
        adapter, _ = self._adapter(error)
        with pytest.raises(ProviderError, match="Cannot connect to ollama at http"):
            await adapter.complete(MESSAGES, model="llama3.1:8b")


class TestRepairRetry:
    """REQ-OC-6: one repair attempt in every mode."""

    JSON_OBJECT_START = StructuredOutputMode.JSON_OBJECT

    def _resolver(self) -> ModelResolver:
        return _resolver(_entry(structured_output=self.JSON_OBJECT_START))

    async def test_second_response_repairs_the_first(self) -> None:
        adapter, create = _adapter(
            _completion('{"wrong": 1}'), _completion(), resolver=self._resolver()
        )
        result = await _structured(adapter)
        assert result == Sample(name="n", items=[Item(label="a")])
        assert create.await_count == 2

    async def test_repair_call_ends_with_the_repair_prompt(self) -> None:
        adapter, create = _adapter(
            _completion('{"wrong": 1}'), _completion(), resolver=self._resolver()
        )
        await _structured(adapter)
        messages = _kwargs(create, 1)["messages"]
        assert messages[-2] == {"role": "assistant", "content": '{"wrong": 1}'}
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"].startswith(
            "Your previous reply was not valid JSON for the required schema."
        )

    async def test_repair_prompt_carries_the_validation_error(self) -> None:
        adapter, create = _adapter(
            _completion('{"wrong": 1}'), _completion(), resolver=self._resolver()
        )
        await _structured(adapter)
        assert "Sample" in _kwargs(create, 1)["messages"][-1]["content"]

    async def test_first_call_messages_are_not_changed_by_the_repair(self) -> None:
        adapter, create = _adapter(
            _completion('{"wrong": 1}'), _completion(), resolver=self._resolver()
        )
        await _structured(adapter)
        assert len(_kwargs(create, 0)["messages"]) == len(MESSAGES)

    async def test_repair_keeps_the_mode_of_the_failed_call(self) -> None:
        adapter, create = _adapter(
            _completion("not json"), _completion(), resolver=self._resolver()
        )
        await _structured(adapter)
        assert _kwargs(create, 1)["response_format"] == {"type": "json_object"}

    async def test_repair_works_in_strict_json_schema_mode_too(self) -> None:
        adapter, create = _adapter(_completion("not json"), _completion())
        await _structured(adapter)
        assert _kwargs(create, 1)["response_format"]["type"] == "json_schema"

    async def test_usage_of_both_calls_is_summed(self) -> None:
        adapter, _ = _adapter(
            _completion("not json", prompt_tokens=100, completion_tokens=50),
            _completion(prompt_tokens=20, completion_tokens=7),
        )
        await _structured(adapter)
        assert adapter.get_last_usage() == TokenUsage(
            input_tokens=120, output_tokens=57
        )

    async def test_two_invalid_responses_raise_a_validation_error(self) -> None:
        adapter, create = _adapter(_completion("not json"), _completion("still bad"))
        with pytest.raises(ValidationError, match="after one repair attempt"):
            await _structured(adapter)
        assert create.await_count == 2

    async def test_validation_error_names_provider_and_model_class(self) -> None:
        adapter, _ = _adapter(_completion("not json"), _completion("still bad"))
        with pytest.raises(ValidationError, match=f"{PROVIDER} returned invalid"):
            await _structured(adapter)

    async def test_repair_prompt_template_names_the_error_slot(self) -> None:
        assert "{error}" in REPAIR_PROMPT

    async def test_json_that_is_not_an_object_is_repaired(self) -> None:
        adapter, create = _adapter(_completion("[1, 2]"), _completion())
        await _structured(adapter)
        assert create.await_count == 2

    async def test_provider_error_during_repair_is_mapped(self) -> None:
        rate_limit = openai.RateLimitError(
            "slow down", response=_http_response(429), body=None
        )
        adapter, _ = _adapter(_completion("not json"), rate_limit)
        with pytest.raises(RateLimitError):
            await _structured(adapter)


class TestRefusalAndTruncation:
    async def test_refusal_raises_a_provider_error(self) -> None:
        adapter, _ = _adapter(_completion(None, refusal="I can't help with that"))
        with pytest.raises(ProviderError, match="Model refused the request") as caught:
            await _structured(adapter)
        assert caught.value.provider == PROVIDER

    async def test_truncation_raises_without_a_repair_call(self) -> None:
        adapter, create = _adapter(_completion('{"name": "n', finish_reason="length"))
        with pytest.raises(ProviderError) as caught:
            await _structured(adapter)
        assert "truncated" in str(caught.value)
        assert "increase max_tokens" in str(caught.value)
        assert create.await_count == 1

    async def test_truncation_message_reports_the_limit_sent(self) -> None:
        resolver = _resolver(_entry(min_output_tokens=16000))
        adapter, _ = _adapter(
            _completion("{", finish_reason="length"), resolver=resolver
        )
        with pytest.raises(ProviderError, match="truncated at 16000 tokens"):
            await _structured(adapter)

    async def test_truncated_repair_response_raises(self) -> None:
        adapter, _ = _adapter(
            _completion("not json"), _completion("{", finish_reason="length")
        )
        with pytest.raises(ProviderError, match="truncated"):
            await _structured(adapter)


class TestParameterAdaptation:
    """REQ-OC-7 and design section 5.5."""

    TEMPERATURE_REJECTION = "temperature is not supported for this model"
    TOKENS_REJECTION = (
        "Unsupported parameter: 'max_tokens' is not supported with this model. "
        "Use 'max_completion_tokens' instead."
    )

    async def test_temperature_rejection_retries_without_temperature(self) -> None:
        adapter, create = _adapter(
            _bad_request(self.TEMPERATURE_REJECTION), _completion()
        )
        await _structured(adapter)
        assert "temperature" in _kwargs(create, 0)
        assert "temperature" not in _kwargs(create, 1)

    async def test_temperature_adaptation_keeps_json_schema(self) -> None:
        adapter, create = _adapter(
            _bad_request(self.TEMPERATURE_REJECTION), _completion()
        )
        await _structured(adapter)
        assert _kwargs(create, 1)["response_format"]["type"] == "json_schema"
        assert create.await_count == 2

    async def test_temperature_adaptation_is_remembered_per_model(self) -> None:
        adapter, create = _adapter(
            _bad_request(self.TEMPERATURE_REJECTION), _completion(), _completion()
        )
        await _structured(adapter)
        await _structured(adapter)
        assert "temperature" not in _kwargs(create, 2)

    async def test_temperature_adaptation_does_not_leak_to_other_models(self) -> None:
        adapter, create = _adapter(
            _bad_request(self.TEMPERATURE_REJECTION), _completion(), _completion()
        )
        await _structured(adapter)
        await _structured(adapter, model="other-model")
        assert "temperature" in _kwargs(create, 2)

    async def test_adaptation_is_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING)
        adapter, _ = _adapter(_bad_request(self.TEMPERATURE_REJECTION), _completion())
        await _structured(adapter)
        assert (
            f"{PROVIDER} rejected 'temperature' for model {MODEL}; retrying without it"
        ) in caplog.text

    async def test_max_tokens_rejection_switches_to_max_completion_tokens(
        self,
    ) -> None:
        adapter, create = _adapter(_bad_request(self.TOKENS_REJECTION), _completion())
        await _structured(adapter, max_tokens=2048)
        assert "max_tokens" in _kwargs(create, 0)
        retry = _kwargs(create, 1)
        assert retry["max_completion_tokens"] == 2048
        assert "max_tokens" not in retry

    async def test_token_param_adaptation_is_remembered(self) -> None:
        adapter, create = _adapter(
            _bad_request(self.TOKENS_REJECTION), _completion(), _completion()
        )
        await _structured(adapter)
        await _structured(adapter)
        assert "max_completion_tokens" in _kwargs(create, 2)

    async def test_two_consecutive_rejections_raise_after_two_calls(self) -> None:
        adapter, create = _adapter(
            _bad_request(self.TEMPERATURE_REJECTION),
            _bad_request(self.TEMPERATURE_REJECTION),
        )
        with pytest.raises(ProviderError):
            await _structured(adapter)
        assert create.await_count == 2

    async def test_rejection_of_a_parameter_not_sent_is_not_retried(self) -> None:
        defaults = COMPATIBLE_DEFAULTS.overlay(
            CapabilityOverlay(accepts_sampling_params=False)
        )
        adapter, create = _adapter(
            _bad_request(self.TEMPERATURE_REJECTION),
            resolver=_resolver(defaults=defaults),
        )
        with pytest.raises(ProviderError):
            await _structured(adapter)
        assert create.await_count == 1

    async def test_both_parameters_can_be_adapted_in_sequence(self) -> None:
        adapter, create = _adapter(
            _bad_request(self.TEMPERATURE_REJECTION),
            _bad_request(self.TOKENS_REJECTION),
            _completion(),
        )
        await _structured(adapter)
        final = _kwargs(create, 2)
        assert "temperature" not in final
        assert "max_completion_tokens" in final

    async def test_adaptation_then_degradation_compose(self) -> None:
        adapter, create = _adapter(
            _bad_request(self.TEMPERATURE_REJECTION),
            _bad_request("response_format json_schema is not supported"),
            _completion(),
        )
        await _structured(adapter)
        final = _kwargs(create, 2)
        assert final["response_format"] == {"type": "json_object"}
        assert "temperature" not in final

    async def test_complete_adapts_temperature_too(self) -> None:
        adapter, create = _adapter(
            _bad_request(self.TEMPERATURE_REJECTION), _completion("ok")
        )
        assert await adapter.complete(MESSAGES, model=MODEL) == "ok"
        assert "temperature" not in _kwargs(create, 1)


class TestPlainComplete:
    async def test_returns_message_content(self) -> None:
        adapter, _ = _adapter(_completion("Hello"))
        assert await adapter.complete(MESSAGES, model=MODEL) == "Hello"

    async def test_none_content_becomes_an_empty_string(self) -> None:
        adapter, _ = _adapter(_completion(None))
        assert await adapter.complete(MESSAGES, model=MODEL) == ""

    async def test_request_has_no_response_format(self) -> None:
        adapter, create = _adapter(_completion("Hello"))
        await adapter.complete(MESSAGES, model=MODEL, temperature=0.5, max_tokens=700)
        kwargs = _kwargs(create, 0)
        assert "response_format" not in kwargs
        assert (kwargs["temperature"], kwargs["max_tokens"]) == (0.5, 700)
        assert kwargs["messages"] == MESSAGES

    async def test_usage_is_recorded(self) -> None:
        adapter, _ = _adapter(_completion("x", prompt_tokens=3, completion_tokens=4))
        await adapter.complete(MESSAGES, model=MODEL)
        assert adapter.get_last_usage() == TokenUsage(input_tokens=3, output_tokens=4)


class TestOutputLimit:
    async def test_catalog_floor_raises_a_small_request(self) -> None:
        resolver = _resolver(_entry(min_output_tokens=16000))
        adapter, create = _adapter(_completion(), resolver=resolver)
        await _structured(adapter, max_tokens=4096)
        assert _kwargs(create, 0)["max_tokens"] == 16000

    async def test_catalog_ceiling_caps_a_large_request(self) -> None:
        resolver = _resolver(_entry(max_output_tokens=2000))
        adapter, create = _adapter(_completion(), resolver=resolver)
        await _structured(adapter, max_tokens=4096)
        assert _kwargs(create, 0)["max_tokens"] == 2000

    async def test_provider_token_param_is_used(self) -> None:
        defaults = COMPATIBLE_DEFAULTS.overlay(
            CapabilityOverlay(token_param=TokenParam.MAX_COMPLETION_TOKENS)
        )
        adapter, create = _adapter(
            _completion("x"), resolver=_resolver(defaults=defaults)
        )
        await adapter.complete(MESSAGES, model=MODEL, max_tokens=800)
        kwargs = _kwargs(create, 0)
        assert kwargs["max_completion_tokens"] == 800
        assert "max_tokens" not in kwargs

    async def test_models_that_reject_sampling_get_no_temperature(self) -> None:
        resolver = _resolver(_entry(accepts_sampling_params=False))
        adapter, create = _adapter(_completion(), resolver=resolver)
        await _structured(adapter)
        assert "temperature" not in _kwargs(create, 0)


def _rate_limit() -> openai.RateLimitError:
    return openai.RateLimitError("slow down", response=_http_response(429), body=None)


def _authentication() -> openai.AuthenticationError:
    return openai.AuthenticationError(
        "bad key", response=_http_response(401), body=None
    )


def _permission() -> openai.PermissionDeniedError:
    return openai.PermissionDeniedError(
        "no access", response=_http_response(403), body=None
    )


def _context() -> openai.BadRequestError:
    return _bad_request("This model's maximum context length is 8192 tokens")


def _generic_bad_request() -> openai.BadRequestError:
    return _bad_request("model not found")


def _unprocessable() -> openai.UnprocessableEntityError:
    return openai.UnprocessableEntityError(
        "bad entity", response=_http_response(422), body=None
    )


def _server_error() -> openai.InternalServerError:
    return openai.InternalServerError("boom", response=_http_response(500), body=None)


def _connection() -> openai.APIConnectionError:
    return openai.APIConnectionError(
        request=httpx.Request("POST", f"{BASE_URL}/chat/completions")
    )


ERROR_CASES: list[tuple[Callable[[], openai.APIError], type[ProviderError]]] = [
    (_rate_limit, RateLimitError),
    (_authentication, AuthenticationError),
    (_permission, AuthenticationError),
    (_context, ContextLengthError),
    (_generic_bad_request, ProviderError),
    (_unprocessable, ProviderError),
    (_server_error, ProviderError),
    (_connection, ProviderError),
]


class TestErrorMapping:
    """REQ-OC-9: every mapped error carries the adapter's provider name."""

    @pytest.mark.parametrize(
        ("make_error", "expected"),
        ERROR_CASES,
        ids=lambda v: getattr(v, "__name__", ""),
    )
    async def test_complete_maps_sdk_errors(
        self, make_error: Callable[[], openai.APIError], expected: type[ProviderError]
    ) -> None:
        adapter, _ = _adapter(make_error())
        with pytest.raises(ProviderError) as caught:
            await adapter.complete(MESSAGES, model=MODEL)
        assert type(caught.value) is expected
        assert caught.value.provider == PROVIDER

    @pytest.mark.parametrize(
        ("make_error", "expected"),
        ERROR_CASES,
        ids=lambda v: getattr(v, "__name__", ""),
    )
    async def test_complete_structured_maps_sdk_errors(
        self, make_error: Callable[[], openai.APIError], expected: type[ProviderError]
    ) -> None:
        adapter, _ = _adapter(make_error())
        with pytest.raises(ProviderError) as caught:
            await _structured(adapter)
        assert type(caught.value) is expected
        assert caught.value.provider == PROVIDER

    async def test_original_sdk_error_is_chained(self) -> None:
        original = _rate_limit()
        adapter, _ = _adapter(original)
        with pytest.raises(RateLimitError) as caught:
            await adapter.complete(MESSAGES, model=MODEL)
        assert caught.value.__cause__ is original

    async def test_refusal_and_truncation_errors_carry_the_provider(self) -> None:
        adapter, _ = _adapter(_completion(None, refusal="no"))
        with pytest.raises(ProviderError) as caught:
            await _structured(adapter)
        assert caught.value.provider == PROVIDER


class TestConnectionErrors:
    """REQ-OC-8."""

    async def test_complete_names_provider_and_url(self) -> None:
        adapter, _ = _adapter(_connection())
        with pytest.raises(
            ProviderError, match=f"Cannot connect to {PROVIDER} at {BASE_URL}"
        ):
            await adapter.complete(MESSAGES, model=MODEL)

    async def test_complete_structured_names_provider_and_url(self) -> None:
        adapter, _ = _adapter(_connection())
        with pytest.raises(
            ProviderError, match=f"Cannot connect to {PROVIDER} at {BASE_URL}"
        ):
            await _structured(adapter)


JD_DATA: dict[str, Any] = {
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


class TestAugmentWithSchema:
    """Behaviour carried over from the removed OllamaAdapter helper."""

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

    def test_preserves_user_and_assistant_messages(self) -> None:
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        result = _augment_with_schema(messages, "\nS")
        assert result[1]["content"] == "Hello"
        assert result[2]["content"] == "Hi"

    def test_input_list_is_not_modified(self) -> None:
        messages = [{"role": "user", "content": "Hi"}]
        _augment_with_schema(messages, "\nS")
        assert messages == [{"role": "user", "content": "Hi"}]


class TestRealResponseModels:
    """End-to-end parsing with a production response model."""

    async def test_json_object_mode_returns_the_model(self) -> None:
        resolver = _resolver(_entry(structured_output=StructuredOutputMode.JSON_OBJECT))
        adapter, _ = _adapter(_completion(json.dumps(JD_DATA)), resolver=resolver)
        result = await adapter.complete_structured(
            [{"role": "user", "content": "analyze this JD"}],
            model=MODEL,
            response_model=JDAnalysis,
        )
        assert isinstance(result, JDAnalysis)
        assert result.company == "TestCo"
        assert isinstance(result.core_requirements[0], Requirement)

    async def test_strict_schema_mode_accepts_nulls_for_optional_fields(self) -> None:
        reply = {**JD_DATA, "compensation": None, "team_or_org": None}
        adapter, _ = _adapter(_completion(json.dumps(reply)))
        result = await adapter.complete_structured(
            [{"role": "user", "content": "analyze this JD"}],
            model=MODEL,
            response_model=JDAnalysis,
        )
        assert isinstance(result, JDAnalysis)

    async def test_usage_of_a_structured_call_is_recorded(self) -> None:
        adapter, _ = _adapter(
            _completion(json.dumps(JD_DATA), prompt_tokens=50, completion_tokens=100)
        )
        await adapter.complete_structured(
            [{"role": "user", "content": "analyze this JD"}],
            model=MODEL,
            response_model=JDAnalysis,
        )
        assert adapter.get_last_usage() == TokenUsage(
            input_tokens=50, output_tokens=100
        )

    async def test_unparseable_reply_raises_after_one_repair(self) -> None:
        adapter, create = _adapter(
            _completion("not valid json at all {{{"),
            _completion("still {{{ not json"),
        )
        with pytest.raises(ValidationError):
            await adapter.complete_structured(
                [{"role": "user", "content": "analyze this JD"}],
                model=MODEL,
                response_model=JDAnalysis,
            )
        assert create.await_count == 2

    async def test_incomplete_data_raises_a_validation_error(self) -> None:
        incomplete = _completion(json.dumps({"company": "TestCo"}))
        adapter, _ = _adapter(incomplete, incomplete)
        with pytest.raises(ValidationError):
            await adapter.complete_structured(
                [{"role": "user", "content": "analyze this JD"}],
                model=MODEL,
                response_model=JDAnalysis,
            )

    async def test_generic_status_error_maps_to_a_provider_error(self) -> None:
        error = openai.APIStatusError(
            "internal server error", response=_http_response(500), body=None
        )
        adapter, _ = _adapter(error)
        with pytest.raises(ProviderError):
            await adapter.complete(MESSAGES, model=MODEL)

    async def test_connection_error_with_a_bare_request_is_handled(self) -> None:
        adapter, _ = _adapter(
            openai.APIConnectionError(request=httpx.Request("GET", BASE_URL))
        )
        with pytest.raises(ProviderError, match=f"Cannot connect to {PROVIDER}"):
            await adapter.complete_structured(
                [{"role": "user", "content": "analyze"}],
                model=MODEL,
                response_model=JDAnalysis,
            )
