"""Tests for CoverLetterService._call_with_retry retry logic."""

from unittest.mock import AsyncMock, patch

import pytest

from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.exceptions.context_length import ContextLengthError
from mkcv.core.exceptions.cover_letter import CoverLetterError
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.exceptions.rate_limit import RateLimitError
from mkcv.core.exceptions.validation import ValidationError
from mkcv.core.services.cover_letter import CoverLetterService

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_SLEEP = "mkcv.core.services.cover_letter.asyncio.sleep"


def _make_service() -> CoverLetterService:
    """Create a minimal CoverLetterService for retry tests."""
    return CoverLetterService(
        providers={},
        prompts=AsyncMock(),  # type: ignore[arg-type]
        artifacts=AsyncMock(),  # type: ignore[arg-type]
        renderer=AsyncMock(),  # type: ignore[arg-type]
    )


# ------------------------------------------------------------------
# Test: Retry succeeds on second attempt
# ------------------------------------------------------------------


class TestRetrySuccess:
    """Transient failures are retried and can succeed."""

    async def test_retry_succeeds_after_validation_error(
        self,
    ) -> None:
        """Should succeed on second attempt after ValidationError."""
        service = _make_service()
        call_count = 0

        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValidationError("bad JSON output")
            return "success"

        with patch(_SLEEP, new_callable=AsyncMock):
            result = await service._call_with_retry(
                flaky,
                stage_name="generate_cover_letter",
                stage_number=1,
            )

        assert result == "success"
        assert call_count == 2

    async def test_retry_succeeds_after_value_error(self) -> None:
        """Should succeed on second attempt after ValueError."""
        service = _make_service()
        call_count = 0

        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("malformed output")
            return "ok"

        with patch(_SLEEP, new_callable=AsyncMock):
            result = await service._call_with_retry(
                flaky,
                stage_name="review_cover_letter",
                stage_number=2,
            )

        assert result == "ok"
        assert call_count == 2


# ------------------------------------------------------------------
# Test: Retry exhaustion raises CoverLetterError
# ------------------------------------------------------------------


class TestRetryExhaustion:
    """Exhausted retries raise CoverLetterError."""

    async def test_all_retries_exhausted_raises_error(self) -> None:
        """Should raise CoverLetterError after max_retries."""
        service = _make_service()

        async def always_fail() -> str:
            raise ValidationError("persistent bad output")

        with (
            patch(_SLEEP, new_callable=AsyncMock),
            pytest.raises(
                CoverLetterError,
                match="failed after 3 attempts",
            ),
        ):
            await service._call_with_retry(
                always_fail,
                stage_name="generate_cover_letter",
                stage_number=1,
            )

    async def test_exhaustion_preserves_cause(self) -> None:
        """__cause__ of CoverLetterError is the last error."""
        service = _make_service()

        async def always_fail() -> str:
            raise ValidationError("root cause")

        with (
            patch(_SLEEP, new_callable=AsyncMock),
            pytest.raises(CoverLetterError) as exc_info,
        ):
            await service._call_with_retry(
                always_fail,
                stage_name="generate_cover_letter",
                stage_number=1,
            )

        assert isinstance(exc_info.value.__cause__, ValidationError)


# ------------------------------------------------------------------
# Test: Non-retryable errors are raised immediately
# ------------------------------------------------------------------


class TestNonRetryableErrors:
    """Provider errors bypass retry and propagate immediately."""

    async def test_authentication_error_not_retried(self) -> None:
        """AuthenticationError should raise on first attempt."""
        service = _make_service()
        call_count = 0

        async def auth_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise AuthenticationError("invalid API key")

        with pytest.raises(AuthenticationError):
            await service._call_with_retry(
                auth_fail,
                stage_name="generate_cover_letter",
                stage_number=1,
            )

        assert call_count == 1

    async def test_context_length_error_not_retried(self) -> None:
        """ContextLengthError should raise on first attempt."""
        service = _make_service()
        call_count = 0

        async def ctx_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise ContextLengthError("too many tokens")

        with pytest.raises(ContextLengthError):
            await service._call_with_retry(
                ctx_fail,
                stage_name="review_cover_letter",
                stage_number=2,
            )

        assert call_count == 1

    async def test_rate_limit_error_not_retried(self) -> None:
        """RateLimitError should raise immediately."""
        service = _make_service()
        call_count = 0

        async def rate_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise RateLimitError("rate limited")

        with pytest.raises(RateLimitError):
            await service._call_with_retry(
                rate_fail,
                stage_name="generate_cover_letter",
                stage_number=1,
            )

        assert call_count == 1

    async def test_provider_error_not_retried(self) -> None:
        """ProviderError should raise on first attempt."""
        service = _make_service()
        call_count = 0

        async def provider_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise ProviderError("connection refused")

        with pytest.raises(ProviderError):
            await service._call_with_retry(
                provider_fail,
                stage_name="generate_cover_letter",
                stage_number=1,
            )

        assert call_count == 1
