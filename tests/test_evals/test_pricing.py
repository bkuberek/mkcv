"""Tests for pricing calls online, batched, and with cached prompt tokens."""

import pytest

from evals.harness.pricing import actual_cost, batch_discounts, online_cost
from evals.models.call_usage import CallUsage
from evals.models.pricing_settings import PricingSettings
from evals.report.markdown_report import render_markdown
from tests.test_evals.report_support import manifest, recommendation, summary

PRICE = (4.0, 20.0)  # USD per 1M input / output tokens
SETTINGS = PricingSettings()


def _usage(**fields: object) -> CallUsage:
    base: dict[str, object] = {
        "scope": "job",
        "provider": "anthropic",
        "model": "claude-opus-5-5",
        "input_tokens": 1_000_000,
        "output_tokens": 100_000,
    }
    return CallUsage.model_validate({**base, **fields})


def test_the_online_cost_is_every_token_at_catalog_price() -> None:
    assert online_cost(_usage(), PRICE) == pytest.approx(4.0 + 2.0)


def test_a_batched_call_costs_half_for_the_three_providers() -> None:
    for provider in ("anthropic", "openai", "google"):
        usage = _usage(provider=provider, batched=True)
        assert actual_cost(usage, PRICE, SETTINGS) == pytest.approx(3.0)


def test_cache_reads_are_priced_at_the_providers_multiplier() -> None:
    usage = _usage(cache_read_tokens=500_000)
    # 500K uncached at $4 + 500K read at $0.40 + output $2
    assert actual_cost(usage, PRICE, SETTINGS) == pytest.approx(2.0 + 0.2 + 2.0)


def test_anthropic_cache_writes_cost_a_quarter_more() -> None:
    usage = _usage(cache_write_tokens=1_000_000)
    assert actual_cost(usage, PRICE, SETTINGS) == pytest.approx(5.0 + 2.0)


def test_caching_and_batching_stack() -> None:
    usage = _usage(cache_read_tokens=1_000_000, batched=True)
    assert actual_cost(usage, PRICE, SETTINGS) == pytest.approx((0.4 + 2.0) / 2)


def test_an_unlisted_provider_gets_no_discount() -> None:
    usage = _usage(provider="ollama", batched=True, cache_read_tokens=500_000)
    assert actual_cost(usage, PRICE, SETTINGS) == pytest.approx(6.0)


def test_only_batching_providers_get_a_discount() -> None:
    assert batch_discounts(SETTINGS, {"openai": True, "google": False}) == {
        "openai": 0.5
    }


class TestReportCost:
    def _report(self, *usage: CallUsage) -> str:
        record = manifest().model_copy(
            update={"catalog_prices": {"anthropic/claude-opus-5-5": PRICE}}
        )
        return render_markdown(record, [summary()], [recommendation()], usage=usage)

    def _cost(self, report: str) -> str:
        start = report.index("## Cost")
        return report[start : report.find("\n## ", start + 1)]

    def test_it_sets_the_actual_cost_beside_the_online_one(self) -> None:
        section = self._cost(self._report(_usage(batched=True)))
        assert (
            "| anthropic | claude-opus-5-5 | evaluated | 1 | 1 | 0 | $6.0000 "
            "| $3.0000 |" in section
        )

    def test_judge_calls_are_their_own_rows(self) -> None:
        section = self._cost(self._report(_usage(scope="job/judge/tailoring_judge/x")))
        assert "| judge |" in section

    def test_it_says_how_much_batching_and_caching_saved(self) -> None:
        section = self._cost(self._report(_usage(batched=True), _usage()))
        assert "Online: $12.0000; as sent: $9.0000 (saved $3.0000, 25%)" in section
