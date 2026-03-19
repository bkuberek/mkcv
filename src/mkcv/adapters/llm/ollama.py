"""Ollama LLM adapter for local model support.

Uses the OpenAI-compatible API endpoint provided by Ollama
(http://localhost:11434/v1 by default). No additional dependencies
required beyond the openai package.
"""

import logging
from typing import Any

import openai
from pydantic import BaseModel

from mkcv.adapters.llm._utils import (
    build_schema_prompt,
    extract_json_from_text,
    validate_structured_response,
)
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.models.token_usage import TokenUsage

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_OLLAMA_MODEL = "llama3.1"


class OllamaAdapter:
    """LLM adapter using a local Ollama instance.

    Connects to Ollama's OpenAI-compatible API endpoint. Requires
    Ollama to be running locally with the desired model pulled.

    Implements: LLMPort
    """

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        model: str = DEFAULT_OLLAMA_MODEL,
    ) -> None:
        self._client = openai.AsyncOpenAI(
            api_key="ollama",  # Ollama doesn't require a key
            base_url=base_url,
        )
        self._default_model = model
        self._last_usage = TokenUsage()

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Send a completion request to the local Ollama instance."""
        resolved_model = model or self._default_model

        try:
            response = await self._client.chat.completions.create(
                model=resolved_model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if response.usage:
                self._last_usage = TokenUsage(
                    input_tokens=response.usage.prompt_tokens,
                    output_tokens=response.usage.completion_tokens,
                )
            return response.choices[0].message.content or ""
        except openai.APIConnectionError as e:
            raise ProviderError(
                f"Cannot connect to Ollama at {self._client.base_url}. "
                f"Is Ollama running? Error: {e}",
                provider="ollama",
            ) from e
        except openai.APIError as e:
            raise ProviderError(str(e), provider="ollama") from e

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        response_model: type[BaseModel],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> BaseModel:
        """Send a structured completion request to Ollama.

        Uses JSON mode with schema instruction appended to the system
        message, similar to the OpenAI adapter.
        """
        resolved_model = model or self._default_model
        schema_instruction = build_schema_prompt(response_model)

        augmented_messages = _augment_with_schema(messages, schema_instruction)

        try:
            create_kwargs: dict[str, Any] = {
                "model": resolved_model,
                "messages": augmented_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
            }
            response = await self._client.chat.completions.create(**create_kwargs)
            if response.usage:
                self._last_usage = TokenUsage(
                    input_tokens=response.usage.prompt_tokens,
                    output_tokens=response.usage.completion_tokens,
                )

            content = response.choices[0].message.content or ""
            data = extract_json_from_text(content)
            return validate_structured_response(data, response_model)

        except ProviderError:
            raise
        except openai.APIConnectionError as e:
            raise ProviderError(
                f"Cannot connect to Ollama at {self._client.base_url}. "
                f"Is Ollama running? Error: {e}",
                provider="ollama",
            ) from e
        except openai.APIError as e:
            raise ProviderError(str(e), provider="ollama") from e

    def get_last_usage(self) -> TokenUsage:
        """Return token usage from the most recent API call."""
        return self._last_usage


def _augment_with_schema(
    messages: list[dict[str, str]],
    schema_instruction: str,
) -> list[dict[str, str]]:
    """Append JSON schema instruction to the system message.

    If no system message exists, prepend one.
    """
    augmented: list[dict[str, str]] = []
    has_system = False

    for msg in messages:
        if msg["role"] == "system":
            augmented.append(
                {
                    "role": "system",
                    "content": msg["content"] + schema_instruction,
                }
            )
            has_system = True
        else:
            augmented.append(msg)

    if not has_system:
        augmented.insert(
            0,
            {
                "role": "system",
                "content": (f"You are a helpful assistant.{schema_instruction}"),
            },
        )

    return augmented
