"""Quality tiers used to compare models against stage requirements."""

from enum import StrEnum


class ModelTier(StrEnum):
    """Coarse quality tier of a model, from weakest to strongest."""

    MINIMAL = "minimal"
    EFFICIENT = "efficient"
    STRONG = "strong"
    FRONTIER = "frontier"

    def rank(self) -> int:
        """Return the tier's position: 0 for minimal up to 3 for frontier."""
        return list(ModelTier).index(self)
