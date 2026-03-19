"""Tests for RetryingLLMAdapter."""

import pytest
from pydantic import BaseModel

from mkcv.adapters.llm.retry import RetryingLLMAdapter
from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.exceptions.rate_limit import RateLimitError


class _SimpleModel(BaseModel):
    value: str


class _FlakyLLM:
    """Stub LLM that fails N times before succeeding."""

    def __init__(
        self,
        *,
        fail_count: int = 1,
        error_type: type[Exception] = RateLimitError,
    ) -> None:
        self._fail_count = fail_count
        self._error_type = error_type
        self._attempts = 0

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        self._attempts += 1
        if self._attempts <= self._fail_count:
            if self._error_type is RateLimitError:
                raise RateLimitError("rate limited", provider="test")
            raise self._error_type("other error", provider="test")
        return "success"

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        response_model: type[BaseModel],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> BaseModel:
        self._attempts += 1
        if self._attempts <= self._fail_count:
            if self._error_type is RateLimitError:
                raise RateLimitError("rate limited", provider="test")
            raise self._error_type("other error", provider="test")
        return _SimpleModel(value="success")

    @property
    def attempts(self) -> int:
        return self._attempts


class TestRetryOnRateLimit:
    """Tests for retry behavior on RateLimitError."""

    async def test_succeeds_without_retry(self) -> None:
        inner = _FlakyLLM(fail_count=0)
        adapter = RetryingLLMAdapter(inner, base_delay=0.0)
        result = await adapter.complete([{"role": "user", "content": "hi"}], model="m")
        assert result == "success"
        assert inner.attempts == 1

    async def test_retries_once_on_rate_limit(self) -> None:
        inner = _FlakyLLM(fail_count=1)
        adapter = RetryingLLMAdapter(inner, base_delay=0.0)
        result = await adapter.complete([{"role": "user", "content": "hi"}], model="m")
        assert result == "success"
        assert inner.attempts == 2

    async def test_retries_up_to_max(self) -> None:
        inner = _FlakyLLM(fail_count=3)
        adapter = RetryingLLMAdapter(inner, max_retries=3, base_delay=0.0)
        result = await adapter.complete([{"role": "user", "content": "hi"}], model="m")
        assert result == "success"
        assert inner.attempts == 4

    async def test_raises_after_exhausting_retries(self) -> None:
        inner = _FlakyLLM(fail_count=10)
        adapter = RetryingLLMAdapter(inner, max_retries=2, base_delay=0.0)
        with pytest.raises(RateLimitError, match="rate limited"):
            await adapter.complete([{"role": "user", "content": "hi"}], model="m")
        assert inner.attempts == 3  # 1 initial + 2 retries

    async def test_structured_retries_on_rate_limit(self) -> None:
        inner = _FlakyLLM(fail_count=1)
        adapter = RetryingLLMAdapter(inner, base_delay=0.0)
        result = await adapter.complete_structured(
            [{"role": "user", "content": "hi"}],
            model="m",
            response_model=_SimpleModel,
        )
        assert isinstance(result, _SimpleModel)
        assert inner.attempts == 2


class TestNoRetryOnOtherErrors:
    """Tests that non-rate-limit errors are raised immediately."""

    async def test_auth_error_not_retried(self) -> None:
        inner = _FlakyLLM(fail_count=5, error_type=AuthenticationError)
        adapter = RetryingLLMAdapter(inner, base_delay=0.0)
        with pytest.raises(AuthenticationError):
            await adapter.complete([{"role": "user", "content": "hi"}], model="m")
        assert inner.attempts == 1

    async def test_structured_auth_error_not_retried(self) -> None:
        inner = _FlakyLLM(fail_count=5, error_type=AuthenticationError)
        adapter = RetryingLLMAdapter(inner, base_delay=0.0)
        with pytest.raises(AuthenticationError):
            await adapter.complete_structured(
                [{"role": "user", "content": "hi"}],
                model="m",
                response_model=_SimpleModel,
            )
        assert inner.attempts == 1


class TestRetryConfiguration:
    """Tests for retry configuration options."""

    async def test_default_max_retries_is_three(self) -> None:
        inner = _FlakyLLM(fail_count=100)
        adapter = RetryingLLMAdapter(inner, base_delay=0.0)
        with pytest.raises(RateLimitError):
            await adapter.complete([{"role": "user", "content": "hi"}], model="m")
        assert inner.attempts == 4  # 1 initial + 3 retries

    async def test_zero_retries_means_no_retry(self) -> None:
        inner = _FlakyLLM(fail_count=1)
        adapter = RetryingLLMAdapter(inner, max_retries=0, base_delay=0.0)
        with pytest.raises(RateLimitError):
            await adapter.complete([{"role": "user", "content": "hi"}], model="m")
        assert inner.attempts == 1
