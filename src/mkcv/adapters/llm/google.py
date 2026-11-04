"""LLM adapter for Google Gemini, built on the ``google-genai`` SDK.

Structured calls ask Gemini for JSON constrained by the response model's
schema. Gemini reasons before it answers and bills those thinking tokens as
output, so usage counts them and the output limit has a generous floor (see
the provider-kind defaults). Every reply is validated with Pydantic and gets
one repair attempt.

The registry imports this module only when a Google provider is actually
used, so the SDK costs nothing at startup for everyone else.
"""

import logging
from collections.abc import Callable
from enum import Enum
from typing import Any

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from mkcv.adapters.llm._utils import (
    extract_json_from_text,
    resolve_schema_refs,
    validate_structured_response,
)
from mkcv.adapters.llm.model_resolver import ModelResolver, builtin_resolver
from mkcv.adapters.llm.request_adaptation import rejected_parameter
from mkcv.adapters.llm.vertex_target import VertexTarget
from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.exceptions.context_length import ContextLengthError
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.exceptions.rate_limit import RateLimitError
from mkcv.core.exceptions.validation import ValidationError
from mkcv.core.models.provider_kind import ProviderKind
from mkcv.core.models.resolved_model import ResolvedModel
from mkcv.core.models.token_usage import TokenUsage

logger = logging.getLogger(__name__)

# Same wording as the OpenAI-compatible adapter; a test keeps them identical.
REPAIR_PROMPT = (
    "Your previous reply was not valid JSON for the required schema. "
    "Error: {error}\n"
    "Reply again with only the corrected JSON object. Do not add any other text."
)

_REPAIR_ERROR_LIMIT = 2000
_JSON_MIME_TYPE = "application/json"

_HTTP_BAD_REQUEST = 400
_HTTP_UNAUTHORIZED = 401
_HTTP_FORBIDDEN = 403
_HTTP_TOO_MANY_REQUESTS = 429

_DROP_TEMPERATURE = "drop_temperature"

_USER_ROLE = "user"
_MODEL_ROLE = "model"
_SYSTEM_ROLE = "system"
_ASSISTANT_ROLE = "assistant"

_NO_BLOCK_REASON = "BLOCKED_REASON_UNSPECIFIED"
_MAX_TOKENS_REASON = "MAX_TOKENS"
_NORMAL_FINISH_REASONS = frozenset({"STOP", "FINISH_REASON_UNSPECIFIED"})

_PARSE_ERRORS = (ValueError, ValidationError)

type _RequestBuilder = Callable[[], dict[str, Any]]


def _create_client(
    api_key: str | None,
    vertex: VertexTarget | None,
    http_options: types.HttpOptions | None,
) -> genai.Client:
    if vertex is not None:
        pinned = {"credentials": vertex.credentials} if vertex.credentials else {}
        return genai.Client(
            vertexai=True,
            project=vertex.project,
            location=vertex.location,
            http_options=http_options,
            **pinned,
        )
    return genai.Client(api_key=api_key, http_options=http_options)


