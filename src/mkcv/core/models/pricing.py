"""LLM model pricing and cost calculation, derived from the model catalog."""

from mkcv.core.catalog.builtin_models import BUILTIN_MODEL_CAPABILITIES
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.token_usage import TokenUsage

_TOKENS_PER_UNIT = 1000
_TOKENS_PER_MILLION = 1_000_000
_PER_UNIT_PRECISION = 12


def _derive_model_pricing() -> dict[str, tuple[float, float]]:
    """Build the per-1K price table from the built-in catalog.

    Only exact entries with both prices are listed, and the first entry wins
    when a model ID appears under more than one provider. Prices are rounded
    so that converting from per-1M prices adds no floating-point noise.
    """
    pricing: dict[str, tuple[float, float]] = {}
    for entry in BUILTIN_MODEL_CAPABILITIES:
        if entry.match_type != "exact" or entry.match in pricing:
            continue
        if entry.input_price_per_mtok is None or entry.output_price_per_mtok is None:
            continue
        pricing[entry.match] = (
            round(entry.input_price_per_mtok / _TOKENS_PER_UNIT, _PER_UNIT_PRECISION),
            round(entry.output_price_per_mtok / _TOKENS_PER_UNIT, _PER_UNIT_PRECISION),
        )
    return pricing


# Pricing per 1K tokens: (input_cost, output_cost), derived from the built-in
# catalog (which stores USD per 1M tokens).
MODEL_PRICING: dict[str, tuple[float, float]] = _derive_model_pricing()


def calculate_cost(
    model: str,
    usage: TokenUsage,
    catalog: ModelCatalog | None = None,
    *,
    provider: str | None = None,
) -> float:
    """Calculate the USD cost for a single LLM call.

    Looks up per-token pricing for the model in the catalog and multiplies
    by actual token counts. Returns 0.0 for models with no catalog price
    (e.g. local Ollama models that have no per-token cost).

    Args:
        model: The model identifier string.
        usage: Token counts from the LLM call.
        catalog: Catalog to price against; defaults to the built-in one.
        provider: Restrict the price lookup to this provider's entries.

    Returns:
        Estimated cost in USD, rounded to 6 decimal places.
    """
    catalog = catalog or ModelCatalog.builtin()
    price = catalog.price_for(model, provider=provider)
    if price is None:
        return 0.0

    input_per_mtok, output_per_mtok = price
    cost = (
        usage.input_tokens * input_per_mtok + usage.output_tokens * output_per_mtok
    ) / _TOKENS_PER_MILLION

    return round(cost, 6)
