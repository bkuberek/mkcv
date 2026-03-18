"""OpenAI GPT LLM adapter."""

import logging
from typing import Any

import openai
from pydantic import BaseModel

from mkcv.adapters.llm._utils import (
    build_schema_prompt,
    extract_json_from_text,
    validate_structured_response,
)
from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.exceptions.context_length import ContextLengthError
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.exceptions.rate_limit import RateLimitError

logger = logging.getLogger(__name__)


class OpenAIAdapter:
    """LLM adapter using the OpenAI API.

    Also works with OpenRouter and other OpenAI-compatible APIs
    by setting a custom base_url.

    Implements: LLMPort
    """

    def __init__(self, api_key: str, *, base_url: str | None = None) -> None:
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = openai.AsyncOpenAI(**kwargs)

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Send a completion request and return the text response."""
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except openai.RateLimitError as e:
            raise RateLimitError(str(e), provider="openai") from e
        except openai.AuthenticationError as e:
            raise AuthenticationError(str(e), provider="openai") from e
        except openai.BadRequestError as e:
            if "context" in str(e).lower() or "token" in str(e).lower():
                raise ContextLengthError(str(e), provider="openai") from e
            raise ProviderError(str(e), provider="openai") from e
        except openai.APIError as e:
            raise ProviderError(str(e), provider="openai") from e

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
        # Add schema instruction to system message
        schema_instruction = build_schema_prompt(response_model)

        augmented_messages = []
        has_system = False
        for msg in messages:
            if msg["role"] == "system":
                augmented_messages.append(
                    {
                        "role": "system",
                        "content": msg["content"] + schema_instruction,
                    }
                )
                has_system = True
            else:
                augmented_messages.append(msg)

        if not has_system:
            augmented_messages.insert(
                0,
                {
                    "role": "system",
                    "content": (f"You are a helpful assistant.{schema_instruction}"),
                },
            )

        try:
            create_kwargs: dict[str, Any] = {
                "model": model,
                "messages": augmented_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
            }
            response = await self._client.chat.completions.create(**create_kwargs)

            content = response.choices[0].message.content or ""
            data = extract_json_from_text(content)
            return validate_structured_response(data, response_model)

        except (
            RateLimitError,
            AuthenticationError,
            ContextLengthError,
            ProviderError,
        ):
            raise
        except openai.RateLimitError as e:
            raise RateLimitError(str(e), provider="openai") from e
        except openai.AuthenticationError as e:
            raise AuthenticationError(str(e), provider="openai") from e
        except openai.APIError as e:
            raise ProviderError(str(e), provider="openai") from e
