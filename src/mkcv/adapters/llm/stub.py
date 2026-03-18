"""Configurable stub LLM adapter for testing and development."""

from typing import Any

from pydantic import BaseModel


class StubLLMAdapter:
    """Configurable stub LLM adapter for testing.

    Instead of raising NotImplementedError, returns canned responses
    that can be configured per-test.

    Implements: LLMPort

    Usage:
        # For testing with specific model responses:
        stub = StubLLMAdapter(
            default_response="Hello!",
            responses={JDAnalysis: sample_jd_analysis},
        )

        # For quick integration testing:
        stub = StubLLMAdapter()  # returns empty defaults
    """

    def __init__(
        self,
        *,
        default_response: str = "",
        responses: dict[type[BaseModel], BaseModel] | None = None,
    ) -> None:
        self._default_response = default_response
        self._responses: dict[type[BaseModel], BaseModel] = responses or {}
        self._call_log: list[dict[str, Any]] = []

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Return the configured default response."""
        self._call_log.append(
            {
                "method": "complete",
                "messages": messages,
                "model": model,
                "temperature": temperature,
            }
        )
        return self._default_response

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        response_model: type[BaseModel],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> BaseModel:
        """Return a configured canned response for the given model type."""
        self._call_log.append(
            {
                "method": "complete_structured",
                "messages": messages,
                "model": model,
                "response_model": response_model.__name__,
            }
        )

        if response_model in self._responses:
            return self._responses[response_model]

        # Return a default instance with required fields if possible
        raise NotImplementedError(
            f"No canned response configured for {response_model.__name__}. "
            f"Pass responses={{...}} to StubLLMAdapter constructor."
        )

    @property
    def call_log(self) -> list[dict[str, Any]]:
        """Access the log of all calls made to this adapter."""
        return self._call_log.copy()

    def reset(self) -> None:
        """Clear the call log."""
        self._call_log.clear()
