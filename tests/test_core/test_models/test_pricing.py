"""Tests for LLM cost calculation."""

import pytest

from mkcv.core.models.model_capability import ModelCapability
from mkcv.core.models.model_catalog import ModelCatalog
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


# Per-1K prices that shipped before pricing was derived from the catalog.
_LEGACY_PRICING_PER_1K: dict[str, tuple[float, float]] = {
    "claude-opus-5-5": (0.004, 0.020),
    "claude-sonnet-5-5": (0.002, 0.010),
    "claude-haiku-5-5": (0.0001, 0.0005),
    "claude-opus-4-6": (0.005, 0.025),
    "claude-sonnet-4-6": (0.003, 0.015),
    "claude-haiku-4-5": (0.001, 0.005),
    "claude-haiku-4-5-20251001": (0.001, 0.005),
    "claude-opus-4-20250514": (0.015, 0.075),
    "claude-sonnet-4-20250514": (0.003, 0.015),
    "claude-haiku-4-20250414": (0.0008, 0.004),
    "gpt-4o": (0.0025, 0.010),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4.1": (0.002, 0.008),
    "gpt-4.1-mini": (0.0004, 0.0016),
    "gpt-4.1-nano": (0.0001, 0.0004),
    "anthropic/claude-sonnet-4": (0.003, 0.015),
    "anthropic/claude-haiku-4": (0.0008, 0.004),
    "openai/gpt-4o": (0.0025, 0.010),
    "openai/gpt-4.1": (0.002, 0.008),
    "google/gemini-2.5-pro-preview": (0.00125, 0.010),
    "google/gemini-2.5-flash-preview": (0.00015, 0.0006),
    "deepseek/deepseek-chat-v3": (0.00014, 0.00028),
}


class TestModelPricingIsDerivedFromTheCatalog:
    """REQ-CAT-7: MODEL_PRICING keeps every legacy key and value."""

    @pytest.mark.parametrize("model", sorted(_LEGACY_PRICING_PER_1K))
    def test_legacy_key_keeps_its_per_1k_price(self, model: str) -> None:
        assert MODEL_PRICING[model] == _LEGACY_PRICING_PER_1K[model]

    def test_table_type_is_a_plain_dict_of_price_pairs(self) -> None:
        assert all(
            isinstance(key, str) and len(value) == 2
            for key, value in MODEL_PRICING.items()
        )

    def test_prefix_entries_are_not_priced(self) -> None:
        assert "claude-opus-4-" not in MODEL_PRICING

    def test_entries_without_prices_are_left_out(self) -> None:
        assert "gemini-2.5-pro" not in MODEL_PRICING

    def test_new_models_are_priced_per_1k(self) -> None:
        assert MODEL_PRICING["gpt-6.1-sol"] == pytest.approx((0.002, 0.010))


class TestCatalogBackedCost:
    def test_gpt_6_sol_costs_twelve_dollars_per_million_each_way(self) -> None:
        usage = TokenUsage(input_tokens=_ONE_MILLION, output_tokens=_ONE_MILLION)
        assert calculate_cost("gpt-6.1-sol", usage) == pytest.approx(12.0)

    def test_gemini_argon_costs_twenty_four_dollars_per_million_each_way(
        self,
    ) -> None:
        usage = TokenUsage(input_tokens=_ONE_MILLION, output_tokens=_ONE_MILLION)
        assert calculate_cost("gemini-4-argon", usage) == pytest.approx(24.0)

    def test_local_model_without_a_price_costs_nothing(self) -> None:
        usage = TokenUsage(input_tokens=_ONE_MILLION, output_tokens=_ONE_MILLION)
        assert calculate_cost("llama3.1:8b", usage, provider="ollama") == 0.0

    def test_unknown_model_costs_nothing(self) -> None:
        usage = TokenUsage(input_tokens=_ONE_MILLION, output_tokens=_ONE_MILLION)
        assert calculate_cost("unknown-model", usage) == 0.0

    def test_provider_scopes_the_price_lookup(self) -> None:
        usage = TokenUsage(input_tokens=_ONE_MILLION, output_tokens=_ONE_MILLION)
        assert calculate_cost("gpt-4o", usage, provider="anthropic") == 0.0

    def test_provider_keyword_selects_that_providers_price(self) -> None:
        usage = TokenUsage(input_tokens=_ONE_MILLION, output_tokens=_ONE_MILLION)
        cost = calculate_cost("gpt-6.1-sol", usage, provider="openai")
        assert cost == pytest.approx(12.0)

    def test_injected_catalog_overrides_the_builtin_price(self) -> None:
        catalog = ModelCatalog.builtin().with_overrides(
            [
                ModelCapability(
                    provider="openai",
                    match="gpt-6.1-sol",
                    input_price_per_mtok=1.8,
                )
            ]
        )
        usage = TokenUsage(input_tokens=_ONE_MILLION, output_tokens=_ONE_MILLION)
        assert calculate_cost("gpt-6.1-sol", usage, catalog) == pytest.approx(11.8)

    def test_cost_is_rounded_to_six_places(self) -> None:
        usage = TokenUsage(input_tokens=1, output_tokens=1)
        cost = calculate_cost("claude-haiku-5-5", usage)
        assert cost == round(cost, 6)

    def test_dated_variant_without_exact_price_costs_nothing(self) -> None:
        usage = TokenUsage(input_tokens=_ONE_MILLION, output_tokens=_ONE_MILLION)
        assert calculate_cost("claude-sonnet-5-5-20261001", usage) == 0.0
