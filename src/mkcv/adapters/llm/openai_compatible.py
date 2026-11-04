"""LLM adapter for OpenAI Chat Completions and compatible endpoints.

Works with OpenAI itself and with any server that speaks the Chat Completions
protocol (Ollama, OpenRouter, Groq, vLLM, LM Studio, ...). Structured output
starts at the strongest mode the model supports and degrades one step at a
time when the endpoint rejects it:

    json_schema (strict) -> json_object -> prompt-only

Every reply is validated with Pydantic and gets one repair attempt.
"""

import logging
import re
from collections.abc import Callable
from typing import Any

import openai
from openai.types.chat import ChatCompletion
from pydantic import BaseModel

from mkcv.adapters.llm._utils import (
    build_schema_prompt,
    extract_json_from_text,
    validate_structured_response,
)
from mkcv.adapters.llm.model_resolver import ModelResolver, builtin_resolver
from mkcv.adapters.llm.request_adaptation import (
    is_structured_output_rejection,
    rejected_parameter,
)
from mkcv.adapters.llm.strict_schema import (
    drop_nulls_for_defaulted_fields,
    to_strict_json_schema,
)
from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.exceptions.context_length import ContextLengthError
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.exceptions.rate_limit import RateLimitError
from mkcv.core.exceptions.validation import ValidationError
from mkcv.core.models.provider_kind import ProviderKind
from mkcv.core.models.resolved_model import ResolvedModel
from mkcv.core.models.structured_output_mode import StructuredOutputMode
from mkcv.core.models.token_param import TokenParam
from mkcv.core.models.token_usage import TokenUsage

logger = logging.getLogger(__name__)

REPAIR_PROMPT = (
    "Your previous reply was not valid JSON for the required schema. "
    "Error: {error}\n"
    "Reply again with only the corrected JSON object. Do not add any other text."
)

_DEGRADATION_ORDER = (
    StructuredOutputMode.JSON_SCHEMA,
    StructuredOutputMode.JSON_OBJECT,
    StructuredOutputMode.PROMPT,
)

_DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."
_SCHEMA_NAME_LIMIT = 64
_REPAIR_ERROR_LIMIT = 2000

_DROP_TEMPERATURE = "drop_temperature"
_USE_MAX_COMPLETION_TOKENS = "use_max_completion_tokens"

_REJECTION_ERRORS = (openai.BadRequestError, openai.UnprocessableEntityError)
_PARSE_ERRORS = (ValueError, ValidationError)

type _RequestBuilder = Callable[[], dict[str, Any]]


