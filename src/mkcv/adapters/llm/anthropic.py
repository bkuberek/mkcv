"""Anthropic (Claude) LLM adapter."""

import logging
from typing import Any

import anthropic
from pydantic import BaseModel

from mkcv.adapters.llm._utils import (
    extract_json_from_text,
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
        """Send a completion request and return the text response."""
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
            response = await self._client.messages.create(**kwargs)
            self._last_usage = TokenUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
            # Extract text from first content block
            for block in response.content:
                if block.type == "text":
                    return str(block.text)
            return ""
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
        """Send a completion request and return a validated Pydantic model."""
        # Use tool_use for structured output
        system, user_messages = split_system_message(messages)

        tool_name = f"extract_{response_model.__name__.lower()}"
        tool_schema = response_model.model_json_schema()

        # Remove metadata keys that Anthropic doesn't accept
        tool_input_schema: dict[str, Any] = {
            "type": "object",
            "properties": tool_schema.get("properties", {}),
            "required": tool_schema.get("required", []),
        }
        # Handle $defs for nested models
        if "$defs" in tool_schema:
            tool_input_schema["$defs"] = tool_schema["$defs"]

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
            response = await self._client.messages.create(**kwargs)
            self._last_usage = TokenUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

            # Extract tool call input
            for block in response.content:
                if (
                    block.type == "tool_use"
                    and hasattr(block, "name")
                    and block.name == tool_name
                ):
                    return validate_structured_response(
                        block.input,
                        response_model,
                    )

            # Fallback: try to extract JSON from text blocks
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
