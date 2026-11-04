"""Tests for OpenAIAdapter: native strict structured outputs (REQ-OAI-1 to 10)."""

import json
import logging
from typing import Any
from unittest.mock import AsyncMock

import httpx
import openai
import pytest
from openai.types.chat import ChatCompletion
from pydantic import BaseModel, Field

from mkcv.adapters.llm.builtin_providers import KIND_DEFAULTS
from mkcv.adapters.llm.model_resolver import ModelResolver, builtin_resolver
from mkcv.adapters.llm.openai import OpenAIAdapter
from mkcv.adapters.llm.openai_compatible import OpenAICompatibleAdapter
from mkcv.adapters.llm.strict_schema import to_strict_json_schema
from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.exceptions.context_length import ContextLengthError
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.exceptions.rate_limit import RateLimitError
from mkcv.core.exceptions.validation import ValidationError
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.provider_kind import ProviderKind
from mkcv.core.models.requirement import Requirement
from mkcv.core.models.resolved_model import ResolvedModel
from mkcv.core.models.token_param import TokenParam
from mkcv.core.models.token_usage import TokenUsage
from mkcv.core.ports.llm import LLMPort

MESSAGES = [
    {"role": "system", "content": "You are an analyst."},
    {"role": "user", "content": "Describe it."},
]
VALID_REPLY = json.dumps({"name": "n", "items": [{"label": "a"}]})


class Item(BaseModel):
    label: str


class M(BaseModel):
    name: str
    note: str = "x"
    count: int | None = None
    items: list[Item] = Field(default_factory=list)


