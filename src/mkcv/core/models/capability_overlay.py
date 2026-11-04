"""Partial set of model capabilities that can be layered over another."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from mkcv.core.models.model_tier import ModelTier
from mkcv.core.models.structured_output_mode import StructuredOutputMode
from mkcv.core.models.token_param import TokenParam


class CapabilityOverlay(BaseModel):
    """Capabilities of a model where ``None`` means "inherit".

    Overlays are folded in a fixed order (see ``ModelCatalog``): every
    non-``None`` field of a later overlay replaces the earlier value.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    structured_output: StructuredOutputMode | None = Field(
        default=None, description="First structured-output mode to try"
    )
    allow_structured_fallback: bool | None = Field(
        default=None,
        description="Whether a weaker structured-output mode may be tried "
        "after a rejection",
    )
    accepts_sampling_params: bool | None = Field(
        default=None, description="Whether temperature may be sent"
    )
    token_param: TokenParam | None = Field(
        default=None, description="Name of the output-limit parameter"
    )
    min_output_tokens: int | None = Field(
        default=None, ge=0, description="Floor applied to the output limit"
    )
    max_output_tokens: int | None = Field(
        default=None, gt=0, description="Ceiling applied after the floor"
    )
    context_window: int | None = Field(
        default=None, gt=0, description="Context window in tokens (informational)"
    )
    input_price_per_mtok: float | None = Field(
        default=None, ge=0, description="USD per 1M input tokens"
    )
    output_price_per_mtok: float | None = Field(
        default=None, ge=0, description="USD per 1M output tokens"
    )
    tier: ModelTier | None = Field(default=None, description="Quality tier")
    deprecated: bool | None = Field(
        default=None, description="Whether the provider has deprecated the model"
    )
    notes: str | None = Field(
        default=None, description="Shown with warnings and in the catalog listing"
    )

    def overlay(self, other: "CapabilityOverlay") -> "CapabilityOverlay":
        """Return a new overlay where ``other``'s set fields replace this one's.

        The result is always a plain ``CapabilityOverlay``, even when either
        operand is a subclass such as ``ModelCapability``.
        """
        merged: dict[str, Any] = {}
        for name in CapabilityOverlay.model_fields:
            replacement = getattr(other, name)
            merged[name] = (
                replacement if replacement is not None else getattr(self, name)
            )
        return CapabilityOverlay(**merged)