class OpenAICompatibleAdapter:
    """LLM adapter for any Chat Completions endpoint.

    Request shape per model comes from the capability resolver: whether
    ``temperature`` is sent, which output-limit parameter is used, the output
    floor, and the first structured-output mode. When an endpoint rejects a
    parameter or a structured-output mode, the adapter adapts and remembers
    the adaptation for that model for the life of the instance.

    Implements: LLMPort
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        resolver: ModelResolver | None = None,
        provider_name: str = "openai-compatible",
    ) -> None:
        client_options: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_options["base_url"] = base_url
        self._client = openai.AsyncOpenAI(**client_options)
        self._resolver = resolver or builtin_resolver(ProviderKind.OPENAI_COMPATIBLE)
        self._provider_name = provider_name
        self._last_usage = TokenUsage()
        self._adaptations: dict[str, set[str]] = {}
        self._degraded_modes: dict[str, StructuredOutputMode] = {}

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Send a completion request and return the text response."""
        resolved = self._resolver(self._provider_name, model)
        limit = resolved.output_limit(max_tokens)

        def build() -> dict[str, Any]:
            return self._base_request(model, messages, resolved, temperature, limit)

        try:
            response = await self._create(model, build)
        except openai.APIError as error:
            raise self._map_error(error) from error

        self._last_usage = _usage_of(response)
        return response.choices[0].message.content or ""

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        response_model: type[BaseModel],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> BaseModel:
        """Send a structured completion and return a validated Pydantic model."""
        resolved = self._resolver(self._provider_name, model)
        limit = resolved.output_limit(max_tokens)
        chain = self._mode_chain(model, resolved)

        def builder_for(mode: StructuredOutputMode) -> _RequestBuilder:
            def build() -> dict[str, Any]:
                request = self._base_request(
                    model, messages, resolved, temperature, limit
                )
                _apply_mode(request, mode, messages, response_model)
                return request

            return build

        position = 0
        while True:
            mode = chain[position]
            build = builder_for(mode)
            try:
                response = await self._create(model, build)
            except _REJECTION_ERRORS as error:
                is_last_mode = position == len(chain) - 1
                if is_last_mode or not is_structured_output_rejection(str(error)):
                    raise self._map_error(error) from error
                position += 1
                self._degrade(model, mode, chain[position])
                continue
            except openai.APIError as error:
                raise self._map_error(error) from error

            return await self._parse_with_repair(
                response, build, model, limit, response_model, mode
            )

    def get_last_usage(self) -> TokenUsage:
        """Return token usage from the most recent call."""
        return self._last_usage

    def _mode_chain(
        self, model: str, resolved: ResolvedModel
    ) -> list[StructuredOutputMode]:
        """Return the structured-output modes to try, strongest first."""
        start = self._degraded_modes.get(model) or _as_chat_mode(
            resolved.structured_output
        )
        if not self._may_degrade(resolved):
            return [start]
        return list(_DEGRADATION_ORDER[_DEGRADATION_ORDER.index(start) :])

    def _may_degrade(self, resolved: ResolvedModel) -> bool:
        """Return True when a weaker structured-output mode may be tried."""
        return resolved.allow_structured_fallback

    def _degrade(
        self, model: str, rejected: StructuredOutputMode, fallback: StructuredOutputMode
    ) -> None:
        self._degraded_modes[model] = fallback
        logger.warning(
            "%s rejected %s structured output for %s; falling back to %s",
            self._provider_name,
            rejected,
            model,
            fallback,
        )

    def _base_request(
        self,
        model: str,
        messages: list[dict[str, str]],
        resolved: ResolvedModel,
        temperature: float,
        limit: int,
    ) -> dict[str, Any]:
        adaptations = self._adaptations.get(model, set())
        token_param = (
            TokenParam.MAX_COMPLETION_TOKENS
            if _USE_MAX_COMPLETION_TOKENS in adaptations
            else resolved.token_param
        )
        request: dict[str, Any] = {
            "model": model,
            "messages": messages,
            token_param.value: limit,
        }
        if resolved.accepts_sampling_params and _DROP_TEMPERATURE not in adaptations:
            request["temperature"] = temperature
        return request

    async def _create(self, model: str, build: _RequestBuilder) -> ChatCompletion:
        """Call the API, adapting once per parameter the endpoint rejects."""
        while True:
            request = build()
            try:
                return await self._client.chat.completions.create(**request)
            except _REJECTION_ERRORS as error:
                parameter = rejected_parameter(str(error))
                if parameter is None or not self._adapt(model, parameter, request):
                    raise

    def _adapt(self, model: str, parameter: str, request: dict[str, Any]) -> bool:
        """Record an adaptation for a rejected parameter; False if not applicable."""
        if parameter == "temperature" and "temperature" in request:
            adaptation = _DROP_TEMPERATURE
        elif parameter == "max_tokens" and "max_tokens" in request:
            adaptation = _USE_MAX_COMPLETION_TOKENS
        else:
            return False

        self._adaptations.setdefault(model, set()).add(adaptation)
        logger.warning(
            "%s rejected '%s' for model %s; retrying without it",
            self._provider_name,
            parameter,
            model,
        )
        return True

    async def _parse_with_repair(
        self,
        response: ChatCompletion,
        build: _RequestBuilder,
        model: str,
        limit: int,
        response_model: type[BaseModel],
        mode: StructuredOutputMode,
    ) -> BaseModel:
        """Validate the reply, asking the model to fix it once if invalid."""
        content = self._read_content(response, model, limit, accumulate=False)
        try:
            return _parse_content(content, response_model, mode)
        except _PARSE_ERRORS as first_error:
            logger.debug(
                "Invalid structured reply; requesting a repair: %s", first_error
            )
            repaired = await self._request_repair(
                build, model, limit, content, first_error
            )

        try:
            return _parse_content(repaired, response_model, mode)
        except _PARSE_ERRORS as second_error:
            raise ValidationError(
                f"{self._provider_name} returned invalid structured output for "
                f"{response_model.__name__} after one repair attempt: {second_error}"
            ) from second_error

    async def _request_repair(
        self,
        build: _RequestBuilder,
        model: str,
        limit: int,
        content: str,
        error: Exception,
    ) -> str:
        def build_repair() -> dict[str, Any]:
            request = build()
            request["messages"] = [
                *request["messages"],
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": REPAIR_PROMPT.format(
                        error=str(error)[:_REPAIR_ERROR_LIMIT]
                    ),
                },
            ]
            return request

        try:
            response = await self._create(model, build_repair)
        except openai.APIError as api_error:
            raise self._map_error(api_error) from api_error
        return self._read_content(response, model, limit, accumulate=True)

    def _read_content(
        self, response: ChatCompletion, model: str, limit: int, *, accumulate: bool
    ) -> str:
        """Record usage and return the reply text, rejecting refusals and cut-offs."""
        usage = _usage_of(response)
        if accumulate:
            usage = TokenUsage(
                input_tokens=self._last_usage.input_tokens + usage.input_tokens,
                output_tokens=self._last_usage.output_tokens + usage.output_tokens,
            )
        self._last_usage = usage

        choice = response.choices[0]
        refusal = choice.message.refusal
        if isinstance(refusal, str) and refusal:
            raise ProviderError(
                f"Model refused the request: {refusal}", provider=self._provider_name
            )
        if choice.finish_reason == "length":
            raise ProviderError(
                f"{self._provider_name} output was truncated at {limit} tokens "
                f"for {model}; increase max_tokens",
                provider=self._provider_name,
            )
        return choice.message.content or ""

    def _map_error(self, error: openai.APIError) -> ProviderError:
        """Translate an SDK error into the mkcv error hierarchy."""
        name = self._provider_name
        message = str(error)

        if isinstance(error, openai.RateLimitError):
            return RateLimitError(message, provider=name)
        if isinstance(error, openai.AuthenticationError | openai.PermissionDeniedError):
            return AuthenticationError(message, provider=name)
        if isinstance(error, openai.APIConnectionError):
            return ProviderError(
                f"Cannot connect to {name} at {self._client.base_url}: {error}",
                provider=name,
            )
        if isinstance(error, _REJECTION_ERRORS):
            lowered = message.lower()
            if "context" in lowered or "token" in lowered:
                return ContextLengthError(message, provider=name)
        return ProviderError(message, provider=name)


