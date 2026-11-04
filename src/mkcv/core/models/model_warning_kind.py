"""Kinds of non-blocking warnings about the models a run will use."""

from enum import StrEnum


class ModelWarningKind(StrEnum):
    """Why mkcv is warning about a model or provider."""

    UNKNOWN_MODEL = "unknown_model"
    TIER_UNKNOWN = "tier_unknown"
    BELOW_RECOMMENDED_TIER = "below_recommended_tier"
    DEPRECATED_MODEL = "deprecated_model"
    MISSING_API_KEY = "missing_api_key"
