"""How batch and cached tokens are priced: ``[pricing]``."""

from pydantic import BaseModel, ConfigDict, Field


def _per_provider(anthropic: float, openai: float, google: float) -> dict[str, float]:
    return {"anthropic": anthropic, "openai": openai, "google": google}


class PricingSettings(BaseModel):
    """Discounts on catalog prices, by provider name.

    ``batch_discount`` is taken off every token of a batched call (the three
    providers publish 50% off for batches). ``cache_read_multiplier`` prices
    prompt tokens read from the provider's cache against the input price,
    and ``cache_write_multiplier`` prices prompt tokens written to it (only
    Anthropic charges extra for writes). A provider not listed gets no
    discount and a multiplier of 1.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    batch_discount: dict[str, float] = Field(
        default_factory=lambda: _per_provider(0.5, 0.5, 0.5)
    )
    cache_read_multiplier: dict[str, float] = Field(
        default_factory=lambda: _per_provider(0.1, 0.5, 0.25)
    )
    cache_write_multiplier: dict[str, float] = Field(
        default_factory=lambda: {"anthropic": 1.25}
    )