def _as_chat_mode(mode: StructuredOutputMode) -> StructuredOutputMode:
    """Chat Completions has no forced-tool mode; treat it as strict JSON schema."""
    if mode is StructuredOutputMode.TOOL:
        return StructuredOutputMode.JSON_SCHEMA
    return mode


def _usage_of(response: ChatCompletion) -> TokenUsage:
    if response.usage is None:
        return TokenUsage()
    return TokenUsage(
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
    )


def _apply_mode(
    request: dict[str, Any],
    mode: StructuredOutputMode,
    messages: list[dict[str, str]],
    response_model: type[BaseModel],
) -> None:
    """Add the structured-output fields for ``mode`` to ``request``."""
    if mode is StructuredOutputMode.JSON_SCHEMA:
        request["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": _schema_name(response_model),
                "schema": to_strict_json_schema(response_model),
                "strict": True,
            },
        }
        return

    if mode is StructuredOutputMode.JSON_OBJECT:
        request["response_format"] = {"type": "json_object"}
    request["messages"] = _augment_with_schema(
        messages, build_schema_prompt(response_model)
    )


def _schema_name(response_model: type[BaseModel]) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", response_model.__name__)[:_SCHEMA_NAME_LIMIT]


def _augment_with_schema(
    messages: list[dict[str, str]],
    schema_instruction: str,
) -> list[dict[str, str]]:
    """Append the JSON schema instruction to the system message.

    If no system message exists, prepend one. The input is not modified.
    """
    augmented: list[dict[str, str]] = []
    has_system = False

    for message in messages:
        if message["role"] == "system":
            augmented.append(
                {"role": "system", "content": message["content"] + schema_instruction}
            )
            has_system = True
        else:
            augmented.append(message)

    if not has_system:
        augmented.insert(
            0,
            {
                "role": "system",
                "content": f"{_DEFAULT_SYSTEM_PROMPT}{schema_instruction}",
            },
        )

    return augmented


def _parse_content(
    content: str,
    response_model: type[BaseModel],
    mode: StructuredOutputMode,
) -> BaseModel:
    data = extract_json_from_text(content)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object, got {type(data).__name__}")
    if mode is StructuredOutputMode.JSON_SCHEMA:
        data = drop_nulls_for_defaulted_fields(data, response_model)
    return validate_structured_response(data, response_model)
