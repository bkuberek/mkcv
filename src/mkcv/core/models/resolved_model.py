"""What an adapter needs to know about one model for one request."""

from pydantic import BaseModel, ConfigDict

from mkcv.core.models.model_tier import ModelTier
from mkcv.core.models.structured_output_mode import StructuredOutputMode
from mkcv.core.models.token_param import TokenParam


class ResolvedModel(BaseModel):
    """Capabilities of a model after catalog and provider defaults are merged."""

    model_config = ConfigDict(frozen=True)

    provider: str
    model: str
    known: bool
    structured_output: StructuredOutputMode
    allow_structured_fallback: bool
    accepts_sampling_params: bool
    token_param: TokenParam
    min_output_tokens: int
    max_output_tokens: int | None
    context_window: int | None
    input_price_per_mtok: float | None
    output_price_per_mtok: float | None
    tier: ModelTier | None
    deprecated: bool
    notes: str | None

    def output_limit(self, requested: int) -> int:
        """Return the output limit to send for a requested ``max_tokens``.

        The floor applies first, then the ceiling.
        """
        limit = max(requested, self.min_output_tokens)
        if self.max_output_tokens is not None:
            limit = min(limit, self.max_output_tokens)
        return limit
