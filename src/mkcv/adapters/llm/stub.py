"""Stub LLM adapter for development and testing."""

from pydantic import BaseModel


class StubLLMAdapter:
    """Stub LLM adapter that raises NotImplementedError.

    Used as a placeholder until real provider adapters
    (Anthropic, OpenAI, Ollama, OpenRouter) are implemented.

    Implements: LLMPort
    """

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Not implemented — raises NotImplementedError."""
        raise NotImplementedError(
            "LLM completion not yet implemented. "
            "Configure a real provider (anthropic, openai, ollama) in your config."
        )

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        response_model: type[BaseModel],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> BaseModel:
        """Not implemented — raises NotImplementedError."""
        raise NotImplementedError(
            "Structured LLM completion not yet implemented. "
            "Configure a real provider in your config."
        )
