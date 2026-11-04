"""Anthropic (Claude) LLM adapter.

Uses streaming for all API calls to avoid the 10-minute timeout on
long-running requests (required by the Anthropic API for operations
that may produce large outputs).

How a request is shaped (sampling parameters, output floor, structured-output
mechanism) comes from the model capability catalog, not from model-name
checks in this module.
"""

import functools
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import anthropic
from anthropic.types import Message, OutputConfigParam
from pydantic import BaseModel

from mkcv.adapters.llm._utils import (
    extract_json_from_text,
    resolve_schema_refs,
    split_system_message,
    validate_structured_response,
)
from mkcv.adapters.llm.model_resolver import ModelResolver, builtin_resolver
from mkcv.adapters.llm.request_adaptation import rejected_parameter
from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.exceptions.context_length import ContextLengthError
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.exceptions.rate_limit import RateLimitError
from mkcv.core.models.provider_kind import ProviderKind
from mkcv.core.models.resolved_model import ResolvedModel
from mkcv.core.models.structured_output_mode import StructuredOutputMode
from mkcv.core.models.token_usage import TokenUsage

logger = logging.getLogger(__name__)

CLAUDE_5_MIN_MAX_TOKENS = 16_000
"""Output floor for Claude 5.x, whose always-on thinking counts against max_tokens."""

_DROP_TEMPERATURE = "drop_temperature"

type _RequestBuilder = Callable[[], dict[str, Any]]


@functools.cache
def _builtin_anthropic_resolver() -> ModelResolver:
    return builtin_resolver(ProviderKind.ANTHROPIC)


def uses_strict_request_rules(model: str) -> bool:
    """Return True for models with the Claude 5.x request rules (incl. Opus 4.7/4.8).

    These models reject sampling parameters and forced ``tool_choice``,
    and always think before answering. The answer comes from the built-in
    capability catalog; models it does not know get the same conservative
    treatment.
    """
    return not _builtin_anthropic_resolver()("anthropic", model).accepts_sampling_params


def _join_text_blocks(response: Message) -> str:
    """Concatenate the text blocks of a response, skipping thinking blocks."""
    return "".join(
        str(block.text) for block in response.content if block.type == "text"
    )