class GoogleGeminiAdapter:
    """LLM adapter for the Gemini API, or for Gemini on Vertex AI.

    With a ``vertex`` target the client authenticates with Application Default
    Credentials and no API key is used.

    Request shape per model comes from the capability resolver: whether
    ``temperature`` is sent and the output-token floor. When Gemini rejects
    ``temperature`` for a model, the adapter drops it and remembers that for
    the life of the instance.

    Implements: LLMPort
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        vertex: VertexTarget | None = None,
        base_url: str | None = None,
        resolver: ModelResolver | None = None,
        provider_name: str = "google",
    ) -> None:
        http_options = types.HttpOptions(base_url=base_url) if base_url else None
        self._client = _create_client(api_key, vertex, http_options)
        self._resolver = resolver or builtin_resolver(ProviderKind.GOOGLE)
        self._provider_name = provider_name
        self._last_usage = TokenUsage()
        self._adaptations: dict[str, set[str]] = {}

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
        system, contents = _split_conversation(messages)

        def build() -> dict[str, Any]:
            return self._request(
                model, contents, system, resolved, temperature, limit, schema=None
            )

        response = await self._generate(model, build)
        return self._read_text(response, model, limit, accumulate=False)

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
        system, contents = _split_conversation(messages)
        schema = resolve_schema_refs(response_model.model_json_schema())

        def build() -> dict[str, Any]:
            return self._request(
                model, contents, system, resolved, temperature, limit, schema=schema
            )

        response = await self._generate(model, build)
        return await self._parse_with_repair(
            response, build, model, limit, response_model
        )

    def get_last_usage(self) -> TokenUsage:
        """Return token usage from the most recent call."""
        return self._last_usage

    def _request(
        self,
        model: str,
        contents: list[types.Content],
        system: str | None,
        resolved: ResolvedModel,
        temperature: float,
        limit: int,
        *,
        schema: dict[str, Any] | None,
    ) -> dict[str, Any]:
        adaptations = self._adaptations.get(model, set())
        sends_temperature = (
            resolved.accepts_sampling_params and _DROP_TEMPERATURE not in adaptations
        )
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=limit,
            temperature=temperature if sends_temperature else None,
            response_mime_type=_JSON_MIME_TYPE if schema is not None else None,
            response_json_schema=schema,
        )
        return {"model": model, "contents": contents, "config": config}

    async def _generate(
        self, model: str, build: _RequestBuilder
    ) -> types.GenerateContentResponse:
        """Call the API, adapting once if Gemini rejects ``temperature``."""
        while True:
            request = build()
            try:
                return await self._client.aio.models.generate_content(**request)
            except errors.ClientError as error:
                if self._adapt(model, error, request):
                    continue
                raise self._map_error(error) from error
            except (errors.APIError, httpx.TransportError) as error:
                raise self._map_error(error) from error

    def _adapt(
        self, model: str, error: errors.ClientError, request: dict[str, Any]
    ) -> bool:
        """Record dropping ``temperature`` if Gemini rejected it; else False."""
        if error.code != _HTTP_BAD_REQUEST:
            return False
        if rejected_parameter(_detail(error)) != "temperature":
            return False
        if request["config"].temperature is None:
            return False

        self._adaptations.setdefault(model, set()).add(_DROP_TEMPERATURE)
        logger.warning(
            "%s rejected '%s' for model %s; retrying without it",
            self._provider_name,
            "temperature",
            model,
        )
        return True

    async def _parse_with_repair(
        self,
        response: types.GenerateContentResponse,
        build: _RequestBuilder,
        model: str,
        limit: int,
        response_model: type[BaseModel],
    ) -> BaseModel:
        """Validate the reply, asking the model to fix it once if invalid."""
        text = self._read_text(response, model, limit, accumulate=False)
        try:
            return _parse_text(text, response_model)
        except _PARSE_ERRORS as first_error:
            logger.debug(
                "Invalid structured reply; requesting a repair: %s", first_error
            )
            repaired = await self._request_repair(
                build, model, limit, text, first_error
            )

        try:
            return _parse_text(repaired, response_model)
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
        text: str,
        error: Exception,
    ) -> str:
        def build_repair() -> dict[str, Any]:
            request = build()
            request["contents"] = [
                *request["contents"],
                _turn(_MODEL_ROLE, text),
                _turn(
                    _USER_ROLE,
                    REPAIR_PROMPT.format(error=str(error)[:_REPAIR_ERROR_LIMIT]),
                ),
            ]
            return request

        response = await self._generate(model, build_repair)
        return self._read_text(response, model, limit, accumulate=True)

    def _read_text(
        self,
        response: types.GenerateContentResponse,
        model: str,
        limit: int,
        *,
        accumulate: bool,
    ) -> str:
        """Record usage and return the reply text, explaining an empty reply."""
        usage = _usage_of(response)
        if accumulate:
            usage = TokenUsage(
                input_tokens=self._last_usage.input_tokens + usage.input_tokens,
                output_tokens=self._last_usage.output_tokens + usage.output_tokens,
            )
        self._last_usage = usage

        text = response.text or ""
        if not text:
            raise self._empty_reply_error(response, model, limit)
        return text

    def _empty_reply_error(
        self, response: types.GenerateContentResponse, model: str, limit: int
    ) -> ProviderError:
        name = self._provider_name
        feedback = response.prompt_feedback
        if feedback is not None and feedback.block_reason is not None:
            reason = _name_of(feedback.block_reason)
            if reason != _NO_BLOCK_REASON:
                return ProviderError(
                    f"Gemini blocked the prompt: {reason}", provider=name
                )

        candidates = response.candidates or []
        finish = _name_of(candidates[0].finish_reason) if candidates else None
        if finish == _MAX_TOKENS_REASON:
            return ProviderError(
                f"{name} output was truncated at {limit} tokens for {model}; "
                "increase max_tokens",
                provider=name,
            )
        if finish is not None and finish not in _NORMAL_FINISH_REASONS:
            return ProviderError(
                f"Gemini returned no text (finish reason: {finish})", provider=name
            )
        return ProviderError("Gemini returned no text", provider=name)

    def _map_error(
        self, error: errors.APIError | httpx.TransportError
    ) -> ProviderError:
        """Translate an SDK or transport error into the mkcv error hierarchy."""
        name = self._provider_name
        if isinstance(error, httpx.TransportError):
            return ProviderError(f"Cannot connect to {name}: {error}", provider=name)

        message = str(error)
        if isinstance(error, errors.ClientError):
            if error.code == _HTTP_TOO_MANY_REQUESTS:
                return RateLimitError(message, provider=name)
            if error.code in (_HTTP_UNAUTHORIZED, _HTTP_FORBIDDEN):
                return AuthenticationError(message, provider=name)
            if error.code == _HTTP_BAD_REQUEST and _exceeds_context(error):
                return ContextLengthError(message, provider=name)
        return ProviderError(message, provider=name)


def _split_conversation(
    messages: list[dict[str, str]],
) -> tuple[str | None, list[types.Content]]:
    """Split chat messages into Gemini's system instruction and conversation turns.

    System messages are joined with a blank line; ``assistant`` becomes the
    ``model`` role and every other role is sent as ``user``.
    """
    system_parts: list[str] = []
    contents: list[types.Content] = []
    for message in messages:
        role = message["role"]
        if role == _SYSTEM_ROLE:
            system_parts.append(message["content"])
        elif role == _ASSISTANT_ROLE:
            contents.append(_turn(_MODEL_ROLE, message["content"]))
        else:
            contents.append(_turn(_USER_ROLE, message["content"]))
    return "\n\n".join(system_parts) or None, contents


def _turn(role: str, text: str) -> types.Content:
    return types.Content(role=role, parts=[types.Part.from_text(text=text)])


def _usage_of(response: types.GenerateContentResponse) -> TokenUsage:
    """Count thinking tokens as output, because Gemini bills them that way."""
    metadata = response.usage_metadata
    if metadata is None:
        return TokenUsage()
    return TokenUsage(
        input_tokens=metadata.prompt_token_count or 0,
        output_tokens=(metadata.candidates_token_count or 0)
        + (metadata.thoughts_token_count or 0),
    )


def _parse_text(text: str, response_model: type[BaseModel]) -> BaseModel:
    data = extract_json_from_text(text)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object, got {type(data).__name__}")
    return validate_structured_response(data, response_model)


def _detail(error: errors.APIError) -> str:
    """The error's own message, without the HTTP status text SDK errors prepend."""
    return error.message or str(error)


def _exceeds_context(error: errors.APIError) -> bool:
    lowered = _detail(error).lower()
    return "token" in lowered or "context" in lowered


def _name_of(value: object) -> str:
    """Name of an SDK enum member (``SAFETY``), or the plain string form."""
    return value.name if isinstance(value, Enum) else str(value)
