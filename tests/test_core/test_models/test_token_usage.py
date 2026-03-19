"""Tests for TokenUsage model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.token_usage import TokenUsage


class TestTokenUsage:
    """Tests for TokenUsage model."""

    def test_defaults_to_zero(self) -> None:
        usage = TokenUsage()
        assert usage.input_tokens == 0

    def test_output_tokens_defaults_to_zero(self) -> None:
        usage = TokenUsage()
        assert usage.output_tokens == 0

    def test_valid_token_counts(self) -> None:
        usage = TokenUsage(input_tokens=1500, output_tokens=500)
        assert usage.input_tokens == 1500

    def test_output_tokens_value(self) -> None:
        usage = TokenUsage(input_tokens=1500, output_tokens=500)
        assert usage.output_tokens == 500

    def test_model_dump_keys(self) -> None:
        usage = TokenUsage(input_tokens=100, output_tokens=200)
        data = usage.model_dump()
        assert set(data.keys()) == {"input_tokens", "output_tokens"}

    def test_model_dump_values(self) -> None:
        usage = TokenUsage(input_tokens=100, output_tokens=200)
        data = usage.model_dump()
        assert data == {"input_tokens": 100, "output_tokens": 200}

    def test_invalid_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TokenUsage(input_tokens="abc")  # type: ignore[arg-type]
