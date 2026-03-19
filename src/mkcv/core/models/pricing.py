"""LLM model pricing and cost calculation."""

from mkcv.core.models.token_usage import TokenUsage

# Pricing per 1K tokens: (input_cost, output_cost)
# Source: provider pricing pages as of 2025
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # Anthropic Claude
    "claude-sonnet-4-20250514": (0.003, 0.015),
    "claude-haiku-4-20250414": (0.0008, 0.004),
    # OpenAI GPT-4o
    "gpt-4o": (0.0025, 0.010),
    "gpt-4o-mini": (0.00015, 0.0006),
    # OpenAI GPT-4.1
    "gpt-4.1": (0.002, 0.008),
    "gpt-4.1-mini": (0.0004, 0.0016),
    "gpt-4.1-nano": (0.0001, 0.0004),
}

_TOKENS_PER_UNIT = 1000


def calculate_cost(model: str, usage: TokenUsage) -> float:
    """Calculate the USD cost for a single LLM call.

    Looks up per-token pricing for the model and multiplies by
    actual token counts. Returns 0.0 for unknown models (e.g.
    local Ollama models that have no per-token cost).

    Args:
        model: The model identifier string.
        usage: Token counts from the LLM call.

    Returns:
        Estimated cost in USD, rounded to 6 decimal places.
    """
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return 0.0

    input_cost_per_1k, output_cost_per_1k = pricing
    cost = (
        usage.input_tokens * input_cost_per_1k
        + usage.output_tokens * output_cost_per_1k
    ) / _TOKENS_PER_UNIT

    return round(cost, 6)
