"""A catalog entry describing what one model (or model family) can do."""

from typing import Literal

from pydantic import Field

from mkcv.core.models.capability_overlay import CapabilityOverlay


class ModelCapability(CapabilityOverlay):
    """Capabilities of the models a provider exposes under a given match.

    ``match`` is a model ID (``match_type="exact"``) or an ID prefix
    (``match_type="prefix"``).
    """

    provider: str = Field(min_length=1, description="Provider name the entry targets")
    match: str = Field(min_length=1, description="Model ID or prefix")
    match_type: Literal["exact", "prefix"] = "exact"
    display_name: str | None = None

    def matches(self, model: str) -> bool:
        """Return True when ``model`` is covered by this entry."""
        if self.match_type == "exact":
            return model == self.match
        return model.startswith(self.match)

    @property
    def key(self) -> tuple[str, str, str]:
        """Identity of the entry: ``(provider, match, match_type)``."""
        return (self.provider, self.match, self.match_type)
