"""Anthropic (Claude) LLM adapter.

Uses streaming for all API calls to avoid the 10-minute timeout on
long-running requests (required by the Anthropic API for operations
that may produce large outputs).
"""

import json
import logging
from typing import Any

import anthropic
from pydantic import BaseModel

from mkcv.adapters.llm._utils import (
    extract_json_from_text,
    resolve_schema_refs,
    split_system_message,
    validate_structured_response,
)
from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.exceptions.context_length import ContextLengthError
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.exceptions.rate_limit import RateLimitError
from mkcv.core.models.token_usage import TokenUsage

logger = logging.getLogger(__name__)


class AnthropicAdapter:
    """LLM adapter using the Anthropic Claude API.

    All calls use streaming to comply with Anthropic's requirement
    that requests potentially exceeding 10 minutes must stream.

    Implements: LLMPort
    """

    def __init__(self, api_key: str, *, base_url: str | None = None) -> None:
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = anthropic.AsyncAnthropic(**kwargs)
        self._last_usage = TokenUsage()

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Send a streaming completion request and return the text response."""
        system, user_messages = split_system_message(messages)
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": user_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if system:
                kwargs["system"] = system

            collected_text: list[str] = []
            async with self._client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    collected_text.append(text)
                response = await stream.get_final_message()

            self._last_usage = TokenUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
            return "".join(collected_text)
        except anthropic.RateLimitError as e:
            raise RateLimitError(str(e), provider="anthropic") from e
        except anthropic.AuthenticationError as e:
            raise AuthenticationError(str(e), provider="anthropic") from e
        except anthropic.BadRequestError as e:
            if "context" in str(e).lower() or "token" in str(e).lower():
                raise ContextLengthError(str(e), provider="anthropic") from e
            raise ProviderError(str(e), provider="anthropic") from e
        except anthropic.APIError as e:
            raise ProviderError(str(e), provider="anthropic") from e

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
        system, user_messages = split_system_message(messages)

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

        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": user_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "tools": tools,
                "tool_choice": {"type": "tool", "name": tool_name},
            }
            if system:
                kwargs["system"] = system

            # Stream the response and collect tool JSON fragments
            input_json_parts: list[str] = []
            async with self._client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if hasattr(event, "type") and event.type == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if (
                            delta is not None
                            and getattr(delta, "type", None) == "input_json_delta"
                        ):
                            input_json_parts.append(getattr(delta, "partial_json", ""))
                response = await stream.get_final_message()

            self._last_usage = TokenUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

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
                provider="anthropic",
            )

        except (
            RateLimitError,
            AuthenticationError,
            ContextLengthError,
            ProviderError,
        ):
            raise
        except anthropic.RateLimitError as e:
            raise RateLimitError(str(e), provider="anthropic") from e
        except anthropic.AuthenticationError as e:
            raise AuthenticationError(str(e), provider="anthropic") from e
        except anthropic.APIError as e:
            raise ProviderError(str(e), provider="anthropic") from e

    def get_last_usage(self) -> TokenUsage:
        """Return token usage from the most recent API call."""
        return self._last_usage
