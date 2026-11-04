"""Tests for LLM cost calculation."""

import pytest

from mkcv.core.models.pricing import MODEL_PRICING, calculate_cost
from mkcv.core.models.token_usage import TokenUsage

_ONE_MILLION = 1_000_000


class TestPublishedClaudeRates:
    """Pin Claude rates to Anthropic's published per-1M-token prices."""

    @pytest.mark.parametrize(
        ("model", "input_per_million", "output_per_million"),
        [
            ("claude-opus-5-5", 4.00, 20.00),
            ("claude-sonnet-5-5", 2.00, 10.00),
            ("claude-haiku-5-5", 0.10, 0.50),
            ("claude-opus-4-6", 5.00, 25.00),
            ("claude-sonnet-4-6", 3.00, 15.00),
            ("claude-haiku-4-5", 1.00, 5.00),
        ],
    )
    def test_cost_per_million_tokens(
        self, model: str, input_per_million: float, output_per_million: float
    ) -> None:
        usage = TokenUsage(input_tokens=_ONE_MILLION, output_tokens=_ONE_MILLION)
        assert calculate_cost(model, usage) == pytest.approx(
            input_per_million + output_per_million
        )

    @pytest.mark.parametrize(
        "model",
        ["claude-sonnet-4-20250514", "claude-haiku-4-20250414"],
    )
    def test_legacy_dated_ids_still_price(self, model: str) -> None:
        usage = TokenUsage(input_tokens=1000, output_tokens=1000)
        assert calculate_cost(model, usage) > 0.0


class TestCalculateCost:
    """Tests for calculate_cost()."""

    def test_claude_sonnet_cost(self) -> None:
        usage = TokenUsage(input_tokens=1000, output_tokens=500)
        cost = calculate_cost("claude-sonnet-5-5", usage)
        input_rate, output_rate = MODEL_PRICING["claude-sonnet-5-5"]
        expected = (1000 * input_rate + 500 * output_rate) / 1000
        assert cost == round(expected, 6)

    def test_claude_haiku_cost(self) -> None:
        usage = TokenUsage(input_tokens=2000, output_tokens=1000)
        cost = calculate_cost("claude-haiku-5-5", usage)
        input_rate, output_rate = MODEL_PRICING["claude-haiku-5-5"]
        expected = (2000 * input_rate + 1000 * output_rate) / 1000
        assert cost == round(expected, 6)

    def test_gpt4o_cost(self) -> None:
        usage = TokenUsage(input_tokens=500, output_tokens=200)
        cost = calculate_cost("gpt-4o", usage)
        input_rate, output_rate = MODEL_PRICING["gpt-4o"]
        expected = (500 * input_rate + 200 * output_rate) / 1000
        assert cost == round(expected, 6)

    def test_gpt4o_mini_cost(self) -> None:
        usage = TokenUsage(input_tokens=1000, output_tokens=1000)
        cost = calculate_cost("gpt-4o-mini", usage)
        input_rate, output_rate = MODEL_PRICING["gpt-4o-mini"]
        expected = (1000 * input_rate + 1000 * output_rate) / 1000
        assert cost == round(expected, 6)

    def test_unknown_model_returns_zero(self) -> None:
        usage = TokenUsage(input_tokens=5000, output_tokens=2000)
        cost = calculate_cost("llama-3.3-70b", usage)
        assert cost == 0.0

    def test_zero_tokens_returns_zero(self) -> None:
        usage = TokenUsage(input_tokens=0, output_tokens=0)
        cost = calculate_cost("claude-sonnet-5-5", usage)
        assert cost == 0.0

    def test_only_input_tokens(self) -> None:
        usage = TokenUsage(input_tokens=1000, output_tokens=0)
        cost = calculate_cost("claude-sonnet-5-5", usage)
        input_rate, _ = MODEL_PRICING["claude-sonnet-5-5"]
        expected = (1000 * input_rate) / 1000
        assert cost == round(expected, 6)

    def test_only_output_tokens(self) -> None:
        usage = TokenUsage(input_tokens=0, output_tokens=1000)
        cost = calculate_cost("claude-sonnet-5-5", usage)
        _, output_rate = MODEL_PRICING["claude-sonnet-5-5"]
        expected = (1000 * output_rate) / 1000
        assert cost == round(expected, 6)
