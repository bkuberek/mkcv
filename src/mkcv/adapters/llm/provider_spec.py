"""Specification of a named LLM provider."""

from pydantic import BaseModel, ConfigDict, Field

from mkcv.core.models.capability_overlay import CapabilityOverlay
from mkcv.core.models.provider_kind import ProviderKind


class ProviderSpec(BaseModel):
    """Everything needed to reach and describe one named provider."""

    model_config = ConfigDict(frozen=True)

    name: str
    kind: ProviderKind
    base_url: str | None = None
    api_key_env: tuple[str, ...] = ()
    api_key: str | None = Field(
        default=None,
        description="Literal key from config; prefer the environment variable",
    )
    requires_api_key: bool = True
    defaults: CapabilityOverlay = Field(
        default_factory=CapabilityOverlay,
        description="Provider-level overlay on the kind defaults",
    )
    builtin: bool = False
