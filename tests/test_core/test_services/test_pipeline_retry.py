"""Tests for PipelineService._call_with_retry output quality retry logic."""

from unittest.mock import AsyncMock, patch

import pytest

from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.exceptions.context_length import ContextLengthError
from mkcv.core.exceptions.pipeline_stage import PipelineStageError
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.exceptions.rate_limit import RateLimitError
from mkcv.core.exceptions.validation import ValidationError
from mkcv.core.services.pipeline import PipelineService

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_SLEEP = "mkcv.core.services.pipeline.asyncio.sleep"


def _make_pipeline() -> PipelineService:
    """Create a minimal PipelineService for testing _call_with_retry."""
    return PipelineService(
        providers={},
        prompts=AsyncMock(),  # type: ignore[arg-type]
        artifacts=AsyncMock(),  # type: ignore[arg-type]
    )


# ------------------------------------------------------------------
# Test: Retry succeeds on second attempt
# ------------------------------------------------------------------


class TestRetrySuccess:
    """Tests that transient failures are retried and can succeed."""

    async def test_retry_succeeds_after_validation_error(
        self,
    ) -> None:
        """Should succeed on second attempt after ValidationError."""
        pipeline = _make_pipeline()
        call_count = 0

        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValidationError("bad JSON output")
            return "success"

        with patch(_SLEEP, new_callable=AsyncMock):
            result = await pipeline._call_with_retry(
                flaky,
                stage_name="analyze_jd",
                stage_number=1,
            )

        assert result == "success"
        assert call_count == 2

    async def test_retry_succeeds_after_value_error(self) -> None:
        """Should succeed on second attempt after ValueError."""
        pipeline = _make_pipeline()
        call_count = 0

        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("malformed output")
            return "ok"

        with patch(_SLEEP, new_callable=AsyncMock):
            result = await pipeline._call_with_retry(
                flaky,
                stage_name="tailor_content",
                stage_number=3,
            )

        assert result == "ok"
        assert call_count == 2

    async def test_retry_succeeds_on_third_attempt(self) -> None:
        """Should succeed on third attempt after two failures."""
        pipeline = _make_pipeline()
        call_count = 0

        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValidationError("schema mismatch")
            return "finally"

        with patch(_SLEEP, new_callable=AsyncMock):
            result = await pipeline._call_with_retry(
                flaky,
                stage_name="review",
                stage_number=5,
            )

        assert result == "finally"
        assert call_count == 3


# ------------------------------------------------------------------
# Test: Retry exhaustion raises PipelineStageError
# ------------------------------------------------------------------


class TestRetryExhaustion:
    """Tests that exhausted retries raise PipelineStageError."""

    async def test_all_retries_exhausted_raises_error(self) -> None:
        """Should raise PipelineStageError after max_retries."""
        pipeline = _make_pipeline()

        async def always_fail() -> str:
            raise ValidationError("persistent bad output")

        with (
            patch(_SLEEP, new_callable=AsyncMock),
            pytest.raises(
                PipelineStageError,
                match="failed after 3 attempts",
            ),
        ):
            await pipeline._call_with_retry(
                always_fail,
                stage_name="analyze_jd",
                stage_number=1,
            )

    async def test_exhaustion_error_includes_stage_info(
        self,
    ) -> None:
        """PipelineStageError should carry stage name and number."""
        pipeline = _make_pipeline()

        async def always_fail() -> str:
            raise ValidationError("bad schema")

        with (
            patch(_SLEEP, new_callable=AsyncMock),
            pytest.raises(PipelineStageError) as exc_info,
        ):
            await pipeline._call_with_retry(
                always_fail,
                stage_name="tailor_content",
                stage_number=3,
            )

        assert exc_info.value.stage == "tailor_content"
        assert exc_info.value.stage_number == 3

    async def test_exhaustion_preserves_cause(self) -> None:
        """__cause__ of PipelineStageError is the last error."""
        pipeline = _make_pipeline()

        async def always_fail() -> str:
            raise ValidationError("root cause")

        with (
            patch(_SLEEP, new_callable=AsyncMock),
            pytest.raises(PipelineStageError) as exc_info,
        ):
            await pipeline._call_with_retry(
                always_fail,
                stage_name="analyze_jd",
                stage_number=1,
            )

        assert isinstance(exc_info.value.__cause__, ValidationError)

    async def test_custom_max_retries(self) -> None:
        """Should respect a custom max_retries parameter."""
        pipeline = _make_pipeline()
        call_count = 0

        async def always_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise ValidationError("bad")

        with (
            patch(_SLEEP, new_callable=AsyncMock),
            pytest.raises(PipelineStageError),
        ):
            await pipeline._call_with_retry(
                always_fail,
                stage_name="review",
                stage_number=5,
                max_retries=2,
            )

        assert call_count == 2


