"""Tests for LLM cost calculation."""

from mkcv.core.models.pricing import MODEL_PRICING, calculate_cost
from mkcv.core.models.token_usage import TokenUsage


class TestCalculateCost:
    """Tests for calculate_cost()."""

    def test_claude_sonnet_cost(self) -> None:
        usage = TokenUsage(input_tokens=1000, output_tokens=500)
        cost = calculate_cost("claude-sonnet-4-20250514", usage)
        input_rate, output_rate = MODEL_PRICING["claude-sonnet-4-20250514"]
        expected = (1000 * input_rate + 500 * output_rate) / 1000
        assert cost == round(expected, 6)

    def test_claude_haiku_cost(self) -> None:
        usage = TokenUsage(input_tokens=2000, output_tokens=1000)
        cost = calculate_cost("claude-haiku-4-20250414", usage)
        input_rate, output_rate = MODEL_PRICING["claude-haiku-4-20250414"]
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
        cost = calculate_cost("claude-sonnet-4-20250514", usage)
        assert cost == 0.0

    def test_only_input_tokens(self) -> None:
        usage = TokenUsage(input_tokens=1000, output_tokens=0)
        cost = calculate_cost("claude-sonnet-4-20250514", usage)
        input_rate, _ = MODEL_PRICING["claude-sonnet-4-20250514"]
        expected = (1000 * input_rate) / 1000
        assert cost == round(expected, 6)

    def test_only_output_tokens(self) -> None:
        usage = TokenUsage(input_tokens=0, output_tokens=1000)
        cost = calculate_cost("claude-sonnet-4-20250514", usage)
        _, output_rate = MODEL_PRICING["claude-sonnet-4-20250514"]
        expected = (1000 * output_rate) / 1000
        assert cost == round(expected, 6)