def _completion(
    content: str | None = VALID_REPLY,
    *,
    finish_reason: str = "stop",
    refusal: str | None = None,
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
) -> ChatCompletion:
    return ChatCompletion.model_validate(
        {
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-6.1-sol",
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
        status,
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )


def _bad_request(message: str) -> openai.BadRequestError:
    return openai.BadRequestError(message, response=_http_response(400), body=None)


def _adapter(
    *responses: Any, resolver: ModelResolver | None = None
) -> tuple[OpenAIAdapter, AsyncMock]:
    adapter = (
        OpenAIAdapter(api_key="test-key", resolver=resolver)
        if resolver
        else OpenAIAdapter(api_key="test-key")
    )
    create = AsyncMock(side_effect=list(responses))
    adapter._client.chat.completions.create = create  # type: ignore[method-assign]
    return adapter, create


def _kwargs(create: AsyncMock, call: int) -> dict[str, Any]:
    kwargs: dict[str, Any] = create.call_args_list[call].kwargs
    return kwargs


async def _structured(
    adapter: OpenAIAdapter,
    *,
    model: str = "gpt-6.1-sol",
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> BaseModel:
    return await adapter.complete_structured(
        MESSAGES,
        model=model,
        response_model=M,
        temperature=temperature,
        max_tokens=max_tokens,
    )


class TestConstruction:
    def test_adapter_satisfies_the_llm_port(self) -> None:
        assert isinstance(OpenAIAdapter(api_key="k"), LLMPort)

    def test_adapter_extends_the_compatible_adapter(self) -> None:
        assert issubclass(OpenAIAdapter, OpenAICompatibleAdapter)

    def test_base_url_is_passed_to_the_client(self) -> None:
        adapter = OpenAIAdapter(api_key="k", base_url="https://proxy.example/v1")
        assert str(adapter._client.base_url).startswith("https://proxy.example/v1")

    def test_default_resolver_is_the_native_openai_resolver(self) -> None:
        adapter = OpenAIAdapter(api_key="k")
        expected = builtin_resolver(ProviderKind.OPENAI)("openai", "gpt-6.1-sol")
        assert adapter._resolver("openai", "gpt-6.1-sol") == expected

    async def test_default_provider_name_is_openai(self) -> None:
        adapter, _ = _adapter(_bad_request("nope"))
        with pytest.raises(ProviderError) as caught:
            await adapter.complete(MESSAGES, model="gpt-4o")
        assert caught.value.provider == "openai"

    async def test_provider_name_can_be_overridden(self) -> None:
        adapter = OpenAIAdapter(api_key="k", provider_name="my-proxy")
        adapter._client.chat.completions.create = AsyncMock(  # type: ignore[method-assign]
            side_effect=_bad_request("nope")
        )
        with pytest.raises(ProviderError) as caught:
            await adapter.complete(MESSAGES, model="gpt-4o")
        assert caught.value.provider == "my-proxy"

    async def test_custom_resolver_is_honoured(self) -> None:
        catalog = ModelCatalog([])

        def resolver(provider: str, model: str) -> ResolvedModel:
            return catalog.resolve(
                provider, model, defaults=KIND_DEFAULTS[ProviderKind.OPENAI]
            ).model_copy(update={"min_output_tokens": 123})

        adapter, create = _adapter(_completion(), resolver=resolver)
        await _structured(adapter, max_tokens=10)
        assert _kwargs(create, 0)["max_completion_tokens"] == 123


class TestStrictJsonSchemaRequest:
    """REQ-OAI-1."""

    async def test_request_asks_for_strict_json_schema(self) -> None:
        adapter, create = _adapter(_completion())
        await _structured(adapter)
        response_format = _kwargs(create, 0)["response_format"]
        assert response_format["type"] == "json_schema"
        assert response_format["json_schema"]["strict"] is True
        assert response_format["json_schema"]["name"] == "M"

    async def test_schema_is_the_strict_transform_of_the_response_model(self) -> None:
        adapter, create = _adapter(_completion())
        await _structured(adapter)
        schema = _kwargs(create, 0)["response_format"]["json_schema"]["schema"]
        assert schema == to_strict_json_schema(M)

    async def test_reasoning_models_get_no_temperature(self) -> None:
        adapter, create = _adapter(_completion())
        await _structured(adapter, temperature=0.3)
        assert "temperature" not in _kwargs(create, 0)

    async def test_output_limit_uses_max_completion_tokens_with_the_floor(
        self,
    ) -> None:
        adapter, create = _adapter(_completion())
        await _structured(adapter, max_tokens=4096)
        kwargs = _kwargs(create, 0)
        assert kwargs["max_completion_tokens"] == 16000
        assert "max_tokens" not in kwargs

    async def test_system_message_is_unchanged(self) -> None:
        adapter, create = _adapter(_completion())
        await _structured(adapter)
        assert _kwargs(create, 0)["messages"] == MESSAGES

    async def test_only_one_call_is_made(self) -> None:
        adapter, create = _adapter(_completion())
        await _structured(adapter)
        assert create.await_count == 1

    async def test_large_requests_exceed_the_floor(self) -> None:
        adapter, create = _adapter(_completion())
        await _structured(adapter, max_tokens=20000)
        assert _kwargs(create, 0)["max_completion_tokens"] == 20000


class TestModelsThatAcceptSampling:
    """REQ-OAI-2."""

    async def test_gpt_4o_receives_temperature_and_the_requested_limit(self) -> None:
        adapter, create = _adapter(_completion())
        await _structured(adapter, model="gpt-4o", temperature=0.3, max_tokens=4096)
        kwargs = _kwargs(create, 0)
        assert kwargs["temperature"] == 0.3
        assert kwargs["max_completion_tokens"] == 4096


class TestParsingAndUsage:
    """REQ-OAI-3."""

    async def test_valid_json_becomes_the_response_model(self) -> None:
        adapter, _ = _adapter(_completion())
        result = await _structured(adapter)
        assert result == M(name="n", items=[Item(label="a")])

    async def test_usage_of_the_call_is_recorded(self) -> None:
        adapter, _ = _adapter(_completion(prompt_tokens=100, completion_tokens=50))
        await _structured(adapter)
        assert adapter.get_last_usage() == TokenUsage(
            input_tokens=100, output_tokens=50
        )

    async def test_null_for_a_defaulted_field_keeps_the_default(self) -> None:
        reply = json.dumps({"name": "n", "note": None, "count": None, "items": None})
        adapter, _ = _adapter(_completion(reply))
        result = await _structured(adapter)
        assert isinstance(result, M)
        assert (result.note, result.count, result.items) == ("x", None, [])

    async def test_real_response_model_round_trips(self) -> None:
        jd_data = {
            "company": "TestCo",
            "role_title": "Engineer",
            "seniority_level": "Senior",
            "core_requirements": [
                {
                    "skill": "Python",
                    "importance": "must_have",
                    "context": "Backend development",
                    "years_implied": None,
                }
            ],
            "technical_stack": ["Python"],
            "soft_skills": ["Communication"],
            "leadership_signals": [],
            "culture_keywords": [],
            "ats_keywords": ["Python"],
            "hidden_requirements": [],
            "role_summary": "A senior engineer role.",
            "compensation": None,
        }
        adapter, _ = _adapter(_completion(json.dumps(jd_data)))
        result = await adapter.complete_structured(
            [{"role": "user", "content": "analyze this JD"}],
            model="gpt-6.1-sol",
            response_model=JDAnalysis,
        )
        assert isinstance(result, JDAnalysis)
        assert result.company == "TestCo"
        assert isinstance(result.core_requirements[0], Requirement)


class TestRefusal:
    """REQ-OAI-4."""

    async def test_refusal_raises_a_provider_error(self) -> None:
        adapter, _ = _adapter(_completion(None, refusal="I can't help with that"))
        with pytest.raises(ProviderError, match="Model refused the request"):
            await _structured(adapter)

    async def test_refusal_text_is_included(self) -> None:
        adapter, _ = _adapter(_completion(None, refusal="I can't help with that"))
        with pytest.raises(ProviderError, match="I can't help with that"):
            await _structured(adapter)


class TestTruncation:
    """REQ-OAI-5."""

    async def test_length_finish_reason_raises_without_a_repair_call(self) -> None:
        adapter, create = _adapter(_completion('{"name": "n', finish_reason="length"))
        with pytest.raises(ProviderError) as caught:
            await _structured(adapter)
        assert "truncated" in str(caught.value)
        assert "increase max_tokens" in str(caught.value)
        assert create.await_count == 1


class TestRepairRetry:
    """REQ-OAI-6."""

    async def test_second_response_repairs_the_first(self) -> None:
        adapter, create = _adapter(_completion("not json"), _completion())
        result = await _structured(adapter)
        assert isinstance(result, M)
        assert create.await_count == 2

    async def test_repair_call_appends_the_failed_reply_and_the_repair_prompt(
        self,
    ) -> None:
        adapter, create = _adapter(_completion("not json"), _completion())
        await _structured(adapter)
        messages = _kwargs(create, 1)["messages"]
        assert messages[-2] == {"role": "assistant", "content": "not json"}
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"].startswith(
            "Your previous reply was not valid JSON"
        )

    async def test_usage_is_the_sum_of_both_calls(self) -> None:
        adapter, _ = _adapter(
            _completion("not json", prompt_tokens=100, completion_tokens=50),
            _completion(prompt_tokens=40, completion_tokens=10),
        )
        await _structured(adapter)
        assert adapter.get_last_usage() == TokenUsage(
            input_tokens=140, output_tokens=60
        )

    async def test_two_invalid_responses_raise_a_validation_error(self) -> None:
        adapter, create = _adapter(_completion("not json"), _completion("nope"))
        with pytest.raises(ValidationError, match="after one repair attempt"):
            await _structured(adapter)
        assert create.await_count == 2


class TestNoStructuredDegradation:
    """REQ-OAI-7: native OpenAI never falls back from strict JSON schema."""

    async def test_schema_rejection_raises_after_one_call(self) -> None:
        adapter, create = _adapter(
            _bad_request("Invalid schema for response_format 'M'")
        )
        with pytest.raises(ProviderError):
            await _structured(adapter)
        assert create.await_count == 1


class TestRequestAdaptation:
    """REQ-OAI-8."""

    TEMPERATURE_REJECTION = (
        "Unsupported value: 'temperature' does not support 0.3 with this model."
    )

    async def test_temperature_rejection_is_retried_without_temperature(self) -> None:
        adapter, create = _adapter(
            _bad_request(self.TEMPERATURE_REJECTION), _completion()
        )
        result = await _structured(adapter, model="gpt-4o")
        assert isinstance(result, M)
        assert "temperature" in _kwargs(create, 0)
        assert "temperature" not in _kwargs(create, 1)

    async def test_adaptation_is_remembered_for_the_model(self) -> None:
        adapter, create = _adapter(
            _bad_request(self.TEMPERATURE_REJECTION), _completion(), _completion()
        )
        await _structured(adapter, model="gpt-4o")
        await _structured(adapter, model="gpt-4o")
        assert "temperature" not in _kwargs(create, 2)

    async def test_adaptation_is_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING)
        adapter, _ = _adapter(_bad_request(self.TEMPERATURE_REJECTION), _completion())
        await _structured(adapter, model="gpt-4o")
        assert "rejected 'temperature' for model gpt-4o" in caplog.text

    async def test_max_tokens_rejection_switches_to_max_completion_tokens(
        self,
    ) -> None:
        catalog = ModelCatalog([])
        defaults = KIND_DEFAULTS[ProviderKind.OPENAI].model_copy(
            update={"token_param": TokenParam.MAX_TOKENS, "min_output_tokens": 0}
        )

        def resolver(provider: str, model: str) -> ResolvedModel:
            return catalog.resolve(provider, model, defaults=defaults)

        rejection = (
            "Unsupported parameter: 'max_tokens' is not supported with this model. "
            "Use 'max_completion_tokens' instead."
        )
        adapter, create = _adapter(
            _bad_request(rejection), _completion(), resolver=resolver
        )
        await _structured(adapter, max_tokens=2048)
        assert _kwargs(create, 0)["max_tokens"] == 2048
        retry = _kwargs(create, 1)
        assert retry["max_completion_tokens"] == 2048
        assert "max_tokens" not in retry

    async def test_two_consecutive_rejections_raise_after_two_calls(self) -> None:
        adapter, create = _adapter(
            _bad_request(self.TEMPERATURE_REJECTION),
            _bad_request(self.TEMPERATURE_REJECTION),
        )
        with pytest.raises(ProviderError):
            await _structured(adapter, model="gpt-4o")
        assert create.await_count == 2


