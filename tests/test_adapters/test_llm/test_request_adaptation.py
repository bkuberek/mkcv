"""Tests for detecting rejected request parameters in provider error messages."""

import pytest

from mkcv.adapters.llm.request_adaptation import (
    is_structured_output_rejection,
    rejected_parameter,
)


class TestRejectedParameter:
    @pytest.mark.parametrize(
        "message",
        [
            "Unsupported value: 'temperature' does not support 0.3 with this model. "
            "Only the default (1) value is supported.",
            "temperature is not supported for this model",
            "'temperature' is not allowed for reasoning models",
            "Invalid temperature for this model",
            "Unsupported parameter: temperature",
            "TEMPERATURE: only the default value is accepted, only the default (1)",
        ],
    )
    def test_temperature_rejection_is_detected(self, message: str) -> None:
        assert rejected_parameter(message) == "temperature"

    def test_max_tokens_rejection_is_detected(self) -> None:
        message = (
            "Unsupported parameter: 'max_tokens' is not supported with this "
            "model. Use 'max_completion_tokens' instead."
        )
        assert rejected_parameter(message) == "max_tokens"

    def test_max_tokens_alone_is_not_a_rejection(self) -> None:
        assert rejected_parameter("max_tokens is too large for this model") is None

    def test_max_completion_tokens_alone_is_not_a_rejection(self) -> None:
        assert rejected_parameter("max_completion_tokens must be positive") is None

    def test_temperature_range_error_is_not_a_rejection(self) -> None:
        assert rejected_parameter("temperature must be between 0 and 2") is None

    def test_temperature_wins_when_both_parameters_are_named(self) -> None:
        message = (
            "temperature is not supported; max_tokens is not supported, "
            "use max_completion_tokens"
        )
        assert rejected_parameter(message) == "temperature"

    @pytest.mark.parametrize(
        "message",
        [
            "",
            "rate limit exceeded",
            "This model's maximum context length is 8192 tokens",
            "Invalid schema for response_format 'M'",
        ],
    )
    def test_unrelated_messages_are_ignored(self, message: str) -> None:
        assert rejected_parameter(message) is None


class TestIsStructuredOutputRejection:
    @pytest.mark.parametrize(
        "message",
        [
            "response_format json_schema is not supported by this backend",
            "response_format is not supported",
            "Invalid schema for response_format 'M'",
            "json_schema is unavailable on this model",
            "'json_object' is not a valid response type",
            "Structured output is not supported for this model",
            "The response schema is too large",
            "RESPONSE_FORMAT unsupported",
        ],
    )
    def test_structured_output_rejection_is_detected(self, message: str) -> None:
        assert is_structured_output_rejection(message) is True

    @pytest.mark.parametrize(
        "message",
        [
            "",
            "rate limit exceeded",
            "This model's maximum context length is 8192 tokens",
            "Invalid API key",
        ],
    )
    def test_unrelated_messages_are_not_structured_rejections(
        self, message: str
    ) -> None:
        assert is_structured_output_rejection(message) is False

    def test_parameter_rejection_takes_precedence(self) -> None:
        message = "temperature is not supported when response_format is json_schema"
        assert is_structured_output_rejection(message) is False

    def test_max_tokens_rejection_takes_precedence(self) -> None:
        message = (
            "response_format ok but max_tokens is not supported, "
            "use max_completion_tokens"
        )
        assert is_structured_output_rejection(message) is False
