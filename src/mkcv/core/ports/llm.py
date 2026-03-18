"""Port interface for LLM provider access."""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


@runtime_checkable
class LLMPort(Protocol):
    """Interface for AI language model providers.

    Implementations: AnthropicAdapter, OpenAIAdapter, OllamaAdapter, etc.
    """

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Send a completion request and return the text response."""
        ...

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
        ...