# ------------------------------------------------------------------
# Test: Non-retryable errors are raised immediately
# ------------------------------------------------------------------


class TestNonRetryableErrors:
    """Provider errors bypass retry and propagate immediately."""

    async def test_authentication_error_not_retried(self) -> None:
        """AuthenticationError should raise on first attempt."""
        pipeline = _make_pipeline()
        call_count = 0

        async def auth_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise AuthenticationError("invalid API key")

        with pytest.raises(AuthenticationError):
            await pipeline._call_with_retry(
                auth_fail,
                stage_name="analyze_jd",
                stage_number=1,
            )

        assert call_count == 1

    async def test_context_length_error_not_retried(self) -> None:
        """ContextLengthError should raise on first attempt."""
        pipeline = _make_pipeline()
        call_count = 0

        async def ctx_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise ContextLengthError("too many tokens")

        with pytest.raises(ContextLengthError):
            await pipeline._call_with_retry(
                ctx_fail,
                stage_name="tailor_content",
                stage_number=3,
            )

        assert call_count == 1

    async def test_rate_limit_error_not_retried(self) -> None:
        """RateLimitError should raise immediately."""
        pipeline = _make_pipeline()
        call_count = 0

        async def rate_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise RateLimitError("rate limited")

        with pytest.raises(RateLimitError):
            await pipeline._call_with_retry(
                rate_fail,
                stage_name="select_experience",
                stage_number=2,
            )

        assert call_count == 1

    async def test_provider_error_not_retried(self) -> None:
        """ProviderError should raise on first attempt."""
        pipeline = _make_pipeline()
        call_count = 0

        async def provider_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise ProviderError("connection refused")

        with pytest.raises(ProviderError):
            await pipeline._call_with_retry(
                provider_fail,
                stage_name="structure_yaml",
                stage_number=4,
            )

        assert call_count == 1


# ------------------------------------------------------------------
# Test: Retry logging
# ------------------------------------------------------------------


class TestRetryLogging:
    """Tests that retry attempts are logged correctly."""

    async def test_retry_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Should log a warning on each retry attempt."""
        pipeline = _make_pipeline()
        call_count = 0

        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValidationError("bad output")
            return "ok"

        with (
            patch(_SLEEP, new_callable=AsyncMock),
            caplog.at_level(
                "WARNING",
                logger="mkcv.core.services.pipeline",
            ),
        ):
            await pipeline._call_with_retry(
                flaky,
                stage_name="analyze_jd",
                stage_number=1,
            )

        assert "attempt 1/3" in caplog.text
        assert "attempt 2/3" in caplog.text
        assert "Retrying..." in caplog.text

    async def test_no_log_on_first_success(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No warning when the first attempt succeeds."""
        pipeline = _make_pipeline()

        async def ok() -> str:
            return "success"

        with caplog.at_level(
            "WARNING",
            logger="mkcv.core.services.pipeline",
        ):
            await pipeline._call_with_retry(
                ok,
                stage_name="analyze_jd",
                stage_number=1,
            )

        assert "Retrying..." not in caplog.text


# ------------------------------------------------------------------
# Test: Backoff timing
# ------------------------------------------------------------------


class TestRetryBackoff:
    """Tests that backoff delays are applied correctly."""

    async def test_backoff_delays_increase_linearly(
        self,
    ) -> None:
        """Should sleep 1s, 2s between the 3 attempts."""
        pipeline = _make_pipeline()
        sleep_calls: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        call_count = 0

        async def always_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise ValidationError("bad")

        with (
            patch(_SLEEP, side_effect=fake_sleep),
            pytest.raises(PipelineStageError),
        ):
            await pipeline._call_with_retry(
                always_fail,
                stage_name="review",
                stage_number=5,
            )

        # 3 attempts: sleep after 1 (1.0s), after 2 (2.0s),
        # no sleep after 3 (exhausted)
        assert sleep_calls == [1.0, 2.0]
