"""Retrying LLM adapter with exponential backoff."""

import asyncio
import logging

from pydantic import BaseModel

from mkcv.core.exceptions.rate_limit import RateLimitError
from mkcv.core.models.token_usage import TokenUsage
from mkcv.core.ports.llm import LLMPort

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 60.0
DEFAULT_BACKOFF_FACTOR = 2.0


class RetryingLLMAdapter:
    """Wraps an LLMPort with exponential backoff on rate limit errors.

    Retries only on RateLimitError. Authentication errors, context length
    errors, and validation errors are raised immediately.

    Implements: LLMPort
    """

    def __init__(
        self,
        inner: LLMPort,
        *,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    ) -> None:
        self._inner = inner
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._backoff_factor = backoff_factor

    def get_last_usage(self) -> TokenUsage:
        """Delegate to the inner adapter's usage tracking."""
        return self._inner.get_last_usage()

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Send a completion request with retry on rate limit."""
        result = await self._retry(
            self._inner.complete,
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return str(result)

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        response_model: type[BaseModel],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> BaseModel:
        """Send a structured completion request with retry."""
        result = await self._retry(
            self._inner.complete_structured,
            messages,
            model=model,
            response_model=response_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        assert isinstance(result, BaseModel)
        return result

    async def _retry(
        self,
        fn: object,
        *args: object,
        **kwargs: object,
    ) -> object:
        """Execute a function with exponential backoff on RateLimitError.

        Args:
            fn: The async function to call.
            *args: Positional arguments for fn.
            **kwargs: Keyword arguments for fn.

        Returns:
            The result of fn.

        Raises:
            RateLimitError: If all retries are exhausted.
        """
        last_error: RateLimitError | None = None
        delay = self._base_delay

        for attempt in range(self._max_retries + 1):
            try:
                return await fn(*args, **kwargs)  # type: ignore[operator]
            except RateLimitError as exc:
                last_error = exc
                if attempt < self._max_retries:
                    logger.warning(
                        "Rate limited (attempt %d/%d). Retrying in %.1fs...",
                        attempt + 1,
                        self._max_retries + 1,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    delay = min(
                        delay * self._backoff_factor,
                        self._max_delay,
                    )

        logger.error(
            "All %d retry attempts exhausted after rate limiting.",
            self._max_retries + 1,
        )
        raise last_error  # type: ignore[misc]
