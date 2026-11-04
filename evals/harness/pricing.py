"""Price model calls: online, batched, and with cached prompt tokens."""

from collections.abc import Mapping

from evals.models.call_usage import CallUsage
from evals.models.pricing_settings import PricingSettings

_PER_MILLION = 1_000_000


def online_cost(usage: CallUsage, price: tuple[float, float]) -> float:
    """What the call costs online with no cache: every token at catalog price."""
    input_price, output_price = price
    return (usage.input_tokens * input_price + usage.output_tokens * output_price) / (
        _PER_MILLION
    )


def actual_cost(
    usage: CallUsage, price: tuple[float, float], settings: PricingSettings
) -> float:
    """What the call costs as sent: cache reads and writes, and the batch discount."""
    input_price, output_price = price
    provider = usage.provider
    read = settings.cache_read_multiplier.get(provider, 1.0)
    write = settings.cache_write_multiplier.get(provider, 1.0)
    uncached = max(
        0, usage.input_tokens - usage.cache_read_tokens - usage.cache_write_tokens
    )
    cost = (
        uncached * input_price
        + usage.cache_read_tokens * input_price * read
        + usage.cache_write_tokens * input_price * write
        + usage.output_tokens * output_price
    ) / _PER_MILLION
    if usage.batched:
        cost *= 1.0 - settings.batch_discount.get(provider, 0.0)
    return cost


def batch_discounts(
    settings: PricingSettings, providers: Mapping[str, bool]
) -> dict[str, float]:
    """The batch discount of each provider that batches (``providers[p]`` True)."""
    return {
        provider: settings.batch_discount.get(provider, 0.0)
        for provider, batches in providers.items()
        if batches
    }