class AnthropicAdapter:
    """LLM adapter using the Anthropic Claude API.

    All calls use streaming to comply with Anthropic's requirement
    that requests potentially exceeding 10 minutes must stream.

    Per model, the capability resolver decides whether ``temperature`` is
    sent, the output-token floor, and how structured output is requested:
    ``json_schema`` uses structured outputs (``output_config``), anything
    else uses a forced tool call. If the API rejects ``temperature`` for a
    model the catalog thought accepted it, the call is retried once without
    it and the model is remembered for the life of the adapter.

    Implements: LLMPort
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        resolver: ModelResolver | None = None,
        provider_name: str = "anthropic",
    ) -> None:
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = anthropic.AsyncAnthropic(**kwargs)
        self._resolver = resolver or builtin_resolver(ProviderKind.ANTHROPIC)
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
        """Send a streaming completion request and return the text response."""
        resolved = self._resolver(self._provider_name, model)

        def build() -> dict[str, Any]:
            return self._build_request(
                messages, model, temperature, max_tokens, resolved
            )

        try:
            response = await self._with_adaptation(model, build, self._stream_message)
            self._record_usage(response)
            return _join_text_blocks(response)
        except anthropic.RateLimitError as e:
            raise RateLimitError(str(e), provider=self._provider_name) from e
        except anthropic.AuthenticationError as e:
            raise AuthenticationError(str(e), provider=self._provider_name) from e
        except anthropic.BadRequestError as e:
            if "context" in str(e).lower() or "token" in str(e).lower():
                raise ContextLengthError(str(e), provider=self._provider_name) from e
            raise ProviderError(str(e), provider=self._provider_name) from e
        except anthropic.APIError as e:
            raise ProviderError(str(e), provider=self._provider_name) from e

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        response_model: type[BaseModel],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> BaseModel:
        """Send a streaming structured completion and return a Pydantic model."""
        resolved = self._resolver(self._provider_name, model)

        def build() -> dict[str, Any]:
            return self._build_request(
                messages, model, temperature, max_tokens, resolved
            )

        call: Callable[[dict[str, Any]], Awaitable[BaseModel]]
        if resolved.structured_output is StructuredOutputMode.JSON_SCHEMA:
            call = functools.partial(
                self._complete_with_output_format, response_model=response_model
            )
        else:
            call = functools.partial(
                self._complete_with_forced_tool, response_model=response_model
            )

        try:
            return await self._with_adaptation(model, build, call)
        except (
            RateLimitError,
            AuthenticationError,
            ContextLengthError,
            ProviderError,
        ):
            raise
        except anthropic.RateLimitError as e:
            raise RateLimitError(str(e), provider=self._provider_name) from e
        except anthropic.AuthenticationError as e:
            raise AuthenticationError(str(e), provider=self._provider_name) from e
        except anthropic.APIError as e:
            raise ProviderError(str(e), provider=self._provider_name) from e

    def get_last_usage(self) -> TokenUsage:
        """Return token usage from the most recent API call."""
        return self._last_usage

    def _build_request(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        resolved: ResolvedModel,
    ) -> dict[str, Any]:
        """Build the request kwargs shared by plain and structured calls."""
        system, user_messages = split_system_message(messages)
        request: dict[str, Any] = {
            "model": model,
            "messages": user_messages,
            "max_tokens": resolved.output_limit(max_tokens),
        }
        dropped = _DROP_TEMPERATURE in self._adaptations.get(model, set())
        if resolved.accepts_sampling_params and not dropped:
            request["temperature"] = temperature
        if system:
            request["system"] = system
        return request

    async def _with_adaptation[T](
        self,
        model: str,
        build: _RequestBuilder,
        call: Callable[[dict[str, Any]], Awaitable[T]],
    ) -> T:
        """Run ``call``, retrying once if the API rejects ``temperature``."""
        while True:
            request = build()
            try:
                return await call(request)
            except anthropic.BadRequestError as error:
                if not self._adapt(model, request, str(error)):
                    raise

    def _adapt(self, model: str, request: dict[str, Any], message: str) -> bool:
        """Record a dropped ``temperature`` for ``model``; False if not applicable."""
        if rejected_parameter(message) != "temperature" or "temperature" not in request:
            return False
        self._adaptations.setdefault(model, set()).add(_DROP_TEMPERATURE)
        logger.warning(
            "%s rejected '%s' for model %s; retrying without it",
            self._provider_name,
            "temperature",
            model,
        )
        return True

    async def _stream_message(self, request: dict[str, Any]) -> Message:
        async with self._client.messages.stream(**request) as stream:
            return await stream.get_final_message()

    def _record_usage(self, response: Message) -> None:
        self._last_usage = TokenUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    async def _complete_with_output_format(
        self,
        request: dict[str, Any],
        *,
        response_model: type[BaseModel],
    ) -> BaseModel:
        """Constrain the reply to the model's JSON schema via structured outputs."""
        output_config: OutputConfigParam = {
            "format": {
                "type": "json_schema",
                "schema": anthropic.transform_schema(response_model),
            }
        }
        async with self._client.messages.stream(
            **request, output_config=output_config
        ) as stream:
            response = await stream.get_final_message()

        self._record_usage(response)

        text = _join_text_blocks(response)
        if not text:
            raise ProviderError(
                "Anthropic returned no text content "
                f"(stop_reason={response.stop_reason})",
                provider=self._provider_name,
            )
        try:
            data = extract_json_from_text(text)
        except ValueError as e:
            raise ProviderError(
                "Anthropic returned unparseable JSON "
                f"(stop_reason={response.stop_reason})",
                provider=self._provider_name,
            ) from e
        return validate_structured_response(data, response_model)

    async def _complete_with_forced_tool(
        self,
        request: dict[str, Any],
        *,
        response_model: type[BaseModel],
    ) -> BaseModel:
        """Force a single tool call whose input is the structured reply."""
        tool_name = f"extract_{response_model.__name__.lower()}"
        tool_schema = response_model.model_json_schema()

        tool_input_schema: dict[str, Any] = {
            "type": "object",
            "properties": tool_schema.get("properties", {}),
            "required": tool_schema.get("required", []),
        }
        if "$defs" in tool_schema:
            tool_input_schema["$defs"] = tool_schema["$defs"]

        # Resolve $ref references so models get a flat, unambiguous schema
        tool_input_schema = resolve_schema_refs(tool_input_schema)

        tools = [
            {
                "name": tool_name,
                "description": (
                    f"Extract structured data as {response_model.__name__}"
                ),
                "input_schema": tool_input_schema,
            }
        ]

        # Stream the response and collect tool JSON fragments
        input_json_parts: list[str] = []
        tool_request: dict[str, Any] = {
            **request,
            "tools": tools,
            "tool_choice": {"type": "tool", "name": tool_name},
        }
        async with self._client.messages.stream(**tool_request) as stream:
            async for event in stream:
                if hasattr(event, "type") and event.type == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if (
                        delta is not None
                        and getattr(delta, "type", None) == "input_json_delta"
                    ):
                        input_json_parts.append(getattr(delta, "partial_json", ""))
            response = await stream.get_final_message()

        self._record_usage(response)

        # Prefer reassembled JSON from stream fragments — this is
        # the most reliable path for large tool responses.
        if input_json_parts:
            raw_json = "".join(input_json_parts)
            try:
                data: dict[str, Any] = json.loads(raw_json)
                # Detect when streamed fragments are the tool schema
                # rather than the actual response data.  Opus
                # sometimes emits the schema definition instead of
                # the tool input; skip it and fall through to the
                # final-message fallback.
                schema_keys = {"$defs", "properties", "required", "type"}
                if schema_keys.issubset(data.keys()):
                    logger.warning(
                        "Streamed JSON appears to be tool schema, not "
                        "response data (keys: %s); falling back to "
                        "final message",
                        list(data.keys()),
                    )
                else:
                    return validate_structured_response(data, response_model)
            except json.JSONDecodeError:
                logger.warning(
                    "Failed to parse streamed JSON fragments (%d parts, "
                    "%d chars); falling back to final message",
                    len(input_json_parts),
                    len(raw_json),
                )

        # Fallback: extract from the final assembled message
        for block in response.content:
            if (
                block.type == "tool_use"
                and hasattr(block, "name")
                and block.name == tool_name
            ):
                tool_data = block.input
                logger.debug(
                    "Tool response keys: %s",
                    list(tool_data.keys())
                    if isinstance(tool_data, dict)
                    else type(tool_data),
                )
                return validate_structured_response(
                    tool_data,
                    response_model,
                )

        # Last resort: try to extract JSON from text blocks
        for block in response.content:
            if block.type == "text":
                data = extract_json_from_text(str(block.text))
                return validate_structured_response(data, response_model)

        raise ProviderError(
            "Anthropic returned no tool_use or text content",
            provider=self._provider_name,
        )