class TestErrorMapping:
    """REQ-OAI-9."""

    async def test_rate_limit_error(self) -> None:
        adapter, _ = _adapter(
            openai.RateLimitError("slow", response=_http_response(429), body=None)
        )
        with pytest.raises(RateLimitError) as caught:
            await _structured(adapter)
        assert caught.value.provider == "openai"

    @pytest.mark.parametrize(
        "error",
        [
            openai.AuthenticationError("bad", response=_http_response(401), body=None),
            openai.PermissionDeniedError("no", response=_http_response(403), body=None),
        ],
        ids=["authentication", "permission"],
    )
    async def test_authentication_errors(self, error: openai.APIStatusError) -> None:
        adapter, _ = _adapter(error)
        with pytest.raises(AuthenticationError):
            await _structured(adapter)

    async def test_context_length_error(self) -> None:
        adapter, _ = _adapter(
            _bad_request("This model's maximum context length is 8192 tokens")
        )
        with pytest.raises(ContextLengthError):
            await _structured(adapter)

    async def test_connection_error(self) -> None:
        adapter, _ = _adapter(
            openai.APIConnectionError(
                request=httpx.Request("POST", "https://api.openai.com/v1")
            )
        )
        with pytest.raises(ProviderError, match="Cannot connect to openai"):
            await _structured(adapter)

    async def test_other_api_errors(self) -> None:
        adapter, _ = _adapter(
            openai.InternalServerError("boom", response=_http_response(500), body=None)
        )
        with pytest.raises(ProviderError) as caught:
            await _structured(adapter)
        assert type(caught.value) is ProviderError

    async def test_complete_maps_errors_too(self) -> None:
        adapter, _ = _adapter(
            openai.RateLimitError("slow", response=_http_response(429), body=None)
        )
        with pytest.raises(RateLimitError):
            await adapter.complete(MESSAGES, model="gpt-4o")


class TestPlainCompletion:
    """REQ-OAI-10."""

    async def test_returns_message_content(self) -> None:
        adapter, _ = _adapter(_completion("Hello from GPT"))
        result = await adapter.complete(MESSAGES, model="gpt-6-luna")
        assert result == "Hello from GPT"

    async def test_none_content_becomes_an_empty_string(self) -> None:
        adapter, _ = _adapter(_completion(None))
        assert await adapter.complete(MESSAGES, model="gpt-6-luna") == ""

    async def test_request_uses_the_floor_and_omits_sampling_and_format(self) -> None:
        adapter, create = _adapter(_completion("x"))
        await adapter.complete(
            MESSAGES, model="gpt-6-luna", temperature=0.5, max_tokens=1000
        )
        kwargs = _kwargs(create, 0)
        assert kwargs["max_completion_tokens"] == 16000
        assert "temperature" not in kwargs
        assert "response_format" not in kwargs

    async def test_usage_is_recorded(self) -> None:
        adapter, _ = _adapter(_completion("x", prompt_tokens=7, completion_tokens=3))
        await adapter.complete(MESSAGES, model="gpt-6-luna")
        assert adapter.get_last_usage() == TokenUsage(input_tokens=7, output_tokens=3)
